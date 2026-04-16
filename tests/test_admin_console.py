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
        assert first_item["free_quota_total"] == 10
        assert first_item["free_quota_used"] == 0
        assert first_item["free_remaining"] == 10
        assert first_item["paid_remaining"] == 0
        assert first_item["total_remaining"] == 10
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


def test_admin_can_grant_user_quota_and_history_reflects_remaining_times(tmp_path, monkeypatch):
    client = _create_client(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    seeded = _seed_job(
        openid="history-grant-user",
        created_at=now.isoformat(),
        nickname="阿澈",
        job_status="succeeded",
        with_media=True,
    )

    with client:
        _login_admin(client)

        grant_response = client.post(
            f"/api/admin/users/{seeded['user_id']}/quota/grant",
            json={"count": 3},
        )
        assert grant_response.status_code == 200
        payload = grant_response.json()
        assert payload["user_id"] == seeded["user_id"]
        assert payload["nickname"] == "阿澈"
        assert payload["user_openid"] == "history-grant-user"
        assert payload["free_remaining"] == 10
        assert payload["paid_remaining"] == 3
        assert payload["total_remaining"] == 13
        assert payload["total_jobs"] == 1
        assert payload["completed_jobs"] == 1
        assert payload["processing_jobs"] == 0
        assert payload["last_job_created_at"] == now.isoformat()

        history_response = client.get(f"/api/admin/history?user_id={seeded['user_id']}")
        assert history_response.status_code == 200
        history_payload = history_response.json()
        assert history_payload["total"] == 1
        item = history_payload["items"][0]
        assert item["user_id"] == seeded["user_id"]
        assert item["free_remaining"] == 10
        assert item["paid_remaining"] == 3
        assert item["total_remaining"] == 13


def test_admin_users_requires_login_and_lists_user_summaries(tmp_path, monkeypatch):
    client = _create_client(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    primary_old = (now - timedelta(hours=2)).isoformat()
    primary_new = now.isoformat()
    secondary_time = (now - timedelta(minutes=30)).isoformat()

    primary_first = _seed_job(
        openid="admin-users-primary",
        created_at=primary_old,
        nickname="林夏",
        job_status="succeeded",
        with_media=True,
    )
    _seed_job(
        openid="admin-users-primary",
        created_at=primary_new,
        nickname="林夏",
        job_status="failed",
        error_code="provider_error",
        error_message="primary follow-up failed",
        with_media=False,
    )
    secondary = _seed_job(
        openid="admin-users-secondary",
        created_at=secondary_time,
        nickname="周周",
        job_status="failed",
        error_code="provider_error",
        error_message="upstream failed",
        with_media=False,
    )

    with client:
        users_response = client.get("/api/admin/users")
        assert users_response.status_code == 401

        page_response = client.get("/admin/users", follow_redirects=False)
        assert page_response.status_code == 303
        assert page_response.headers["location"] == "/admin?next=/admin/users"

        _login_admin(client)

        grant_response = client.post(
            f"/api/admin/users/{primary_first['user_id']}/quota/grant",
            json={"count": 5},
        )
        assert grant_response.status_code == 200

        list_response = client.get("/api/admin/users")
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["total"] == 2
        assert payload["page"] == 1
        assert payload["page_size"] == 20
        assert len(payload["items"]) == 2

        primary_item = next(
            item for item in payload["items"] if item["user_id"] == primary_first["user_id"]
        )
        assert primary_item["nickname"] == "林夏"
        assert primary_item["user_openid"] == "admin-users-primary"
        assert primary_item["free_remaining"] == 10
        assert primary_item["paid_remaining"] == 5
        assert primary_item["total_remaining"] == 15
        assert primary_item["total_jobs"] == 2
        assert primary_item["completed_jobs"] == 1
        assert primary_item["processing_jobs"] == 0
        assert primary_item["last_job_created_at"] == primary_new

        secondary_item = next(
            item for item in payload["items"] if item["user_id"] == secondary["user_id"]
        )
        assert secondary_item["nickname"] == "周周"
        assert secondary_item["user_openid"] == "admin-users-secondary"
        assert secondary_item["total_jobs"] == 1
        assert secondary_item["completed_jobs"] == 0
        assert secondary_item["processing_jobs"] == 0

        keyword_response = client.get("/api/admin/users?keyword=%E6%9E%97%E5%A4%8F")
        assert keyword_response.status_code == 200
        keyword_payload = keyword_response.json()
        assert keyword_payload["total"] == 1
        assert keyword_payload["items"][0]["user_id"] == primary_first["user_id"]

        user_filter_response = client.get(f"/api/admin/users?user_id={secondary['user_id']}")
        assert user_filter_response.status_code == 200
        user_filter_payload = user_filter_response.json()
        assert user_filter_payload["total"] == 1
        assert user_filter_payload["items"][0]["user_id"] == secondary["user_id"]


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
