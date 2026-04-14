from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import update


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _build_test_image(color: str = "#8ecae6") -> bytes:
    image = Image.new("RGB", (768, 1024), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _configure_runtime_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_GENERATOR", "true")
    monkeypatch.setenv("ALLOW_DEV_LOGIN", "true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "false")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "storage" / "app.db"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'storage' / 'app.db').resolve()}")
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "local")
    monkeypatch.setenv("RUN_EMBEDDED_WORKER", "true")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "nano_banana_pro")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_MODEL", "Nano_Banana_Pro_2K_1")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "understanding-key")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_BASE_URL", "https://understanding.example.test/v1")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_MODEL", "gemini-3-pro-preview")
    monkeypatch.setenv("ADMIN_CONSOLE_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_CONSOLE_PASSWORD", "secret-pass")
    monkeypatch.setenv("ADMIN_CONSOLE_SESSION_SECRET", "test-admin-session-secret")


def _clear_runtime_caches() -> None:
    from app.config import get_settings
    from app.db import get_engine, get_session_factory
    from app.services import generation
    from app.services.storage import get_object_storage

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_object_storage.cache_clear()
    generation._PROVIDER_BACKOFF_UNTIL.clear()


def _create_client(tmp_path, monkeypatch) -> TestClient:
    _configure_runtime_env(tmp_path, monkeypatch)
    _clear_runtime_caches()

    from app.config import get_settings
    from app.db import init_db
    from app.main import create_app

    settings = get_settings()
    settings.ensure_directories()
    init_db()
    return TestClient(create_app())


