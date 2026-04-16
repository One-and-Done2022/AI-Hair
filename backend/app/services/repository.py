from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import String, and_, case, cast, delete, func, insert, not_, or_, select, update

from app.config import get_settings
from app.db import (
    auth_tokens,
    feedback_submissions,
    jobs,
    purchase_orders,
    session_scope,
    uploads,
    users,
)

DEFAULT_FREE_QUOTA_TOTAL = 10
_ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")


class QuotaExceededError(Exception):
    def __init__(self, quota: dict):
        super().__init__("No remaining generation quota.")
        self.quota = quota

ACTIVE_JOB_STATUSES = (
    "pending",
    "hair_generating",
    "hair_ready",
    "scene_generating",
    "scene_partial",
    "processing",
    "preview_ready",
)
TERMINAL_JOB_STATUSES = ("succeeded", "failed")
PURCHASE_ORDER_PENDING = "pending"
PURCHASE_ORDER_PAYMENT_PREPARED = "payment_prepared"
PURCHASE_ORDER_CONFIRMED = "confirmed"
FEEDBACK_SURVEY_FIRST_SUCCESS = "first_success"
FEEDBACK_SURVEY_FOURTH_SUCCESS = "fourth_success"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_admin_datetime_filter(
    value: str | None,
    *,
    end_of_day: bool = False,
) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None

    if len(normalized) == 10:
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if end_of_day:
            parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=0)
        else:
            parsed = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
        parsed = parsed.replace(tzinfo=_ASIA_SHANGHAI)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    parsed = _parse_iso_datetime(normalized)
    if parsed is None:
        return None
    return parsed.replace(microsecond=0).isoformat()


def _mapping_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _resolved_nickname(user_id: object, nickname: object | None = None) -> str:
    normalized = str(nickname or "").strip()
    if normalized:
        return normalized
    return f"微信用户 {user_id}"


def _normalize_quota_int(value: object, default: int = 0) -> int:
    try:
        normalized = int(value if value is not None else default)
    except (TypeError, ValueError):
        normalized = default
    return max(0, normalized)


def _build_quota_snapshot(user_row: dict) -> dict:
    free_quota_total = _normalize_quota_int(
        user_row.get("free_quota_total"),
        DEFAULT_FREE_QUOTA_TOTAL,
    )
    free_quota_used = min(
        _normalize_quota_int(user_row.get("free_quota_used"), 0),
        free_quota_total,
    )
    paid_quota_balance = _normalize_quota_int(user_row.get("paid_quota_balance"), 0)
    free_remaining = max(0, free_quota_total - free_quota_used)
    total_remaining = free_remaining + paid_quota_balance
    return {
        "free_quota_total": free_quota_total,
        "free_quota_used": free_quota_used,
        "free_remaining": free_remaining,
        "paid_remaining": paid_quota_balance,
        "paid_quota_balance": paid_quota_balance,
        "total_remaining": total_remaining,
    }


def _purchase_order_amount(quantity: int, unit_price_cents: int) -> int:
    return max(0, quantity) * max(0, unit_price_cents)


def get_or_create_user(openid: str, nickname: str | None = None) -> dict:
    with session_scope() as session:
        row = session.execute(
            select(users).where(users.c.openid == openid)
        ).mappings().one_or_none()
        if row is not None:
            normalized_nickname = str(nickname or "").strip()
            if normalized_nickname and normalized_nickname != str(row.get("nickname") or "").strip():
                session.execute(
                    update(users)
                    .where(users.c.id == row["id"])
                    .values(nickname=normalized_nickname)
                )
                updated_row = dict(row)
                updated_row["nickname"] = normalized_nickname
                return updated_row
            return dict(row)

        created_at = utc_now()
        result = session.execute(
            insert(users).values(
                openid=openid,
                nickname=str(nickname or "").strip() or None,
                created_at=created_at,
                free_quota_total=DEFAULT_FREE_QUOTA_TOTAL,
                free_quota_used=0,
                paid_quota_balance=0,
            )
        )
        user_id = result.inserted_primary_key[0]
        return {
            "id": user_id,
            "openid": openid,
            "nickname": str(nickname or "").strip() or None,
            "created_at": created_at,
            "free_quota_total": DEFAULT_FREE_QUOTA_TOTAL,
            "free_quota_used": 0,
            "paid_quota_balance": 0,
        }


