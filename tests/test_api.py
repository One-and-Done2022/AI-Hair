from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

import pytest
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


def _build_app(tmp_path):
    os.environ["USE_MOCK_GENERATOR"] = "true"
    os.environ["ALLOW_DEV_LOGIN"] = "true"
    os.environ["ENFORCE_FACE_DETECTION"] = "false"
    os.environ["STORAGE_DIR"] = str(tmp_path / "storage")
    os.environ["DATABASE_PATH"] = str(tmp_path / "storage" / "app.db")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    return create_app()


def test_build_prompt_uses_faceprompt_single_image_structure():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("indoor-film-lifestyle")

    assert hairstyle is not None
    assert scene is not None

    prompt = templates.build_prompt(hairstyle, scene, seed_source="prompt-structure")

    assert "生成 1 张高相似度、写实风格的人像写真" in prompt
    assert "忽略原照片中的背景、原服饰、原发型和原有动作" in prompt
    assert "只输出 1 张完整成片" in prompt
    assert "胡桃木门框" in prompt
    assert "发型改为前刺头" in prompt
    assert "白色宽松衬衫" in prompt
    assert "不要拼图排版" in prompt
    assert "图片需要符合物理逻辑" in prompt
    assert "不可以有不符合物理逻辑的身体部位" in prompt
    assert "只选择 1 种主体动作" in prompt
    assert "不要与主体动作叠加成不合理肢体效果" in prompt
    assert "后端每次只选 1 个主体动作" in prompt


def test_prompt_filters_hand_conflicting_hairstyle_actions():
    from app.services import templates

    compatible_actions = templates._filter_compatible_hairstyle_actions(
        "双手轻握杯子停顿",
        ["看镜头微抬下巴", "单手抓起头顶前区发束", "半侧脸回望镜头"],
    )

    assert compatible_actions == ["看镜头微抬下巴", "半侧脸回望镜头"]


def test_build_prompt_uses_one_subject_action_and_one_compatible_detail_action():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("morning-window-softlight")

    assert hairstyle is not None
    assert scene is not None

    prompt = templates.build_prompt(hairstyle, scene, seed_source="hand-conflict-scene")

    assert "靠在窗台边；抬手整理窗边发丝；双手轻握杯子停顿" not in prompt
    assert "人物动作：单张图中只选择 1 种主体动作，本张图固定为：" in prompt
    assert "单手抓起头顶前区发束" not in prompt
    assert "双手抓起顶部卷度" not in prompt


def test_faceprompt_catalog_counts_and_legacy_aliases():
    from app.services import templates

    assert len(templates.SCENES) == 20
    assert len(templates.HAIRSTYLES) == 40
    assert len([item for item in templates.HAIRSTYLES if item["gender"] == "male"]) == 20
    assert len([item for item in templates.HAIRSTYLES if item["gender"] == "female"]) == 20

    assert templates.get_hairstyle("american-spiky")["id"] == "male-forward-spikes"
    assert templates.get_scene("lifestyle-interior")["id"] == "indoor-film-lifestyle"


def test_auth_upload_job_history_flow(tmp_path):
    app = _build_app(tmp_path)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        assert login.status_code == 200
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("portrait.png", _build_test_image(), "image/png")},
        )
        assert upload.status_code == 200
        upload_id = upload.json()["upload_id"]

        templates = client.get("/api/templates")
        assert templates.status_code == 200
        catalog = templates.json()
        assert len(catalog["hairstyles"]) == 40
        assert len(catalog["scenes"]) == 20
        assert len([item for item in catalog["hairstyles"] if item["gender"] == "male"]) == 20
        assert len([item for item in catalog["hairstyles"] if item["gender"] == "female"]) == 20
        assert catalog["hairstyles"][0]["style_line_label"]

        job_create = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": catalog["hairstyles"][0]["id"],
                "scene_id": catalog["scenes"][0]["id"],
            },
        )
        assert job_create.status_code == 201
        job_id = job_create.json()["job_id"]

        status_payload = None
        for _ in range(30):
            job_detail = client.get(f"/api/jobs/{job_id}", headers=headers)
            assert job_detail.status_code == 200
            status_payload = job_detail.json()
            if status_payload["status"] == "succeeded":
                break
            time.sleep(0.1)

        assert status_payload is not None
        assert status_payload["status"] == "succeeded"
        assert status_payload["result_image_url"]
        assert len(status_payload["result_image_urls"]) == 3
        assert status_payload["result_image_urls"][0] == status_payload["result_image_url"]

        history = client.get("/api/history", headers=headers)
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) == 1
        assert items[0]["job_id"] == job_id
        assert len(items[0]["result_image_urls"]) == 3


