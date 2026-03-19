from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

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


def _build_app(tmp_path):
    os.environ["USE_MOCK_GENERATOR"] = "true"
    os.environ["ALLOW_DEV_LOGIN"] = "true"
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

    prompt = templates.build_prompt(hairstyle, scene)

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
