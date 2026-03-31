from __future__ import annotations

import base64
import io
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import update


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
    monkeypatch.delenv("ARK_API_KEYS", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY_ID", raising=False)
    monkeypatch.delenv("ARK_API_KEY_MAX_CONCURRENCY", raising=False)
    monkeypatch.delenv("ARK_API_KEY_DEFAULT_WEIGHT", raising=False)
    monkeypatch.delenv("ARK_API_KEY_COOLDOWN_SECONDS", raising=False)
    monkeypatch.delenv("SEEDREAM_BASIC_MODEL", raising=False)
    monkeypatch.delenv("SEEDREAM_PREMIUM_MODEL", raising=False)
    monkeypatch.delenv("IMAGE_GENERATOR_BACKEND", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_API_KEY", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_BASE_URL", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_MODEL", raising=False)
    monkeypatch.delenv("NANO_BANANA_2_API_KEY", raising=False)
    monkeypatch.delenv("NANO_BANANA_2_BASE_URL", raising=False)
    monkeypatch.delenv("NANO_BANANA_2_MODEL", raising=False)
    monkeypatch.delenv("SORA_IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("SORA_IMAGE_BASE_URL", raising=False)
    monkeypatch.delenv("SORA_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("JOB_WORKER_CONCURRENCY", raising=False)
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    monkeypatch.delenv("DB_POOL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DB_POOL_RECYCLE_SECONDS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_QUEUE_KEY", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("OSS_ENDPOINT", raising=False)
    monkeypatch.delenv("OSS_BUCKET_NAME", raising=False)
    monkeypatch.delenv("OSS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("OSS_ACCESS_KEY_SECRET", raising=False)
    monkeypatch.delenv("OSS_PREFIX", raising=False)


def _clear_runtime_caches() -> None:
    from app.config import get_settings
    from app.db import get_engine, get_session_factory
    from app.services.storage import get_object_storage

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_object_storage.cache_clear()


def _build_app(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    _clear_runtime_caches()

    from app.main import create_app

    return create_app()


def _create_job_fixture(tmp_path, monkeypatch, *, ark_api_keys: str | None = None) -> dict:
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    if ark_api_keys is not None:
        monkeypatch.setenv("ARK_API_KEYS", ark_api_keys)

    from app.config import get_settings
    from app.db import init_db
    from app.services import repository, storage, templates

    _clear_runtime_caches()
    settings = get_settings()
    settings.ensure_directories()
    init_db()

    user = repository.get_or_create_user("test-openid")
    image_bytes = _build_test_image()
    stored_path = storage.save_upload_file(image_bytes, ".png")
    upload = repository.create_upload(
        user_id=user["id"],
        original_name="portrait.png",
        stored_path=stored_path,
        mime_type="image/png",
        file_size=len(image_bytes),
        width=768,
        height=1024,
    )
    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("morning-window-softlight")
    assert hairstyle is not None
    assert scene is not None
    prompt = templates.build_job_prompt_payload(
        hairstyle,
        scene,
        generator_backend="basic",
        aspect_ratio="3:4",
        resolution="2K",
        seed_source="job-fixture",
    )
    job = repository.create_job(
        user_id=user["id"],
        upload_id=upload["id"],
        hairstyle_id=hairstyle["id"],
        scene_id=scene["id"],
        prompt=prompt,
        model_name="test-generator",
    )
    return {
        "settings": settings,
        "user": user,
        "upload": upload,
        "job": job,
        "hairstyle": hairstyle,
        "scene": scene,
    }


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
    assert "服饰：" in prompt
    assert "妆容：" in prompt
    assert "妆造约束：" in prompt
    assert "不要拼图排版" in prompt
    assert "图片需要符合物理逻辑" in prompt
    assert "不可以有不符合物理逻辑的身体部位" in prompt
    assert "只选择 1 种主体动作" in prompt
    assert "不要与主体动作叠加成不合理肢体效果" in prompt
    assert "后端每次只选 1 个主体动作" in prompt


def test_build_and_parse_job_prompt_payload_preserves_output_options():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("morning-window-softlight")

    assert hairstyle is not None
    assert scene is not None

    payload = templates.build_job_prompt_payload(
        hairstyle,
        scene,
        generator_backend="nano_banana_2",
        aspect_ratio="3:4",
        resolution="2K",
        seed_source="job-payload",
    )
    parsed = templates.parse_job_prompt_payload(payload)

    assert parsed["output_options"] == {
        "generator_backend": "basic",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    }
    assert parsed["styling_id"]
    assert "full_prompt" in parsed
    assert "hairstyle_only_prompt" in parsed
    assert "scene_only_prompt" in parsed


def test_parse_job_prompt_payload_keeps_legacy_output_options_for_history():
    from app.services import templates

    payload = {
        "version": 2,
        "full_prompt": "legacy full",
        "hairstyle_only_prompt": "legacy hair",
        "scene_only_prompt": "legacy scene",
        "styling_id": "legacy-style",
        "output_options": {
            "generator_backend": "basic",
            "aspect_ratio": "1:8",
            "resolution": "4K",
        },
    }

    parsed = templates.parse_job_prompt_payload(json.dumps(payload, ensure_ascii=False))

    assert parsed["output_options"] == {
        "generator_backend": "basic",
        "aspect_ratio": "1:8",
        "resolution": "4K",
    }


def test_build_prompt_assembly_returns_structured_blocks():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("morning-window-softlight")

    assert hairstyle is not None
    assert scene is not None

    assembly = templates.build_prompt_assembly(
        mode="full_stylize",
        hairstyle=hairstyle,
        scene=scene,
        seed_source="api-assembly",
    )

    assert assembly.mode == "full_stylize"
    assert [block.key for block in assembly.blocks] == [
        "identity_lock",
        "output_format",
        "shot",
        "scene_environment",
        "scene_lighting",
        "scene_mood",
        "expression",
        "subject_action",
        "hairstyle_action",
        "makeup",
        "outfit",
        "hair_target",
        "styling_constraints",
        "scene_constraints",
        "hair_constraints",
        "motion_safety_constraints",
        "quality_skin_texture",
        "quality_image_finish",
        "negative_identity_artifact",
        "negative_physical_logic",
    ]
    assert assembly.render() == templates.build_prompt(hairstyle, scene, seed_source="api-assembly")
    assert assembly.blocks[0].label == "身份锁定"
    assert assembly.blocks[3].label == "场景环境"


def test_prompt_block_labels_use_english_keys_and_chinese_labels():
    from app.services import templates

    labels = templates.get_prompt_block_labels()

    assert labels["identity_lock"] == "身份锁定"
    assert labels["scene_environment"] == "场景环境"
    assert labels["makeup"] == "人物妆容"
    assert labels["hair_lock"] == "发型锁定"
    assert labels["negative_physical_logic"] == "物理逻辑负面约束"


def test_prompt_rule_table_declares_mode_boundaries():
    from app.services import templates

    rules = templates.get_prompt_rule_table()

    assert "scene_only" in rules
    assert "hairstyle_only" in rules
    assert "hair_lock" in rules["scene_only"].required_blocks
    assert "makeup" in rules["scene_only"].required_blocks
    assert "styling_constraints" in rules["scene_only"].required_blocks
    assert "hair_target" in rules["hairstyle_only"].required_blocks
    assert "hair_target" in rules["scene_only"].forbidden_blocks
    assert "scene_environment" in rules["hairstyle_only"].forbidden_blocks
    assert "shot" in rules["hairstyle_only"].forbidden_blocks
    assert "scene_control" in rules["hairstyle_only"].forbidden_blocks
    assert "face_strategy" in rules["hairstyle_only"].forbidden_blocks
    assert "makeup" in rules["hairstyle_only"].forbidden_blocks
    assert "styling_constraints" in rules["hairstyle_only"].forbidden_blocks


def test_build_hairstyle_only_prompt_uses_identity_lock_and_hair_swap_structure():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert hairstyle is not None

    prompt = templates.build_hairstyle_only_prompt(hairstyle)

    assert "只更换图中人物的发型" in prompt
    assert "换发目标：只更换图中人物的发型为：前刺头。" in prompt
    assert "人物发型：发型改为前刺头" in prompt
    assert "尽量保持原图中的背景、服饰、姿态、表情、构图、镜头距离、光线和氛围不变" in prompt
    assert "不能把新发型做成悬浮假发" in prompt
    assert "负面约束：不要换脸、不要改变性别表达、不要生成第二个人" in prompt


def test_build_scene_only_prompt_locks_existing_hairstyle_and_updates_scene():
    from app.services import templates

    scene = templates.get_scene("morning-window-softlight")

    assert scene is not None

    prompt = templates.build_scene_only_prompt(scene, seed_source="scene-only-lock")

    assert "不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质和发型" in prompt
    assert "忽略原照片中的背景、原服饰、原有动作" in prompt
    assert "人物发型：保持参考图中已经生成完成的发型不变" in prompt
    assert "妆容：" in prompt
    assert "服饰：" in prompt
    assert "不要因为动作、风感或镜头变化把当前发型改成另一种发型" in prompt
    assert "抬手整理窗边发丝" not in prompt


def test_scene_only_prompt_prefers_gendered_scene_styling_rules():
    from app.services import templates

    scene = templates.get_scene("indoor-film-lifestyle")

    assert scene is not None

    female_prompt = templates.build_scene_only_prompt(
        scene,
        preferred_gender="female",
        seed_source="scene-only-female-rule",
    )
    male_prompt = templates.build_scene_only_prompt(
        scene,
        preferred_gender="male",
        seed_source="scene-only-male-rule",
    )

    assert "内搭浅色背心或吊带" in female_prompt
    assert "米白或浅灰针织上衣" in male_prompt
    assert female_prompt != male_prompt


def test_scene_only_prompt_assembly_exposes_hair_lock_block():
    from app.services import templates

    scene = templates.get_scene("walnut-study-portrait")

    assert scene is not None

    assembly = templates.build_prompt_assembly(
        mode="scene_only",
        scene=scene,
        seed_source="scene-only-api-assembly",
    )

    assert assembly.mode == "scene_only"
    hair_blocks = [block.text for block in assembly.blocks if block.key == "hair_lock"]
    assert len(hair_blocks) == 1
    assert "保持参考图中已经生成完成的发型不变" in hair_blocks[0]
    assert any(block.key == "makeup" for block in assembly.blocks)
    assert any(block.key == "styling_constraints" for block in assembly.blocks)


def test_default_styling_prefers_matching_gender_when_available():
    from app.services import templates

    female_styling = templates._default_styling(
        "realistic_editorial",
        "female",
        "styling-gender-female",
    )
    male_styling = templates._default_styling(
        "realistic_editorial",
        "male",
        "styling-gender-male",
    )

    assert female_styling["gender"] == "female"
    assert male_styling["gender"] == "male"


def test_prompt_filters_hand_conflicting_hairstyle_actions():
    from app.services import templates

    compatible_actions = templates._filter_compatible_hairstyle_actions(
        "双手轻握杯子停顿",
        ["看镜头微抬下巴", "单手抓起头顶前区发束", "半侧脸回望镜头"],
    )

    assert compatible_actions == ["看镜头微抬下巴", "半侧脸回望镜头"]


def test_scene_only_prompt_filters_hair_touching_subject_actions():
    from app.services import templates

    compatible_actions = templates._filter_scene_actions_for_locked_hairstyle(
        ["靠在窗台边", "抬手整理窗边发丝", "双手轻握杯子停顿"]
    )

    assert compatible_actions == ["靠在窗台边", "双手轻握杯子停顿"]


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

    assert len(templates.SCENES) >= 20
    assert len(templates.HAIRSTYLES) == 56
    assert len(templates.STYLINGS) == 7
    assert len([item for item in templates.HAIRSTYLES if item["gender"] == "male"]) == 23
    assert len([item for item in templates.HAIRSTYLES if item["gender"] == "female"]) == 33

    assert templates.get_hairstyle("american-spiky")["id"] == "male-forward-spikes"
    assert templates.get_scene("lifestyle-interior")["id"] == "indoor-film-lifestyle"
    assert templates.get_hairstyle("male-morgan-fringe") is None
    assert templates.get_hairstyle("male-comma-bangs") is None


def test_scene_templates_expose_sample_image_ids_and_structured_lighting():
    from app.services import templates

    lifestyle_scene = templates.get_scene("morning-window-softlight")
    fashion_scene = templates.get_scene("city-neon-night")

    assert lifestyle_scene is not None
    assert fashion_scene is not None

    assert lifestyle_scene["lighting_profile"]["light_direction"] == "side"
    assert lifestyle_scene["outfit_palette"]
    assert templates.resolve_scene_sample_image_id(lifestyle_scene, "female") == "female3"
    assert templates.resolve_scene_sample_image_id(fashion_scene, "male") == "male1"


def test_template_cover_svg_uses_visual_layout_without_large_text_overlay():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("city-neon-night")

    assert hairstyle is not None
    assert scene is not None

    hairstyle_svg = templates.template_cover_svg("hairstyles", hairstyle)
    scene_svg = templates.template_cover_svg("scenes", scene)

    assert 'viewBox="0 0 720 960"' in hairstyle_svg
    assert 'viewBox="0 0 720 960"' in scene_svg
    assert hairstyle["name"] not in hairstyle_svg
    assert scene["name"] not in scene_svg
    assert "<text" not in hairstyle_svg
    assert "<text" not in scene_svg


def test_settings_resolve_relative_paths_against_repository_root(monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", "tmp-relative-storage")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp-relative-db/app.db")
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "local")
    monkeypatch.setenv("RUN_EMBEDDED_WORKER", "true")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")
    _clear_runtime_caches()

    from app.config import ROOT_DIR, get_settings

    settings = get_settings()

    assert settings.storage_dir == (ROOT_DIR / "tmp-relative-storage").resolve()
    assert settings.database_path == (ROOT_DIR / "tmp-relative-db" / "app.db").resolve()
    assert settings.database_url.endswith("/tmp-relative-db/app.db")


def test_settings_reject_local_queue_without_embedded_worker(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "local")
    monkeypatch.setenv("RUN_EMBEDDED_WORKER", "false")
    _clear_runtime_caches()

    from app.config import get_settings

    with pytest.raises(ValueError, match="RUN_EMBEDDED_WORKER"):
        get_settings()


def test_auth_upload_job_history_flow(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    from app.services import templates as template_service

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
        assert len(catalog["hairstyles"]) == 56
        assert len(catalog["scenes"]) == len(template_service.SCENES)
        assert len(catalog["generation_backends"]) == 2
        assert len([item for item in catalog["hairstyles"] if item["gender"] == "male"]) == 23
        assert len([item for item in catalog["hairstyles"] if item["gender"] == "female"]) == 33
        assert catalog["hairstyles"][0]["style_line_label"]
        assert catalog["hairstyles"][0]["category_key"]
        assert catalog["hairstyles"][0]["category_label"]
        assert not any(item["id"] == "male-morgan-fringe" for item in catalog["hairstyles"])
        assert not any(item["id"] == "male-comma-bangs" for item in catalog["hairstyles"])

        job_create = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": catalog["hairstyles"][0]["id"],
                "scene_id": catalog["scenes"][0]["id"],
                "generator_backend": "premium",
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
        assert status_payload["hair_preview_url"]
        assert status_payload["result_image_url"]
        assert len(status_payload["result_image_urls"]) == 2
        assert status_payload["result_image_urls"][0] == status_payload["result_image_url"]
        assert status_payload["generator_backend"] == "premium"
        assert status_payload["completed_scene_count"] == 2
        assert status_payload["media_expired"] is False
        assert status_payload["media_expires_at"]

        history = client.get("/api/history", headers=headers)
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) == 1
        assert items[0]["job_id"] == job_id
        assert items[0]["hair_preview_url"]
        assert len(items[0]["result_image_urls"]) == 2
        assert items[0]["media_expired"] is False

        me = client.get("/api/me", headers=headers)
        assert me.status_code == 200
        me_payload = me.json()
        assert me_payload["user_id"] == login.json()["user_id"]
        assert me_payload["nickname"] == f"微信用户 {login.json()['user_id']}"
        assert me_payload["member_status"] == "普通用户"
        assert me_payload["monthly_used"] == 1
        assert me_payload["total_jobs"] == 1
        assert me_payload["completed_jobs"] == 1
        assert me_payload["processing_jobs"] == 0
        assert me_payload["remaining_quota"] == 19

        delete_response = client.delete(f"/api/jobs/{job_id}", headers=headers)
        assert delete_response.status_code == 204

        history_after_delete = client.get("/api/history", headers=headers)
        assert history_after_delete.status_code == 200
        assert history_after_delete.json()["items"] == []

        from app.services import repository

        assert repository.get_job(job_id) is None
        assert repository.get_upload(upload_id) is None
        assert list((tmp_path / "storage" / "uploads").iterdir()) == []
        assert list((tmp_path / "storage" / "results").iterdir()) == []


def test_upload_validation_accepts_single_prominent_face(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")
    _clear_runtime_caches()

    from app.services import storage

    monkeypatch.setattr(
        storage,
        "_detect_faces",
        lambda image_bytes: ((164, 112, 252, 320),),
    )

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024
    assert metadata.extension == ".png"


def test_upload_validation_rejects_multiple_prominent_faces(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")
    _clear_runtime_caches()

    from app.services import storage

    monkeypatch.setattr(
        storage,
        "_detect_faces",
        lambda image_bytes: (
            (120, 120, 220, 300),
            (420, 140, 210, 290),
        ),
    )

    with pytest.raises(storage.UploadValidationError) as exc_info:
        storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert exc_info.value.code == "multiple_faces"


def test_upload_validation_rejects_face_that_is_too_small(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")
    _clear_runtime_caches()

    from app.services import storage

    monkeypatch.setattr(
        storage,
        "_detect_faces",
        lambda image_bytes: ((340, 280, 60, 72),),
    )

    with pytest.raises(storage.UploadValidationError) as exc_info:
        storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert exc_info.value.code == "face_too_small"


def test_template_catalog_prefers_real_cover_url_when_available(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    from app.services import storage, templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    assert hairstyle is not None

    original_values = {
        "cover_image_path": hairstyle.get("cover_image_path", ""),
        "cover_image_updated_at": hairstyle.get("cover_image_updated_at", ""),
        "cover_image_source": hairstyle.get("cover_image_source", ""),
    }
    hairstyle["cover_image_path"] = storage.save_template_asset(
        "hairstyles",
        hairstyle["id"],
        _build_colored_image("#264653"),
    )
    hairstyle["cover_image_updated_at"] = "2026-03-26T12:34:56+00:00"
    hairstyle["cover_image_source"] = "test"

    try:
        with TestClient(app) as client:
            response = client.get("/api/templates")
            assert response.status_code == 200
            catalog = response.json()
            current = next(item for item in catalog["hairstyles"] if item["id"] == hairstyle["id"])
            assert "/media/template_assets/hairstyles/" in current["cover_url"]
            assert current["cover_url"].endswith("?v=20260326T1234560000")
            assert not current["cover_url"].endswith(".svg")
    finally:
        hairstyle.update(original_values)


def test_job_accepts_extended_output_options(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

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
                "generator_backend": "basic",
                "aspect_ratio": "21:9",
                "resolution": "2K",
            },
        )

        assert job_create.status_code == 201
        payload = job_create.json()
        assert payload["generator_backend"] == "basic"
        assert payload["aspect_ratio"] == "21:9"
        assert payload["resolution"] == "2K"


def test_templates_catalog_exposes_plan_specific_output_capabilities(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        catalog = client.get("/api/templates", headers=headers)
        assert catalog.status_code == 200
        backends = {item["id"]: item for item in catalog.json()["generation_backends"]}

        assert backends["basic"]["aspect_ratios"] == [
            "1:1",
            "16:9",
            "9:16",
            "4:3",
            "3:4",
            "3:2",
            "2:3",
            "21:9",
            "5:4",
            "4:5",
        ]
        assert backends["basic"]["resolutions"] == ["2K"]
        assert backends["basic"]["default_resolution"] == "2K"
        assert backends["premium"]["resolutions"] == ["1K", "2K"]
        assert backends["premium"]["default_resolution"] == "2K"


def test_job_rejects_plan_specific_unsupported_output_options(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

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
        job_basic_4k = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": catalog["hairstyles"][0]["id"],
                "scene_id": catalog["scenes"][0]["id"],
                "generator_backend": "basic",
                "aspect_ratio": "3:4",
                "resolution": "4K",
            },
        )
        assert job_basic_4k.status_code == 400
        assert "Unsupported resolution: 4K" in job_basic_4k.json()["detail"]

        job_premium_extreme_ratio = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": catalog["hairstyles"][0]["id"],
                "scene_id": catalog["scenes"][0]["id"],
                "generator_backend": "premium",
                "aspect_ratio": "1:8",
                "resolution": "2K",
            },
        )
        assert job_premium_extreme_ratio.status_code == 400
        assert "Unsupported aspect ratio: 1:8" in job_premium_extreme_ratio.json()["detail"]


def test_media_cleanup_removes_expired_images_but_keeps_history(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

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

        catalog = client.get("/api/templates")
        assert catalog.status_code == 200
        catalog_payload = catalog.json()

        job_create = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": catalog_payload["hairstyles"][0]["id"],
                "scene_id": catalog_payload["scenes"][0]["id"],
            },
        )
        assert job_create.status_code == 201
        job_id = job_create.json()["job_id"]

        final_payload = None
        for _ in range(30):
            job_detail = client.get(f"/api/jobs/{job_id}", headers=headers)
            assert job_detail.status_code == 200
            final_payload = job_detail.json()
            if final_payload["status"] == "succeeded":
                break
            time.sleep(0.1)

        assert final_payload is not None
        assert final_payload["hair_preview_url"]
        assert final_payload["result_image_url"]
        assert len(final_payload["result_image_urls"]) == 2

        from app.db import jobs, session_scope, uploads
        from app.services import repository
        from app.services.retention import purge_expired_media

        expired_created_at = (
            datetime.now(timezone.utc) - timedelta(days=8)
        ).replace(microsecond=0).isoformat()

        with session_scope() as session:
            session.execute(
                update(uploads)
                .where(uploads.c.id == upload_id)
                .values(created_at=expired_created_at)
            )
            session.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(created_at=expired_created_at, updated_at=expired_created_at)
            )

        purge_expired_media(force=True)

        expired_job = client.get(f"/api/jobs/{job_id}", headers=headers)
        assert expired_job.status_code == 200
        expired_payload = expired_job.json()
        assert expired_payload["status"] == "succeeded"
        assert expired_payload["media_expired"] is True
        assert expired_payload["upload_url"] is None
        assert expired_payload["hair_preview_url"] is None
        assert expired_payload["result_image_url"] is None
        assert expired_payload["result_image_urls"] == []

        history = client.get("/api/history", headers=headers)
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) == 1
        assert items[0]["job_id"] == job_id
        assert items[0]["media_expired"] is True
        assert items[0]["hair_preview_url"] is None
        assert items[0]["result_image_url"] is None

        upload_record = repository.get_upload(upload_id)
        job_record = repository.get_job(job_id)
        assert upload_record is not None
        assert job_record is not None
        assert upload_record["stored_path"] == ""
        assert job_record["result_path"] is None
        assert list((tmp_path / "storage" / "uploads").iterdir()) == []
        assert list((tmp_path / "storage" / "results").iterdir()) == []


def test_job_exposes_preview_before_final_result(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")

    from app.main import create_app
    import app.main as app_main
    from app.services.generation import GenerationResult

    class SlowPreviewGenerator:
        model_name = "slow-preview-generator"

        def generate(
            self,
            source_image_path,
            prompt,
            context,
            provider_key=None,
            on_preview=None,
            on_candidate=None,
        ):
            first = _build_colored_image("#264653")
            second = _build_colored_image("#2a9d8f")
            if on_preview is not None:
                on_preview(first)
            if on_candidate is not None:
                on_candidate(first)
            time.sleep(0.45)
            if on_candidate is not None and int(getattr(context, "image_count", 1) or 1) > 1:
                on_candidate(second)
            return GenerationResult(
                primary_image_bytes=first,
                candidate_image_bytes=[first, second],
            )

    _clear_runtime_caches()
    monkeypatch.setattr(app_main, "build_generator", lambda backend=None: SlowPreviewGenerator())
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
            if payload["hair_preview_url"]:
                preview_payload = payload
                break
            time.sleep(0.05)

        assert preview_payload is not None
        assert preview_payload["hair_preview_url"]
        assert preview_payload["result_image_url"]
        assert preview_payload["result_image_url"] == preview_payload["hair_preview_url"]

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
        assert len(final_payload["result_image_urls"]) == 2
        assert final_payload["result_image_urls"][0] == final_payload["result_image_url"]


def test_recommendations_api_returns_payload(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    from app.services import recommendations as recommendation_service

    monkeypatch.setattr(
        recommendation_service,
        "build_recommendation_payload",
        lambda upload: {
            "face_shape": {"id": "oval", "label": "椭圆脸"},
            "feature_tags": ["比例均衡", "轮廓柔和"],
            "summary": "推荐优先选择更能平衡面部比例的发型和场景。",
            "measurements": {"face_aspect_ratio": 1.36},
            "recommended_hairstyles": {
                "male": [
                    {
                        "id": "male-forward-spikes",
                        "name": "前刺短发",
                        "score": 6,
                        "reasons": ["适合拉长面部纵向比例"],
                    }
                ],
                "female": [],
            },
            "recommended_scenes": [
                {
                    "id": "morning-window-softlight",
                    "name": "晨光窗边",
                    "score": 5,
                    "reasons": ["更适合柔和自然的生活感场景"],
                }
            ],
        },
    )

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("portrait.png", _build_test_image(), "image/png")},
        )
        assert upload.status_code == 200

        response = client.post(
            "/api/recommendations",
            headers=headers,
            json={"upload_id": upload.json()["upload_id"]},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["face_shape"]["label"] == "椭圆脸"
        assert payload["feature_tags"] == ["比例均衡", "轮廓柔和"]
        assert payload["recommended_hairstyles"]["male"][0]["id"] == "male-forward-spikes"
        assert payload["recommended_scenes"][0]["id"] == "morning-window-softlight"


def test_recommendations_api_returns_unavailable_error(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    from app.services import recommendations as recommendation_service

    def _raise_recommendation_error(upload):
        raise recommendation_service.RecommendationError("未识别到清晰人脸")

    monkeypatch.setattr(
        recommendation_service,
        "build_recommendation_payload",
        _raise_recommendation_error,
    )

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("portrait.png", _build_test_image(), "image/png")},
        )
        assert upload.status_code == 200

        response = client.post(
            "/api/recommendations",
            headers=headers,
            json={"upload_id": upload.json()["upload_id"]},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == {
            "code": "recommendation_unavailable",
            "message": "未识别到清晰人脸",
        }


def test_seedream_generator_requests_preview_first_then_tops_up(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_IMAGE_MODEL", "doubao-seedream-4-5-251128")

    from app.config import get_settings
    from app.services.generation import SeedreamGenerator
    from app.services.key_pool import ApiKeyLease

    get_settings.cache_clear()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    generator = SeedreamGenerator()
    preview_image = _build_colored_image("#264653")
    second_image = _build_colored_image("#2a9d8f")
    third_image = _build_colored_image("#e9c46a")
    call_log = []
    preview_events = []

    def fake_collect(
        self,
        *,
        client,
        prompt,
        image_data,
        max_images,
        on_first_candidate=None,
        on_candidate=None,
    ):
        call_log.append(("collect", max_images))
        if on_first_candidate is not None:
            on_first_candidate(preview_image)
            preview_events.append("preview")
        if on_candidate is not None:
            on_candidate(preview_image)
        return [preview_image]

    def fake_top_up(
        self,
        *,
        client,
        prompt,
        image_data,
        existing_count,
        target_count,
        on_first_candidate=None,
        on_candidate=None,
    ):
        call_log.append(("top_up", existing_count, target_count))
        return [second_image, third_image]

    monkeypatch.setattr(SeedreamGenerator, "_collect_stream_candidates", fake_collect)
    monkeypatch.setattr(SeedreamGenerator, "_top_up_candidates", fake_top_up)

    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test prompt",
        context=None,
        provider_key=ApiKeyLease(key_id="default", api_key="test-key"),
        on_preview=lambda image_bytes: preview_events.append("callback"),
    )

    assert call_log == [("collect", 1), ("top_up", 1, 3)]
    assert preview_events == ["callback", "preview"]
    assert len(result.candidate_image_bytes) == 3


def test_seedream_5_generator_uses_rest_images_generation_api(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_IMAGE_MODEL", "doubao-seedream-5-0-260128")

    from app.config import get_settings
    from app.services.generation import GenerationContext, SeedreamGenerator
    from app.services.key_pool import ApiKeyLease

    get_settings.cache_clear()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = {"post": [], "get": []}

    class FakePostResponse:
        status_code = 200

        def json(self):
            index = len(request_log["post"])
            return {
                "data": [
                    {
                        "url": f"https://cdn.example.com/seedream5-{index}.png",
                    }
                ]
            }

    class FakeGetResponse:
        def __init__(self, url):
            self.content = _build_colored_image("#264653" if url.endswith("-1.png") else "#2a9d8f")

        def raise_for_status(self):
            return None

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log["post"].append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakePostResponse()

    def fake_get(url, *, timeout=None):
        request_log["get"].append({"url": url, "timeout": timeout})
        return FakeGetResponse(url)

    monkeypatch.setattr("app.services.generation.httpx.post", fake_post)
    monkeypatch.setattr("app.services.generation.httpx.get", fake_get)

    previews = []
    result = SeedreamGenerator().generate(
        source_image_path=str(source_path),
        prompt="test seedream 5 prompt",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="4K",
        ),
        provider_key=ApiKeyLease(key_id="default", api_key="test-key"),
        on_preview=lambda image_bytes: previews.append(image_bytes),
    )

    assert len(request_log["post"]) == 3
    first_request = request_log["post"][0]
    assert first_request["url"].endswith("/images/generations")
    assert first_request["headers"]["Authorization"] == "Bearer test-key"
    assert first_request["json"]["model"] == "doubao-seedream-5-0-260128"
    assert first_request["json"]["response_format"] == "url"
    assert first_request["json"]["stream"] is False
    assert first_request["json"]["sequential_image_generation"] == "disabled"
    assert first_request["json"]["size"] == "2K"
    assert first_request["json"]["image"].startswith("data:image/png;base64,")
    assert len(request_log["get"]) == 3
    assert len(previews) == 1
    assert len(result.candidate_image_bytes) == 3


def test_nano_banana_pro_settings_use_renamed_envs(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "new-pro-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://example.test/api")
    monkeypatch.setenv("NANO_BANANA_PRO_MODEL", "gemini-3-pro-image-preview")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.nano_banana_pro_api_key == "new-pro-key"
    assert settings.nano_banana_pro_base_url == "https://example.test/api"
    assert settings.nano_banana_pro_model == "gemini-3-pro-image-preview"


def test_nano_banana_generator_uses_native_image_config(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "nano_banana_pro")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "nano-test-key")

    from app.config import get_settings
    from app.services.generation import GenerationContext, NanoBananaProGenerator

    get_settings.cache_clear()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
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
            }

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log["url"] = url
        request_log["headers"] = headers
        request_log["json"] = json
        request_log["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.generation.httpx.post", fake_post)

    generator = NanoBananaProGenerator()
    previews = []
    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test nano prompt",
        context=GenerationContext(
            hairstyle_name="法式慵懒卷",
            scene_name="咖啡馆抓拍座位人像",
            aspect_ratio="3:4",
            resolution="4K",
        ),
        on_preview=lambda image_bytes: previews.append(image_bytes),
    )

    assert request_log["url"].endswith(":generateContent")
    assert request_log["headers"]["Authorization"] == "Bearer nano-test-key"
    assert request_log["json"]["generationConfig"]["imageConfig"] == {
        "aspectRatio": "3:4",
        "imageSize": "4K",
    }
    assert request_log["timeout"] == 360
    assert len(previews) == 1
    assert len(result.candidate_image_bytes) == 1


def test_nano_banana_2_generator_uses_native_image_config(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "nano_banana_2")
    monkeypatch.setenv("NANO_BANANA_2_API_KEY", "nano-2-test-key")

    from app.config import get_settings
    from app.services.generation import GenerationContext, NanoBanana2Generator

    get_settings.cache_clear()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": base64.b64encode(_build_colored_image("#8338ec")).decode("utf-8"),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log["url"] = url
        request_log["headers"] = headers
        request_log["json"] = json
        request_log["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.generation.httpx.post", fake_post)

    generator = NanoBanana2Generator()
    previews = []
    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test nano banana 2 prompt",
        context=GenerationContext(
            hairstyle_name="法式慵懒卷",
            scene_name="咖啡馆抓拍座位人像",
            aspect_ratio="1:8",
            resolution="512px",
        ),
        on_preview=lambda image_bytes: previews.append(image_bytes),
    )

    assert request_log["url"].endswith(":generateContent")
    assert request_log["headers"]["Authorization"] == "Bearer nano-2-test-key"
    assert request_log["json"]["generationConfig"]["imageConfig"] == {
        "aspectRatio": "1:8",
        "imageSize": "512px",
    }
    assert request_log["timeout"] == 120
    assert len(previews) == 1
    assert len(result.candidate_image_bytes) == 1


def test_sora_image_generator_uses_chat_completion_with_reference_image(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "sora_image")
    monkeypatch.setenv("SORA_IMAGE_API_KEY", "sora-test-key")

    from app.config import get_settings
    from app.services.generation import GenerationContext, SoraImageGenerator

    get_settings.cache_clear()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = {}

    class FakePostResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "![gen_image](https://cdn.example.com/generated/sora.png)"
                        }
                    }
                ]
            }

    class FakeGetResponse:
        content = _build_colored_image("#ef476f")

        def raise_for_status(self):
            return None

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log["url"] = url
        request_log["headers"] = headers
        request_log["json"] = json
        request_log["timeout"] = timeout
        return FakePostResponse()

    def fake_get(url, *, timeout=None):
        request_log["download_url"] = url
        request_log["download_timeout"] = timeout
        return FakeGetResponse()

    monkeypatch.setattr("app.services.generation.httpx.post", fake_post)
    monkeypatch.setattr("app.services.generation.httpx.get", fake_get)

    generator = SoraImageGenerator()
    previews = []
    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test sora prompt",
        context=GenerationContext(
            hairstyle_name="法式慵懒卷",
            scene_name="咖啡馆抓拍座位人像",
            aspect_ratio="2:3",
            resolution=None,
        ),
        on_preview=lambda image_bytes: previews.append(image_bytes),
    )

    assert request_log["url"].endswith("/chat/completions")
    assert request_log["headers"]["Authorization"] == "Bearer sora-test-key"
    content = request_log["json"]["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert "〖2:3〗" in content[0]["text"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert request_log["download_url"] == "https://cdn.example.com/generated/sora.png"
    assert len(previews) == 1
    assert len(result.candidate_image_bytes) == 1


def test_map_openai_error_disables_key_for_model_not_open():
    import httpx
    from openai import APIStatusError

    from app.services.generation import _map_openai_error

    request = httpx.Request("POST", "https://example.com/v1/images")
    response = httpx.Response(
        404,
        request=request,
        json={
            "error": {
                "code": "ModelNotOpen",
                "message": "Your account has not activated the model.",
            }
        },
    )
    error = APIStatusError(
        "Error code: 404",
        response=response,
        body=response.json(),
    )

    mapped = _map_openai_error(error)

    assert mapped.code == "model_not_open"
    assert mapped.retryable is True
    assert mapped.disable_key is True


def test_map_openai_error_disables_key_for_set_limit_exceeded():
    import httpx
    from openai import APIStatusError

    from app.services.generation import _map_openai_error

    request = httpx.Request("POST", "https://example.com/v1/images")
    response = httpx.Response(
        429,
        request=request,
        json={
            "error": {
                "code": "SetLimitExceeded",
                "message": "Set limit exceeded for this account.",
            }
        },
    )
    error = APIStatusError(
        "Error code: 429",
        response=response,
        body=response.json(),
    )

    mapped = _map_openai_error(error)

    assert mapped.code == "set_limit_exceeded"
    assert mapped.retryable is True
    assert mapped.disable_key is True
    assert mapped.retry_after_seconds == 3600


def test_map_seedream_http_error_disables_key_for_set_limit_exceeded():
    import httpx

    from app.services.generation import _map_seedream_http_error

    response = httpx.Response(
        429,
        request=httpx.Request("POST", "https://example.com/api/v3/images/generations"),
        json={
            "error": {
                "message": "Your account [2122895780] has reached the set inference limit for the [doubao-seedream-5-0] model, and the model service has been paused. Please adjust Safe Experience Mode.",
            }
        },
    )

    mapped = _map_seedream_http_error(response)

    assert mapped.code == "set_limit_exceeded"
    assert mapped.retryable is True
    assert mapped.disable_key is True
    assert mapped.retry_after_seconds == 3600


def test_settings_parse_multi_ark_api_keys_and_default_worker_concurrency(
    tmp_path, monkeypatch
):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEYS", "key-a:alpha,key-b:beta")
    monkeypatch.setenv("ARK_API_KEY_MAX_CONCURRENCY", "2")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert [credential.key_id for credential in settings.ark_api_keys] == ["key-a", "key-b"]
    assert [credential.api_key for credential in settings.ark_api_keys] == ["alpha", "beta"]
    assert all(credential.max_concurrency == 2 for credential in settings.ark_api_keys)
    assert settings.job_worker_concurrency == 4
    assert settings.use_mock_generator is False


def test_settings_parse_disabled_ark_api_key_ids(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEYS", "key-a:alpha,key-b:beta")
    monkeypatch.setenv("ARK_API_DISABLED_KEY_IDS", "key-a,key-c")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.ark_api_disabled_key_ids == ("key-a", "key-c")


def test_api_key_pool_disables_key_and_stops_future_allocation(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEYS", "key-a:alpha,key-b:beta")

    from app.config import get_settings
    from app.services.key_pool import ApiKeyPool

    get_settings.cache_clear()
    settings = get_settings()
    pool = ApiKeyPool(
        settings.ark_api_keys,
        default_cooldown_seconds=settings.ark_key_cooldown_seconds,
    )

    lease = pool.acquire(timeout=0.1)
    assert lease is not None
    pool.disable_key(lease.key_id, reason="ModelNotOpen")

    assert pool.is_disabled(lease.key_id) is True
    assert pool.active_size == 1

    next_lease = pool.acquire(timeout=0.1)
    assert next_lease is not None
    assert next_lease.key_id != lease.key_id


def test_api_key_pool_skips_config_disabled_keys(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEYS", "key-a:alpha,key-b:beta")
    monkeypatch.setenv("ARK_API_DISABLED_KEY_IDS", "key-a")

    from app.config import get_settings
    from app.services.key_pool import ApiKeyPool

    get_settings.cache_clear()
    settings = get_settings()
    pool = ApiKeyPool(
        settings.ark_api_keys,
        default_cooldown_seconds=settings.ark_key_cooldown_seconds,
        disabled_key_ids=settings.ark_api_disabled_key_ids,
    )

    assert pool.is_disabled("key-a") is True
    assert pool.active_size == 1

    lease = pool.acquire(timeout=0.1)
    assert lease is not None
    assert lease.key_id == "key-b"


def test_job_worker_switches_to_next_key_before_preview(tmp_path, monkeypatch):
    fixture = _create_job_fixture(
        tmp_path,
        monkeypatch,
        ark_api_keys="key-a:alpha,key-b:beta",
    )

    from app.services import repository, storage
    from app.services.generation import GenerationResult, ImageGenerationError
    from app.services.job_queue import JobWorker
    from app.services.key_pool import ApiKeyPool

    call_order: list[str] = []

    class FailoverGenerator:
        model_name = "failover-generator"

        def generate(
            self,
            source_image_path,
            prompt,
            context,
            provider_key=None,
            on_preview=None,
            on_candidate=None,
        ):
            assert provider_key is not None
            call_order.append(provider_key.key_id)
            if provider_key.key_id == "key-a":
                raise ImageGenerationError(
                    "rate_limited",
                    "provider busy",
                    retryable=True,
                    retry_after_seconds=1,
                )

            first = _build_colored_image("#264653")
            second = _build_colored_image("#2a9d8f")
            if on_preview is not None:
                on_preview(first)
            if on_candidate is not None:
                on_candidate(first)
                on_candidate(second)
            return GenerationResult(
                primary_image_bytes=first,
                candidate_image_bytes=[first, second],
            )

    class HairStageGenerator:
        model_name = "hair-stage-generator"

        def generate(
            self,
            source_image_path,
            prompt,
            context,
            provider_key=None,
            on_preview=None,
            on_candidate=None,
        ):
            preview = _build_colored_image("#1d3557")
            if on_preview is not None:
                on_preview(preview)
            if on_candidate is not None:
                on_candidate(preview)
            return GenerationResult(
                primary_image_bytes=preview,
                candidate_image_bytes=[preview],
            )

    worker = JobWorker(
        FailoverGenerator(),
        key_pool=ApiKeyPool(
            fixture["settings"].ark_api_keys,
            default_cooldown_seconds=fixture["settings"].ark_key_cooldown_seconds,
        ),
        concurrency=1,
    )
    hair_stage_generator = HairStageGenerator()
    scene_generator = worker.generator
    scene_key_pool = worker.key_pool
    worker._resolve_runtime = lambda backend, model_name=None: (
        (hair_stage_generator, None)
        if backend.startswith("nano_banana")
        else (scene_generator, scene_key_pool)
    )

    worker._process(fixture["job"]["id"])

    job = repository.get_job(fixture["job"]["id"])
    assert job is not None
    assert call_order == ["key-a", "key-b"]
    assert job["status"] == "succeeded"
    assert job["assigned_key_id"] is None
    assert storage.get_hair_preview_path(job["id"]) is not None
    assert len(storage.list_scene_results(job["id"])) == 2


def test_job_worker_disables_invalid_key_and_falls_back_to_next_key(
    tmp_path, monkeypatch
):
    fixture = _create_job_fixture(
        tmp_path,
        monkeypatch,
        ark_api_keys="key-a:alpha,key-b:beta",
    )

    from app.services import repository, storage
    from app.services.generation import GenerationResult, ImageGenerationError
    from app.services.job_queue import JobWorker
    from app.services.key_pool import ApiKeyPool

    call_order: list[str] = []
    key_pool = ApiKeyPool(
        fixture["settings"].ark_api_keys,
        default_cooldown_seconds=fixture["settings"].ark_key_cooldown_seconds,
    )

    class DisableThenFallbackGenerator:
        model_name = "disable-then-fallback-generator"

        def generate(
            self,
            source_image_path,
            prompt,
            context,
            provider_key=None,
            on_preview=None,
            on_candidate=None,
        ):
            assert provider_key is not None
            call_order.append(provider_key.key_id)
            if provider_key.key_id == "key-a":
                raise ImageGenerationError(
                    "model_not_open",
                    "ModelNotOpen",
                    retryable=True,
                    disable_key=True,
                )

            first = _build_colored_image("#264653")
            second = _build_colored_image("#2a9d8f")
            if on_preview is not None:
                on_preview(first)
            if on_candidate is not None:
                on_candidate(first)
                on_candidate(second)
            return GenerationResult(
                primary_image_bytes=first,
                candidate_image_bytes=[first, second],
            )

    class HairStageGenerator:
        model_name = "hair-stage-generator"

        def generate(
            self,
            source_image_path,
            prompt,
            context,
            provider_key=None,
            on_preview=None,
            on_candidate=None,
        ):
            preview = _build_colored_image("#1d3557")
            if on_preview is not None:
                on_preview(preview)
            if on_candidate is not None:
                on_candidate(preview)
            return GenerationResult(
                primary_image_bytes=preview,
                candidate_image_bytes=[preview],
            )

    worker = JobWorker(
        DisableThenFallbackGenerator(),
        key_pool=key_pool,
        concurrency=1,
    )
    hair_stage_generator = HairStageGenerator()
    scene_generator = worker.generator
    worker._resolve_runtime = lambda backend, model_name=None: (
        (hair_stage_generator, None)
        if backend.startswith("nano_banana")
        else (scene_generator, key_pool)
    )

    worker._process(fixture["job"]["id"])

    job = repository.get_job(fixture["job"]["id"])
    assert job is not None
    assert call_order == ["key-a", "key-b"]
    assert job["status"] == "succeeded"
    assert job["assigned_key_id"] is None
    assert key_pool.is_disabled("key-a") is True
    assert key_pool.active_size == 1
    assert storage.get_hair_preview_path(job["id"]) is not None
    assert len(storage.list_scene_results(job["id"])) == 2


def test_job_worker_keeps_preview_result_when_error_happens_after_preview(
    tmp_path, monkeypatch
):
    fixture = _create_job_fixture(
        tmp_path,
        monkeypatch,
        ark_api_keys="key-a:alpha,key-b:beta",
    )

    from app.services import repository, storage
    from app.services.generation import GenerationResult, ImageGenerationError
    from app.services.job_queue import JobWorker
    from app.services.key_pool import ApiKeyPool

    call_order: list[str] = []

    class PreviewThenFailGenerator:
        model_name = "preview-then-fail-generator"

        def generate(
            self,
            source_image_path,
            prompt,
            context,
            provider_key=None,
            on_preview=None,
            on_candidate=None,
        ):
            assert provider_key is not None
            call_order.append(provider_key.key_id)
            raise ImageGenerationError(
                "rate_limited",
                "provider busy after preview",
                retryable=True,
                retry_after_seconds=1,
            )

    class HairStageGenerator:
        model_name = "hair-stage-generator"

        def generate(
            self,
            source_image_path,
            prompt,
            context,
            provider_key=None,
            on_preview=None,
            on_candidate=None,
        ):
            preview = _build_colored_image("#1d3557")
            if on_preview is not None:
                on_preview(preview)
            if on_candidate is not None:
                on_candidate(preview)
            return GenerationResult(
                primary_image_bytes=preview,
                candidate_image_bytes=[preview],
            )

    worker = JobWorker(
        PreviewThenFailGenerator(),
        key_pool=ApiKeyPool(
            fixture["settings"].ark_api_keys,
            default_cooldown_seconds=fixture["settings"].ark_key_cooldown_seconds,
        ),
        concurrency=1,
    )
    hair_stage_generator = HairStageGenerator()
    scene_generator = worker.generator
    scene_key_pool = worker.key_pool
    worker._resolve_runtime = lambda backend, model_name=None: (
        (hair_stage_generator, None)
        if backend.startswith("nano_banana")
        else (scene_generator, scene_key_pool)
    )

    worker._process(fixture["job"]["id"])

    job = repository.get_job(fixture["job"]["id"])
    assert job is not None
    assert call_order == ["key-a", "key-b"]
    assert job["status"] == "failed"
    assert job["assigned_key_id"] is None
    assert storage.get_hair_preview_path(job["id"]) is not None
    assert len(storage.list_scene_results(job["id"])) == 0


def test_strict_face_detection_rejects_small_face(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "_detect_faces", lambda _: ((0, 0, 60, 60),))

    with pytest.raises(storage.UploadValidationError) as excinfo:
        storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert excinfo.value.code == "face_too_small"


def test_strict_face_detection_accepts_single_clear_face(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "_detect_faces", lambda _: ((120, 140, 180, 220),))

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024


def test_strict_face_detection_ignores_tiny_secondary_box(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(
        storage,
        "_detect_faces",
        lambda _: ((120, 140, 180, 220), (24, 30, 36, 36)),
    )

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024


def test_strict_face_detection_ignores_small_background_face(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(
        storage,
        "_detect_faces",
        lambda _: ((120, 140, 180, 220), (520, 96, 98, 112)),
    )

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024


def test_strict_face_detection_rejects_multiple_prominent_faces(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(
        storage,
        "_detect_faces",
        lambda _: ((120, 140, 180, 220), (420, 150, 170, 210)),
    )

    with pytest.raises(storage.UploadValidationError) as excinfo:
        storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert excinfo.value.code == "multiple_faces"


def test_showcases_endpoint_returns_curated_examples(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.get("/api/templates/showcases")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 6
    assert payload["items"][0]["hairstyle_id"]
    assert payload["items"][0]["scene_id"]
    assert payload["items"][0]["cover_url"]
    assert payload["items"][0]["hairstyle_cover_url"]
    assert payload["items"][0]["scene_cover_url"]


def test_scene_understanding_endpoint_returns_blocks_and_scene_draft(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    class FakeImageUnderstandingService:
        def __init__(self):
            self.model_name = "gemini-3-pro-preview"

        def extract_scene_blocks(self, image_bytes: bytes):
            assert image_bytes
            from app.services.image_understanding import SceneUnderstandingResult

            return SceneUnderstandingResult(
                subject_gender="female",
                blocks={
                    "shot": "3:4 竖构图，胸口以上近景，平视镜头。",
                    "scene_environment": "室内留白墙面与木质家具背景，窗边区域干净克制。",
                    "scene_lighting": "窗边柔和自然光从侧前方进入，整体亮部通透。",
                    "scene_mood": "安静、松弛、生活感高级。",
                    "expression": "温和看向镜头。",
                    "subject_action": "靠坐在椅子上轻微侧身。",
                    "makeup": "轻透自然底妆。",
                    "outfit": "米白色针织上衣。",
                    "styling_constraints": "不要厚重浓妆；避免复杂配饰。",
                    "scene_constraints": "背景保持简洁留白；不要加入复杂前景。",
                },
                raw_response="{}",
                model_name="gemini-3-pro-preview",
            )

    monkeypatch.setattr(
        "app.routers.scene_understanding.image_understanding.ImageUnderstandingService",
        FakeImageUnderstandingService,
    )

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        assert login.status_code == 200
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("scene-ref.png", _build_test_image(), "image/png")},
        )
        assert upload.status_code == 200
        upload_id = upload.json()["upload_id"]

        response = client.post(
            "/api/scene-understanding",
            headers=headers,
            json={
                "upload_id": upload_id,
                "title": "窗边安静人像",
                "detail_tags": ["室内", "窗边", "自然光"],
                "pairing_advice": ["法式慵懒卷", "蓬松锁骨发"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["upload_id"] == upload_id
        assert payload["model_name"] == "gemini-3-pro-preview"
        assert payload["subject_gender"] == "female"
        assert payload["blocks"]["scene_environment"].startswith("室内留白墙面")
        assert payload["blocks"]["makeup"] == "轻透自然底妆。"
        assert payload["blocks"]["styling_constraints"] == "不要厚重浓妆；避免复杂配饰。"
        assert payload["scene_draft"]["title"] == "窗边安静人像"
        assert payload["scene_draft"]["detailTags"] == ["室内", "窗边", "自然光"]
        assert payload["scene_draft"]["pairingAdvice"] == ["法式慵懒卷", "蓬松锁骨发"]
        assert payload["scene_draft"]["lightingProfile"]["lightDirection"] == "side"
        assert payload["scene_draft"]["sampleImageIds"]["female"] == ["female3"]
        assert payload["scene_draft"]["controlProfile"]["lightingHardness"] == "soft"


def test_scene_understanding_endpoint_requires_owned_upload(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        first_login = client.post("/api/auth/wechat/login", json={"code": "dev-user-1"})
        second_login = client.post("/api/auth/wechat/login", json={"code": "dev-user-2"})
        headers_one = {"Authorization": f"Bearer {first_login.json()['token']}"}
        headers_two = {"Authorization": f"Bearer {second_login.json()['token']}"}

        upload = client.post(
            "/api/uploads",
            headers=headers_one,
            files={"file": ("scene-ref.png", _build_test_image(), "image/png")},
        )
        assert upload.status_code == 200

        response = client.post(
            "/api/scene-understanding",
            headers=headers_two,
            json={"upload_id": upload.json()["upload_id"]},
        )

        assert response.status_code == 404
