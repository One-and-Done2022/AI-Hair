from __future__ import annotations

import sys
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _configure_probe_env(tmp_path, monkeypatch) -> None:
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("DATABASE_PATH", str(storage_dir / "app.db"))
    monkeypatch.setenv("USE_MOCK_GENERATOR", "true")
    monkeypatch.setenv("ARK_API_KEYS", "seed:test-seed-key")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example.test/api/v3")
    monkeypatch.setenv("SEEDREAM_BASIC_MODEL", "doubao-seedream-4-5-251128")
    monkeypatch.setenv("SEEDREAM_PREMIUM_MODEL", "doubao-seedream-5-0-260128")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")
    monkeypatch.setenv("NANO_BANANA_2_API_KEY", "nano-2-key")
    monkeypatch.setenv("NANO_BANANA_2_BASE_URL", "https://nano2.example.test")
    monkeypatch.setenv("SORA_IMAGE_API_KEY", "sora-key")
    monkeypatch.setenv("SORA_IMAGE_BASE_URL", "https://sora.example.test/v1")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "understanding-key")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_BASE_URL", "https://understanding.example.test/v1")
    monkeypatch.setenv("PROVIDER_CONNECTIVITY_CHECK_ENABLED", "true")
    monkeypatch.setenv("PROVIDER_CONNECTIVITY_CHECK_INTERVAL_SECONDS", "300")
    monkeypatch.setenv("PROVIDER_CONNECTIVITY_CHECK_TIMEOUT_SECONDS", "5")


def _clear_probe_runtime_caches() -> None:
    from app.config import get_settings

    get_settings.cache_clear()


def test_build_probe_targets_covers_all_configured_entries(tmp_path, monkeypatch):
    _configure_probe_env(tmp_path, monkeypatch)
    _clear_probe_runtime_caches()

    from app.services import provider_connectivity

    targets = provider_connectivity.build_probe_targets()

    assert [target.target_id for target in targets] == [
        "seedream.basic",
        "seedream.premium",
        "nano_banana_pro.route2",
        "nano_banana_pro.route1",
        "nano_banana_pro.primary",
        "nano_banana_2.primary",
        "image_understanding.primary",
    ]


def test_run_probe_once_treats_non_5xx_http_as_healthy(tmp_path, monkeypatch):
    _configure_probe_env(tmp_path, monkeypatch)
    _clear_probe_runtime_caches()

    from app.services import provider_connectivity

    calls = []

    def fake_request(method, url, *, timeout=None, follow_redirects=None):
        calls.append((method, url, timeout, follow_redirects))
        return httpx.Response(
            405,
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr("app.services.provider_connectivity.httpx.request", fake_request)

    state = provider_connectivity.run_probe_once()

    assert len(state["targets"]) == 7
    assert all(item["healthy"] is True for item in state["targets"])
    assert all(item["reachable"] is True for item in state["targets"])
    assert all(item["detail"] == "HTTP 405" for item in state["targets"])
    assert calls
    assert all(call[0] == "HEAD" for call in calls)


def test_run_probe_once_single_provider_merges_existing_state(tmp_path, monkeypatch):
    _configure_probe_env(tmp_path, monkeypatch)
    _clear_probe_runtime_caches()

    from app.config import get_settings
    from app.services import provider_connectivity

    settings = get_settings()
    settings.ensure_directories()
    state_path = settings.storage_dir / "provider_connectivity.json"
    state_path.write_text(
        """{
  \"updated_at\": \"2026-04-11T10:00:00+00:00\",
  \"targets\": [
    {
      \"provider_id\": \"seedream\",
      \"entry_id\": \"basic\",
      \"target_id\": \"seedream.basic\",
      \"label\": \"Seedream / Ark 基础模型\",
      \"url\": \"https://ark.example.test/api/v3/images/generations\",
      \"checked_at\": \"2026-04-11T10:00:00+00:00\",
      \"method\": \"HEAD\",
      \"reachable\": true,
      \"healthy\": true,
      \"status_code\": 401,
      \"detail\": \"HTTP 401\"
    }
  ]
}""",
        encoding="utf-8",
    )

    def fake_request(method, url, *, timeout=None, follow_redirects=None):
        if "chat.example.test" in url:
            raise httpx.TimeoutException("probe timeout")
        status_code = 500 if "backup.example.test" in url else 401
        return httpx.Response(
            status_code,
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr("app.services.provider_connectivity.httpx.request", fake_request)

    state = provider_connectivity.run_probe_once(provider_id="nano_banana_pro")

    assert len(state["targets"]) == 7
    seedream_basic = next(item for item in state["targets"] if item["target_id"] == "seedream.basic")
    route2 = next(item for item in state["targets"] if item["target_id"] == "nano_banana_pro.route2")
    route1 = next(item for item in state["targets"] if item["target_id"] == "nano_banana_pro.route1")

    assert seedream_basic["detail"] == "HTTP 401"
    assert seedream_basic["checked_at"] == "2026-04-11T10:00:00+00:00"
    assert route2["healthy"] is False
    assert route2["reachable"] is False
    assert "timeout" in route2["detail"]
    assert route1["healthy"] is False
    assert route1["status_code"] == 500
