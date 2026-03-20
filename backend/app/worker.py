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
    if not settings.use_mock_generator and settings.ark_api_keys:
        key_pool = ApiKeyPool(
            settings.ark_api_keys,
            default_cooldown_seconds=settings.ark_key_cooldown_seconds,
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
