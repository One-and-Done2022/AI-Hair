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
    SeedreamGenerator,
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

        storage.delete_result_bundle(job_id)
        prompt_payload = templates.parse_job_prompt_payload(job.get("prompt") or "")
        generation_plan = templates.get_generation_plan(
            prompt_payload["output_options"].get("generator_backend")
        )
        if generation_plan is None:
            repository.update_job_status(
                job_id,
                status="failed",
                error_code="invalid_job",
                error_message="Unknown generation plan.",
            )
            return

        source_bytes = storage.read_file_bytes(upload["stored_path"])
        suffix = os.path.splitext(upload["stored_path"])[1] or ".jpg"
        source_temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        source_temp.write(source_bytes)
        source_temp.flush()
        source_temp.close()
        source_path = source_temp.name
        hair_source_path: str | None = None
        hair_preview_path: str | None = None
        first_scene_path: str | None = None
        scene_count = 0

        try:
            repository.update_job_status(
                job_id,
                status="hair_generating",
                error_code=None,
                error_message=None,
            )

            def handle_hair_candidate(image_bytes: bytes) -> None:
                nonlocal hair_preview_path
                if hair_preview_path is not None:
                    return
                hair_preview_path = storage.save_hair_preview_result(job_id, image_bytes)
                repository.update_job_status(
                    job_id,
                    status="hair_ready",
                    result_path=hair_preview_path,
                    error_code=None,
                    error_message=None,
                )

            hair_generator, hair_key_pool = self._resolve_runtime(generation_plan["hair_backend"])
            hair_result = self._execute_generation(
                job_id=job_id,
                generator=hair_generator,
                key_pool=hair_key_pool,
                source_image_path=source_path,
                prompt=prompt_payload["hairstyle_only_prompt"],
                context=GenerationContext(
                    hairstyle_name=hairstyle["name"],
                    scene_name=scene["name"],
                    aspect_ratio=prompt_payload["output_options"]["aspect_ratio"],
                    resolution=prompt_payload["output_options"]["resolution"],
                    image_count=1,
                    full_prompt=prompt_payload["full_prompt"],
                    hairstyle_only_prompt=prompt_payload["hairstyle_only_prompt"],
                    scene_only_prompt=prompt_payload["scene_only_prompt"],
                ),
                on_candidate=handle_hair_candidate,
            )
            if hair_preview_path is None:
                handle_hair_candidate(hair_result.primary_image_bytes)

            hair_preview_bytes = hair_result.primary_image_bytes
            hair_suffix = os.path.splitext(hair_preview_path or "")[1] or ".png"
            hair_temp = tempfile.NamedTemporaryFile(delete=False, suffix=hair_suffix)
            hair_temp.write(hair_preview_bytes)
            hair_temp.flush()
            hair_temp.close()
            hair_source_path = hair_temp.name

            repository.update_job_status(
                job_id,
                status="scene_generating",
                result_path=hair_preview_path,
                error_code=None,
                error_message=None,
            )

            def handle_scene_candidate(image_bytes: bytes) -> None:
                nonlocal scene_count, first_scene_path
                scene_count += 1
                scene_path = storage.save_scene_result(job_id, image_bytes, index=scene_count)
                if first_scene_path is None:
                    first_scene_path = scene_path
                repository.update_job_status(
                    job_id,
                    status="scene_partial",
                    result_path=first_scene_path,
                    error_code=None,
                    error_message=None,
                )

            scene_generator, scene_key_pool = self._resolve_runtime(
                generation_plan["scene_backend"],
                model_name=generation_plan["scene_model_name"],
            )
            scene_result = self._execute_generation(
                job_id=job_id,
                generator=scene_generator,
                key_pool=scene_key_pool,
                source_image_path=hair_source_path,
                prompt=prompt_payload["scene_only_prompt"],
                context=GenerationContext(
                    hairstyle_name=hairstyle["name"],
                    scene_name=scene["name"],
                    aspect_ratio=prompt_payload["output_options"]["aspect_ratio"],
                    resolution=prompt_payload["output_options"]["resolution"],
                    image_count=2,
                    full_prompt=prompt_payload["full_prompt"],
                    hairstyle_only_prompt=prompt_payload["hairstyle_only_prompt"],
                    scene_only_prompt=prompt_payload["scene_only_prompt"],
                ),
                on_candidate=handle_scene_candidate,
            )

            for image_bytes in scene_result.candidate_image_bytes:
                if scene_count >= 2:
                    break
                handle_scene_candidate(image_bytes)

            if first_scene_path is None:
                repository.update_job_status(
                    job_id,
                    status="failed",
                    result_path=hair_preview_path,
                    error_code="upstream_empty",
                    error_message="Scene generation returned no image payload.",
                )
                repository.assign_job_key(job_id, None)
                return

            repository.update_job_status(
                job_id,
                status="succeeded",
                result_path=first_scene_path,
                error_code=None,
                error_message=None,
            )
            repository.assign_job_key(job_id, None)
            return
        except ImageGenerationError as exc:
            repository.update_job_status(
                job_id,
                status="failed",
                result_path=first_scene_path or hair_preview_path,
                error_code=exc.code,
                error_message=str(exc),
            )
            repository.assign_job_key(job_id, None)
            return
        except Exception as exc:  # pragma: no cover
            repository.update_job_status(
                job_id,
                status="failed",
                result_path=first_scene_path or hair_preview_path,
                error_code="internal_error",
                error_message=str(exc),
            )
            repository.assign_job_key(job_id, None)
            return
        finally:
            try:
                os.unlink(source_path)
            except FileNotFoundError:
                pass
            if hair_source_path:
                try:
                    os.unlink(hair_source_path)
                except FileNotFoundError:
                    pass

    def _execute_generation(
        self,
        *,
        job_id: str,
        generator: BaseGenerator,
        key_pool: ApiKeyPool | None,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        on_preview=None,
        on_candidate=None,
    ):
        settings = get_settings()
        attempted_key_ids: set[str] = set()
        max_attempts = key_pool.active_size if key_pool is not None else 1
        last_generation_error: ImageGenerationError | None = None
        last_unexpected_error: Exception | None = None

        for _ in range(max_attempts):
            provider_key = self._acquire_provider_key(key_pool, attempted_key_ids)
            if key_pool is not None and provider_key is None:
                break

            if provider_key is not None:
                repository.assign_job_key(job_id, provider_key.key_id)

            delivered_candidate = False

            def emit_preview(image_bytes):
                if on_preview is not None:
                    on_preview(image_bytes)

            def emit_candidate(image_bytes):
                nonlocal delivered_candidate
                delivered_candidate = True
                if on_candidate is not None:
                    on_candidate(image_bytes)

            try:
                result = generator.generate(
                    source_image_path=source_image_path,
                    prompt=prompt,
                    context=context,
                    provider_key=provider_key,
                    on_preview=emit_preview,
                    on_candidate=emit_candidate,
                )
                if key_pool is not None and provider_key is not None:
                    key_pool.release_success(provider_key.key_id)
                return result
            except ImageGenerationError as exc:
                last_generation_error = exc
                if key_pool is not None and provider_key is not None:
                    if exc.disable_key:
                        key_pool.disable_key(
                            provider_key.key_id,
                            reason=str(exc),
                        )
                        logger.warning(
                            "Disabled Ark API key %s after permanent upstream error %s",
                            provider_key.key_id,
                            exc.code,
                        )
                    else:
                        key_pool.release_error(
                            provider_key.key_id,
                            cooldown_seconds=exc.retry_after_seconds,
                        )
                    attempted_key_ids.add(provider_key.key_id)

                if (
                    not delivered_candidate
                    and key_pool is not None
                    and provider_key is not None
                    and (exc.retryable or exc.disable_key)
                ):
                    continue

                if (
                    key_pool is not None
                    and provider_key is not None
                    and delivered_candidate
                ):
                    logger.warning(
                        "Stopped retrying job %s after partial image delivery from %s.",
                        job_id,
                        getattr(generator, "model_name", "generator"),
                    )
                break
            except Exception as exc:  # pragma: no cover
                last_unexpected_error = exc
                if key_pool is not None and provider_key is not None:
                    key_pool.release_error(
                        provider_key.key_id,
                        cooldown_seconds=settings.ark_key_cooldown_seconds,
                    )
                    attempted_key_ids.add(provider_key.key_id)

                if not delivered_candidate and key_pool is not None and provider_key is not None:
                    continue
                break

        if last_generation_error is not None:
            raise last_generation_error
        if last_unexpected_error is not None:
            raise ImageGenerationError("internal_error", str(last_unexpected_error))
        raise ImageGenerationError(
            "no_available_api_key",
            "No available Ark API key could be assigned to this job.",
        )

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

    def _resolve_runtime(
        self,
        backend: str,
        *,
        model_name: str | None = None,
    ) -> tuple[BaseGenerator, ApiKeyPool | None]:
        settings = get_settings()
        generator_cache_key = f"{backend}:{model_name}" if model_name else backend
        with self._runtime_lock:
            generator = self._generator_cache.get(generator_cache_key)
            if generator is None:
                if settings.use_mock_generator:
                    generator = build_generator(backend)
                elif backend == "seedream":
                    default_seedream_models = {
                        settings.seedream_premium_model,
                        settings.ark_image_model,
                    }
                    if (
                        settings.image_generator_backend == "seedream"
                        and (model_name is None or model_name in default_seedream_models)
                    ):
                        generator = self.generator
                    else:
                        generator = SeedreamGenerator(model_name=model_name)
                elif backend == settings.image_generator_backend:
                    generator = self.generator
                else:
                    generator = build_generator(backend)
                self._generator_cache[generator_cache_key] = generator

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
                        disabled_key_ids=settings.ark_api_disabled_key_ids,
                    )
                else:
                    key_pool = None
                self._key_pool_cache[backend] = key_pool

            return generator, key_pool
