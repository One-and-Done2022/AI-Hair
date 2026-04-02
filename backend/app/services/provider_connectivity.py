from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

import httpx

from app.config import Settings, get_settings


logger = logging.getLogger(__name__)
_STATE_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class ProbeTarget:
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
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "updated_at": None,
            "targets": [],
        }


def _probe_endpoint(base_url: str, protocol: str, model_name: str) -> str:
    normalized = base_url.rstrip("/")
    if protocol == "openai_chat_markdown":
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"
    if protocol == "gemini_v1beta":
        return f"{normalized}/v1beta/models/{model_name}:generateContent"
    return normalized


def build_probe_targets(settings: Settings | None = None) -> list[ProbeTarget]:
    current = settings or get_settings()
    targets: list[ProbeTarget] = []

    if current.ark_base_url.strip():
        targets.append(
            ProbeTarget(
                target_id="seedream",
                label=f"Seedream {current.seedream_basic_model}",
                url=f"{current.ark_base_url.rstrip('/')}/images/generations",
            )
        )

    for profile_id, profile_label, base_url, _api_key, protocol, model_name in current.nano_banana_pro_profiles():
        targets.append(
            ProbeTarget(
                target_id=f"nano_banana_pro.{profile_id}",
                label=f"Nano Banana Pro {profile_label}",
                url=_probe_endpoint(base_url, protocol, model_name),
            )
        )

    if current.nano_banana_2_api_key.strip() and current.nano_banana_2_base_url.strip():
        targets.append(
            ProbeTarget(
                target_id="nano_banana_2.primary",
                label="Nano Banana 2 主线路",
                url=_probe_endpoint(
                    current.nano_banana_2_base_url,
                    "gemini_v1beta",
                    current.nano_banana_2_model,
                ),
            )
        )

    if current.sora_image_api_key.strip() and current.sora_image_base_url.strip():
        targets.append(
            ProbeTarget(
                target_id="sora_image.primary",
                label="Sora Image 主线路",
                url=f"{current.sora_image_base_url.rstrip('/')}/chat/completions",
            )
        )

    if (
        current.image_understanding_api_key.strip()
        and current.image_understanding_base_url.strip()
    ):
        targets.append(
            ProbeTarget(
                target_id="image_understanding.primary",
                label="图片理解主线路",
                url=f"{current.image_understanding_base_url.rstrip('/')}/chat/completions",
            )
        )

    return targets


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
            return {
                "target_id": target.target_id,
                "label": target.label,
                "url": target.url,
                "checked_at": _utc_now(),
                "method": method,
                "reachable": True,
                "healthy": response.status_code < 500,
                "status_code": response.status_code,
                "detail": f"HTTP {response.status_code}",
            }
        except httpx.TimeoutException:
            last_error = f"{method} timeout"
        except httpx.HTTPError as exc:
            last_error = f"{method} {exc.__class__.__name__}: {exc}"

    return {
        "target_id": target.target_id,
        "label": target.label,
        "url": target.url,
        "checked_at": _utc_now(),
        "method": "GET",
        "reachable": False,
        "healthy": False,
        "status_code": None,
        "detail": last_error or "unreachable",
    }


def run_probe_once(settings: Settings | None = None) -> dict:
    current = settings or get_settings()
    targets = build_probe_targets(current)
    results = [
        _probe_target(
            target,
            timeout_seconds=current.provider_connectivity_check_timeout_seconds,
        )
        for target in targets
    ]
    state = {
        "updated_at": _utc_now(),
        "enabled": current.provider_connectivity_check_enabled,
        "interval_seconds": current.provider_connectivity_check_interval_seconds,
        "timeout_seconds": current.provider_connectivity_check_timeout_seconds,
        "targets": results,
    }
    with _STATE_LOCK:
        _save_state(state)
    unhealthy = [item["label"] for item in results if not item["healthy"]]
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

