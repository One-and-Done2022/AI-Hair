from __future__ import annotations

import logging
import os
import tempfile
from threading import Lock
from threading import Event, Thread

from app.config import get_settings
from app.services import repository, storage, templates
from app.services.dispatch_queue import BaseJobQueue, build_job_queue
from app.services.generation import (
    BaseGenerator,
    GenerationContext,
    ImageGenerationError,
    build_generator,
)
from app.services.key_pool import ApiKeyLease, ApiKeyPool


logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(
        self,
        generator: BaseGenerator,
        *,
        key_pool: ApiKeyPool | None = None,
        concurrency: int = 1,
        job_queue: BaseJobQueue | None = None,
    ) -> None:
        self.generator = generator
        self.key_pool = key_pool
        self.concurrency = max(1, concurrency)
        self.job_queue = job_queue or build_job_queue()
        self._stop_event = Event()
        self._threads: list[Thread] = []
        self._runtime_lock = Lock()
        settings = get_settings()
        self._generator_cache: dict[str, BaseGenerator] = {
            settings.image_generator_backend: generator,
        }
        self._key_pool_cache: dict[str, ApiKeyPool | None] = {
            settings.image_generator_backend: key_pool,
        }

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return

        self.job_queue.recover_inflight()
        recovered_job_ids = repository.requeue_active_jobs(
            include_pending=not self.job_queue.is_durable
        )
        if not self.job_queue.is_durable:
            for job_id in recovered_job_ids:
                self.enqueue(job_id)

        self._stop_event.clear()
        self._threads = [
            Thread(
                target=self._run,
                daemon=True,
                name=f"image-job-worker-{index + 1}",
            )
            for index in range(self.concurrency)
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=3)
        self._threads = []

    def enqueue(self, job_id: str) -> None:
        self.job_queue.enqueue(job_id)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            lease = self.job_queue.dequeue(timeout=0.5)
            if lease is None:
                continue

            try:
                self._process(lease.job_id)
            finally:
                self.job_queue.ack(lease)

    def _process(self, job_id: str) -> None:
        job = repository.get_job(job_id)
        if job is None:
            return

        hairstyle = templates.get_hairstyle(job["hairstyle_id"])
        scene = templates.get_scene(job["scene_id"])
        upload = repository.get_upload(job["upload_id"])
        if hairstyle is None or scene is None or upload is None:
            repository.update_job_status(
                job_id,
                status="failed",
                error_code="invalid_job",
                error_message="Job configuration is incomplete.",
            )
            return

        repository.update_job_status(
            job_id,
            status="processing",
            error_code=None,
            error_message=None,
        )
        settings = get_settings()
        prompt_payload = templates.parse_job_prompt_payload(job.get("prompt") or "")
        generator_backend = str(
            prompt_payload["output_options"].get("generator_backend") or settings.image_generator_backend
        )
        runtime_generator, runtime_key_pool = self._resolve_runtime(generator_backend)
        source_bytes = storage.read_file_bytes(upload["stored_path"])
        suffix = os.path.splitext(upload["stored_path"])[1] or ".jpg"
        source_temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        source_temp.write(source_bytes)
        source_temp.flush()
        source_temp.close()
        source_path = source_temp.name
        preview_path: str | None = None
        attempted_key_ids: set[str] = set()
        max_attempts = runtime_key_pool.active_size if runtime_key_pool is not None else 1
        last_generation_error: ImageGenerationError | None = None
        last_unexpected_error: Exception | None = None

        try:
            for _ in range(max_attempts):
                provider_key = self._acquire_provider_key(runtime_key_pool, attempted_key_ids)
                if runtime_key_pool is not None and provider_key is None:
                    break

                if provider_key is not None:
                    repository.assign_job_key(job_id, provider_key.key_id)

                preview_emitted = False

                def handle_preview(image_bytes: bytes) -> None:
                    nonlocal preview_path, preview_emitted
                    if preview_path is not None:
                        return
                    preview_emitted = True
                    preview_path = storage.save_preview_result(job_id, image_bytes)
                    repository.update_job_status(
                        job_id,
                        status="preview_ready",
                        result_path=preview_path,
                        error_code=None,
                        error_message=None,
                    )

                try:
                    generation_result = runtime_generator.generate(
                        source_image_path=source_path,
                        prompt=prompt_payload["full_prompt"],
                        context=GenerationContext(
                            hairstyle_name=hairstyle["name"],
                            scene_name=scene["name"],
                            aspect_ratio=prompt_payload["output_options"]["aspect_ratio"],
                            resolution=prompt_payload["output_options"]["resolution"],
                            full_prompt=prompt_payload["full_prompt"],
                            hairstyle_only_prompt=prompt_payload["hairstyle_only_prompt"],
                            scene_only_prompt=prompt_payload["scene_only_prompt"],
                        ),
                        provider_key=provider_key,
                        on_preview=handle_preview,
                    )
                    if runtime_key_pool is not None and provider_key is not None:
                        runtime_key_pool.release_success(provider_key.key_id)

                    result_bundle = storage.save_result_bundle(
                        job_id,
                        generation_result.candidate_image_bytes,
                    )
                    repository.update_job_status(
                        job_id,
                        status="succeeded",
                        result_path=result_bundle.primary_path,
                        error_code=None,
                        error_message=None,
                    )
                    return
                except ImageGenerationError as exc:
                    last_generation_error = exc
                    if runtime_key_pool is not None and provider_key is not None:
                        if exc.disable_key:
                            runtime_key_pool.disable_key(
                                provider_key.key_id,
                                reason=str(exc),
                            )
                            logger.warning(
                                "Disabled Ark API key %s after permanent upstream error %s",
                                provider_key.key_id,
                                exc.code,
                            )
                        else:
                            runtime_key_pool.release_error(
                                provider_key.key_id,
                                cooldown_seconds=exc.retry_after_seconds,
                            )
                        attempted_key_ids.add(provider_key.key_id)

                    if preview_emitted and preview_path is not None:
                        repository.update_job_status(
                            job_id,
                            status="succeeded",
                            result_path=preview_path,
                            error_code=None,
                            error_message=None,
                        )
                        return

                    if (
                        runtime_key_pool is not None
                        and provider_key is not None
                        and (exc.retryable or exc.disable_key)
                    ):
                        continue
                    break
                except Exception as exc:  # pragma: no cover
                    last_unexpected_error = exc
                    if runtime_key_pool is not None and provider_key is not None:
                        runtime_key_pool.release_error(
                            provider_key.key_id,
                            cooldown_seconds=settings.ark_key_cooldown_seconds,
                        )
                        attempted_key_ids.add(provider_key.key_id)

                    if preview_emitted and preview_path is not None:
                        repository.update_job_status(
                            job_id,
                            status="succeeded",
                            result_path=preview_path,
                            error_code=None,
                            error_message=None,
                        )
                        return

                    if runtime_key_pool is not None and provider_key is not None:
                        continue
                    break

            if last_generation_error is not None:
                repository.update_job_status(
                    job_id,
                    status="failed",
                    error_code=last_generation_error.code,
                    error_message=str(last_generation_error),
                )
                repository.assign_job_key(job_id, None)
                return

            if last_unexpected_error is not None:
                repository.update_job_status(
                    job_id,
                    status="failed",
                    error_code="internal_error",
                    error_message=str(last_unexpected_error),
                )
                repository.assign_job_key(job_id, None)
                return

            repository.update_job_status(
                job_id,
                status="failed",
                error_code="no_available_api_key",
                error_message="No available Ark API key could be assigned to this job.",
            )
            repository.assign_job_key(job_id, None)
        finally:
            try:
                os.unlink(source_path)
            except FileNotFoundError:
                pass

    def _acquire_provider_key(
        self,
        key_pool: ApiKeyPool | None,
        attempted_key_ids: set[str],
    ) -> ApiKeyLease | None:
        if key_pool is None:
            return None

        excluded = attempted_key_ids if len(attempted_key_ids) < key_pool.size else set()
        while not self._stop_event.is_set():
            lease = key_pool.acquire(
                excluded_key_ids=excluded,
                timeout=0.5,
            )
            if lease is not None:
                return lease
        return None

    def _resolve_runtime(self, backend: str) -> tuple[BaseGenerator, ApiKeyPool | None]:
        settings = get_settings()
        with self._runtime_lock:
            generator = self._generator_cache.get(backend)
            if generator is None:
                generator = build_generator(backend)
                self._generator_cache[backend] = generator

            key_pool = self._key_pool_cache.get(backend)
            if backend not in self._key_pool_cache:
                if (
                    not settings.use_mock_generator
                    and getattr(generator, "supports_key_pool", False)
                    and settings.ark_api_keys
                ):
                    key_pool = ApiKeyPool(
                        settings.ark_api_keys,
                        default_cooldown_seconds=settings.ark_key_cooldown_seconds,
                    )
                else:
                    key_pool = None
                self._key_pool_cache[backend] = key_pool

            return generator, key_pool
