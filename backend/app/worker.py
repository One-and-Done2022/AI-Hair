from __future__ import annotations

import signal
import time
from threading import Event

from app.config import get_settings
from app.db import init_db
from app.services.dispatch_queue import build_job_queue
from app.services.generation import build_generator
from app.services.job_queue import JobWorker
from app.services.key_pool import ApiKeyPool


def main() -> None:
    settings = get_settings()
    if settings.queue_backend == "local":
        raise RuntimeError(
            "Standalone worker requires JOB_QUEUE_BACKEND=redis. "
            "Use RUN_EMBEDDED_WORKER=true for local fallback mode."
        )

    settings.ensure_directories()
    init_db()

    generator = build_generator()
    job_queue = build_job_queue()
    key_pool = None
    initial_model_name = getattr(generator, "model_name", None)
    initial_credentials = settings.ark_api_keys_for_model(initial_model_name)
    if (
        not settings.use_mock_generator
        and getattr(generator, "supports_key_pool", False)
        and initial_credentials
    ):
        key_pool = ApiKeyPool(
            initial_credentials,
            default_cooldown_seconds=settings.ark_key_cooldown_seconds,
            disabled_key_ids=settings.ark_api_disabled_key_ids,
        )

    worker = JobWorker(
        generator,
        key_pool=key_pool,
        concurrency=settings.job_worker_concurrency,
        job_queue=job_queue,
    )

    shutdown_event = Event()

    def _request_shutdown(*_args) -> None:
        shutdown_event.set()

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    worker.start()
    try:
        while not shutdown_event.is_set():
            time.sleep(0.5)
    finally:
        worker.stop()


if __name__ == "__main__":
    main()
