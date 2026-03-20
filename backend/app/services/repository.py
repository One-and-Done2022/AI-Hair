from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, insert, select, update

from app.config import get_settings
from app.db import auth_tokens, jobs, session_scope, uploads, users


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mapping_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def get_or_create_user(openid: str) -> dict:
    with session_scope() as session:
        row = session.execute(
            select(users).where(users.c.openid == openid)
        ).mappings().one_or_none()
        if row is not None:
            return dict(row)

        created_at = utc_now()
        result = session.execute(
            insert(users).values(openid=openid, created_at=created_at)
        )
        user_id = result.inserted_primary_key[0]
        return {
            "id": user_id,
            "openid": openid,
            "created_at": created_at,
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
        ("pending", "processing", "preview_ready")
        if include_pending
        else ("processing", "preview_ready")
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
