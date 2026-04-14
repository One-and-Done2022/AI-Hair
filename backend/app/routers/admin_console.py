from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse

from app.config import get_settings
from app.dependencies import get_current_admin
from app.schemas import (
    AdminHistoryItem,
    AdminHistoryResponse,
    AdminSessionLoginRequest,
    AdminSessionResponse,
)
from app.services import admin_auth, repository, retention, storage, templates


router = APIRouter(tags=["admin-console"])
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_HOME_PAGE_PATH = _STATIC_DIR / "admin_home.html"
_HISTORY_PAGE_PATH = _STATIC_DIR / "admin_history.html"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _storage_root_label() -> str:
    settings = get_settings()
    if settings.uses_local_media:
        return str(settings.storage_dir.resolve())
    public_base_url = settings.object_storage_public_base_url.strip()
    if public_base_url:
        return public_base_url
    return settings.object_storage_backend


def _result_dir_path(job_id: str) -> str:
    settings = get_settings()
    relative_path = f"results/{job_id}"
    if settings.object_storage_backend == "aliyun_oss" and settings.oss_prefix.strip():
        return f"{settings.oss_prefix.strip('/')}/{relative_path}"
    return relative_path


def _absolute_media_path(object_key: str | None) -> str | None:
    settings = get_settings()
    if not settings.uses_local_media or not object_key:
        return None
    return str((settings.storage_dir / object_key).resolve())


def _file_mtime_iso(object_key: str | None) -> str | None:
    settings = get_settings()
    if not settings.uses_local_media or not object_key:
        return None
    file_path = settings.storage_dir / object_key
    if not file_path.exists():
        return None
    return datetime.fromtimestamp(
        file_path.stat().st_mtime,
        tz=timezone.utc,
    ).replace(microsecond=0).isoformat()


def _media_object_exists(object_key: str | None) -> bool:
    settings = get_settings()
    if not object_key:
        return False
    if not settings.uses_local_media:
        return True
    return (settings.storage_dir / object_key).exists()


def _optional_media_url(object_key: str | None, *, base_url: str) -> str | None:
    if not object_key or not _media_object_exists(object_key):
        return None
    return storage.media_url(object_key, base_url=base_url)


def _effective_event_time(*values: str | None) -> str | None:
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return None


def _duration_seconds(start_value: str | None, end_value: str | None) -> float | None:
    start_dt = repository._parse_iso_datetime(start_value)
    end_dt = repository._parse_iso_datetime(end_value)
    if start_dt is None or end_dt is None:
        return None
    return round(max(0.0, (end_dt - start_dt).total_seconds()), 2)


