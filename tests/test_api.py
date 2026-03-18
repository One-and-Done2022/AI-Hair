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


def test_build_prompt_uses_single_image_stable_structure():
    from app.services import templates

    hairstyle = templates.get_hairstyle("american-spiky")
    scene = templates.get_scene("lifestyle-interior")

    assert hairstyle is not None
    assert scene is not None

    prompt = templates.build_prompt(hairstyle, scene)

    assert "生成 1 张高相似度、写实风格的人像写真" in prompt
    assert "严格保留参考人物的真实身份特征" in prompt
    assert "微微歪头，一只手自然轻触头发" in prompt
    assert "白色宽松衬衫" in prompt
    assert "人物发型改为美式前刺" in prompt
    assert "背景替换为室内生活感空间" in prompt
    assert "负向约束：" in prompt


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

        history = client.get("/api/history", headers=headers)
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) == 1
        assert items[0]["job_id"] == job_id