def get_user(user_id: int) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(users).where(users.c.id == user_id)
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def update_user_nickname(user_id: int, nickname: str | None) -> dict | None:
    normalized_nickname = str(nickname or "").strip() or None
    with session_scope() as session:
        session.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(nickname=normalized_nickname)
        )
    return get_user(user_id)


def grant_user_paid_quota(user_id: int, count: int) -> dict:
    normalized_count = _normalize_quota_int(count, 0)
    if normalized_count <= 0:
        raise ValueError("grant_count_must_be_positive")

    with session_scope() as session:
        user_row = session.execute(
            select(users).where(users.c.id == user_id)
        ).mappings().one_or_none()
        if user_row is None:
            raise ValueError(f"User not found: {user_id}")

        current_balance = _normalize_quota_int(user_row.get("paid_quota_balance"), 0)
        session.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(paid_quota_balance=current_balance + normalized_count)
        )

    summary = get_admin_user_quota_summary(user_id)
    if not summary:
        raise ValueError(f"User not found: {user_id}")
    return summary


def create_auth_token(user_id: int) -> str:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    created_at = utc_now()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=settings.api_token_ttl_hours)
    ).replace(microsecond=0).isoformat()

    with session_scope() as session:
        session.execute(
            insert(auth_tokens).values(
                token=token,
                user_id=user_id,
                created_at=created_at,
                expires_at=expires_at,
            )
        )
    return token