def _protected_page_response(
    request: Request,
    *,
    page_path: Path,
    next_path: str,
) -> Response:
    if admin_auth.current_admin_from_request(request) is None:
        redirect_target = f"/admin?next={quote(next_path, safe='/?:=&')}"
        return RedirectResponse(
            url=redirect_target,
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return FileResponse(page_path)


def _admin_history_item_response(request: Request, job: dict) -> AdminHistoryItem:
    hairstyle = templates.get_hairstyle(job["hairstyle_id"])
    scene = templates.get_scene(job["scene_id"])
    prompt_payload = templates.parse_job_prompt_payload(job.get("prompt") or "")
    template_selection = prompt_payload.get("template_selection") or {}
    preset_id = str(template_selection.get("preset_id") or "").strip() or None
    preset_name = str(template_selection.get("preset_name") or "").strip() or None
    resolved_hairstyle_name = (
        str(template_selection.get("resolved_hairstyle_name") or "").strip() or None
    )
    base_url = str(request.base_url).rstrip("/")
    upload_path = str(job.get("upload_stored_path") or "").strip() or None
    upload_url = _optional_media_url(upload_path, base_url=base_url)
    hair_preview_path = storage.get_hair_preview_path(job["id"])
    hair_preview_url = _optional_media_url(hair_preview_path, base_url=base_url)
    result_image_paths = storage.list_scene_results(job["id"])
    result_image_urls = [
        resolved
        for resolved in (
            _optional_media_url(path, base_url=base_url) for path in result_image_paths
        )
        if resolved
    ]
    result_image_url = result_image_urls[0] if result_image_urls else hair_preview_url
    media_expires_at = retention.media_expires_at(job["created_at"])
    media_expired = retention.is_media_expired(job["created_at"])
    hair_preview_file_time = _file_mtime_iso(hair_preview_path)
    first_result_path = result_image_paths[0] if result_image_paths else None
    first_result_file_time = _file_mtime_iso(first_result_path)
    latest_result_file_time = _file_mtime_iso(result_image_paths[-1]) if result_image_paths else None
    hair_started_at = _effective_event_time(job.get("hair_started_at"))
    first_image_ready_at = _effective_event_time(
        job.get("first_image_ready_at"),
        hair_preview_file_time,
    )
    scene_started_at = _effective_event_time(job.get("scene_started_at"))
    first_scene_ready_at = _effective_event_time(
        job.get("first_scene_ready_at"),
        first_result_file_time,
    )
    completed_at = _effective_event_time(
        job.get("completed_at"),
        latest_result_file_time,
        job.get("updated_at"),
    )
    hair_color_selection = prompt_payload.get("hair_color_selection") or {}
    hair_color_tone = str(hair_color_selection.get("tone_id") or "").strip() or None
    hair_color_tone_label = (
        str(hair_color_selection.get("tone_label") or "").strip() or None
    )
    hair_color_technique = (
        str(hair_color_selection.get("technique_id") or "").strip() or None
    )
    hair_color_technique_label = (
        str(hair_color_selection.get("technique_label") or "").strip() or None
    )
    hair_color_professional_id = (
        str(hair_color_selection.get("professional_id") or "").strip() or None
    )
    hair_color_professional_brand = (
        str(hair_color_selection.get("professional_brand") or "").strip() or None
    )
    hair_color_professional_series = (
        str(hair_color_selection.get("professional_series") or "").strip() or None
    )
    hair_color_professional_series_label = (
        str(hair_color_selection.get("professional_series_label") or "").strip() or None
    )
    hair_color_professional_code = (
        str(hair_color_selection.get("professional_code") or "").strip() or None
    )
    hair_color_professional_note = (
        str(hair_color_selection.get("professional_note") or "").strip() or None
    )
    hair_color_professional_hex_estimate = (
        str(hair_color_selection.get("professional_hex_estimate") or "").strip() or None
    )
    result_dir_path = _result_dir_path(job["id"])
    return AdminHistoryItem(
        job_id=job["id"],
        user_id=int(job["user_id"]),
        nickname=repository._resolved_nickname(
            job["user_id"],
            job.get("user_nickname"),
        ),
        status=job["status"],
        upload_url=upload_url,
        hair_preview_url=hair_preview_url,
        result_image_url=result_image_url,
        result_image_urls=result_image_urls,
        completed_scene_count=len(result_image_urls),
        media_expired=media_expired,
        media_expires_at=media_expires_at,
        hairstyle_id=job["hairstyle_id"],
        hairstyle_name=(
            preset_name
            or (hairstyle["name"] if hairstyle else (resolved_hairstyle_name or job["hairstyle_id"]))
        ),
        preset_id=preset_id,
        preset_name=preset_name,
        scene_id=job["scene_id"],
        scene_name=scene["name"] if scene else job["scene_id"],
        generator_backend=prompt_payload["output_options"]["generator_backend"],
        aspect_ratio=prompt_payload["output_options"]["aspect_ratio"],
        resolution=prompt_payload["output_options"]["resolution"],
        hair_color_tone=hair_color_tone,
        hair_color_tone_label=hair_color_tone_label,
        hair_color_technique=hair_color_technique,
        hair_color_technique_label=hair_color_technique_label,
        hair_color_professional_id=hair_color_professional_id,
        hair_color_professional_brand=hair_color_professional_brand,
        hair_color_professional_series=hair_color_professional_series,
        hair_color_professional_series_label=hair_color_professional_series_label,
        hair_color_professional_code=hair_color_professional_code,
        hair_color_professional_note=hair_color_professional_note,
        hair_color_professional_hex_estimate=hair_color_professional_hex_estimate,
        error_code=job.get("error_code"),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        model_name=str(job.get("model_name") or ""),
        upload_id=str(job.get("upload_id") or ""),
        user_openid=str(job.get("user_openid") or "").strip() or None,
        upload_path=upload_path,
        upload_absolute_path=_absolute_media_path(upload_path),
        hair_preview_path=hair_preview_path,
        hair_preview_absolute_path=_absolute_media_path(hair_preview_path),
        result_dir_path=result_dir_path,
        result_dir_absolute_path=(
            str((get_settings().result_dir / job["id"]).resolve())
            if get_settings().uses_local_media
            else None
        ),
        result_image_paths=result_image_paths,
        result_image_absolute_paths=[
            absolute
            for absolute in (_absolute_media_path(path) for path in result_image_paths)
            if absolute
        ],
        hair_started_at=hair_started_at,
        first_image_ready_at=first_image_ready_at,
        first_image_duration_seconds=_duration_seconds(
            job.get("created_at"),
            first_image_ready_at,
        ),
        scene_started_at=scene_started_at,
        first_scene_ready_at=first_scene_ready_at,
        first_scene_duration_seconds=_duration_seconds(
            job.get("created_at"),
            first_scene_ready_at,
        ),
        completed_at=completed_at,
        completed_duration_seconds=_duration_seconds(
            job.get("created_at"),
            completed_at,
        ),
    )


@router.get("/admin", response_class=FileResponse)
def admin_home_page() -> FileResponse:
    return FileResponse(_HOME_PAGE_PATH)


@router.get("/admin/history", response_class=FileResponse)
def admin_history_page(request: Request) -> Response:
    return _protected_page_response(
        request,
        page_path=_HISTORY_PAGE_PATH,
        next_path="/admin/history",
    )


@router.get("/api/admin/session", response_model=AdminSessionResponse)
def get_admin_session(request: Request) -> AdminSessionResponse:
    current_admin = admin_auth.current_admin_from_request(request)
    settings = get_settings()
    return AdminSessionResponse(
        configured=settings.admin_console_enabled,
        authenticated=current_admin is not None,
        username=(current_admin or {}).get("username"),
        expires_at=(current_admin or {}).get("expires_at"),
    )


@router.post("/api/admin/session/login", response_model=AdminSessionResponse)
def login_admin_session(
    payload: AdminSessionLoginRequest,
    response: Response,
) -> AdminSessionResponse:
    settings = get_settings()
    if not admin_auth.is_admin_auth_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="管理员后台未配置账号密码。",
        )

    if not admin_auth.validate_admin_credentials(
        payload.username,
        payload.password,
        settings,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误。",
        )

    session_token, expires_at = admin_auth.create_admin_session_token(
        payload.username,
        settings=settings,
    )
    response.set_cookie(
        key=admin_auth.ADMIN_SESSION_COOKIE_NAME,
        value=session_token,
        max_age=max(1, settings.admin_console_session_ttl_hours) * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return AdminSessionResponse(
        configured=True,
        authenticated=True,
        username=payload.username.strip(),
        expires_at=expires_at,
    )


@router.post("/api/admin/session/logout", response_model=AdminSessionResponse)
def logout_admin_session(response: Response) -> AdminSessionResponse:
    response.delete_cookie(
        key=admin_auth.ADMIN_SESSION_COOKIE_NAME,
        path="/",
    )
    return AdminSessionResponse(
        configured=get_settings().admin_console_enabled,
        authenticated=False,
        username=None,
        expires_at=None,
    )


@router.get("/api/admin/history", response_model=AdminHistoryResponse)
def get_admin_history(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user_id: int | None = Query(default=None),
    status_name: str | None = Query(default=None, alias="status"),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    current_admin: dict = Depends(get_current_admin),
) -> AdminHistoryResponse:
    del current_admin

    retention.purge_expired_media()
    now = _utc_now().replace(microsecond=0)
    query_result = repository.list_admin_jobs(
        page=page,
        page_size=page_size,
        user_id=user_id,
        status=status_name,
        created_from=created_from or (now - timedelta(days=7)).isoformat(),
        created_to=created_to or now.isoformat(),
        keyword=keyword,
    )
    return AdminHistoryResponse(
        page=query_result["page"],
        page_size=query_result["page_size"],
        total=query_result["total"],
        storage_root=_storage_root_label(),
        items=[
            _admin_history_item_response(request, job)
            for job in query_result["items"]
        ],
    )
