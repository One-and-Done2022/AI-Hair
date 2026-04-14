from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request

from app.config import Settings, get_settings


ADMIN_SESSION_COOKIE_NAME = "aiface_admin_session"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def _session_secret(settings: Settings | None = None) -> bytes:
    current = settings or get_settings()
    configured_secret = current.admin_console_session_secret.strip()
    if configured_secret:
        return configured_secret.encode("utf-8")
    derived_secret = (
        f"{current.app_name}|"
        f"{current.admin_console_username}|"
        f"{current.admin_console_password}"
    )
    return hashlib.sha256(derived_secret.encode("utf-8")).digest()


def is_admin_auth_configured(settings: Settings | None = None) -> bool:
    current = settings or get_settings()
    return current.admin_console_enabled


def validate_admin_credentials(
    username: str,
    password: str,
    settings: Settings | None = None,
) -> bool:
    current = settings or get_settings()
    if not is_admin_auth_configured(current):
        return False
    expected_username = current.admin_console_username.strip()
    expected_password = current.admin_console_password.strip()
    return hmac.compare_digest(username.strip(), expected_username) and hmac.compare_digest(
        password,
        expected_password,
    )


def create_admin_session_token(
    username: str,
    *,
    settings: Settings | None = None,
) -> tuple[str, str]:
    current = settings or get_settings()
    issued_at = _utc_now()
    expires_at = issued_at + timedelta(hours=current.admin_console_session_ttl_hours)
    payload = {
        "username": username.strip(),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_segment = _base64url_encode(payload_bytes)
    signature = hmac.new(
        _session_secret(current),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = f"{payload_segment}.{_base64url_encode(signature)}"
    return token, expires_at.replace(microsecond=0).isoformat()


def read_admin_session(token: str, *, settings: Settings | None = None) -> dict[str, Any] | None:
    current = settings or get_settings()
    if not is_admin_auth_configured(current):
        return None
    if not token or "." not in token:
        return None
    payload_segment, signature_segment = token.split(".", 1)
    expected_signature = hmac.new(
        _session_secret(current),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    try:
        provided_signature = _base64url_decode(signature_segment)
    except Exception:
        return None
    if not hmac.compare_digest(provided_signature, expected_signature):
        return None
    try:
        payload = json.loads(_base64url_decode(payload_segment).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    username = str(payload.get("username") or "").strip()
    expires_at_timestamp = payload.get("exp")
    if not username or not isinstance(expires_at_timestamp, int):
        return None
    if expires_at_timestamp <= int(_utc_now().timestamp()):
        return None
    return {
        "username": username,
        "expires_at": datetime.fromtimestamp(
            expires_at_timestamp,
            tz=timezone.utc,
        ).replace(microsecond=0).isoformat(),
    }


def current_admin_from_request(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)
    if not token:
        return None
    return read_admin_session(token)