def _login_admin(client: TestClient) -> None:
    response = client.post(
        "/api/admin/session/login",
        json={"username": "admin", "password": "secret-pass"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True


def _seed_job(
    *,
    openid: str,
    created_at: str,
    nickname: str | None = None,
    job_status: str = "succeeded",
    error_code: str | None = None,
    error_message: str | None = None,
    with_media: bool = True,
) -> dict:
    from app.db import jobs, session_scope, uploads
    from app.services import repository, storage

    user = repository.get_or_create_user(openid, nickname=nickname)
    upload_bytes = _build_test_image("#8ecae6")
    upload_path = storage.save_upload_file(upload_bytes, ".png")
    upload = repository.create_upload(
        user_id=user["id"],
        original_name="source.png",
        stored_path=upload_path,
        mime_type="image/png",
        file_size=len(upload_bytes),
        width=768,
        height=1024,
    )
    job = repository.create_job(
        user_id=user["id"],
        upload_id=upload["id"],
        hairstyle_id="test_style",
        scene_id="test_scene",
        prompt="",
        model_name="test-model",
    )

    result_path = None
    if with_media:
        storage.save_hair_preview_result(job["id"], _build_test_image("#264653"))
        result_path = storage.save_scene_result(job["id"], _build_test_image("#2a9d8f"), index=1)
        storage.save_scene_result(job["id"], _build_test_image("#e76f51"), index=2)

    repository.update_job_status(
        job["id"],
        status=job_status,
        result_path=result_path,
        error_code=error_code,
        error_message=error_message,
    )

    with session_scope() as session:
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        hair_started_at = (created_dt + timedelta(seconds=1)).replace(microsecond=0).isoformat()
        first_image_ready_at = (
            (created_dt + timedelta(seconds=45)).replace(microsecond=0).isoformat()
            if with_media
            else None
        )
        scene_started_at = (
            (created_dt + timedelta(seconds=50)).replace(microsecond=0).isoformat()
            if with_media
            else None
        )
        first_scene_ready_at = (
            (created_dt + timedelta(seconds=120)).replace(microsecond=0).isoformat()
            if with_media
            else None
        )
        completed_at = (created_dt + timedelta(seconds=150)).replace(microsecond=0).isoformat()
        session.execute(
            update(uploads)
            .where(uploads.c.id == upload["id"])
            .values(created_at=created_at)
        )
        session.execute(
            update(jobs)
            .where(jobs.c.id == job["id"])
            .values(
                created_at=created_at,
                updated_at=completed_at,
                hair_started_at=hair_started_at,
                first_image_ready_at=first_image_ready_at,
                scene_started_at=scene_started_at,
                first_scene_ready_at=first_scene_ready_at,
                completed_at=completed_at,
            )
        )

    return {
        "user_id": user["id"],
        "upload_id": upload["id"],
        "job_id": job["id"],
    }


def test_admin_history_requires_login_and_supports_session_login(tmp_path, monkeypatch):
    client = _create_client(tmp_path, monkeypatch)

    with client:
        history_response = client.get("/api/admin/history")
        assert history_response.status_code == 401

        page_response = client.get("/admin/history", follow_redirects=False)
        assert page_response.status_code == 303
        assert page_response.headers["location"] == "/admin?next=/admin/history"

        wrong_password = client.post(
            "/api/admin/session/login",
            json={"username": "admin", "password": "bad-pass"},
        )
        assert wrong_password.status_code == 401

        _login_admin(client)

        session_response = client.get("/api/admin/session")
        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] is True

        history_after_login = client.get("/api/admin/history")
        assert history_after_login.status_code == 200
        assert history_after_login.json()["items"] == []


def test_admin_history_filters_and_pagination(tmp_path, monkeypatch):
    client = _create_client(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    recent_a = now.isoformat()
    recent_b = (now - timedelta(hours=2)).isoformat()
    old_created_at = (now - timedelta(days=10)).isoformat()

    recent_success = _seed_job(
        openid="history-user-a",
        created_at=recent_a,
        nickname="阿青",
        job_status="succeeded",
        with_media=True,
    )
    recent_failed = _seed_job(
        openid="history-user-b",
        created_at=recent_b,
        job_status="failed",
        error_code="route_timeout",
        error_message="route2 timed out",
        with_media=False,
    )
    _seed_job(
        openid="history-user-c",
        created_at=old_created_at,
        job_status="succeeded",
        with_media=True,
    )

    with client:
        _login_admin(client)

        default_response = client.get("/api/admin/history")
        assert default_response.status_code == 200
        default_payload = default_response.json()
        assert default_payload["total"] == 2
        assert len(default_payload["items"]) == 2
        assert default_payload["storage_root"].endswith("storage")

        first_item = default_payload["items"][0]
        assert first_item["upload_url"]
        assert first_item["hair_preview_url"]
        assert len(first_item["result_image_urls"]) == 2
        assert first_item["result_dir_absolute_path"].endswith(first_item["job_id"])
        assert first_item["nickname"] == "阿青"
        assert first_item["first_image_duration_seconds"] == 45.0
        assert first_item["first_scene_duration_seconds"] == 120.0
        assert first_item["completed_duration_seconds"] == 150.0

        user_filter = client.get(f"/api/admin/history?user_id={recent_success['user_id']}")
        assert user_filter.status_code == 200
        user_payload = user_filter.json()
        assert user_payload["total"] == 1
        assert user_payload["items"][0]["user_id"] == recent_success["user_id"]

        status_filter = client.get("/api/admin/history?status=failed")
        assert status_filter.status_code == 200
        status_payload = status_filter.json()
        assert status_payload["total"] == 1
        assert status_payload["items"][0]["error_code"] == "route_timeout"

        keyword_filter = client.get("/api/admin/history?keyword=timed+out")
        assert keyword_filter.status_code == 200
        keyword_payload = keyword_filter.json()
        assert keyword_payload["total"] == 1
        assert keyword_payload["items"][0]["job_id"] == recent_failed["job_id"]

        paged_response = client.get("/api/admin/history?page_size=1&page=2")
        assert paged_response.status_code == 200
        paged_payload = paged_response.json()
        assert paged_payload["page"] == 2
        assert paged_payload["page_size"] == 1
        assert paged_payload["total"] == 2
        assert len(paged_payload["items"]) == 1


def test_admin_history_keeps_records_after_media_cleanup(tmp_path, monkeypatch):
    client = _create_client(tmp_path, monkeypatch)
    old_created_at = (datetime.now(timezone.utc) - timedelta(days=10)).replace(microsecond=0).isoformat()
    expired_job = _seed_job(
        openid="history-expired-user",
        created_at=old_created_at,
        job_status="succeeded",
        with_media=True,
    )

    from app.services import retention

    retention.purge_expired_media(force=True)

    with client:
        _login_admin(client)

        response = client.get("/api/admin/history?created_from=2026-01-01T00:00:00+00:00")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["job_id"] == expired_job["job_id"]
        assert item["media_expired"] is True
        assert item["upload_url"] is None
        assert item["hair_preview_url"] is None
        assert item["result_image_urls"] == []
        assert item["upload_path"] is None
        assert item["result_dir_absolute_path"].endswith(expired_job["job_id"])


def test_admin_feedback_requires_login_and_supports_filters(tmp_path, monkeypatch):
    client = _create_client(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    first_job = _seed_job(
        openid="feedback-user-a",
        created_at=now.isoformat(),
        nickname="阿青",
        job_status="succeeded",
        with_media=True,
    )
    fourth_job = _seed_job(
        openid="feedback-user-b",
        created_at=(now - timedelta(hours=1)).isoformat(),
        nickname="小满",
        job_status="succeeded",
        with_media=True,
    )

    from app.services import repository

    repository.create_feedback_submission(
        user_id=first_job["user_id"],
        job_id=first_job["job_id"],
        survey_type="first_success",
        trigger_completed_jobs=1,
        hairstyle_expectation="met",
        hair_color_satisfaction="satisfied",
        scene_satisfaction="neutral",
        wait_time_feeling="acceptable",
        image_clarity_satisfaction="clear",
        ui_usability="easy",
        improvement_suggestion="希望场景匹配再丰富一点",
    )
    repository.create_feedback_submission(
        user_id=fourth_job["user_id"],
        job_id=fourth_job["job_id"],
        survey_type="fourth_success",
        trigger_completed_jobs=4,
        hairstyle_expectation="mostly_met",
        hair_color_satisfaction="neutral",
        scene_satisfaction="satisfied",
        wait_time_feeling="a_bit_long",
        image_clarity_satisfaction="clear",
        ui_usability="neutral",
        improvement_suggestion="整体不错，但还想再快一些",
    )

    with client:
        response = client.get("/api/admin/feedback")
        assert response.status_code == 401

        page_response = client.get("/admin/feedback", follow_redirects=False)
        assert page_response.status_code == 303
        assert page_response.headers["location"] == "/admin?next=/admin/feedback"

        _login_admin(client)

        feedback_response = client.get("/api/admin/feedback")
        assert feedback_response.status_code == 200
        payload = feedback_response.json()
        assert payload["total"] == 2
        assert payload["summary"]["total_count"] == 2
        assert payload["summary"]["first_success_count"] == 1
        assert payload["summary"]["fourth_success_count"] == 1
        assert payload["items"][0]["nickname"] in {"阿青", "小满"}

        survey_filter = client.get("/api/admin/feedback?survey_type=first_success")
        assert survey_filter.status_code == 200
        survey_payload = survey_filter.json()
        assert survey_payload["total"] == 1
        assert survey_payload["summary"]["total_count"] == 1
        assert survey_payload["summary"]["first_success_count"] == 1
        assert survey_payload["summary"]["fourth_success_count"] == 0
        assert survey_payload["items"][0]["survey_type"] == "first_success"
        assert survey_payload["items"][0]["nickname"] == "阿青"

        keyword_filter = client.get("/api/admin/feedback?keyword=%E6%83%B3%E5%86%8D%E5%BF%AB%E4%B8%80%E4%BA%9B")
        assert keyword_filter.status_code == 200
        keyword_payload = keyword_filter.json()
        assert keyword_payload["total"] == 1
        assert keyword_payload["items"][0]["nickname"] == "小满"
        assert keyword_payload["items"][0]["improvement_suggestion"] == "整体不错，但还想再快一些"