def get_user_by_token(token: str) -> dict | None:
    now = utc_now()
    with session_scope() as session:
        row = session.execute(
            select(
                users.c.id,
                users.c.openid,
                users.c.nickname,
                users.c.created_at,
            )
            .select_from(auth_tokens.join(users, users.c.id == auth_tokens.c.user_id))
            .where(
                and_(
                    auth_tokens.c.token == token,
                    auth_tokens.c.expires_at > now,
                )
            )
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def create_upload(
    *,
    user_id: int,
    original_name: str,
    stored_path: str,
    mime_type: str,
    file_size: int,
    width: int,
    height: int,
) -> dict:
    upload_id = uuid.uuid4().hex
    created_at = utc_now()
    with session_scope() as session:
        session.execute(
            insert(uploads).values(
                id=upload_id,
                user_id=user_id,
                original_name=original_name,
                stored_path=stored_path,
                mime_type=mime_type,
                file_size=file_size,
                width=width,
                height=height,
                created_at=created_at,
            )
        )
    return get_upload(upload_id)


def get_upload(upload_id: str) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(uploads).where(uploads.c.id == upload_id)
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def create_job(
    *,
    user_id: int,
    upload_id: str,
    hairstyle_id: str,
    scene_id: str,
    prompt: str,
    model_name: str,
) -> dict:
    job_id = uuid.uuid4().hex
    created_at = utc_now()
    with session_scope() as session:
        session.execute(
            insert(jobs).values(
                id=job_id,
                user_id=user_id,
                upload_id=upload_id,
                hairstyle_id=hairstyle_id,
                scene_id=scene_id,
                status="pending",
                prompt=prompt,
                model_name=model_name,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    return get_job(job_id)


def create_job_consuming_quota(
    *,
    user_id: int,
    upload_id: str,
    hairstyle_id: str,
    scene_id: str,
    prompt: str,
    model_name: str,
) -> dict:
    job_id = uuid.uuid4().hex
    created_at = utc_now()
    with session_scope() as session:
        user_row = session.execute(
            select(users).where(users.c.id == user_id)
        ).mappings().one_or_none()
        if user_row is None:
            raise ValueError(f"User not found: {user_id}")

        quota = _build_quota_snapshot(dict(user_row))
        if quota["total_remaining"] <= 0:
            raise QuotaExceededError(quota)

        if quota["free_remaining"] > 0:
            session.execute(
                update(users)
                .where(users.c.id == user_id)
                .values(free_quota_used=quota["free_quota_used"] + 1)
            )
        else:
            session.execute(
                update(users)
                .where(users.c.id == user_id)
                .values(paid_quota_balance=quota["paid_quota_balance"] - 1)
            )

        session.execute(
            insert(jobs).values(
                id=job_id,
                user_id=user_id,
                upload_id=upload_id,
                hairstyle_id=hairstyle_id,
                scene_id=scene_id,
                status="pending",
                prompt=prompt,
                model_name=model_name,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    return get_job(job_id)


def get_job(job_id: str) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(jobs).where(jobs.c.id == job_id)
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def get_job_for_user(job_id: str, user_id: int) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(jobs).where(
                and_(
                    jobs.c.id == job_id,
                    jobs.c.user_id == user_id,
                )
            )
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def list_jobs_for_user(user_id: int) -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            select(jobs)
            .where(jobs.c.user_id == user_id)
            .order_by(jobs.c.created_at.desc())
        ).mappings().all()
        return [dict(row) for row in rows]


def list_admin_jobs(
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    status: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    normalized_created_from = _normalize_admin_datetime_filter(created_from)
    normalized_created_to = _normalize_admin_datetime_filter(created_to, end_of_day=True)
    filters = []

    if user_id is not None:
        filters.append(jobs.c.user_id == user_id)

    normalized_status = str(status or "").strip()
    if normalized_status:
        filters.append(jobs.c.status == normalized_status)

    if normalized_created_from:
        filters.append(jobs.c.created_at >= normalized_created_from)
    if normalized_created_to:
        filters.append(jobs.c.created_at <= normalized_created_to)

    normalized_keyword = str(keyword or "").strip().lower()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        filters.append(
            or_(
                func.lower(cast(jobs.c.id, String)).like(pattern),
                func.lower(cast(jobs.c.upload_id, String)).like(pattern),
                func.lower(cast(jobs.c.hairstyle_id, String)).like(pattern),
                func.lower(cast(jobs.c.scene_id, String)).like(pattern),
                func.lower(cast(jobs.c.error_code, String)).like(pattern),
                func.lower(cast(jobs.c.error_message, String)).like(pattern),
                func.lower(cast(jobs.c.model_name, String)).like(pattern),
                func.lower(cast(jobs.c.user_id, String)).like(pattern),
                func.lower(cast(users.c.nickname, String)).like(pattern),
                func.lower(cast(users.c.openid, String)).like(pattern),
            )
        )

    joined_tables = (
        jobs.join(users, users.c.id == jobs.c.user_id)
        .outerjoin(uploads, uploads.c.id == jobs.c.upload_id)
    )
    where_clause = and_(*filters) if filters else None

    total_statement = select(func.count()).select_from(joined_tables)
    list_statement = (
        select(
            jobs,
            users.c.nickname.label("user_nickname"),
            users.c.openid.label("user_openid"),
            users.c.free_quota_total.label("user_free_quota_total"),
            users.c.free_quota_used.label("user_free_quota_used"),
            users.c.paid_quota_balance.label("user_paid_quota_balance"),
            uploads.c.original_name.label("upload_original_name"),
            uploads.c.stored_path.label("upload_stored_path"),
            uploads.c.mime_type.label("upload_mime_type"),
            uploads.c.file_size.label("upload_file_size"),
            uploads.c.width.label("upload_width"),
            uploads.c.height.label("upload_height"),
            uploads.c.created_at.label("upload_created_at"),
        )
        .select_from(joined_tables)
        .order_by(jobs.c.created_at.desc())
        .limit(page_size)
        .offset(max(0, page - 1) * page_size)
    )
    if where_clause is not None:
        total_statement = total_statement.where(where_clause)
        list_statement = list_statement.where(where_clause)

    with session_scope() as session:
        total = int(session.execute(total_statement).scalar_one() or 0)
        rows = session.execute(list_statement).mappings().all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [dict(row) for row in rows],
    }


def _admin_user_stats_subquery():
    return (
        select(
            jobs.c.user_id.label("user_id"),
            func.count(jobs.c.id).label("total_jobs"),
            func.sum(
                case(
                    (jobs.c.status == "succeeded", 1),
                    else_=0,
                )
            ).label("completed_jobs"),
            func.sum(
                case(
                    (jobs.c.status.in_(ACTIVE_JOB_STATUSES), 1),
                    else_=0,
                )
            ).label("processing_jobs"),
            func.max(jobs.c.created_at).label("last_job_created_at"),
        )
        .group_by(jobs.c.user_id)
        .subquery()
    )


def _build_admin_user_quota_summary_from_row(row: dict) -> dict:
    quota = _build_quota_snapshot(row)
    return {
        "user_id": int(row["id"]),
        "nickname": _resolved_nickname(row["id"], row.get("nickname")),
        "user_openid": str(row.get("openid") or "").strip() or None,
        "free_quota_total": quota["free_quota_total"],
        "free_quota_used": quota["free_quota_used"],
        "free_remaining": quota["free_remaining"],
        "paid_remaining": quota["paid_remaining"],
        "total_remaining": quota["total_remaining"],
        "total_jobs": int(row.get("total_jobs") or 0),
        "completed_jobs": int(row.get("completed_jobs") or 0),
        "processing_jobs": int(row.get("processing_jobs") or 0),
        "last_job_created_at": str(row.get("last_job_created_at") or "").strip() or None,
        "created_at": row["created_at"],
    }


def get_admin_user_quota_summary(user_id: int) -> dict | None:
    stats_subquery = _admin_user_stats_subquery()
    with session_scope() as session:
        row = session.execute(
            select(
                users,
                stats_subquery.c.total_jobs,
                stats_subquery.c.completed_jobs,
                stats_subquery.c.processing_jobs,
                stats_subquery.c.last_job_created_at,
            )
            .select_from(
                users.outerjoin(stats_subquery, stats_subquery.c.user_id == users.c.id)
            )
            .where(users.c.id == user_id)
        ).mappings().one_or_none()
        if row is None:
            return None
        return _build_admin_user_quota_summary_from_row(dict(row))


def list_admin_users(
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    keyword: str | None = None,
    sort_by: str = "last_active",
    sort_direction: str = "desc",
    account_scope: str = "all",
) -> dict[str, Any]:
    stats_subquery = _admin_user_stats_subquery()
    filters = []
    if user_id is not None:
        filters.append(users.c.id == user_id)

    normalized_keyword = str(keyword or "").strip().lower()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        filters.append(
            or_(
                func.lower(cast(users.c.id, String)).like(pattern),
                func.lower(cast(users.c.nickname, String)).like(pattern),
                func.lower(cast(users.c.openid, String)).like(pattern),
            )
        )

    normalized_scope = str(account_scope or "all").strip().lower()
    if normalized_scope == "wechat_only":
        filters.append(users.c.openid.like("og%"))
    elif normalized_scope == "internal_only":
        filters.append(
            or_(
                users.c.openid.like("dev\\_%", escape="\\"),
                users.c.openid.like("provider-admin-%"),
            )
        )

    joined_tables = users.outerjoin(stats_subquery, stats_subquery.c.user_id == users.c.id)
    where_clause = and_(*filters) if filters else None

    free_quota_total_expr = func.coalesce(users.c.free_quota_total, DEFAULT_FREE_QUOTA_TOTAL)
    free_quota_used_expr = func.coalesce(users.c.free_quota_used, 0)
    paid_quota_balance_expr = func.coalesce(users.c.paid_quota_balance, 0)
    free_remaining_expr = case(
        (free_quota_used_expr >= free_quota_total_expr, 0),
        else_=free_quota_total_expr - free_quota_used_expr,
    )
    total_remaining_expr = free_remaining_expr + paid_quota_balance_expr
    total_jobs_expr = func.coalesce(stats_subquery.c.total_jobs, 0)
    last_active_expr = stats_subquery.c.last_job_created_at

    normalized_sort_by = str(sort_by or "last_active").strip().lower()
    normalized_sort_direction = str(sort_direction or "desc").strip().lower()
    sort_is_asc = normalized_sort_direction == "asc"

    sort_expression_map = {
        "last_active": last_active_expr,
        "usage_count": total_jobs_expr,
        "user_id": users.c.id,
        "remaining_quota": total_remaining_expr,
        "created_at": users.c.created_at,
    }
    primary_sort_expr = sort_expression_map.get(normalized_sort_by, last_active_expr)
    primary_sort_clause = primary_sort_expr.asc() if sort_is_asc else primary_sort_expr.desc()

    order_clauses = []
    if normalized_sort_by == "last_active":
        order_clauses.extend(
            [
                case(
                    (last_active_expr.is_(None), 1),
                    else_=0,
                ),
                primary_sort_clause,
                users.c.id.desc(),
            ]
        )
    else:
        order_clauses.extend(
            [
                primary_sort_clause,
                users.c.id.desc() if not sort_is_asc else users.c.id.asc(),
            ]
        )

    total_statement = select(func.count()).select_from(joined_tables)
    list_statement = (
        select(
            users,
            stats_subquery.c.total_jobs,
            stats_subquery.c.completed_jobs,
            stats_subquery.c.processing_jobs,
            stats_subquery.c.last_job_created_at,
        )
        .select_from(joined_tables)
        .order_by(*order_clauses)
        .limit(page_size)
        .offset(max(0, page - 1) * page_size)
    )
    if where_clause is not None:
        total_statement = total_statement.where(where_clause)
        list_statement = list_statement.where(where_clause)

    with session_scope() as session:
        total = int(session.execute(total_statement).scalar_one() or 0)
        rows = session.execute(list_statement).mappings().all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [
            _build_admin_user_quota_summary_from_row(dict(row))
            for row in rows
        ],
    }


def get_user_profile_summary(user_id: int) -> dict:
    with session_scope() as session:
        user_row = session.execute(
            select(users).where(users.c.id == user_id)
        ).mappings().one_or_none()
        if user_row is None:
            raise ValueError(f"User not found: {user_id}")

        job_rows = session.execute(
            select(jobs.c.status, jobs.c.created_at).where(jobs.c.user_id == user_id)
        ).mappings().all()

    total_jobs = len(job_rows)
    completed_jobs = sum(1 for row in job_rows if row["status"] == "succeeded")
    processing_jobs = sum(
        1 for row in job_rows if row["status"] in ACTIVE_JOB_STATUSES
    )

    now = datetime.now(timezone.utc)
    monthly_used = 0
    for row in job_rows:
        created_at = _parse_iso_datetime(row["created_at"])
        if created_at is None:
            continue
        if created_at.year == now.year and created_at.month == now.month:
            monthly_used += 1

    quota = _build_quota_snapshot(dict(user_row))

    return {
        "user_id": user_row["id"],
        "nickname": _resolved_nickname(user_row["id"], user_row.get("nickname")),
        "member_status": "内测用户",
        "remaining_quota": quota["total_remaining"],
        "monthly_used": monthly_used,
        "free_quota_total": quota["free_quota_total"],
        "free_quota_used": quota["free_quota_used"],
        "free_remaining": quota["free_remaining"],
        "paid_remaining": quota["paid_remaining"],
        "total_remaining": quota["total_remaining"],
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "processing_jobs": processing_jobs,
        "created_at": user_row["created_at"],
    }


def count_succeeded_jobs_for_user(user_id: int) -> int:
    with session_scope() as session:
        return int(
            session.execute(
                select(func.count())
                .select_from(jobs)
                .where(
                    and_(
                        jobs.c.user_id == user_id,
                        jobs.c.status == "succeeded",
                    )
                )
            ).scalar_one()
            or 0
        )


def _feedback_prompt_for_success_ordinal(success_ordinal: int) -> dict[str, Any] | None:
    if success_ordinal == 1:
        return {
            "survey_type": FEEDBACK_SURVEY_FIRST_SUCCESS,
            "trigger_completed_jobs": 1,
            "title": "首次使用体验反馈",
            "description": "这是你第一次成功出图，想收集一下首次使用体验。",
        }
    if success_ordinal == 4:
        return {
            "survey_type": FEEDBACK_SURVEY_FOURTH_SUCCESS,
            "trigger_completed_jobs": 4,
            "title": "多次使用体验反馈",
            "description": "你已经累计成功出图 4 次，想了解你连续使用后的真实感受。",
        }
    return None


def get_feedback_submission_for_user(
    user_id: int,
    survey_type: str,
) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(feedback_submissions).where(
                and_(
                    feedback_submissions.c.user_id == user_id,
                    feedback_submissions.c.survey_type == survey_type,
                )
            )
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def get_pending_feedback_for_job(user_id: int, job_id: str) -> dict[str, Any] | None:
    job = get_job_for_user(job_id, user_id)
    if job is None or job.get("status") != "succeeded":
        return None

    with session_scope() as session:
        success_ordinal = int(
            session.execute(
                select(func.count())
                .select_from(jobs)
                .where(
                    and_(
                        jobs.c.user_id == user_id,
                        jobs.c.status == "succeeded",
                        or_(
                            jobs.c.created_at < job["created_at"],
                            and_(
                                jobs.c.created_at == job["created_at"],
                                jobs.c.id <= job["id"],
                            ),
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )

    prompt = _feedback_prompt_for_success_ordinal(success_ordinal)
    if prompt is None:
        return None
    if get_feedback_submission_for_user(user_id, prompt["survey_type"]) is not None:
        return None
    return {
        **prompt,
        "job_id": job["id"],
        "success_ordinal": success_ordinal,
    }


def create_feedback_submission(
    *,
    user_id: int,
    job_id: str,
    survey_type: str,
    trigger_completed_jobs: int,
    hairstyle_expectation: str,
    hair_color_satisfaction: str,
    scene_satisfaction: str,
    wait_time_feeling: str,
    image_clarity_satisfaction: str,
    ui_usability: str,
    improvement_suggestion: str | None = None,
) -> dict:
    submission_id = uuid.uuid4().hex
    created_at = utc_now()
    with session_scope() as session:
        existing = session.execute(
            select(feedback_submissions.c.id).where(
                and_(
                    feedback_submissions.c.user_id == user_id,
                    feedback_submissions.c.survey_type == survey_type,
                )
            )
        ).first()
        if existing is not None:
            raise ValueError("feedback_already_submitted")

        session.execute(
            insert(feedback_submissions).values(
                id=submission_id,
                user_id=user_id,
                job_id=job_id,
                survey_type=survey_type,
                trigger_completed_jobs=trigger_completed_jobs,
                hairstyle_expectation=hairstyle_expectation,
                hair_color_satisfaction=hair_color_satisfaction,
                scene_satisfaction=scene_satisfaction,
                wait_time_feeling=wait_time_feeling,
                image_clarity_satisfaction=image_clarity_satisfaction,
                ui_usability=ui_usability,
                improvement_suggestion=str(improvement_suggestion or "").strip() or None,
                created_at=created_at,
            )
        )
    return get_feedback_submission_by_id(submission_id) or {
        "id": submission_id,
        "created_at": created_at,
    }


def get_feedback_submission_by_id(submission_id: str) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(feedback_submissions).where(feedback_submissions.c.id == submission_id)
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def list_admin_feedback_submissions(
    *,
    page: int = 1,
    page_size: int = 20,
    survey_type: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    filters = []
    normalized_survey_type = str(survey_type or "").strip()
    if normalized_survey_type:
        filters.append(feedback_submissions.c.survey_type == normalized_survey_type)

    normalized_keyword = str(keyword or "").strip().lower()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        filters.append(
            or_(
                func.lower(cast(feedback_submissions.c.id, String)).like(pattern),
                func.lower(cast(feedback_submissions.c.job_id, String)).like(pattern),
                func.lower(cast(feedback_submissions.c.improvement_suggestion, String)).like(pattern),
                func.lower(cast(users.c.nickname, String)).like(pattern),
                func.lower(cast(users.c.openid, String)).like(pattern),
            )
        )

    joined_tables = (
        feedback_submissions.join(users, users.c.id == feedback_submissions.c.user_id)
        .outerjoin(jobs, jobs.c.id == feedback_submissions.c.job_id)
    )
    where_clause = and_(*filters) if filters else None
    total_statement = select(func.count()).select_from(joined_tables)
    list_statement = (
        select(
            feedback_submissions,
            users.c.nickname.label("user_nickname"),
            users.c.openid.label("user_openid"),
            jobs.c.hairstyle_id.label("job_hairstyle_id"),
            jobs.c.scene_id.label("job_scene_id"),
            jobs.c.status.label("job_status"),
            jobs.c.created_at.label("job_created_at"),
        )
        .select_from(joined_tables)
        .order_by(feedback_submissions.c.created_at.desc())
        .limit(page_size)
        .offset(max(0, page - 1) * page_size)
    )
    if where_clause is not None:
        total_statement = total_statement.where(where_clause)
        list_statement = list_statement.where(where_clause)

    with session_scope() as session:
        total = int(session.execute(total_statement).scalar_one() or 0)
        rows = session.execute(list_statement).mappings().all()
        summary_statement = (
            select(
                func.count().label("total_count"),
                func.sum(
                    case(
                        (feedback_submissions.c.survey_type == FEEDBACK_SURVEY_FIRST_SUCCESS, 1),
                        else_=0,
                    )
                ).label("first_success_count"),
                func.sum(
                    case(
                        (feedback_submissions.c.survey_type == FEEDBACK_SURVEY_FOURTH_SUCCESS, 1),
                        else_=0,
                    )
                ).label("fourth_success_count"),
            )
            .select_from(joined_tables)
        )
        if where_clause is not None:
            summary_statement = summary_statement.where(where_clause)
        summary_row = session.execute(summary_statement).mappings().one()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "summary": dict(summary_row),
        "items": [dict(row) for row in rows],
    }


def delete_job_for_user(job_id: str, user_id: int) -> dict | None:
    job = get_job_for_user(job_id, user_id)
    if job is None:
        return None

    with session_scope() as session:
        session.execute(
            delete(jobs).where(
                and_(
                    jobs.c.id == job_id,
                    jobs.c.user_id == user_id,
                )
            )
        )
    return job


def count_jobs_for_upload(upload_id: str) -> int:
    with session_scope() as session:
        rows = session.execute(
            select(jobs.c.id).where(jobs.c.upload_id == upload_id)
        ).all()
        return len(rows)


def delete_upload(upload_id: str) -> None:
    with session_scope() as session:
        session.execute(
            delete(uploads).where(uploads.c.id == upload_id)
        )


def list_expired_uploads(cutoff_iso: str) -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            select(uploads).where(
                and_(
                    uploads.c.created_at < cutoff_iso,
                    uploads.c.stored_path != "",
                    not_(
                        uploads.c.id.in_(
                            select(jobs.c.upload_id).where(jobs.c.status.in_(ACTIVE_JOB_STATUSES))
                        )
                    ),
                )
            )
        ).mappings().all()
        return [dict(row) for row in rows]


def list_expired_jobs_with_media(cutoff_iso: str) -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            select(jobs).where(
                and_(
                    jobs.c.created_at < cutoff_iso,
                    jobs.c.status.in_((*TERMINAL_JOB_STATUSES, "preview_ready")),
                    or_(
                        jobs.c.result_path.is_not(None),
                        jobs.c.status == "preview_ready",
                    ),
                )
            )
        ).mappings().all()
        return [dict(row) for row in rows]


def clear_upload_media(upload_id: str) -> None:
    with session_scope() as session:
        session.execute(
            update(uploads)
            .where(uploads.c.id == upload_id)
            .values(stored_path="")
        )


def create_purchase_order(
    *,
    user_id: int,
    product_id: str,
    product_name: str,
    quantity: int,
    unit_price_cents: int,
) -> dict:
    order_id = uuid.uuid4().hex
    created_at = utc_now()
    amount_cents = _purchase_order_amount(quantity, unit_price_cents)
    with session_scope() as session:
        session.execute(
            insert(purchase_orders).values(
                id=order_id,
                user_id=user_id,
                product_id=product_id,
                product_name=product_name,
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                amount_cents=amount_cents,
                status=PURCHASE_ORDER_PENDING,
                wechat_prepay_id=None,
                wechat_transaction_id=None,
                payment_payload=None,
                created_at=created_at,
                updated_at=created_at,
                confirmed_at=None,
            )
        )
    return get_purchase_order(order_id)


def get_purchase_order(order_id: str) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(purchase_orders).where(purchase_orders.c.id == order_id)
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def get_purchase_order_for_user(order_id: str, user_id: int) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            select(purchase_orders).where(
                and_(
                    purchase_orders.c.id == order_id,
                    purchase_orders.c.user_id == user_id,
                )
            )
        ).mappings().one_or_none()
        return _mapping_to_dict(row)


def mark_purchase_order_payment_prepared(
    order_id: str,
    *,
    wechat_prepay_id: str,
) -> dict | None:
    updated_at = utc_now()
    with session_scope() as session:
        session.execute(
            update(purchase_orders)
            .where(purchase_orders.c.id == order_id)
            .values(
                status=PURCHASE_ORDER_PAYMENT_PREPARED,
                wechat_prepay_id=wechat_prepay_id,
                updated_at=updated_at,
            )
        )
    return get_purchase_order(order_id)


def confirm_purchase_order_for_user(order_id: str, user_id: int) -> dict | None:
    with session_scope() as session:
        order_row = session.execute(
            select(purchase_orders).where(
                and_(
                    purchase_orders.c.id == order_id,
                    purchase_orders.c.user_id == user_id,
                )
            )
        ).mappings().one_or_none()
        if order_row is None:
            return None

        order = dict(order_row)
        if order["status"] == PURCHASE_ORDER_CONFIRMED:
            return order

    return finalize_purchase_order_payment(
        order_id,
        payment_payload={"confirmation_mode": "manual"},
    )


def finalize_purchase_order_payment(
    order_id: str,
    *,
    wechat_transaction_id: str | None = None,
    payment_payload: dict[str, Any] | None = None,
) -> dict | None:
    confirmed_at = utc_now()
    with session_scope() as session:
        order_row = session.execute(
            select(purchase_orders).where(purchase_orders.c.id == order_id)
        ).mappings().one_or_none()
        if order_row is None:
            return None

        order = dict(order_row)
        if order["status"] == PURCHASE_ORDER_CONFIRMED:
            return order

        user_row = session.execute(
            select(users).where(users.c.id == order["user_id"])
        ).mappings().one_or_none()
        if user_row is None:
            raise ValueError(f"User not found: {order['user_id']}")

        current_balance = _normalize_quota_int(user_row.get("paid_quota_balance"), 0)
        quantity = _normalize_quota_int(order.get("quantity"), 0)

        session.execute(
            update(users)
            .where(users.c.id == order["user_id"])
            .values(paid_quota_balance=current_balance + quantity)
        )
        session.execute(
            update(purchase_orders)
            .where(purchase_orders.c.id == order_id)
            .values(
                status=PURCHASE_ORDER_CONFIRMED,
                wechat_transaction_id=wechat_transaction_id or order.get("wechat_transaction_id"),
                payment_payload=(
                    json.dumps(payment_payload, ensure_ascii=False)
                    if payment_payload is not None
                    else order.get("payment_payload")
                ),
                updated_at=confirmed_at,
                confirmed_at=confirmed_at,
            )
        )

    return get_purchase_order(order_id)


def clear_job_media(job_id: str) -> None:
    with session_scope() as session:
        session.execute(
            update(jobs)
            .where(jobs.c.id == job_id)
            .values(result_path=None)
        )


def update_job_status(
    job_id: str,
    *,
    status: str,
    result_path: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    updated_at = utc_now()
    with session_scope() as session:
        current_job = session.execute(
            select(jobs).where(jobs.c.id == job_id)
        ).mappings().one_or_none()
        if current_job is None:
            return
        current = dict(current_job)
        values = {
            "status": status,
            "result_path": result_path,
            "error_code": error_code,
            "error_message": error_message,
            "updated_at": updated_at,
        }
        if status == "hair_generating" and not current.get("hair_started_at"):
            values["hair_started_at"] = updated_at
        if status == "hair_ready" and not current.get("first_image_ready_at"):
            values["first_image_ready_at"] = updated_at
            if not current.get("hair_started_at"):
                values["hair_started_at"] = updated_at
        if status == "scene_generating" and not current.get("scene_started_at"):
            values["scene_started_at"] = updated_at
        if status == "scene_partial" and not current.get("first_scene_ready_at"):
            values["first_scene_ready_at"] = updated_at
            if not current.get("scene_started_at"):
                values["scene_started_at"] = updated_at
        if status in TERMINAL_JOB_STATUSES and not current.get("completed_at"):
            values["completed_at"] = updated_at
            if status == "succeeded" and not current.get("first_scene_ready_at"):
                values["first_scene_ready_at"] = updated_at
        session.execute(
            update(jobs)
            .where(jobs.c.id == job_id)
            .values(**values)
        )


def assign_job_key(job_id: str, assigned_key_id: str | None) -> None:
    updated_at = utc_now()
    with session_scope() as session:
        session.execute(
            update(jobs)
            .where(jobs.c.id == job_id)
            .values(
                assigned_key_id=assigned_key_id,
                updated_at=updated_at,
            )
        )


def requeue_active_jobs(*, include_pending: bool = True) -> list[str]:
    updated_at = utc_now()
    active_statuses = (
        ACTIVE_JOB_STATUSES
        if include_pending
        else tuple(status for status in ACTIVE_JOB_STATUSES if status != "pending")
    )
    with session_scope() as session:
        rows = session.execute(
            select(jobs.c.id).where(jobs.c.status.in_(active_statuses))
        ).all()
        job_ids = [row[0] for row in rows]
        if job_ids:
            session.execute(
                update(jobs)
                .where(jobs.c.status.in_(active_statuses))
                .values(
                    status="pending",
                    assigned_key_id=None,
                    error_code=None,
                    error_message=None,
                    updated_at=updated_at,
                )
            )
    return job_ids
