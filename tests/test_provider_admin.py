from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import httpx
from PIL import Image
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _build_test_image() -> bytes:
    image = Image.new("RGB", (768, 1024), "#8ecae6")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_colored_image(color: str) -> bytes:
    image = Image.new("RGB", (768, 1024), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _configure_runtime_env(tmp_path, monkeypatch, *, use_mock_generator: str = "true") -> None:
    monkeypatch.setenv("USE_MOCK_GENERATOR", use_mock_generator)
    monkeypatch.setenv("ALLOW_DEV_LOGIN", "true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "false")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "storage" / "app.db"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'storage' / 'app.db').resolve()}")
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "local")
    monkeypatch.setenv("RUN_EMBEDDED_WORKER", "true")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "nano_banana_pro")
    monkeypatch.setenv("ARK_API_KEYS", "seed-a:alpha,seed-b:beta")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example.test/api/v3")
    monkeypatch.setenv("SEEDREAM_BASIC_MODEL", "doubao-seedream-4-5-251128")
    monkeypatch.setenv("SEEDREAM_PREMIUM_MODEL", "doubao-seedream-5-0-260128")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_MODEL", "Nano_Banana_Pro_2K_1")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")
    monkeypatch.setenv("NANO_BANANA_2_API_KEY", "nano-2-key")
    monkeypatch.setenv("NANO_BANANA_2_BASE_URL", "https://nano2.example.test")
    monkeypatch.setenv("NANO_BANANA_2_MODEL", "gemini-2.5-flash-image-preview")
    monkeypatch.setenv("SORA_IMAGE_API_KEY", "sora-key")
    monkeypatch.setenv("SORA_IMAGE_BASE_URL", "https://sora.example.test/v1")
    monkeypatch.setenv("SORA_IMAGE_MODEL", "sora_image")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "understanding-key")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_BASE_URL", "https://understanding.example.test/v1")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_MODEL", "gemini-3-pro-preview")


def _clear_runtime_caches() -> None:
    from app.config import get_settings
    from app.db import get_engine, get_session_factory
    from app.services import generation
    from app.services.storage import get_object_storage

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_object_storage.cache_clear()
    generation._PROVIDER_BACKOFF_UNTIL.clear()


def _create_authed_client(tmp_path, monkeypatch, *, use_mock_generator: str = "true"):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator=use_mock_generator)
    _clear_runtime_caches()

    from app.config import get_settings
    from app.db import init_db
    from app.main import create_app
    from app.services import repository

    settings = get_settings()
    settings.ensure_directories()
    init_db()
    user = repository.get_or_create_user("provider-admin-user")
    token = repository.create_auth_token(user["id"])
    client = TestClient(create_app())
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def test_provider_admin_dashboard_lists_all_groups(tmp_path, monkeypatch):
    client, headers = _create_authed_client(tmp_path, monkeypatch, use_mock_generator="true")

    with client:
        page = client.get("/provider-admin")
        assert page.status_code == 200
        assert "多 Provider 统一管理台" in page.text

        response = client.get("/api/provider-admin/providers", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["provider_count"] == 4
        assert [item["provider_id"] for item in payload["providers"]] == [
            "seedream",
            "nano_banana_pro",
            "nano_banana_2",
            "image_understanding",
        ]

        seedream = next(item for item in payload["providers"] if item["provider_id"] == "seedream")
        assert seedream["entries"][0]["console_url"] == "https://console.volcengine.com/auth/login/"

        nano_pro = next(item for item in payload["providers"] if item["provider_id"] == "nano_banana_pro")
        assert [entry["entry_id"] for entry in nano_pro["entries"]] == ["route2", "route1", "primary"]
        route2 = next(entry for entry in nano_pro["entries"] if entry["entry_id"] == "route2")
        assert route2["console_url"] == "https://xais.dchai.cn/"
        assert route2["docs_url"] == "https://my.feishu.cn/wiki/AdrXwbi7HikISik5vh6c8NhOnFd"

        legacy = client.get("/api/provider-admin/nano-pro", headers=headers)
        assert legacy.status_code == 200
        legacy_payload = legacy.json()
        assert [item["profile_id"] for item in legacy_payload["profiles"]] == ["route2", "route1", "primary"]


def test_provider_admin_order_endpoint_updates_nano_banana_pro(tmp_path, monkeypatch):
    client, headers = _create_authed_client(tmp_path, monkeypatch, use_mock_generator="true")

    from app.services import provider_routing

    with client:
        response = client.put(
            "/api/provider-admin/providers/nano_banana_pro/order",
            headers=headers,
            json={
                "items": [
                    {"entry_id": "primary", "enabled": True},
                    {"entry_id": "route2", "enabled": True},
                    {"entry_id": "route1", "enabled": False},
                ]
            },
        )
        assert response.status_code == 200
        payload = response.json()
        nano_pro = next(item for item in payload["providers"] if item["provider_id"] == "nano_banana_pro")
        assert [entry["entry_id"] for entry in nano_pro["entries"]] == ["primary", "route2", "route1"]
        assert nano_pro["entries"][2]["enabled"] is False

    state = provider_routing.get_provider_state("nano_banana_pro")
    assert [item["entry_id"] for item in state["entries"]] == ["primary", "route2", "route1"]


def test_nano_banana_pro_generator_respects_runtime_priority(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    _clear_runtime_caches()

    from app.services import provider_routing
    from app.services.generation import GenerationContext, NanoBananaProGenerator

    provider_routing.update_provider_entries(
        "nano_banana_pro",
        [
            {"entry_id": "primary", "enabled": True},
            {"entry_id": "route2", "enabled": True},
            {"entry_id": "route1", "enabled": False},
        ],
    )

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())
    request_log = []

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "timeout": timeout})
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": base64.b64encode(_build_colored_image("#264653")).decode("utf-8"),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.services.generation.httpx.post", fake_post)

    generator = NanoBananaProGenerator()
    result = generator.generate(
        source_image_path=str(source_path),
        prompt="runtime routing test",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="1K",
        ),
    )

    assert result.primary_image_bytes
    assert len(request_log) == 1
    assert request_log[0]["url"].startswith("https://primary.example.test")
    assert request_log[0]["headers"]["Authorization"] == "Bearer primary-key"


