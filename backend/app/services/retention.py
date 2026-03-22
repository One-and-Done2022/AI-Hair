from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

from app.config import get_settings
from app.services import repository, storage


_cleanup_lock = Lock()
_last_cleanup_started_at = 0.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def media_expires_at(created_at: str) -> str:
    settings = get_settings()
    created_dt = repository._parse_iso_datetime(created_at)
    if created_dt is None:
        created_dt = _utc_now()
    return (created_dt + timedelta(days=settings.media_retention_days)).replace(
        microsecond=0
    ).isoformat()


def is_media_expired(created_at: str, *, now: datetime | None = None) -> bool:
    current = now or _utc_now()
    expires_at = repository._parse_iso_datetime(media_expires_at(created_at))
    if expires_at is None:
        return False
    return current >= expires_at


def purge_expired_media(*, force: bool = False, min_interval_seconds: int = 1800) -> dict[str, int]:
    global _last_cleanup_started_at

    now_monotonic = monotonic()
    if not force and (now_monotonic - _last_cleanup_started_at) < min_interval_seconds:
        return {"uploads": 0, "jobs": 0}

    with _cleanup_lock:
        now_monotonic = monotonic()
        if not force and (now_monotonic - _last_cleanup_started_at) < min_interval_seconds:
            return {"uploads": 0, "jobs": 0}

        _last_cleanup_started_at = now_monotonic
        now = _utc_now()
        cutoff = (now - timedelta(days=get_settings().media_retention_days)).replace(
            microsecond=0
        ).isoformat()

        expired_uploads = repository.list_expired_uploads(cutoff)
        expired_jobs = repository.list_expired_jobs_with_media(cutoff)

        purged_uploads = 0
        purged_jobs = 0

        for upload in expired_uploads:
            stored_path = (upload.get("stored_path") or "").strip()
            if not stored_path:
                continue
            storage.delete_media_object(stored_path)
            repository.clear_upload_media(upload["id"])
            purged_uploads += 1

        for job in expired_jobs:
            storage.delete_result_bundle(job["id"])
            repository.clear_job_media(job["id"])
            purged_jobs += 1

        return {"uploads": purged_uploads, "jobs": purged_jobs}