def test_job_exposes_preview_before_final_result(tmp_path, monkeypatch):
    os.environ["USE_MOCK_GENERATOR"] = "false"
    os.environ["ALLOW_DEV_LOGIN"] = "true"
    os.environ["ENFORCE_FACE_DETECTION"] = "false"
    os.environ["STORAGE_DIR"] = str(tmp_path / "storage")
    os.environ["DATABASE_PATH"] = str(tmp_path / "storage" / "app.db")

    from app.config import get_settings
    from app.main import create_app
    import app.main as app_main
    from app.services.generation import GenerationResult

    class SlowPreviewGenerator:
        model_name = "slow-preview-generator"

        def generate(self, source_image_path, prompt, context, on_preview=None):
            first = _build_colored_image("#264653")
            second = _build_colored_image("#2a9d8f")
            third = _build_colored_image("#e9c46a")
            if on_preview is not None:
                on_preview(first)
            time.sleep(0.45)
            return GenerationResult(
                primary_image_bytes=first,
                candidate_image_bytes=[first, second, third],
            )

    get_settings.cache_clear()
    monkeypatch.setattr(app_main, "build_generator", lambda: SlowPreviewGenerator())
    app = create_app()

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("portrait.png", _build_test_image(), "image/png")},
        )
        upload_id = upload.json()["upload_id"]

        catalog = client.get("/api/templates").json()
        job_create = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": catalog["hairstyles"][0]["id"],
                "scene_id": catalog["scenes"][0]["id"],
            },
        )
        job_id = job_create.json()["job_id"]

        preview_payload = None
        for _ in range(20):
            job_detail = client.get(f"/api/jobs/{job_id}", headers=headers)
            assert job_detail.status_code == 200
            payload = job_detail.json()
            if payload["status"] == "preview_ready":
                preview_payload = payload
                break
            time.sleep(0.05)

        assert preview_payload is not None
        assert preview_payload["result_image_url"]
        assert len(preview_payload["result_image_urls"]) == 1
        assert preview_payload["result_image_urls"][0] == preview_payload["result_image_url"]

        final_payload = None
        for _ in range(20):
            job_detail = client.get(f"/api/jobs/{job_id}", headers=headers)
            assert job_detail.status_code == 200
            payload = job_detail.json()
            if payload["status"] == "succeeded":
                final_payload = payload
                break
            time.sleep(0.05)

        assert final_payload is not None
        assert len(final_payload["result_image_urls"]) == 3
        assert final_payload["result_image_urls"][0] == final_payload["result_image_url"]


def test_seedream_generator_requests_preview_first_then_tops_up(tmp_path, monkeypatch):
    os.environ["ARK_API_KEY"] = "test-key"

    from app.config import get_settings
    from app.services.generation import SeedreamGenerator

    get_settings.cache_clear()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    generator = SeedreamGenerator()
    preview_image = _build_colored_image("#264653")
    second_image = _build_colored_image("#2a9d8f")
    third_image = _build_colored_image("#e9c46a")
    call_log = []
    preview_events = []

    def fake_collect(self, *, prompt, image_data, max_images, on_first_candidate=None):
        call_log.append(("collect", max_images))
        if on_first_candidate is not None:
            on_first_candidate(preview_image)
            preview_events.append("preview")
        return [preview_image]

    def fake_top_up(self, *, prompt, image_data, existing_count, on_first_candidate=None):
        call_log.append(("top_up", existing_count))
        return [second_image, third_image]

    monkeypatch.setattr(SeedreamGenerator, "_collect_stream_candidates", fake_collect)
    monkeypatch.setattr(SeedreamGenerator, "_top_up_candidates", fake_top_up)

    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test prompt",
        context=None,
        on_preview=lambda image_bytes: preview_events.append("callback"),
    )

    assert call_log == [("collect", 1), ("top_up", 1)]
    assert preview_events == ["callback", "preview"]
    assert len(result.candidate_image_bytes) == 3


def test_strict_face_detection_rejects_small_face(monkeypatch):
    os.environ["ENFORCE_FACE_DETECTION"] = "true"

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "_detect_faces", lambda _: ((0, 0, 60, 60),))

    with pytest.raises(storage.UploadValidationError) as excinfo:
        storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert excinfo.value.code == "face_too_small"


def test_strict_face_detection_accepts_single_clear_face(monkeypatch):
    os.environ["ENFORCE_FACE_DETECTION"] = "true"

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "_detect_faces", lambda _: ((120, 140, 180, 220),))

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024