def test_nano_banana_2_disabled_returns_provider_disabled(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    _clear_runtime_caches()

    from app.services import provider_routing
    from app.services.generation import GenerationContext, ImageGenerationError, NanoBanana2Generator

    provider_routing.update_provider_entries(
        "nano_banana_2",
        [{"entry_id": "primary", "enabled": False}],
    )

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())
    generator = NanoBanana2Generator()

    try:
        generator.generate(
            source_image_path=str(source_path),
            prompt="disabled test",
            context=GenerationContext(
                hairstyle_name="前刺短发",
                scene_name="窗边生活感",
            ),
        )
        assert False, "expected provider disabled error"
    except ImageGenerationError as exc:
        assert exc.code == "provider_disabled"


def test_provider_admin_probe_endpoint_returns_dashboard_state(tmp_path, monkeypatch):
    client, headers = _create_authed_client(tmp_path, monkeypatch, use_mock_generator="true")

    fake_state = {
        "updated_at": "2026-04-11T10:00:00+00:00",
        "targets": [
            {
                "target_id": "nano_banana_pro.route2",
                "checked_at": "2026-04-11T10:00:00+00:00",
                "reachable": False,
                "healthy": False,
                "status_code": None,
                "detail": "GET timeout",
            },
            {
                "target_id": "nano_banana_pro.route1",
                "checked_at": "2026-04-11T10:00:00+00:00",
                "reachable": True,
                "healthy": True,
                "status_code": 200,
                "detail": "HTTP 200",
            },
        ],
    }

    monkeypatch.setattr("app.services.provider_connectivity.run_probe_once", lambda settings=None, provider_id=None: fake_state)
    monkeypatch.setattr("app.services.provider_connectivity.load_state", lambda: fake_state)

    with client:
        response = client.post("/api/provider-admin/providers/probe", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["connectivity_updated_at"] == "2026-04-11T10:00:00+00:00"
        nano_pro = next(item for item in payload["providers"] if item["provider_id"] == "nano_banana_pro")
        route2 = next(item for item in nano_pro["entries"] if item["entry_id"] == "route2")
        assert route2["probe"]["healthy"] is False
        assert route2["status"] == "unavailable"


def test_provider_admin_image_understanding_test_endpoint_records_result(tmp_path, monkeypatch):
    client, headers = _create_authed_client(tmp_path, monkeypatch, use_mock_generator="true")

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    from app.services import provider_routing
    from app.services.image_understanding import SceneUnderstandingResult

    def fake_extract_scene_blocks(self, image_bytes, *, enforce_enabled=True):
        assert enforce_enabled is False
        return SceneUnderstandingResult(
            blocks={
                "shot": "半身近景",
                "scene_environment": "室内窗边",
                "scene_lighting": "自然软光",
                "scene_mood": "安静松弛",
                "expression": "自然微笑",
                "subject_action": "轻微侧身",
                "makeup": "清透淡妆",
                "outfit": "浅色针织上衣",
                "styling_constraints": "避免夸张配饰",
                "scene_constraints": "保留窗边柔和层次",
            },
            raw_response="{}",
            model_name="gemini-3-pro-preview",
            subject_gender="male",
        )

    monkeypatch.setattr("app.routers.provider_admin._resolve_test_source_image_path", lambda: source_path)
    monkeypatch.setattr(
        "app.services.image_understanding.ImageUnderstandingService.extract_scene_blocks",
        fake_extract_scene_blocks,
    )

    with client:
        response = client.post(
            "/api/provider-admin/providers/image_understanding/entries/primary/test",
            headers=headers,
            json={"entry_id": "primary", "aspect_ratio": "3:4", "resolution": "2K"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert "主体性别" in payload["summary"]

    state = provider_routing.get_provider_state("image_understanding")
    assert state["last_test_results"]["primary"]["success"] is True
    assert "主体性别" in state["last_test_results"]["primary"]["summary"]
