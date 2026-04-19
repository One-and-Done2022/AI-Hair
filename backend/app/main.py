from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.routers import (
    admin_console,
    auth,
    feedback,
    history,
    jobs,
    me,
    provider_admin,
    purchase,
    quota,
    recommendations,
    scene_understanding,
    templates,
    uploads,
)
from app.services.dispatch_queue import build_job_queue
from app.services.generation import build_generator
from app.services.job_queue import JobWorker
from app.services.key_pool import ApiKeyPool
from app.services import hair_color_reference, provider_connectivity, retention, storage


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        current_settings = get_settings()
        current_settings.ensure_directories()
        try:
            hair_color_reference.ensure_professional_hair_color_reference_pdf_cached()
            hair_color_reference.ensure_professional_hair_color_reference_static_file()
        except Exception:
            pass
        init_db()
        retention.purge_expired_media(force=True)
        generator = build_generator()
        job_queue = build_job_queue()
        key_pool = None
        initial_model_name = getattr(generator, "model_name", None)
        initial_credentials = current_settings.ark_api_keys_for_model(initial_model_name)
        if (
            not current_settings.use_mock_generator
            and getattr(generator, "supports_key_pool", False)
            and initial_credentials
        ):
            key_pool = ApiKeyPool(
                initial_credentials,
                default_cooldown_seconds=current_settings.ark_key_cooldown_seconds,
                disabled_key_ids=current_settings.ark_api_disabled_key_ids,
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
        connectivity_monitor = provider_connectivity.ProviderConnectivityMonitor(
            current_settings
        )
        app.state.provider_connectivity_monitor = connectivity_monitor
        connectivity_monitor.start()
        if current_settings.run_embedded_worker:
            worker.start()
        yield
        if current_settings.run_embedded_worker:
            worker.stop()
        connectivity_monitor.stop()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    settings.ensure_directories()
    try:
        hair_color_reference.ensure_professional_hair_color_reference_static_file()
    except Exception:
        pass
    public_static_dir = settings.storage_dir / "public"
    public_static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=public_static_dir, check_dir=False), name="static")
    if storage.is_local_media_backend():
        app.mount("/media", StaticFiles(directory=settings.storage_dir, check_dir=False), name="media")

    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(uploads.router, prefix=settings.api_prefix)
    app.include_router(templates.router, prefix=settings.api_prefix)
    app.include_router(recommendations.router, prefix=settings.api_prefix)
    app.include_router(scene_understanding.router, prefix=settings.api_prefix)
    app.include_router(jobs.router, prefix=settings.api_prefix)
    app.include_router(history.router, prefix=settings.api_prefix)
    app.include_router(me.router, prefix=settings.api_prefix)
    app.include_router(quota.router, prefix=settings.api_prefix)
    app.include_router(purchase.router, prefix=settings.api_prefix)
    app.include_router(feedback.router, prefix=settings.api_prefix)
    app.include_router(provider_admin.router)
    app.include_router(admin_console.router)

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/healthz/providers")
    def provider_healthcheck() -> dict:
        return provider_connectivity.load_state()

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "docs": "/docs",
        }

    return app


app = create_app()
