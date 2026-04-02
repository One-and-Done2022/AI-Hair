from __future__ import annotations

import httpx


def _configure_probe_env(tmp_path, monkeypatch) -> None:
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("DATABASE_PATH", str(storage_dir / "app.db"))
    monkeypatch.setenv("USE_MOCK_GENERATOR", "true")
    monkeypatch.setenv("ARK_API_KEYS", "seed:test-seed-key")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example.test/api/v3")
    monkeypatch.setenv("SEEDREAM_BASIC_MODEL", "doubao-seedream-4-5-251128")
    monkeypatch.setenv("SEEDREAM_PREMIUM_MODEL", "doubao-seedream-4-5-251128")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
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

    assert state["targets"]
    assert all(item["healthy"] is True for item in state["targets"])
    assert all(item["reachable"] is True for item in state["targets"])
    assert all(item["detail"] == "HTTP 405" for item in state["targets"])
    assert calls
    assert all(call[0] == "HEAD" for call in calls)


def test_run_probe_once_marks_timeout_unhealthy_and_persists_state(tmp_path, monkeypatch):
    _configure_probe_env(tmp_path, monkeypatch)
    _clear_probe_runtime_caches()

    from app.config import get_settings
    from app.services import provider_connectivity

    def fake_request(method, url, *, timeout=None, follow_redirects=None):
        if "chat.example.test" in url:
            raise httpx.TimeoutException("probe timeout")
        return httpx.Response(
            401,
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr("app.services.provider_connectivity.httpx.request", fake_request)

    state = provider_connectivity.run_probe_once()

    timeout_target = next(
        item for item in state["targets"] if item["target_id"] == "nano_banana_pro.route2"
    )
    assert timeout_target["healthy"] is False
    assert timeout_target["reachable"] is False
    assert "timeout" in timeout_target["detail"]

    loaded = provider_connectivity.load_state()
    assert loaded["updated_at"] == state["updated_at"]
    assert len(loaded["targets"]) == len(state["targets"])

    settings = get_settings()
    assert (settings.storage_dir / "provider_connectivity.json").exists()

