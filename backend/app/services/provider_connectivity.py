from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

import httpx

from app.config import Settings, get_settings
from app.services import provider_routing


logger = logging.getLogger(__name__)
_STATE_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    provider_id: str
    entry_id: str
    target_id: str
    label: str
    url: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _state_file() -> Path:
    settings = get_settings()
    settings.ensure_directories()
    return settings.storage_dir / "provider_connectivity.json"


def _save_state(state: dict) -> None:
    path = _state_file()
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_state() -> dict:
    path = _state_file()
    if not path.exists():
        return {
            "updated_at": None,
            "targets": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return {
            "updated_at": None,
            "targets": [],
        }
    targets = payload.get("targets")
    if not isinstance(targets, list):
        targets = []
    return {
        "updated_at": payload.get("updated_at"),
        "enabled": payload.get("enabled"),
        "interval_seconds": payload.get("interval_seconds"),
        "timeout_seconds": payload.get("timeout_seconds"),
        "targets": [item for item in targets if isinstance(item, dict)],
    }


def build_probe_targets(
    settings: Settings | None = None,
    provider_id: str | None = None,
) -> list[ProbeTarget]:
    current = settings or get_settings()
    normalized_provider_id = str(provider_id or "").strip()
    if normalized_provider_id:
        provider_routing.get_provider_definition(normalized_provider_id, current)

    targets: list[ProbeTarget] = []
    for provider in provider_routing.list_provider_definitions(current):
        if normalized_provider_id and provider.provider_id != normalized_provider_id:
            continue
        for entry in provider.entries:
            targets.append(
                ProbeTarget(
                    provider_id=provider.provider_id,
                    entry_id=entry.entry_id,
                    target_id=f"{provider.provider_id}.{entry.entry_id}",
                    label=f"{provider.provider_label} {entry.entry_label}",
                    url=entry.endpoint,
                )
            )
    return targets


def _empty_probe_result(target: ProbeTarget) -> dict:
    payload = asdict(target)
    payload.update(
        {
            "checked_at": None,
            "method": None,
            "reachable": None,
            "healthy": None,
            "status_code": None,
            "detail": None,
        }
    )
    return payload


def _probe_target(target: ProbeTarget, *, timeout_seconds: int) -> dict:
    last_error: str | None = None
    for method in ("HEAD", "GET"):
        try:
            response = httpx.request(
                method,
                target.url,
                timeout=timeout_seconds,
                follow_redirects=True,
            )
            payload = asdict(target)
            payload.update(
                {
                    "checked_at": _utc_now(),
                    "method": method,
                    "reachable": True,
                    "healthy": response.status_code < 500,
                    "status_code": response.status_code,
                    "detail": f"HTTP {response.status_code}",
                }
            )
            return payload
        except httpx.TimeoutException:
            last_error = f"{method} timeout"
        except httpx.HTTPError as exc:
            last_error = f"{method} {exc.__class__.__name__}: {exc}"

    payload = asdict(target)
    payload.update(
        {
            "checked_at": _utc_now(),
            "method": "GET",
            "reachable": False,
            "healthy": False,
            "status_code": None,
            "detail": last_error or "unreachable",
        }
    )
    return payload


def run_probe_once(
    settings: Settings | None = None,
    provider_id: str | None = None,
) -> dict:
    current = settings or get_settings()
    all_targets = build_probe_targets(current)
    normalized_provider_id = str(provider_id or "").strip()
    probe_targets = build_probe_targets(current, normalized_provider_id) if normalized_provider_id else all_targets

    existing_state = load_state()
    existing_map = {
        item.get("target_id"): item
        for item in existing_state.get("targets", [])
        if isinstance(item, dict) and item.get("target_id")
    }
    current_target_ids = {target.target_id for target in all_targets}
    merged_map = {
        target_id: payload
        for target_id, payload in existing_map.items()
        if target_id in current_target_ids
    }

    results = [
        _probe_target(
            target,
            timeout_seconds=current.provider_connectivity_check_timeout_seconds,
        )
        for target in probe_targets
    ]
    for item in results:
        merged_map[item["target_id"]] = item

    ordered_results = [
        merged_map.get(target.target_id, _empty_probe_result(target))
        for target in all_targets
    ]
    state = {
        "updated_at": _utc_now(),
        "enabled": current.provider_connectivity_check_enabled,
        "interval_seconds": current.provider_connectivity_check_interval_seconds,
        "timeout_seconds": current.provider_connectivity_check_timeout_seconds,
        "targets": ordered_results,
    }
    with _STATE_LOCK:
        _save_state(state)

    unhealthy = [item["label"] for item in results if item.get("healthy") is False]
    if unhealthy:
        logger.warning("Provider connectivity probe found unhealthy targets: %s", unhealthy)
    else:
        logger.info("Provider connectivity probe passed for %s targets.", len(results))
    return state


class ProviderConnectivityMonitor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if not self._settings.provider_connectivity_check_enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run,
            daemon=True,
            name="provider-connectivity-monitor",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                run_probe_once(self._settings)
            except Exception:  # pragma: no cover
                logger.exception("Provider connectivity probe failed unexpectedly.")
            if self._stop_event.wait(self._settings.provider_connectivity_check_interval_seconds):
                break
