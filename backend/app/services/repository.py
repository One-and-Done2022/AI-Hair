from __future__ import annotations

import secrets
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db import get_connection


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def get_or_create_user(openid: str) -> dict:
    with closing(get_connection()) as connection, connection:
        row = connection.execute(
            "SELECT id, openid, created_at FROM users WHERE openid = ?",
            (openid,),
        ).fetchone()
        if row is not None:
            return dict(row)

        created_at = utc_now()
        cursor = connection.execute(
            "INSERT INTO users (openid, created_at) VALUES (?, ?)",
            (openid, created_at),
        )
        return {
            "id": cursor.lastrowid,
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

    with closing(get_connection()) as connection, connection:
        connection.execute(
            """
            INSERT INTO auth_tokens (token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, created_at, expires_at),
        )
    return token


def get_user_by_token(token: str) -> dict | None:
    now = utc_now()
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT users.id, users.openid, users.created_at
            FROM auth_tokens
            JOIN users ON users.id = auth_tokens.user_id
            WHERE auth_tokens.token = ? AND auth_tokens.expires_at > ?
            """,
            (token, now),
        ).fetchone()
        return _row_to_dict(row)


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
    with closing(get_connection()) as connection, connection:
        connection.execute(
            """
            INSERT INTO uploads (
                id, user_id, original_name, stored_path, mime_type, file_size,
                width, height, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                user_id,
                original_name,
                stored_path,
                mime_type,
                file_size,
                width,
                height,
                created_at,
            ),
        )
    return get_upload(upload_id)


def get_upload(upload_id: str) -> dict | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, user_id, original_name, stored_path, mime_type, file_size,
                   width, height, created_at
            FROM uploads
            WHERE id = ?
            """,
            (upload_id,),
        ).fetchone()
        return _row_to_dict(row)


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
    with closing(get_connection()) as connection, connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, user_id, upload_id, hairstyle_id, scene_id, status, prompt,
                model_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                upload_id,
                hairstyle_id,
                scene_id,
                prompt,
                model_name,
                created_at,
                created_at,
            ),
        )
    return get_job(job_id)


def get_job(job_id: str) -> dict | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, user_id, upload_id, hairstyle_id, scene_id, status, prompt,
                   model_name, result_path, error_code, error_message,
                   created_at, updated_at
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        return _row_to_dict(row)


def get_job_for_user(job_id: str, user_id: int) -> dict | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, user_id, upload_id, hairstyle_id, scene_id, status, prompt,
                   model_name, result_path, error_code, error_message,
                   created_at, updated_at
            FROM jobs
            WHERE id = ? AND user_id = ?
            """,
            (job_id, user_id),
        ).fetchone()
        return _row_to_dict(row)


def list_jobs_for_user(user_id: int) -> list[dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, upload_id, hairstyle_id, scene_id, status, prompt,
                   model_name, result_path, error_code, error_message,
                   created_at, updated_at
            FROM jobs
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
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
    with closing(get_connection()) as connection, connection:
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, result_path = ?, error_code = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, result_path, error_code, error_message, updated_at, job_id),
        )


def requeue_active_jobs() -> list[str]:
    updated_at = utc_now()
    with closing(get_connection()) as connection, connection:
        rows = connection.execute(
            """
            SELECT id FROM jobs WHERE status IN ('pending', 'processing')
            """
        ).fetchall()
        job_ids = [row["id"] for row in rows]
        if job_ids:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'pending', error_code = NULL, error_message = NULL, updated_at = ?
                WHERE status IN ('pending', 'processing')
                """,
                (updated_at,),
            )
    return job_ids

