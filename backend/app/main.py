from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.routers import auth, history, jobs, templates, uploads
from app.services.generation import build_generator
from app.services.job_queue import JobWorker


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        current_settings = get_settings()
        current_settings.ensure_directories()
        init_db()
        generator = build_generator()
        worker = JobWorker(generator)
        app.state.generator = generator
        app.state.job_worker = worker
        worker.start()
        yield
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

