from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.config import get_settings


_STATE_LOCK = Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _alert_file() -> Path:
    settings = get_settings()
    settings.ensure_directories()
    return settings.storage_dir / "provider_alerts.json"


def _load_state() -> dict[str, dict]:
    path = _alert_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, dict]) -> None:
    path = _alert_file()
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def upsert_alert(*, alert_id: str, message: str) -> None:
    with _STATE_LOCK:
        state = _load_state()
        existing = state.get(alert_id, {})
        state[alert_id] = {
            "message": message,
            "created_at": existing.get("created_at") or _utc_now(),
            "updated_at": _utc_now(),
        }
        _save_state(state)


def clear_alert(alert_id: str) -> None:
    with _STATE_LOCK:
        state = _load_state()
        if alert_id not in state:
            return
        state.pop(alert_id, None)
        _save_state(state)


def list_alert_messages() -> list[str]:
    with _STATE_LOCK:
        state = _load_state()
        items = list(state.values())
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return [
        str(item.get("message") or "").strip()
        for item in items
        if str(item.get("message") or "").strip()
    ]
