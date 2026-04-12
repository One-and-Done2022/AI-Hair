from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, insert, not_, or_, select, update

from app.config import get_settings
from app.db import auth_tokens, jobs, purchase_orders, session_scope, uploads, users

DEFAULT_FREE_QUOTA_TOTAL = 10


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


def _mapping_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


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


def get_or_create_user(openid: str) -> dict:
    with session_scope() as session:
        row = session.execute(
            select(users).where(users.c.openid == openid)
        ).mappings().one_or_none()
        if row is not None:
            return dict(row)

        created_at = utc_now()
        result = session.execute(
            insert(users).values(
                openid=openid,
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
            "created_at": created_at,
            "free_quota_total": DEFAULT_FREE_QUOTA_TOTAL,
            "free_quota_used": 0,
            "paid_quota_balance": 0,
        }


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
        "nickname": f"微信用户 {user_row['id']}",
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
        session.execute(
            update(jobs)
            .where(jobs.c.id == job_id)
            .values(
                status=status,
                result_path=result_path,
                error_code=error_code,
                error_message=error_message,
                updated_at=updated_at,
            )
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
