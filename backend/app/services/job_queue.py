from __future__ import annotations

from queue import Empty, Queue
from threading import Event, Thread

from app.config import get_settings
from app.services import repository, storage, templates
from app.services.generation import BaseGenerator, GenerationContext, ImageGenerationError


class JobWorker:
    def __init__(self, generator: BaseGenerator) -> None:
        self.generator = generator
        self._queue: Queue[str | None] = Queue()
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True, name="image-job-worker")
        self._thread.start()

        for job_id in repository.requeue_active_jobs():
            self.enqueue(job_id)

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)

    def enqueue(self, job_id: str) -> None:
        self._queue.put(job_id)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except Empty:
                continue

            if job_id is None:
                continue

            try:
                self._process(job_id)
            finally:
                self._queue.task_done()

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
        source_path = str(settings.storage_dir / upload["stored_path"])
        preview_path: str | None = None

        def handle_preview(image_bytes: bytes) -> None:
            nonlocal preview_path
            if preview_path is not None:
                return
            preview_path = storage.save_preview_result(job_id, image_bytes)
            repository.update_job_status(
                job_id,
                status="preview_ready",
                result_path=preview_path,
                error_code=None,
                error_message=None,
            )

        try:
            generation_result = self.generator.generate(
                source_image_path=source_path,
                prompt=job["prompt"],
                context=GenerationContext(
                    hairstyle_name=hairstyle["name"],
                    scene_name=scene["name"],
                ),
                on_preview=handle_preview,
            )
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
        except ImageGenerationError as exc:
            if preview_path is not None:
                repository.update_job_status(
                    job_id,
                    status="succeeded",
                    result_path=preview_path,
                    error_code=None,
                    error_message=None,
                )
                return
            repository.update_job_status(
                job_id,
                status="failed",
                error_code=exc.code,
                error_message=str(exc),
            )
        except Exception as exc:  # pragma: no cover
            if preview_path is not None:
                repository.update_job_status(
                    job_id,
                    status="succeeded",
                    result_path=preview_path,
                    error_code=None,
                    error_message=None,
                )
                return
            repository.update_job_status(
                job_id,
                status="failed",
                error_code="internal_error",
                error_message=str(exc),
            )
