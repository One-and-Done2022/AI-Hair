from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _build_test_image() -> bytes:
    image = Image.new("RGB", (768, 1024), "#ffd6e0")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _configure_runtime_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_GENERATOR", "true")
    monkeypatch.setenv("ALLOW_DEV_LOGIN", "true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "false")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "storage" / "app.db"))
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{(tmp_path / 'storage' / 'app.db').resolve()}",
    )
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "local")
    monkeypatch.setenv("RUN_EMBEDDED_WORKER", "true")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")


def _clear_runtime_caches() -> None:
    from app.config import get_settings
    from app.db import get_engine, get_session_factory
    from app.services.storage import get_object_storage

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_object_storage.cache_clear()


def test_image_understanding_settings_use_gemini_defaults(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch)
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "vision-test-key")
    _clear_runtime_caches()

    from app.config import get_settings

    settings = get_settings()

    assert settings.image_understanding_api_key == "vision-test-key"
    assert settings.image_understanding_base_url == "https://api.apiyi.com/v1"
    assert settings.image_understanding_model == "gemini-3-pro-preview"
    assert settings.image_understanding_timeout_seconds == 120


def test_image_understanding_service_uses_configured_model(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch)
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "vision-test-key")
    _clear_runtime_caches()

    request_log: dict[str, object] = {}

    def fake_create(*, model, temperature, messages):
        request_log["model"] = model
        request_log["temperature"] = temperature
        request_log["messages"] = messages
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"shot":"3:4 竖构图，胸口以上近景，平视镜头。",'
                            '"scene_environment":"室内留白墙面与木质家具背景。",'
                            '"scene_lighting":"窗边柔和自然光从侧前方进入。",'
                            '"scene_mood":"安静、克制、松弛。",'
                            '"expression":"温和看向镜头。",'
                            '"subject_action":"靠坐在椅子上轻微侧身。",'
                            '"outfit":"米白色针织上衣。",'
                            '"scene_constraints":"背景保持简洁留白，不要加入复杂前景。"}'
                        )
                    )
                )
            ]
        )

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url, timeout):
            request_log["api_key"] = api_key
            request_log["base_url"] = base_url
            request_log["timeout"] = timeout
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=fake_create)
            )

    monkeypatch.setattr("app.services.image_understanding.OpenAI", FakeOpenAI)

    from app.services.image_understanding import ImageUnderstandingService

    result = ImageUnderstandingService().extract_scene_blocks(_build_test_image())

    assert request_log["api_key"] == "vision-test-key"
    assert request_log["base_url"] == "https://api.apiyi.com/v1"
    assert request_log["timeout"] == 120
    assert request_log["model"] == "gemini-3-pro-preview"
    messages = request_log["messages"]
    assert isinstance(messages, list)
    assert messages[1]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert result.blocks["scene_environment"] == "室内留白墙面与木质家具背景。"
    assert result.model_name == "gemini-3-pro-preview"


def test_build_scene_draft_returns_valid_scene_json_shape():
    from app.services.image_understanding import build_scene_draft

    draft = build_scene_draft(
        {
            "shot": "3:4 竖构图，胸口以上近景，平视镜头。",
            "scene_environment": "室内留白墙面与木质家具背景，窗边区域干净克制。",
            "scene_lighting": "窗边柔和自然光从侧前方进入，整体亮部通透。",
            "scene_mood": "安静、松弛、生活感高级。",
            "expression": "温和看向镜头；轻微放空。",
            "subject_action": "靠坐在椅子上轻微侧身。",
            "outfit": "米白色针织上衣。",
            "scene_constraints": "背景保持简洁留白；不要加入复杂前景。",
        }
    )

    assert draft["styleLine"] == "realistic_editorial"
    assert draft["id"].startswith("window-softlight-")
    assert draft["detailTags"]
    assert draft["pairingAdvice"]
    assert draft["controlProfile"]["windLevel"] == "still"
    assert draft["controlProfile"]["lightingHardness"] == "soft"
    assert draft["referenceSourceIds"] == ["scene-understanding-api"]
