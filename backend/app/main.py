from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.routers import auth, history, jobs, templates, uploads
from app.services.dispatch_queue import build_job_queue
from app.services.generation import build_generator
from app.services.job_queue import JobWorker
from app.services.key_pool import ApiKeyPool
from app.services import storage


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        current_settings = get_settings()
        current_settings.ensure_directories()
        init_db()
        generator = build_generator()
        job_queue = build_job_queue()
        key_pool = None
        if not current_settings.use_mock_generator and current_settings.ark_api_keys:
            key_pool = ApiKeyPool(
                current_settings.ark_api_keys,
                default_cooldown_seconds=current_settings.ark_key_cooldown_seconds,
            )
        worker = JobWorker(
            generator,
            key_pool=key_pool,
            concurrency=current_settings.job_worker_concurrency,
            job_queue=job_queue,
        )
        app.state.generator = generator
        app.state.job_queue = job_queue
        app.state.key_pool = key_pool
        app.state.job_worker = worker
        if current_settings.run_embedded_worker:
            worker.start()
        yield
        if current_settings.run_embedded_worker:
            worker.stop()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    settings.ensure_directories()
    if storage.is_local_media_backend():
        app.mount("/media", StaticFiles(directory=settings.storage_dir, check_dir=False), name="media")

    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(uploads.router, prefix=settings.api_prefix)
    app.include_router(templates.router, prefix=settings.api_prefix)
    app.include_router(jobs.router, prefix=settings.api_prefix)
    app.include_router(history.router, prefix=settings.api_prefix)

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "docs": "/docs",
        }

    return app


app = create_app()
