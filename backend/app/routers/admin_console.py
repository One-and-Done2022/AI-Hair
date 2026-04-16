from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse

from app.config import get_settings
from app.dependencies import get_current_admin
from app.schemas import (
    AdminFeedbackItem,
    AdminFeedbackResponse,
    AdminFeedbackSummary,
    AdminHistoryItem,
    AdminHistoryResponse,
    AdminUserItem,
    AdminUserListResponse,
    AdminSessionLoginRequest,
    AdminSessionResponse,
    AdminUserQuotaGrantRequest,
    AdminUserQuotaResponse,
)
from app.services import admin_auth, repository, retention, storage, templates


router = APIRouter(tags=["admin-console"])
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_HOME_PAGE_PATH = _STATIC_DIR / "admin_home.html"
_FEEDBACK_PAGE_PATH = _STATIC_DIR / "admin_feedback.html"
_HISTORY_PAGE_PATH = _STATIC_DIR / "admin_history.html"
_USERS_PAGE_PATH = _STATIC_DIR / "admin_users.html"


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
    quota = repository._build_quota_snapshot(
        {
            "free_quota_total": job.get("user_free_quota_total"),
            "free_quota_used": job.get("user_free_quota_used"),
            "paid_quota_balance": job.get("user_paid_quota_balance"),
        }
    )
    return AdminHistoryItem(
        job_id=job["id"],
        user_id=int(job["user_id"]),
        nickname=repository._resolved_nickname(
            job["user_id"],
            job.get("user_nickname"),
        ),
        free_quota_total=quota["free_quota_total"],
        free_quota_used=quota["free_quota_used"],
        free_remaining=quota["free_remaining"],
        paid_remaining=quota["paid_remaining"],
        total_remaining=quota["total_remaining"],
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


def _admin_user_quota_response(summary: dict) -> AdminUserQuotaResponse:
    return AdminUserQuotaResponse(
        user_id=int(summary["user_id"]),
        nickname=str(summary.get("nickname") or ""),
        user_openid=str(summary.get("user_openid") or "").strip() or None,
        free_quota_total=int(summary.get("free_quota_total") or 0),
        free_quota_used=int(summary.get("free_quota_used") or 0),
        free_remaining=int(summary.get("free_remaining") or 0),
        paid_remaining=int(summary.get("paid_remaining") or 0),
        total_remaining=int(summary.get("total_remaining") or 0),
        total_jobs=int(summary.get("total_jobs") or 0),
        completed_jobs=int(summary.get("completed_jobs") or 0),
        processing_jobs=int(summary.get("processing_jobs") or 0),
        last_job_created_at=str(summary.get("last_job_created_at") or "").strip() or None,
        created_at=str(summary.get("created_at") or ""),
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


@router.get("/admin/feedback", response_class=FileResponse)
def admin_feedback_page(request: Request) -> Response:
    return _protected_page_response(
        request,
        page_path=_FEEDBACK_PAGE_PATH,
        next_path="/admin/feedback",
    )


@router.get("/admin/users", response_class=FileResponse)
def admin_users_page(request: Request) -> Response:
    return _protected_page_response(
        request,
        page_path=_USERS_PAGE_PATH,
        next_path="/admin/users",
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


@router.get("/api/admin/users", response_model=AdminUserListResponse)
def get_admin_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    current_admin: dict = Depends(get_current_admin),
) -> AdminUserListResponse:
    del current_admin

    query_result = repository.list_admin_users(
        page=page,
        page_size=page_size,
        user_id=user_id,
        keyword=keyword,
    )
    return AdminUserListResponse(
        page=query_result["page"],
        page_size=query_result["page_size"],
        total=query_result["total"],
        items=[
            AdminUserItem.model_validate(item)
            for item in query_result["items"]
        ],
    )


@router.post(
    "/api/admin/users/{user_id}/quota/grant",
    response_model=AdminUserQuotaResponse,
)
def grant_admin_user_quota(
    user_id: int,
    payload: AdminUserQuotaGrantRequest,
    current_admin: dict = Depends(get_current_admin),
) -> AdminUserQuotaResponse:
    del current_admin
    try:
        summary = repository.grant_user_paid_quota(user_id, payload.count)
    except ValueError as exc:
        message = str(exc)
        if message == "grant_count_must_be_positive":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="补发次数必须大于 0。",
            ) from exc
        if message.startswith("User not found:"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在。",
            ) from exc
        raise
    return _admin_user_quota_response(summary)


@router.get("/api/admin/feedback", response_model=AdminFeedbackResponse)
def get_admin_feedback(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    survey_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    current_admin: dict = Depends(get_current_admin),
) -> AdminFeedbackResponse:
    del current_admin

    query_result = repository.list_admin_feedback_submissions(
        page=page,
        page_size=page_size,
        survey_type=survey_type,
        keyword=keyword,
    )
    return AdminFeedbackResponse(
        page=query_result["page"],
        page_size=query_result["page_size"],
        total=query_result["total"],
        summary=AdminFeedbackSummary.model_validate(query_result["summary"]),
        items=[
            AdminFeedbackItem(
                submission_id=item["id"],
                user_id=int(item["user_id"]),
                nickname=repository._resolved_nickname(
                    item["user_id"],
                    item.get("user_nickname"),
                ),
                user_openid=str(item.get("user_openid") or "").strip() or None,
                job_id=str(item.get("job_id") or "").strip() or None,
                job_status=str(item.get("job_status") or "").strip() or None,
                hairstyle_id=str(item.get("job_hairstyle_id") or "").strip() or None,
                scene_id=str(item.get("job_scene_id") or "").strip() or None,
                survey_type=item["survey_type"],
                trigger_completed_jobs=int(item["trigger_completed_jobs"]),
                hairstyle_expectation=item["hairstyle_expectation"],
                hair_color_satisfaction=item["hair_color_satisfaction"],
                scene_satisfaction=item["scene_satisfaction"],
                wait_time_feeling=item["wait_time_feeling"],
                image_clarity_satisfaction=item["image_clarity_satisfaction"],
                ui_usability=item["ui_usability"],
                improvement_suggestion=item.get("improvement_suggestion"),
                created_at=item["created_at"],
                job_created_at=item.get("job_created_at"),
            )
            for item in query_result["items"]
        ],
    )
