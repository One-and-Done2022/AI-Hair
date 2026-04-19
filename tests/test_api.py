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
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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


def _load_asset_image_bytes(name: str) -> bytes:
    return (ROOT_DIR / "assets" / name).read_bytes()


def _write_pem_keypair(private_path: Path, public_path: Path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def _configure_wechat_pay_env(tmp_path, monkeypatch) -> dict[str, Path | str]:
    merchant_private = tmp_path / "merchant_private.pem"
    merchant_public = tmp_path / "merchant_public.pem"
    platform_private = tmp_path / "platform_private.pem"
    platform_public = tmp_path / "platform_public.pem"
    _write_pem_keypair(merchant_private, merchant_public)
    _write_pem_keypair(platform_private, platform_public)
    api_v3_key = "0123456789abcdef0123456789abcdef"

    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "1900001111")
    monkeypatch.setenv("WECHAT_APP_ID", "wx-test-app")
    monkeypatch.setenv("WECHAT_PAY_CERTIFICATE_SERIAL_NO", "merchant-serial-001")
    monkeypatch.setenv("WECHAT_PAY_PRIVATE_KEY_PATH", str(merchant_private))
    monkeypatch.setenv("WECHAT_PAY_API_V3_KEY", api_v3_key)
    monkeypatch.setenv("WECHAT_PAY_NOTIFY_URL", "https://api.lcynas.me/api/purchase/wechat/notify")
    monkeypatch.setenv("WECHAT_PAY_BASE_URL", "https://api.mch.weixin.qq.com")
    monkeypatch.setenv("WECHAT_PAY_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("WECHAT_PAY_PLATFORM_PUBLIC_KEY_PATH", str(platform_public))
    monkeypatch.setenv("WECHAT_PAY_PLATFORM_SERIAL", "platform-serial-001")
    monkeypatch.setenv("PAYMENT_PROVIDER", "wechat_pay")

    return {
        "merchant_private": merchant_private,
        "merchant_public": merchant_public,
        "platform_private": platform_private,
        "platform_public": platform_public,
        "api_v3_key": api_v3_key,
    }


def _configure_xunhu_pay_env(monkeypatch) -> None:
    monkeypatch.setenv("PAYMENT_PROVIDER", "xunhu")
    monkeypatch.setenv("PAYMENT_ENABLED", "true")
    monkeypatch.setenv("XUNHU_PAY_APP_ID", "201906179120")
    monkeypatch.setenv("XUNHU_PAY_API_KEY", "test-xunhu-secret")
    monkeypatch.setenv("XUNHU_PAY_GATEWAY_URL", "https://api.xunhupay.com/payment/do.html")
    monkeypatch.setenv("XUNHU_PAY_NOTIFY_URL", "https://api.lcynas.me/api/purchase/xunhu/notify")
    monkeypatch.setenv("XUNHU_PAY_RETURN_URL", "https://api.lcynas.me/payment/success")
    monkeypatch.setenv("XUNHU_PAY_CALLBACK_URL", "https://api.lcynas.me/payment/retry")
    monkeypatch.setenv("XUNHU_PAY_PLUGINS", "AIFaceMiniapp")
    monkeypatch.setenv("XUNHU_PAY_TIMEOUT_SECONDS", "15")


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
    monkeypatch.delenv("SEEDREAM_BASIC_ALLOWED_KEY_IDS", raising=False)
    monkeypatch.delenv("SEEDREAM_BASIC_MODEL", raising=False)
    monkeypatch.delenv("SEEDREAM_PREMIUM_ALLOWED_KEY_IDS", raising=False)
    monkeypatch.delenv("SEEDREAM_PREMIUM_MODEL", raising=False)
    monkeypatch.delenv("IMAGE_GENERATOR_BACKEND", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_API_KEY", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_BASE_URL", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_MODEL", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_MAX_CONCURRENCY", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_FALLBACK_API_KEY", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("NANO_BANANA_2_API_KEY", raising=False)
    monkeypatch.delenv("NANO_BANANA_2_BASE_URL", raising=False)
    monkeypatch.delenv("NANO_BANANA_2_MODEL", raising=False)
    monkeypatch.delenv("NANO_BANANA_2_MAX_CONCURRENCY", raising=False)
    monkeypatch.delenv("SORA_IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("SORA_IMAGE_BASE_URL", raising=False)
    monkeypatch.delenv("SORA_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("IMAGE_UNDERSTANDING_API_KEY", raising=False)
    monkeypatch.delenv("IMAGE_UNDERSTANDING_BASE_URL", raising=False)
    monkeypatch.delenv("IMAGE_UNDERSTANDING_MODEL", raising=False)
    monkeypatch.delenv("IMAGE_UNDERSTANDING_MAX_CONCURRENCY", raising=False)
    monkeypatch.delenv("IMAGE_UNDERSTANDING_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("WECHAT_PAY_MCH_ID", raising=False)
    monkeypatch.delenv("PAYMENT_ENABLED", raising=False)
    monkeypatch.delenv("PAYMENT_PROVIDER", raising=False)
    monkeypatch.delenv("WECHAT_PAY_CERTIFICATE_SERIAL_NO", raising=False)
    monkeypatch.delenv("WECHAT_PAY_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.delenv("WECHAT_PAY_API_V3_KEY", raising=False)
    monkeypatch.delenv("WECHAT_PAY_NOTIFY_URL", raising=False)
    monkeypatch.delenv("WECHAT_PAY_BASE_URL", raising=False)
    monkeypatch.delenv("WECHAT_PAY_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("WECHAT_PAY_PLATFORM_PUBLIC_KEY_PATH", raising=False)
    monkeypatch.delenv("WECHAT_PAY_PLATFORM_SERIAL", raising=False)
    monkeypatch.delenv("XUNHU_PAY_APP_ID", raising=False)
    monkeypatch.delenv("XUNHU_PAY_API_KEY", raising=False)
    monkeypatch.delenv("XUNHU_PAY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("XUNHU_PAY_NOTIFY_URL", raising=False)
    monkeypatch.delenv("XUNHU_PAY_RETURN_URL", raising=False)
    monkeypatch.delenv("XUNHU_PAY_CALLBACK_URL", raising=False)
    monkeypatch.delenv("XUNHU_PAY_PLUGINS", raising=False)
    monkeypatch.delenv("XUNHU_PAY_TIMEOUT_SECONDS", raising=False)
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
    from app.services import generation
    from app.services.storage import get_object_storage
    from app.services.wechat_pay import clear_key_caches

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_object_storage.cache_clear()
    clear_key_caches()
    generation._PROVIDER_BACKOFF_UNTIL.clear()


def _build_app(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    _clear_runtime_caches()

    from app.main import create_app

    return create_app()


def _build_app_with_wechat_pay(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    key_paths = _configure_wechat_pay_env(tmp_path, monkeypatch)
    _clear_runtime_caches()

    from app.main import create_app

    return create_app(), key_paths


def _build_app_with_xunhu_pay(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    _configure_xunhu_pay_env(monkeypatch)
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
        generator_backend="premium",
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


def _build_wechat_notify_payload(
    *,
    platform_private_key_path: Path,
    api_v3_key: str,
    order_id: str,
    amount_cents: int,
    transaction_id: str = "4200000000000000001",
) -> tuple[dict[str, str], bytes]:
    resource_plaintext = json.dumps(
        {
            "mchid": "1900001111",
            "appid": "wx-test-app",
            "out_trade_no": order_id,
            "transaction_id": transaction_id,
            "trade_state": "SUCCESS",
            "amount": {
                "total": amount_cents,
                "payer_total": amount_cents,
                "currency": "CNY",
                "payer_currency": "CNY",
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    resource_nonce = "0123456789ab"
    associated_data = "transaction"
    ciphertext = AESGCM(api_v3_key.encode("utf-8")).encrypt(
        resource_nonce.encode("utf-8"),
        resource_plaintext,
        associated_data.encode("utf-8"),
    )
    body = json.dumps(
        {
            "id": "notif-test-001",
            "create_time": "2026-04-12T12:00:00+08:00",
            "event_type": "TRANSACTION.SUCCESS",
            "resource_type": "encrypt-resource",
            "summary": "支付成功",
            "resource": {
                "original_type": "transaction",
                "algorithm": "AEAD_AES_256_GCM",
                "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
                "associated_data": associated_data,
                "nonce": resource_nonce,
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = "1712900000"
    nonce = "notify-nonce-001"
    message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n".encode("utf-8")
    private_key = serialization.load_pem_private_key(
        platform_private_key_path.read_bytes(),
        password=None,
    )
    signature = base64.b64encode(
        private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    ).decode("utf-8")
    headers = {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": signature,
        "Wechatpay-Serial": "platform-serial-001",
        "Content-Type": "application/json",
    }
    return headers, body


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
    assert "人物动作固定为" in prompt
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
        "generator_backend": "premium",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    }
    assert parsed["hair_color_selection"] == {
        "tone_id": "natural_black",
        "tone_label": "自然黑",
        "tone_hex": "#1F1A18",
        "technique_id": "solid",
        "technique_label": "统一染",
        "technique_description": "整体发色统一，只保留自然深浅层次。",
        "professional_id": "",
        "professional_brand": "",
        "professional_series": "",
        "professional_series_label": "",
        "professional_code": "",
        "professional_note": "",
        "professional_hex_estimate": "",
        "professional_prompt_alias": "",
    }
    assert parsed["styling_id"]
    assert "full_prompt" in parsed
    assert "hairstyle_only_prompt" in parsed
    assert "scene_only_prompt" in parsed


def test_build_job_prompt_payload_exposes_selected_performance_id():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("morning-window-softlight")

    assert hairstyle is not None
    assert scene is not None

    payload = templates.build_job_prompt_payload(
        hairstyle,
        scene,
        generator_backend="premium",
        aspect_ratio="3:4",
        resolution="2K",
        seed_source="job-performance-id",
    )
    parsed = templates.parse_job_prompt_payload(payload)

    assert parsed["performance_id"] == "modern-still-front"


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
        "generator_backend": "premium",
        "aspect_ratio": "1:8",
        "resolution": "2K",
    }
    assert parsed["hair_color_selection"] == {
        "tone_id": "",
        "tone_label": "",
        "tone_hex": "",
        "technique_id": "",
        "technique_label": "",
        "technique_description": "",
        "professional_id": "",
        "professional_brand": "",
        "professional_series": "",
        "professional_series_label": "",
        "professional_code": "",
        "professional_note": "",
        "professional_hex_estimate": "",
        "professional_prompt_alias": "",
    }


def test_build_and_parse_job_prompt_payload_supports_professional_hair_color_selection():
    from app.services import templates

    hairstyle = templates.get_hairstyle("female-korean-air-cushion-perm")
    scene = templates.get_scene("morning-window-softlight")

    assert hairstyle is not None
    assert scene is not None

    payload = templates.build_job_prompt_payload(
        hairstyle,
        scene,
        generator_backend="premium",
        aspect_ratio="3:4",
        resolution="2K",
        hair_color_professional_id="solutor-cool-mist-5-72",
        seed_source="job-professional-hair-color",
    )
    parsed = templates.parse_job_prompt_payload(payload)

    assert parsed["hair_color_selection"]["tone_id"] == "ash_brown"
    assert parsed["hair_color_selection"]["technique_id"] == "solid"
    assert parsed["hair_color_selection"]["professional_id"] == "solutor-cool-mist-5-72"
    assert parsed["hair_color_selection"]["professional_series_label"] == "烟熏冷雾系列"
    assert parsed["hair_color_selection"]["professional_code"] == "5/72"
    assert parsed["hair_color_selection"]["professional_note"] == "偏灰棕、轻烟熏、低饱和冷雾感"
    assert "发色以烟熏冷雾系列 5/72为唯一目标色号" in parsed["full_prompt"]
    assert "发色以烟熏冷雾系列 5/72为唯一目标色号" in parsed["hairstyle_only_prompt"]
    assert "保持参考图中静态完成的烟熏冷雾系列 5/72这一专业色号效果不变" in parsed["scene_only_prompt"]
    assert "色感表现为偏灰棕、轻烟熏、低饱和冷雾感" in parsed["full_prompt"]
    assert "综合色相可辅助参考接近 HEX #5F5F4F的雾灰棕区间" in parsed["full_prompt"]
    assert "综合色相继续辅助参考接近 HEX #5F5F4F的雾灰棕区间" in parsed["scene_only_prompt"]
    assert "发色调整为雾灰棕；" not in parsed["full_prompt"]
    assert "补充色感为偏灰棕、轻烟熏、低饱和冷雾感" not in parsed["full_prompt"]


def test_parse_job_prompt_payload_tolerates_legacy_unknown_professional_color():
    from app.services import templates

    payload = {
        "version": 5,
        "full_prompt": "legacy full",
        "hairstyle_only_prompt": "legacy hair",
        "scene_only_prompt": "legacy scene",
        "hair_color_selection": {
            "tone_id": "honey_brown",
            "tone_label": "蜂蜜茶棕",
            "tone_hex": "#8B6241",
            "technique_id": "solid",
            "technique_label": "统一染",
            "technique_description": "整体发色统一，只保留自然深浅层次。",
            "professional_id": "solutor-mist-clear-7-32",
            "professional_brand": "SOLUTOR",
            "professional_series": "mist_clear",
            "professional_series_label": "迷雾清透系列",
            "professional_code": "7/32",
            "professional_note": "轻奶茶棕、低饱和暖调、清透柔和",
            "professional_hex_estimate": "#9A7C63",
            "professional_prompt_alias": "light milk tea brown",
        },
        "output_options": {
            "generator_backend": "premium",
            "aspect_ratio": "3:4",
            "resolution": "2K",
        },
    }

    parsed = templates.parse_job_prompt_payload(json.dumps(payload, ensure_ascii=False))

    assert parsed["hair_color_selection"]["tone_id"] == "honey_brown"
    assert parsed["hair_color_selection"]["technique_id"] == "solid"
    assert parsed["hair_color_selection"]["professional_id"] == "solutor-mist-clear-7-32"
    assert parsed["hair_color_selection"]["professional_series_label"] == "迷雾清透系列"
    assert parsed["hair_color_selection"]["professional_code"] == "7/32"
    assert parsed["hair_color_selection"]["professional_note"] == "轻奶茶棕、低饱和暖调、清透柔和"


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
        "output_spec",
        "edit_scope",
        "hair_shape",
        "bangs",
        "hair_color",
        "hair_constraints",
        "scene",
        "styling",
        "subject_performance",
        "quality_control",
        "negative_constraints",
    ]
    assert assembly.render() == templates.build_prompt(hairstyle, scene, seed_source="api-assembly")
    assert assembly.blocks[0].label == "身份锁定"
    assert assembly.blocks[3].label == "主发型结构"


def test_build_prompt_assembly_accepts_identity_locked_scene_render_alias():
    from app.services import templates

    scene = templates.get_scene("morning-window-softlight")
    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert scene is not None
    assert hairstyle is not None

    assembly = templates.build_prompt_assembly(
        mode="identity_locked_scene_render",
        hairstyle=hairstyle,
        scene=scene,
        preferred_gender="male",
        seed_source="identity-locked-alias",
    )

    assert assembly.mode == "scene_only"
    assert assembly.blocks[0].key == "identity_lock"
    assert any(block.key == "subject_performance" for block in assembly.blocks)


def test_prompt_block_labels_use_english_keys_and_chinese_labels():
    from app.services import templates

    labels = templates.get_prompt_block_labels()

    assert labels["identity_lock"] == "身份锁定"
    assert labels["scene"] == "场景系统"
    assert labels["styling"] == "妆造系统"
    assert labels["hair_shape_lock"] == "发型锁定"
    assert labels["hair_color"] == "发色系统"
    assert labels["hair_color_lock"] == "发色锁定"
    assert labels["hair_motion_constraint"] == "风感约束"
    assert labels["negative_constraints"] == "负面约束"


def test_prompt_rule_table_declares_mode_boundaries():
    from app.services import templates

    rules = templates.get_prompt_rule_table()

    assert "scene_only" in rules
    assert "identity_locked_scene_render" in rules
    assert "hair_only" in rules
    assert "hairstyle_only" in rules
    assert "hair_shape_lock" in rules["scene_only"].required_blocks
    assert "bangs_lock" in rules["scene_only"].required_blocks
    assert "hair_color_lock" in rules["scene_only"].required_blocks
    assert "hair_motion_constraint" in rules["scene_only"].required_blocks
    assert "styling" in rules["scene_only"].required_blocks
    assert "subject_performance" in rules["scene_only"].required_blocks
    assert "hair_shape" in rules["hairstyle_only"].required_blocks
    assert "bangs" in rules["hairstyle_only"].required_blocks
    assert "hair_color" in rules["hairstyle_only"].required_blocks
    assert "hair_shape" in rules["scene_only"].forbidden_blocks
    assert "scene" in rules["hairstyle_only"].forbidden_blocks
    assert "styling" in rules["hairstyle_only"].forbidden_blocks
    assert "subject_performance" in rules["hairstyle_only"].forbidden_blocks


def test_build_hairstyle_only_prompt_uses_identity_lock_and_hair_swap_structure():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert hairstyle is not None

    prompt = templates.build_hairstyle_only_prompt(hairstyle)

    assert "只更换图中人物的发型和发色" in prompt
    assert "编辑范围：本次以头发系统编辑为主" in prompt
    assert "轻中度写真级肤质优化与肤色均匀化" in prompt
    assert "主发型结构：发型改为前刺头" in prompt
    assert "刘海系统：" in prompt
    assert "发色系统：发色调整为自然黑" in prompt
    assert "尽量保持原图中的背景、服饰、姿态、表情、构图、镜头距离、光线和氛围不变" in prompt
    assert "负面约束：不要换脸、不要改变性别表达、不要生成第二个人" in prompt


def test_build_scene_only_prompt_locks_existing_hairstyle_and_updates_scene():
    from app.services import templates

    scene = templates.get_scene("morning-window-softlight")

    assert scene is not None

    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert hairstyle is not None

    prompt = templates.build_scene_only_prompt(scene, hairstyle=hairstyle, preferred_gender="male", seed_source="scene-only-lock")

    assert "不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质和发型" in prompt
    assert "忽略原照片中的背景、原服饰、原有动作" in prompt
    assert "发型锁定：" in prompt
    assert "刘海锁定：" in prompt
    assert "发色锁定：" in prompt
    assert "风感约束：" in prompt
    assert "不要二次改色" in prompt
    assert "妆造系统：" in prompt
    assert "场景系统：" in prompt
    assert "人物表现系统：" in prompt
    assert "抬手整理窗边发丝" not in prompt




def test_scene_only_prompt_strengthens_face_and_hair_detail_constraints():
    from app.services import templates

    scene = templates.get_scene("morning-window-softlight")
    hairstyle = templates.get_hairstyle("female-collarbone-xinzhilei")

    assert scene is not None
    assert hairstyle is not None

    prompt = templates.build_scene_only_prompt(
        scene,
        hairstyle=hairstyle,
        preferred_gender="female",
        seed_source="scene-only-quality-detail",
    )

    assert "脸部解析度优先于背景氛围" in prompt
    assert "不要出现低清糊脸、压缩涂抹感、脏噪点或蜡感磨皮" in prompt
    assert "发丝边缘与额头、耳侧、颈侧、衣领的遮挡关系必须准确自然" in prompt

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
        hairstyle=templates.get_hairstyle("male-forward-spikes"),
        preferred_gender="male",
        seed_source="scene-only-male-rule",
    )

    assert "内搭浅色背心或吊带" in female_prompt
    assert "浅灰针织" in male_prompt
    assert female_prompt != male_prompt


def test_scene_only_prompt_assembly_exposes_hair_lock_blocks():
    from app.services import templates

    scene = templates.get_scene("walnut-study-portrait")
    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert scene is not None
    assert hairstyle is not None

    assembly = templates.build_prompt_assembly(
        mode="scene_only",
        hairstyle=hairstyle,
        scene=scene,
        seed_source="scene-only-api-assembly",
    )

    assert assembly.mode == "scene_only"
    assert [block.key for block in assembly.blocks[:7]] == [
        "identity_lock",
        "output_spec",
        "edit_scope",
        "hair_shape_lock",
        "bangs_lock",
        "hair_color_lock",
        "hair_motion_constraint",
    ]
    hair_blocks = [block.text for block in assembly.blocks if block.key == "hair_shape_lock"]
    assert len(hair_blocks) == 1
    assert "保持参考图中静态打理完成的当前主发型结构不变" in hair_blocks[0]
    bangs_blocks = [block.text for block in assembly.blocks if block.key == "bangs_lock"]
    assert len(bangs_blocks) == 1
    motion_blocks = [block.text for block in assembly.blocks if block.key == "hair_motion_constraint"]
    assert len(motion_blocks) == 1
    assert "禁止风力、动作或镜头变化改变主发型结构" in motion_blocks[0]
    hair_color_blocks = [block.text for block in assembly.blocks if block.key == "hair_color_lock"]
    assert len(hair_color_blocks) == 1
    assert "不要二次改色" in hair_color_blocks[0]
    assert any(block.key == "styling" for block in assembly.blocks)
    assert any(block.key == "subject_performance" for block in assembly.blocks)


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
        ["靠在窗台边", "抬手整理窗边发丝", "头部轻微转动让发丝被风掀起", "双手轻握杯子停顿"]
    )

    assert compatible_actions == ["靠在窗台边", "双手轻握杯子停顿"]




def test_rooftop_wind_scene_only_prompt_sanitizes_hair_motion_conflicts():
    from app.services import templates

    scene = templates.get_scene("rooftop-wind")
    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert scene is not None
    assert hairstyle is not None

    prompt = templates.build_scene_only_prompt(
        scene,
        hairstyle=hairstyle,
        preferred_gender="male",
        seed_source="rooftop-wind-lock",
    )

    assert "发型动态是视觉关键" not in prompt
    assert "突出风感发丝" not in prompt
    assert "头部轻微转动让发丝被风掀起" not in prompt
    assert "风感约束：" in prompt
    assert "风主要作用于衣角与空气流动，只允许极少量边缘碎发轻微摆动" in prompt
    assert "禁止风力、动作或镜头变化改变主发型结构" in prompt



def test_scene_only_prompt_ignores_conflicting_subject_action_override():
    from app.services import templates

    scene = templates.get_scene("morning-window-softlight")
    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert scene is not None
    assert hairstyle is not None

    prompt = templates.build_scene_only_prompt(
        scene,
        hairstyle=hairstyle,
        preferred_gender="male",
        seed_source="scene-only-override-sanitize",
        subject_action_override="抬手整理窗边发丝",
    )

    assert "抬手整理窗边发丝" not in prompt
    assert "人物动作固定为" in prompt


def test_scene_only_prompt_sanitizes_dynamic_scene_lighting_language():
    from app.services import templates

    scene = templates.get_scene("dramatic-side-light")
    hairstyle = templates.get_hairstyle("male-forward-spikes")

    assert scene is not None
    assert hairstyle is not None

    prompt = templates.build_scene_only_prompt(
        scene,
        hairstyle=hairstyle,
        preferred_gender="male",
        seed_source="dramatic-side-light-sanitize",
    )

    assert "单侧硬光切过脸部和发型" not in prompt
    assert "发丝纹理被明显勾出" not in prompt
    assert "单侧硬光切过脸部与肩颈轮廓" in prompt

def test_build_prompt_uses_one_subject_action_and_one_compatible_detail_action():
    from app.services import templates

    hairstyle = templates.get_hairstyle("male-forward-spikes")
    scene = templates.get_scene("morning-window-softlight")

    assert hairstyle is not None
    assert scene is not None

    prompt = templates.build_prompt(hairstyle, scene, seed_source="hand-conflict-scene")

    assert "靠在窗台边；抬手整理窗边发丝；双手轻握杯子停顿" not in prompt
    assert "人物表现系统：人物表情固定为" in prompt
    assert "双手抓起顶部卷度" not in prompt


def test_faceprompt_catalog_counts_and_legacy_aliases():
    from app.services import templates

    assert len(templates.SCENES) >= 20
    assert len(templates.HAIRSTYLES) == 56
    assert len(templates.MALE_HAIRSTYLE_PRESETS) == 48
    assert len(templates.STYLINGS) == 7
    assert len([item for item in templates.HAIRSTYLES if item["gender"] == "male"]) == 23
    assert len([item for item in templates.HAIRSTYLES if item["gender"] == "female"]) == 33

    preset = templates.get_male_hairstyle_preset("male-preset-male-american-forward-spike")
    assert preset is not None
    assert preset["name"] == "美式前刺"
    assert preset["structure_id"] == "male-american_forward_spike"

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
        assert upload.json()["detected_hair_color"]["tone_id"]
        upload_id = upload.json()["upload_id"]

        templates = client.get("/api/templates")
        assert templates.status_code == 200
        catalog = templates.json()
        assert len(catalog["hairstyles"]) == 56
        assert len(catalog["scenes"]) == len(template_service.SCENES)
        assert len(catalog["generation_backends"]) == 1
        assert len(catalog["hairstyle_presets_male"]) == 48
        assert len(catalog["hair_colors"]) >= 8
        assert len(catalog["hair_color_techniques"]) >= 5
        assert len(catalog["hair_color_professional_series"]) >= 4
        assert len(catalog["hair_color_professional_options"]) >= 10
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
        assert status_payload["hair_color_tone"]
        assert status_payload["hair_color_tone_label"]
        assert status_payload["hair_color_technique"]
        assert status_payload["hair_color_technique_label"]

        history = client.get("/api/history", headers=headers)
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) == 1
        assert items[0]["job_id"] == job_id
        assert items[0]["hair_preview_url"]
        assert len(items[0]["result_image_urls"]) == 2
        assert items[0]["media_expired"] is False
        assert items[0]["hair_color_tone_label"]

        me = client.get("/api/me", headers=headers)
        assert me.status_code == 200
        me_payload = me.json()
        assert me_payload["user_id"] == login.json()["user_id"]
        assert me_payload["nickname"] == f"微信用户 {login.json()['user_id']}"
        assert me_payload["member_status"] == "内测用户"
        assert me_payload["free_quota_total"] == 1
        assert me_payload["free_quota_used"] == 1
        assert me_payload["free_remaining"] == 0
        assert me_payload["initial_free_remaining"] == 0
        assert me_payload["reward_ad_grant_total"] == 0
        assert me_payload["reward_ad_remaining"] == 0
        assert me_payload["reward_ad_max"] == 2
        assert me_payload["can_unlock_by_ad"] is True
        assert me_payload["paid_remaining"] == 0
        assert me_payload["total_remaining"] == 0
        assert me_payload["monthly_used"] == 1
        assert me_payload["total_jobs"] == 1
        assert me_payload["completed_jobs"] == 1
        assert me_payload["processing_jobs"] == 0
        assert me_payload["remaining_quota"] == 0
        assert me_payload["provider_alerts"] == []

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


def test_me_profile_update_persists_user_nickname(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-profile"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        before = client.get("/api/me", headers=headers)
        assert before.status_code == 200
        assert before.json()["nickname"] == f"微信用户 {login.json()['user_id']}"

        update_profile = client.patch(
            "/api/me/profile",
            headers=headers,
            json={"nickname": "阿晨"},
        )
        assert update_profile.status_code == 200
        assert update_profile.json()["nickname"] == "阿晨"

        after = client.get("/api/me", headers=headers)
        assert after.status_code == 200
        assert after.json()["nickname"] == "阿晨"


def test_upload_validation_allows_when_detector_is_unavailable(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")
    _clear_runtime_caches()

    from app.services import storage

    monkeypatch.setattr(storage, "_detect_faces", lambda image_bytes: None)

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024
    assert metadata.extension == ".png"


def test_upload_validation_still_checks_aspect_ratio_without_face_detection(
    tmp_path, monkeypatch
):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")
    _clear_runtime_caches()

    from app.services import storage

    wide_image = Image.new("RGB", (2400, 800), "#8ecae6")
    buffer = io.BytesIO()
    wide_image.save(buffer, format="PNG")

    with pytest.raises(storage.UploadValidationError) as exc_info:
        storage.validate_upload_bytes(buffer.getvalue(), "image/png")

    assert exc_info.value.code == "bad_aspect_ratio"


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
                "hair_color_tone": "mocha_brown",
                "hair_color_technique": "balayage",
            },
        )

        assert job_create.status_code == 201
        payload = job_create.json()
        assert payload["generator_backend"] == "premium"
        assert payload["aspect_ratio"] == "21:9"
        assert payload["resolution"] == "2K"
        assert payload["hair_color_tone"] == "mocha_brown"
        assert payload["hair_color_tone_label"] == "摩卡棕"
        assert payload["hair_color_technique"] == "balayage"
        assert payload["hair_color_technique_label"] == "手扫染"
        assert payload["hair_color_professional_id"] is None


def test_job_rejects_expired_upload_before_queue(tmp_path, monkeypatch):
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

        from app.db import session_scope, uploads

        with session_scope() as session:
            session.execute(
                update(uploads)
                .where(uploads.c.id == upload_id)
                .values(stored_path="")
            )

        catalog = client.get("/api/templates").json()
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

        assert job_create.status_code == 400
        detail = job_create.json()["detail"]
        assert detail["code"] == "upload_expired"
        assert "重新上传照片" in detail["message"]


def test_job_accepts_professional_hair_color_mapping(tmp_path, monkeypatch):
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
                "hairstyle_id": "female-korean-air-cushion-perm",
                "scene_id": catalog["scenes"][0]["id"],
                "generator_backend": "premium",
                "hair_color_professional_id": "solutor-cool-mist-5-72",
            },
        )

        assert job_create.status_code == 201
        payload = job_create.json()
        assert payload["hair_color_tone"] == "ash_brown"
        assert payload["hair_color_technique"] == "solid"
        assert payload["hair_color_professional_id"] == "solutor-cool-mist-5-72"
        assert payload["hair_color_professional_series_label"] == "烟熏冷雾系列"
    assert payload["hair_color_professional_code"] == "5/72"
    assert payload["hair_color_professional_note"] == "偏灰棕、轻烟熏、低饱和冷雾感"


def test_worker_marks_unhandled_pre_generation_error_as_failed(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        token = login.json()["token"]
        user_id = login.json()["user_id"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("portrait.png", _build_test_image(), "image/png")},
        )
        upload_id = upload.json()["upload_id"]
        catalog = client.get("/api/templates").json()

        from app.db import session_scope, uploads
        from app.services import repository, templates

        with session_scope() as session:
            session.execute(
                update(uploads)
                .where(uploads.c.id == upload_id)
                .values(stored_path="")
            )

        hairstyle = templates.get_hairstyle(catalog["hairstyles"][0]["id"])
        scene = templates.get_scene(catalog["scenes"][0]["id"])
        assert hairstyle is not None
        assert scene is not None

        prompt = templates.build_job_prompt_payload(
            hairstyle,
            scene,
            generator_backend="premium",
            aspect_ratio="3:4",
            resolution="2K",
        )
        job = repository.create_job(
            user_id=user_id,
            upload_id=upload_id,
            hairstyle_id=hairstyle["id"],
            scene_id=scene["id"],
            prompt=prompt,
            model_name="nano_banana_pro+doubao-seedream-4-5-251128",
        )

        client.app.state.job_worker.enqueue(job["id"])

        final_payload = None
        for _ in range(30):
            final_payload = repository.get_job(job["id"])
            assert final_payload is not None
            if final_payload["status"] == "failed":
                break
            time.sleep(0.1)

        assert final_payload is not None
        assert final_payload["status"] == "failed"
        assert final_payload["error_code"] == "worker_exception"
        assert final_payload["error_message"]


def test_generation_quota_and_purchase_flow(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("portrait.png", _build_test_image(), "image/png")},
        )
        assert upload.status_code == 200
        upload_id = upload.json()["upload_id"]

        catalog = client.get("/api/templates").json()
        hairstyle_id = catalog["hairstyles"][0]["id"]
        scene_id = catalog["scenes"][0]["id"]

        me_before = client.get("/api/me", headers=headers)
        assert me_before.status_code == 200
        assert me_before.json()["free_remaining"] == 1
        assert me_before.json()["paid_remaining"] == 0
        assert me_before.json()["total_remaining"] == 1

        for _ in range(1):
            job_create = client.post(
                "/api/jobs",
                headers=headers,
                json={
                    "upload_id": upload_id,
                    "hairstyle_id": hairstyle_id,
                    "scene_id": scene_id,
                    "generator_backend": "premium",
                },
            )
            assert job_create.status_code == 201

        me_exhausted = client.get("/api/me", headers=headers)
        assert me_exhausted.status_code == 200
        assert me_exhausted.json()["free_remaining"] == 0
        assert me_exhausted.json()["reward_ad_remaining"] == 0
        assert me_exhausted.json()["can_unlock_by_ad"] is True
        assert me_exhausted.json()["paid_remaining"] == 0
        assert me_exhausted.json()["total_remaining"] == 0
        assert me_exhausted.json()["remaining_quota"] == 0

        blocked_job = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": hairstyle_id,
                "scene_id": scene_id,
                "generator_backend": "premium",
            },
        )
        assert blocked_job.status_code == 402
        assert blocked_job.json()["detail"]["code"] == "quota_exhausted"

        purchase_catalog = client.get("/api/purchase/catalog")
        assert purchase_catalog.status_code == 200
        purchase_catalog_payload = purchase_catalog.json()
        assert purchase_catalog_payload["payment_enabled"] is True
        catalog_items = purchase_catalog_payload["items"]
        assert len(catalog_items) == 1
        assert catalog_items[0]["product_id"] == "single-generation-pack"
        assert catalog_items[0]["price_cents"] == 100
        assert catalog_items[0]["generation_count"] == 1

        order_create = client.post(
            "/api/purchase/orders",
            headers=headers,
            json={"product_id": catalog_items[0]["product_id"]},
        )
        assert order_create.status_code == 201
        order_payload = order_create.json()
        assert order_payload["status"] == "pending"
        assert order_payload["amount_cents"] == 100
        assert order_payload["amount_label"] == "1 元"

        order_confirm = client.post(
            f"/api/purchase/orders/{order_payload['order_id']}/confirm",
            headers=headers,
        )
        assert order_confirm.status_code == 200
        confirmed_payload = order_confirm.json()
        assert confirmed_payload["status"] == "confirmed"
        assert confirmed_payload["confirmed_at"]

        me_recharged = client.get("/api/me", headers=headers)
        assert me_recharged.status_code == 200
        assert me_recharged.json()["free_remaining"] == 0
        assert me_recharged.json()["paid_remaining"] == 1
        assert me_recharged.json()["total_remaining"] == 1
        assert me_recharged.json()["remaining_quota"] == 1

        paid_job = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": hairstyle_id,
                "scene_id": scene_id,
                "generator_backend": "premium",
            },
        )
        assert paid_job.status_code == 201

        me_after_paid_use = client.get("/api/me", headers=headers)
        assert me_after_paid_use.status_code == 200
        assert me_after_paid_use.json()["paid_remaining"] == 0
        assert me_after_paid_use.json()["total_remaining"] == 0


def test_rewarded_ad_unlock_flow(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-ad-flow"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        upload = client.post(
            "/api/uploads",
            headers=headers,
            files={"file": ("portrait.png", _build_test_image(), "image/png")},
        )
        assert upload.status_code == 200
        upload_id = upload.json()["upload_id"]

        catalog = client.get("/api/templates").json()
        hairstyle_id = catalog["hairstyles"][0]["id"]
        scene_id = catalog["scenes"][0]["id"]

        first_job = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": hairstyle_id,
                "scene_id": scene_id,
                "generator_backend": "premium",
            },
        )
        assert first_job.status_code == 201

        exhausted_me = client.get("/api/me", headers=headers)
        assert exhausted_me.status_code == 200
        assert exhausted_me.json()["total_remaining"] == 0
        assert exhausted_me.json()["can_unlock_by_ad"] is True
        assert exhausted_me.json()["reward_ad_grant_total"] == 0

        session_create = client.post("/api/quota/ad-unlock/session", headers=headers)
        assert session_create.status_code == 200
        session_id = session_create.json()["session_id"]

        claim = client.post(
            "/api/quota/ad-unlock/claim",
            headers=headers,
            json={"session_id": session_id},
        )
        assert claim.status_code == 200
        claim_payload = claim.json()
        assert claim_payload["reward_ad_grant_total"] == 1
        assert claim_payload["reward_ad_remaining"] == 1
        assert claim_payload["total_remaining"] == 1
        assert claim_payload["can_unlock_by_ad"] is False

        duplicate_claim = client.post(
            "/api/quota/ad-unlock/claim",
            headers=headers,
            json={"session_id": session_id},
        )
        assert duplicate_claim.status_code == 409
        assert duplicate_claim.json()["detail"]["code"] == "ad_unlock_session_already_claimed"

        ad_consumed_job = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": hairstyle_id,
                "scene_id": scene_id,
                "generator_backend": "premium",
            },
        )
        assert ad_consumed_job.status_code == 201

        second_session = client.post("/api/quota/ad-unlock/session", headers=headers)
        assert second_session.status_code == 200
        second_claim = client.post(
            "/api/quota/ad-unlock/claim",
            headers=headers,
            json={"session_id": second_session.json()["session_id"]},
        )
        assert second_claim.status_code == 200
        assert second_claim.json()["reward_ad_grant_total"] == 2
        assert second_claim.json()["reward_ad_remaining"] == 1

        second_ad_job = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": hairstyle_id,
                "scene_id": scene_id,
                "generator_backend": "premium",
            },
        )
        assert second_ad_job.status_code == 201

        exhausted_after_ads = client.get("/api/me", headers=headers)
        assert exhausted_after_ads.status_code == 200
        assert exhausted_after_ads.json()["reward_ad_grant_total"] == 2
        assert exhausted_after_ads.json()["reward_ad_remaining"] == 0
        assert exhausted_after_ads.json()["can_unlock_by_ad"] is False

        blocked_session = client.post("/api/quota/ad-unlock/session", headers=headers)
        assert blocked_session.status_code == 409
        assert blocked_session.json()["detail"]["code"] == "reward_ad_limit_reached"


def test_prepare_xunhu_payment_returns_qrcode_session(tmp_path, monkeypatch):
    app = _build_app_with_xunhu_pay(tmp_path, monkeypatch)

    from app.services.xunhu_pay import generate_xunhu_hash

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            payload = {
                "openid": "xh-open-order-001",
                "url_qrcode": "https://api.xunhupay.com/qrcode/demo.png",
                "url": "https://api.xunhupay.com/pay/demo",
                "errcode": 0,
                "errmsg": "success!"
            }
            payload["hash"] = generate_xunhu_hash(payload, "test-xunhu-secret")
            return payload

    def fake_post(url, data=None, timeout=None, follow_redirects=None):
        assert url == "https://api.xunhupay.com/payment/do.html"
        assert data["version"] == "1.1"
        assert data["appid"] == "201906179120"
        assert data["notify_url"].endswith("/api/purchase/xunhu/notify")
        assert data["callback_url"] == "https://api.lcynas.me/payment/retry"
        assert data["return_url"] == "https://api.lcynas.me/payment/success"
        assert data["plugins"] == "AIFaceMiniapp"
        assert data["title"] == "1 次完整生成"
        assert data["total_fee"] == "1"
        assert data["trade_order_id"]
        assert data["nonce_str"]
        assert data["hash"] == generate_xunhu_hash(data, "test-xunhu-secret")
        return _FakeResponse()

    monkeypatch.setattr("app.services.xunhu_pay.httpx.post", fake_post)

    class _FakeGetResponse:
        headers = {"content-type": "image/png"}
        content = b"png-demo"

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, timeout=None, follow_redirects=None):
        assert url == "https://api.xunhupay.com/qrcode/demo.png"
        return _FakeGetResponse()

    monkeypatch.setattr("app.routers.purchase.httpx.get", fake_get)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        catalog_response = client.get("/api/purchase/catalog")
        assert catalog_response.status_code == 200
        catalog_payload = catalog_response.json()
        assert catalog_payload["payment_enabled"] is True
        assert catalog_payload["default_provider"] == "xunhu"
        assert catalog_payload["default_payment_mode"] == "qrcode"

        order_create = client.post(
            "/api/purchase/orders",
            headers=headers,
            json={"product_id": "single-generation-pack"},
        )
        assert order_create.status_code == 201
        order_id = order_create.json()["order_id"]

        pay_prepare = client.post(
            f"/api/purchase/orders/{order_id}/pay",
            headers=headers,
        )
        assert pay_prepare.status_code == 200
        payload = pay_prepare.json()
        assert payload["order"]["status"] == "payment_prepared"
        assert payload["order"]["payment_provider"] == "xunhu"
        assert payload["order"]["payment_mode"] == "qrcode"
        assert payload["order"]["provider_order_id"] == "xh-open-order-001"
        assert payload["payment"]["provider"] == "xunhu"
        assert payload["payment"]["payment_mode"] == "qrcode"
        assert payload["payment"]["qrcode_url"] == "https://api.xunhupay.com/qrcode/demo.png"
        assert payload["payment"]["pay_url"] == "https://api.xunhupay.com/pay/demo"
        assert payload["payment"]["qrcode_download_url"] == f"/api/purchase/orders/{order_id}/qrcode"

        qrcode_response = client.get(
            f"/api/purchase/orders/{order_id}/qrcode",
            headers=headers,
        )
        assert qrcode_response.status_code == 200
        assert qrcode_response.content == b"png-demo"
        assert qrcode_response.headers["content-type"].startswith("image/png")


def test_prepare_wechat_payment_returns_request_payment_params(tmp_path, monkeypatch):
    app, _key_paths = _build_app_with_wechat_pay(tmp_path, monkeypatch)

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"prepay_id": "wx-prepay-001"}

    def fake_post(url, content=None, headers=None, timeout=None):
        assert url == "https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi"
        assert headers is not None
        assert headers["Authorization"].startswith("WECHATPAY2-SHA256-RSA2048 ")
        body = json.loads(content.decode("utf-8"))
        assert body["appid"]
        assert body["mchid"] == "1900001111"
        assert body["notify_url"].endswith("/api/purchase/wechat/notify")
        assert body["payer"]["openid"].startswith("dev_")
        return _FakeResponse()

    monkeypatch.setattr("app.services.wechat_pay.httpx.post", fake_post)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        order_create = client.post(
            "/api/purchase/orders",
            headers=headers,
            json={"product_id": "single-generation-pack"},
        )
        assert order_create.status_code == 201
        order_id = order_create.json()["order_id"]

        pay_prepare = client.post(
            f"/api/purchase/orders/{order_id}/pay",
            headers=headers,
        )
        assert pay_prepare.status_code == 200
        payload = pay_prepare.json()
        assert payload["order"]["status"] == "payment_prepared"
        assert payload["order"]["payment_mode"] == "jsapi"
        assert payload["order"]["wechat_prepay_id"] == "wx-prepay-001"
        assert payload["payment"]["payment_mode"] == "jsapi"
        assert payload["payment"]["provider"] == "wechat_pay"
        assert payload["payment"]["jsapi"]["package"] == "prepay_id=wx-prepay-001"
        assert payload["payment"]["jsapi"]["signType"] == "RSA"
        assert payload["payment"]["jsapi"]["timeStamp"]
        assert payload["payment"]["jsapi"]["nonceStr"]
        assert payload["payment"]["jsapi"]["paySign"]


def test_wechat_payment_notify_confirms_order_and_recharges_quota(tmp_path, monkeypatch):
    app, key_paths = _build_app_with_wechat_pay(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        order_create = client.post(
            "/api/purchase/orders",
            headers=headers,
            json={"product_id": "single-generation-pack"},
        )
        assert order_create.status_code == 201
        order_id = order_create.json()["order_id"]

        me_before = client.get("/api/me", headers=headers)
        assert me_before.status_code == 200
        assert me_before.json()["paid_remaining"] == 0

        notify_headers, notify_body = _build_wechat_notify_payload(
            platform_private_key_path=key_paths["platform_private"],
            api_v3_key=str(key_paths["api_v3_key"]),
            order_id=order_id,
            amount_cents=100,
            transaction_id="4200000000000000009",
        )
        notify_response = client.post(
            "/api/purchase/wechat/notify",
            headers=notify_headers,
            content=notify_body,
        )
        assert notify_response.status_code == 200
        assert notify_response.json() == {"code": "SUCCESS", "message": "成功"}

        order_detail = client.get(f"/api/purchase/orders/{order_id}", headers=headers)
        assert order_detail.status_code == 200
        order_payload = order_detail.json()
        assert order_payload["status"] == "confirmed"
        assert order_payload["wechat_transaction_id"] == "4200000000000000009"
        assert order_payload["confirmed_at"]

        me_after = client.get("/api/me", headers=headers)
        assert me_after.status_code == 200
        assert me_after.json()["paid_remaining"] == 1
        assert me_after.json()["free_remaining"] == 1
        assert me_after.json()["total_remaining"] == 2


def test_xunhu_payment_notify_confirms_order_and_recharges_quota(tmp_path, monkeypatch):
    app = _build_app_with_xunhu_pay(tmp_path, monkeypatch)

    from app.services.xunhu_pay import generate_xunhu_hash

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        order_create = client.post(
            "/api/purchase/orders",
            headers=headers,
            json={"product_id": "single-generation-pack"},
        )
        assert order_create.status_code == 201
        order_id = order_create.json()["order_id"]

        me_before = client.get("/api/me", headers=headers)
        assert me_before.status_code == 200
        assert me_before.json()["paid_remaining"] == 0

        form_payload = {
            "trade_order_id": order_id,
            "total_fee": "1",
            "transaction_id": "txn-demo-001",
            "open_order_id": "xh-order-001",
            "order_title": "1 次完整生成",
            "status": "OD",
            "plugins": "AIFaceMiniapp",
            "attach": "{\"user_id\":1,\"product_id\":\"single-generation-pack\"}",
            "appid": "201906179120"
        }
        form_payload["hash"] = generate_xunhu_hash(form_payload, "test-xunhu-secret")

        notify_response = client.post(
            "/api/purchase/xunhu/notify",
            data=form_payload,
        )
        assert notify_response.status_code == 200
        assert notify_response.text == "success"

        order_detail = client.get(f"/api/purchase/orders/{order_id}", headers=headers)
        assert order_detail.status_code == 200
        order_payload = order_detail.json()
        assert order_payload["status"] == "confirmed"
        assert order_payload["payment_provider"] == "xunhu"
        assert order_payload["provider_order_id"] == "xh-order-001"
        assert order_payload["provider_transaction_id"] == "txn-demo-001"
        assert order_payload["confirmed_at"]

        me_after = client.get("/api/me", headers=headers)
        assert me_after.status_code == 200
        assert me_after.json()["paid_remaining"] == 1
        assert me_after.json()["free_remaining"] == 1
        assert me_after.json()["total_remaining"] == 2


def test_purchase_catalog_returns_empty_items_when_payment_disabled(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    monkeypatch.setenv("PAYMENT_PROVIDER", "xunhu")
    monkeypatch.setenv("PAYMENT_ENABLED", "false")
    _clear_runtime_caches()

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        catalog_response = client.get("/api/purchase/catalog")
        assert catalog_response.status_code == 200
        payload = catalog_response.json()
        assert payload["payment_enabled"] is False
        assert payload["items"] == []

        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        order_create = client.post(
            "/api/purchase/orders",
            headers=headers,
            json={"product_id": "single-generation-pack"},
        )
        assert order_create.status_code == 503
        assert order_create.json()["detail"]["code"] == "payment_disabled"


def test_normalize_hair_color_selection_allows_non_recommended_professional_color(monkeypatch):
    from app.services import templates

    monkeypatch.setattr(
        templates,
        "get_professional_hair_color",
        lambda _professional_id: {
            "id": "solutor-reference-demo",
            "brand": "SOLUTOR",
            "series_type": "base_reference",
            "series_name": "参考基准系列",
            "code": "REF-01",
            "visual_note": "冷调参考棕",
            "hex_estimate": "#6B5446",
            "prompt_alias": "冷调参考棕",
            "mapped_tone_id": "ash_brown",
            "mapped_technique_ids": ["solid"],
            "is_recommended_for_generation": False,
        },
    )

    selection = templates.normalize_hair_color_selection(
        professional_id="solutor-reference-demo",
        strict_professional=True,
    )

    assert selection["professional_id"] == "solutor-reference-demo"
    assert selection["professional_series_label"] == "参考基准系列"
    assert selection["professional_code"] == "REF-01"
    assert selection["tone_id"] == "ash_brown"
    assert selection["technique_id"] == "solid"


def test_job_accepts_male_hairstyle_preset_id(tmp_path, monkeypatch):
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
        preset = catalog["hairstyle_presets_male"][0]
        legacy_male = next(item for item in catalog["hairstyles"] if item["gender"] == "male")
        job_create = client.post(
            "/api/jobs",
            headers=headers,
            json={
                "upload_id": upload_id,
                "hairstyle_id": legacy_male["id"],
                "preset_id": preset["id"],
                "scene_id": catalog["scenes"][0]["id"],
                "generator_backend": "premium",
            },
        )

        assert job_create.status_code == 201
        payload = job_create.json()
        assert payload["preset_id"] == preset["id"]
        assert payload["preset_name"] == preset["name"]
        assert payload["hairstyle_name"] == preset["name"]
        assert payload["hairstyle_id"]


def test_templates_catalog_exposes_plan_specific_output_capabilities(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-test"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        catalog = client.get("/api/templates", headers=headers)
        assert catalog.status_code == 200
        backends = {item["id"]: item for item in catalog.json()["generation_backends"]}
        hair_colors = catalog.json()["hair_colors"]
        hair_color_techniques = catalog.json()["hair_color_techniques"]
        professional_series = catalog.json()["hair_color_professional_series"]
        professional_options = catalog.json()["hair_color_professional_options"]
        assert list(backends.keys()) == ["premium"]
        assert hair_colors[0]["id"] == "natural_black"
        assert hair_colors[0]["allowed_techniques"] == ["solid", "highlight", "earloop"]
        assert hair_color_techniques[0]["id"] == "solid"
        assert professional_series[0]["id"] == "classic_natural"
        assert len(professional_series) >= 9
        assert len(professional_options) >= 80
        assert any(item["id"] == "solutor-cool-mist-5-72" for item in professional_options)
        assert any(item["id"] == "solutor-is-multi-uniform-is-77" for item in professional_options)
        assert backends["premium"]["aspect_ratios"] == [
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
        assert backends["premium"]["resolutions"] == ["2K"]
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
        assert job_basic_4k.status_code == 201
        assert job_basic_4k.json()["generator_backend"] == "premium"
        assert job_basic_4k.json()["resolution"] == "2K"

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

    from app.services.generation import SeedreamGenerator
    from app.services.key_pool import ApiKeyLease

    _clear_runtime_caches()

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

    from app.services.generation import GenerationContext, SeedreamGenerator
    from app.services.key_pool import ApiKeyLease

    _clear_runtime_caches()

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
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-pro-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-pro-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")

    from app.config import get_settings

    _clear_runtime_caches()
    settings = get_settings()

    assert settings.nano_banana_pro_api_key == "new-pro-key"
    assert settings.nano_banana_pro_base_url == "https://example.test/api"
    assert settings.nano_banana_pro_model == "gemini-3-pro-image-preview"
    assert settings.nano_banana_pro_fallback_api_key == "backup-pro-key"
    assert settings.nano_banana_pro_fallback_base_url == "https://backup.example.test"
    assert settings.nano_banana_pro_chat_fallback_api_key == "chat-pro-key"
    assert settings.nano_banana_pro_chat_fallback_base_url == "https://chat.example.test/v1"
    assert settings.nano_banana_pro_chat_fallback_model == "Nano_Banana_Pro_2K_0"
    assert settings.nano_banana_pro_profiles() == (
        (
            "route2",
            "备用路线2",
            "https://chat.example.test/v1",
            "chat-pro-key",
            "openai_chat_markdown",
            "Nano_Banana_Pro_2K_0",
        ),
        (
            "route1",
            "备用路线1",
            "https://backup.example.test",
            "backup-pro-key",
            "gemini_v1beta",
            "gemini-3-pro-image-preview",
        ),
        (
            "primary",
            "主线路",
            "https://example.test/api",
            "new-pro-key",
            "gemini_v1beta",
            "gemini-3-pro-image-preview",
        ),
    )


def test_nano_banana_pro_chat_fallback_model_defaults_to_xais_route_model(
    tmp_path,
    monkeypatch,
):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-pro-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")

    from app.config import get_settings

    _clear_runtime_caches()
    settings = get_settings()

    assert settings.nano_banana_pro_chat_fallback_model == "Nano_Banana_Pro_2K_1"
    assert settings.nano_banana_pro_profiles() == (
        (
            "route2",
            "备用路线2",
            "https://chat.example.test/v1",
            "chat-pro-key",
            "openai_chat_markdown",
            "Nano_Banana_Pro_2K_1",
        ),
    )


def test_nano_banana_generator_uses_native_image_config(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "nano_banana_pro")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "nano-test-key")

    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

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
    assert request_log["json"]["contents"][0]["role"] == "user"
    assert request_log["json"]["generationConfig"]["imageConfig"] == {
        "aspectRatio": "3:4",
        "imageSize": "4K",
    }
    assert request_log["timeout"] == 120
    assert len(previews) == 1
    assert len(result.candidate_image_bytes) == 1


def test_nano_banana_pro_falls_back_to_backup_provider(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")

    import httpx

    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = []

    class FakeSuccessResponse:
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
                                        "data": base64.b64encode(_build_colored_image("#2a9d8f")).decode("utf-8"),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.startswith("https://backup.example.test"):
            return httpx.Response(
                401,
                request=httpx.Request("POST", url),
                json={"error": {"message": "无效的令牌"}},
            )
        return FakeSuccessResponse()

    monkeypatch.setattr("app.services.generation.httpx.post", fake_post)

    generator = NanoBananaProGenerator()
    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test fallback prompt",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="1K",
        ),
    )

    assert len(request_log) == 2
    assert request_log[0]["headers"]["Authorization"] == "Bearer backup-key"
    assert request_log[0]["json"]["contents"][0]["role"] == "user"
    assert request_log[1]["headers"]["Authorization"] == "Bearer primary-key"
    assert request_log[0]["url"].startswith("https://backup.example.test")
    assert result.primary_image_bytes


def test_nano_banana_pro_falls_back_to_chat_provider(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")

    import httpx

    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = []

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.startswith("https://chat.example.test"):
            return httpx.Response(
                503,
                request=httpx.Request("POST", url),
                json={"error": {"message": "upstream unavailable"}},
            )
        if url.startswith("https://backup.example.test"):
            return httpx.Response(
                401,
                request=httpx.Request("POST", url),
                json={"error": {"message": "无效的令牌"}},
            )
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
                                        "data": base64.b64encode(_build_colored_image("#6a994e")).decode("utf-8"),
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
    previews = []
    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test chat fallback prompt",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="1K",
        ),
        on_preview=lambda image_bytes: previews.append(image_bytes),
    )

    assert len(request_log) == 4
    assert request_log[0]["headers"]["Authorization"] == "Bearer chat-key"
    assert request_log[1]["headers"]["Authorization"] == "Bearer chat-key"
    assert request_log[2]["headers"]["Authorization"] == "Bearer backup-key"
    assert request_log[3]["headers"]["Authorization"] == "Bearer primary-key"
    assert request_log[0]["url"] == "https://chat.example.test/v1/chat/completions"
    assert request_log[0]["json"]["model"] == "Nano_Banana_Pro_2K_0"
    assert request_log[0]["json"]["messages"][0]["content"][1]["type"] == "image_url"
    assert request_log[0]["timeout"] == 150
    assert len(previews) == 1
    assert result.primary_image_bytes


def test_nano_banana_pro_skips_chat_retry_after_slow_failure(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")

    import httpx

    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = []
    perf_values = iter([0.0, 11.2])

    def fake_perf_counter():
        return next(perf_values, 11.2)

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.startswith("https://chat.example.test"):
            return httpx.Response(
                503,
                request=httpx.Request("POST", url),
                json={"error": {"message": "upstream unavailable"}},
            )
        if url.startswith("https://backup.example.test"):
            return httpx.Response(
                401,
                request=httpx.Request("POST", url),
                json={"error": {"message": "无效的令牌"}},
            )
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
                                        "data": base64.b64encode(_build_colored_image("#588157")).decode("utf-8"),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.services.generation.httpx.post", fake_post)
    monkeypatch.setattr("app.services.generation.time.perf_counter", fake_perf_counter)

    generator = NanoBananaProGenerator()
    result = generator.generate(
        source_image_path=str(source_path),
        prompt="test slow chat fallback prompt",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="1K",
        ),
    )

    assert len(request_log) == 3
    assert request_log[0]["headers"]["Authorization"] == "Bearer chat-key"
    assert request_log[1]["headers"]["Authorization"] == "Bearer backup-key"
    assert request_log[2]["headers"]["Authorization"] == "Bearer primary-key"
    assert request_log[0]["timeout"] == 150
    assert result.primary_image_bytes


def test_nano_banana_pro_falls_back_when_chat_provider_rejects_role_format(
    tmp_path,
    monkeypatch,
):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")

    import httpx

    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = []

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.startswith("https://chat.example.test"):
            return httpx.Response(
                400,
                request=httpx.Request("POST", url),
                json={"error": {"message": "Please use a valid role: user, model."}},
            )
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
                                        "data": base64.b64encode(_build_colored_image("#386641")).decode("utf-8"),
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
        prompt="test chat role fallback prompt",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="1K",
        ),
    )

    assert len(request_log) == 2
    assert request_log[0]["headers"]["Authorization"] == "Bearer chat-key"
    assert request_log[1]["headers"]["Authorization"] == "Bearer backup-key"
    assert request_log[0]["url"] == "https://chat.example.test/v1/chat/completions"
    assert result.primary_image_bytes


def test_nano_banana_pro_falls_back_when_backup_provider_rejects_role_format(
    tmp_path,
    monkeypatch,
):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.delenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", raising=False)
    monkeypatch.delenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", raising=False)
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")

    import httpx

    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = []

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.startswith("https://backup.example.test"):
            return httpx.Response(
                400,
                request=httpx.Request("POST", url),
                json={"error": {"message": "Please use a valid role: user, model."}},
            )
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
                                        "data": base64.b64encode(_build_colored_image("#4d908e")).decode("utf-8"),
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
        prompt="test backup role fallback prompt",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="1K",
        ),
    )

    assert len(request_log) == 2
    assert request_log[0]["headers"]["Authorization"] == "Bearer backup-key"
    assert request_log[1]["headers"]["Authorization"] == "Bearer primary-key"
    assert result.primary_image_bytes


def test_nano_banana_pro_retryable_route_enters_backoff_and_next_request_skips_it(
    tmp_path,
    monkeypatch,
):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")

    import httpx

    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = []

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.startswith("https://chat.example.test"):
            return httpx.Response(
                503,
                request=httpx.Request("POST", url),
                json={"error": {"message": "upstream unavailable"}},
            )
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
                                        "data": base64.b64encode(_build_colored_image("#577590")).decode("utf-8"),
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
    context = GenerationContext(
        hairstyle_name="前刺短发",
        scene_name="窗边生活感",
        aspect_ratio="3:4",
        resolution="1K",
    )
    first = generator.generate(
        source_image_path=str(source_path),
        prompt="test retryable backoff prompt",
        context=context,
    )
    second = generator.generate(
        source_image_path=str(source_path),
        prompt="test retryable backoff prompt again",
        context=context,
    )

    assert first.primary_image_bytes
    assert second.primary_image_bytes
    assert len(request_log) == 3
    assert request_log[0]["headers"]["Authorization"] == "Bearer chat-key"
    assert request_log[1]["headers"]["Authorization"] == "Bearer backup-key"
    assert request_log[2]["headers"]["Authorization"] == "Bearer backup-key"


def test_nano_banana_pro_quota_exhaustion_adds_alert_and_falls_back(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("NANO_BANANA_PRO_API_KEY", "primary-key")
    monkeypatch.setenv("NANO_BANANA_PRO_BASE_URL", "https://primary.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_API_KEY", "backup-key")
    monkeypatch.setenv("NANO_BANANA_PRO_FALLBACK_BASE_URL", "https://backup.example.test")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_API_KEY", "chat-key")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_BASE_URL", "https://chat.example.test/v1")
    monkeypatch.setenv("NANO_BANANA_PRO_CHAT_FALLBACK_MODEL", "Nano_Banana_Pro_2K_0")

    import httpx

    from app.services import provider_alerts
    from app.services.generation import GenerationContext, NanoBananaProGenerator

    _clear_runtime_caches()

    source_path = tmp_path / "source.png"
    source_path.write_bytes(_build_test_image())

    request_log = []

    def fake_post(url, *, headers=None, json=None, timeout=None):
        request_log.append({"url": url, "headers": headers, "timeout": timeout})
        if url.startswith("https://chat.example.test"):
            return httpx.Response(
                402,
                request=httpx.Request("POST", url),
                json={"error": {"message": "quota exhausted"}},
            )
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
                                        "data": base64.b64encode(_build_colored_image("#2a9d8f")).decode("utf-8"),
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
        prompt="test quota fallback prompt",
        context=GenerationContext(
            hairstyle_name="前刺短发",
            scene_name="窗边生活感",
            aspect_ratio="3:4",
            resolution="2K",
        ),
    )

    assert result.primary_image_bytes
    assert request_log[0]["headers"]["Authorization"] == "Bearer chat-key"
    assert request_log[1]["headers"]["Authorization"] == "Bearer backup-key"
    assert provider_alerts.list_alert_messages() == [
        "Nano Banana Pro 备用路线2额度可能已用完，系统已自动切换到下一条线路。"
    ]


def test_nano_banana_2_generator_uses_native_image_config(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "nano_banana_2")
    monkeypatch.setenv("NANO_BANANA_2_API_KEY", "nano-2-test-key")

    from app.services.generation import GenerationContext, NanoBanana2Generator

    _clear_runtime_caches()

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
    assert request_log["json"]["contents"][0]["role"] == "user"
    assert request_log["json"]["generationConfig"]["imageConfig"] == {
        "aspectRatio": "1:8",
        "imageSize": "512px",
    }
    assert request_log["timeout"] == 40
    assert len(previews) == 1
    assert len(result.candidate_image_bytes) == 1


def test_sora_image_generator_uses_chat_completion_with_reference_image(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "sora_image")
    monkeypatch.setenv("SORA_IMAGE_API_KEY", "sora-test-key")

    from app.services.generation import GenerationContext, SoraImageGenerator

    _clear_runtime_caches()

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


def test_map_nano_http_error_marks_no_available_channel_as_provider_unavailable():
    import httpx

    from app.services.generation import _map_nano_http_error

    response = httpx.Response(
        503,
        request=httpx.Request("POST", "https://example.com/v1beta/models/test:generateContent"),
        json={
            "error": {
                "message": "当前分组 NBPro 下对于模型 gemini-3-pro-image-preview 计费模式 [按次计费] 无可用渠道",
            }
        },
    )

    mapped = _map_nano_http_error(response)

    assert mapped.code == "provider_unavailable"
    assert mapped.retryable is True
    assert mapped.retry_after_seconds == 300


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


def test_settings_filter_ark_keys_by_seedream_model(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEYS", "key-a:alpha,key-b:beta,key-c:gamma")
    monkeypatch.setenv("SEEDREAM_BASIC_MODEL", "doubao-seedream-4-5-251128")
    monkeypatch.setenv("SEEDREAM_PREMIUM_MODEL", "doubao-seedream-5-0-260128")
    monkeypatch.setenv("SEEDREAM_BASIC_ALLOWED_KEY_IDS", "key-a,key-b,key-c")
    monkeypatch.setenv("SEEDREAM_PREMIUM_ALLOWED_KEY_IDS", "key-a")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert [item.key_id for item in settings.ark_api_keys_for_model(settings.seedream_basic_model)] == [
        "key-a",
        "key-b",
        "key-c",
    ]
    assert [item.key_id for item in settings.ark_api_keys_for_model(settings.seedream_premium_model)] == [
        "key-a"
    ]


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


def test_seedream_basic_and_premium_use_isolated_key_pools(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEYS", "key-a:alpha,key-b:beta")
    monkeypatch.setenv("IMAGE_GENERATOR_BACKEND", "seedream")
    monkeypatch.setenv("SEEDREAM_BASIC_MODEL", "doubao-seedream-4-5-251128")
    monkeypatch.setenv("SEEDREAM_PREMIUM_MODEL", "doubao-seedream-5-0-260128")
    _clear_runtime_caches()

    from app.config import get_settings
    from app.services.generation import build_generator
    from app.services.job_queue import JobWorker
    from app.services.key_pool import ApiKeyPool

    settings = get_settings()
    worker = JobWorker(
        build_generator("seedream_premium"),
        key_pool=ApiKeyPool(
            settings.ark_api_keys,
            default_cooldown_seconds=settings.ark_key_cooldown_seconds,
        ),
        concurrency=1,
    )

    basic_generator, basic_pool = worker._resolve_runtime(
        "seedream",
        model_name=settings.seedream_basic_model,
    )
    premium_generator, premium_pool = worker._resolve_runtime(
        "seedream",
        model_name=settings.seedream_premium_model,
    )

    assert basic_pool is not None
    assert premium_pool is not None
    assert basic_pool is not premium_pool
    assert basic_generator.model_name == settings.seedream_basic_model
    assert premium_generator.model_name == settings.seedream_premium_model

    premium_lease = premium_pool.acquire(timeout=0.1)
    assert premium_lease is not None
    premium_pool.disable_key(premium_lease.key_id, reason="set_limit_exceeded")

    assert premium_pool.active_size == 1
    assert basic_pool.active_size == 2


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


def test_upload_validation_allows_when_detector_is_unavailable_without_runtime_fixture(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "_detect_faces", lambda _: None)

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024


def test_upload_validation_rejects_image_without_detected_face(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "_detect_faces", lambda _: ())

    with pytest.raises(storage.UploadValidationError) as exc_info:
        storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert exc_info.value.code == "face_not_detected"


def test_upload_validation_rejects_when_face_is_too_small(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "_detect_faces", lambda _: ((40, 60, 48, 52),))

    with pytest.raises(storage.UploadValidationError) as exc_info:
        storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert exc_info.value.code == "face_too_small"


def test_upload_validation_accepts_multiple_faces_without_blocking(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    get_settings.cache_clear()
    monkeypatch.setattr(
        storage,
        "_detect_faces",
        lambda _: ((120, 140, 180, 220), (420, 150, 170, 210)),
    )

    metadata = storage.validate_upload_bytes(_build_test_image(), "image/png")

    assert metadata.width == 768
    assert metadata.height == 1024


def test_upload_validation_accepts_male2_with_haar_fallback(monkeypatch):
    monkeypatch.setenv("ENFORCE_FACE_DETECTION", "true")

    from app.config import get_settings
    from app.services import storage

    if storage.cv2 is None:
        pytest.skip("opencv is unavailable")

    get_settings.cache_clear()
    monkeypatch.setattr(storage, "mp", None)

    metadata = storage.validate_upload_bytes(_load_asset_image_bytes("male2.jpg"), "image/jpeg")

    assert metadata.width == 768
    assert metadata.height == 1024
    assert metadata.extension == ".jpg"


def test_detect_faces_returns_prominent_face_for_male2(monkeypatch):
    from app.services import storage

    if storage.cv2 is None:
        pytest.skip("opencv is unavailable")

    monkeypatch.setattr(storage, "mp", None)

    image_bytes = _load_asset_image_bytes("male2.jpg")
    faces = storage._detect_faces(image_bytes)

    assert faces
    with Image.open(io.BytesIO(image_bytes)) as image:
        width, height = image.size

    normalized_faces = storage._normalize_detected_faces(faces, width, height)

    assert normalized_faces
    assert any(storage._is_upload_face_usable(face, width, height) for face in normalized_faces)


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
    assert payload["items"][0]["job_id"] is None


def test_showcases_endpoint_prefers_shared_history_scene_images(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    _clear_runtime_caches()

    from app.config import get_settings
    from app.db import init_db
    from app.main import create_app
    from app.services import repository, storage, templates

    settings = get_settings()
    settings.ensure_directories()
    init_db()

    user = repository.get_or_create_user("og-curated-user")
    source_bytes = _build_colored_image("#8ecae6")
    upload_path = storage.save_upload_file(source_bytes, ".png")
    upload = repository.create_upload(
        user_id=user["id"],
        original_name="showcase-source.png",
        stored_path=upload_path,
        mime_type="image/png",
        file_size=len(source_bytes),
        width=768,
        height=1024,
    )
    hairstyle = templates.resolve_male_hairstyle_preset("male-preset-male-messy-forward-spike-mod-messy-texture")
    scene = templates.get_scene("walnut-study-portrait")
    assert hairstyle is not None
    assert scene is not None
    prompt = templates.build_job_prompt_payload(
        hairstyle,
        scene,
        generator_backend="premium",
        aspect_ratio="3:4",
        resolution="2K",
        hair_color_tone_id="honey_brown",
        hair_color_technique_id="solid",
        seed_source="showcase-history-test",
    )
    job = repository.create_job(
        user_id=user["id"],
        upload_id=upload["id"],
        hairstyle_id=hairstyle["resolved_hairstyle_id"],
        scene_id=scene["id"],
        prompt=prompt,
        model_name="showcase-test-model",
    )
    storage.save_hair_preview_result(job["id"], _build_colored_image("#264653"))
    result_path = storage.save_scene_result(job["id"], _build_colored_image("#2a9d8f"), index=1)
    storage.save_scene_result(job["id"], _build_colored_image("#e76f51"), index=2)
    repository.update_job_status(
        job["id"],
        status="succeeded",
        result_path=result_path,
    )

    monkeypatch.setattr(
        templates,
        "get_fixed_showcase_jobs",
        lambda: [
            {
                "job_id": job["id"],
                "title": "固定精选示例",
                "summary": "固定历史成片",
            }
        ],
    )

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/templates/showcases")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    first_item = payload["items"][0]
    assert first_item["job_id"] == job["id"]
    assert f"/media/results/{job['id']}/scene-1" in first_item["cover_url"]
    assert first_item["scene_cover_url"] != first_item["cover_url"]
    assert first_item["preset_id"] == "male-preset-male-messy-forward-spike-mod-messy-texture"
    assert first_item["scene_id"] == "walnut-study-portrait"
    assert first_item["hair_color_tone"] == "honey_brown"
    assert first_item["hair_color_technique"] == "solid"
    assert first_item["title"] == "固定精选示例"
    assert first_item["summary"] == "固定历史成片"


def test_retention_keeps_fixed_showcase_job_media(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="true")
    _clear_runtime_caches()

    from app.config import get_settings
    from app.db import init_db, jobs as jobs_table, session_scope
    from app.services import repository, retention, storage, templates

    settings = get_settings()
    settings.ensure_directories()
    init_db()

    user = repository.get_or_create_user("og-fixed-showcase-user")
    source_bytes = _build_colored_image("#8ecae6")
    upload_path = storage.save_upload_file(source_bytes, ".png")
    upload = repository.create_upload(
        user_id=user["id"],
        original_name="fixed-showcase-source.png",
        stored_path=upload_path,
        mime_type="image/png",
        file_size=len(source_bytes),
        width=768,
        height=1024,
    )
    job = repository.create_job(
        user_id=user["id"],
        upload_id=upload["id"],
        hairstyle_id="male-forward-spikes",
        scene_id="walnut-study-portrait",
        prompt="{}",
        model_name="retention-test-model",
    )
    result_path = storage.save_scene_result(job["id"], _build_colored_image("#2a9d8f"), index=1)
    repository.update_job_status(job["id"], status="succeeded", result_path=result_path)
    scene_path = settings.storage_dir / f"results/{job['id']}/scene-1.png"
    assert scene_path.exists()

    expired_created_at = (
        datetime.now(timezone.utc) - timedelta(days=30)
    ).replace(microsecond=0).isoformat()
    with session_scope() as session:
        session.execute(
            update(jobs_table)
            .where(jobs_table.c.id == job["id"])
            .values(created_at=expired_created_at, updated_at=expired_created_at)
        )

    monkeypatch.setattr(
        templates,
        "get_fixed_showcase_job_ids",
        lambda: [job["id"]],
    )
    monkeypatch.setattr(
        templates,
        "get_fixed_showcase_jobs",
        lambda: [{"job_id": job["id"], "title": "", "summary": ""}],
    )

    result = retention.purge_expired_media(force=True)

    assert result["jobs"] == 0
    assert scene_path.exists()


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


def test_templates_hair_color_reference_pdf_download(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.get('/api/templates/hair-color-reference.pdf')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/pdf')
    assert len(response.content) > 1024
    assert response.content.startswith(b'%PDF')
    cached_path = tmp_path / 'storage' / 'reference_docs' / 'solugtor-hair-color-with-rgb-reference-latest.pdf'
    assert cached_path.exists()
    assert cached_path.read_bytes().startswith(b'%PDF')


def test_templates_hair_color_reference_link_returns_fixed_static_url(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.get('/api/templates/hair-color-reference-link')

    assert response.status_code == 200
    payload = response.json()
    assert payload['filename'] == 'solugtor-hair-color-with-rgb-reference-latest.pdf'
    assert payload['url'] == 'http://testserver/static/reference_docs/solugtor-hair-color-with-rgb-reference-latest.pdf'
    assert payload['static_url'] == 'http://testserver/static/reference_docs/solugtor-hair-color-with-rgb-reference-latest.pdf'
    assert payload['api_url'] == 'http://testserver/api/templates/hair-color-reference.pdf'


def test_templates_hair_color_reference_static_url_download(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.get('/static/reference_docs/solugtor-hair-color-with-rgb-reference-latest.pdf')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/pdf')
    assert response.content.startswith(b'%PDF')


def _create_feedback_ready_job_for_user(
    *,
    user_id: int,
    created_at: str,
    status_name: str = "succeeded",
) -> dict:
    from app.db import jobs, session_scope, uploads
    from app.services import repository, storage

    source_bytes = _build_colored_image("#8ecae6")
    upload_path = storage.save_upload_file(source_bytes, ".png")
    upload = repository.create_upload(
        user_id=user_id,
        original_name="feedback-source.png",
        stored_path=upload_path,
        mime_type="image/png",
        file_size=len(source_bytes),
        width=768,
        height=1024,
    )
    job = repository.create_job(
        user_id=user_id,
        upload_id=upload["id"],
        hairstyle_id="male-forward-spikes",
        scene_id="morning-window-softlight",
        prompt="feedback prompt",
        model_name="feedback-model",
    )

    result_path = None
    if status_name == "succeeded":
        storage.save_hair_preview_result(job["id"], _build_colored_image("#264653"))
        result_path = storage.save_scene_result(job["id"], _build_colored_image("#2a9d8f"), index=1)
        storage.save_scene_result(job["id"], _build_colored_image("#e76f51"), index=2)

    repository.update_job_status(
        job["id"],
        status=status_name,
        result_path=result_path,
        error_code=None if status_name == "succeeded" else "mock_failed",
        error_message=None if status_name == "succeeded" else "mock failed",
    )

    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    updated_at = (created_dt + timedelta(seconds=10)).replace(microsecond=0).isoformat()
    with session_scope() as session:
        session.execute(
            update(uploads)
            .where(uploads.c.id == upload["id"])
            .values(created_at=created_at)
        )
        session.execute(
            update(jobs)
            .where(jobs.c.id == job["id"])
            .values(
                created_at=created_at,
                updated_at=updated_at,
                completed_at=updated_at if status_name == "succeeded" else None,
            )
        )

    return job


def test_feedback_pending_and_submission_flow(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-feedback-user"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        user_id = login.json()["user_id"]

        first_job = _create_feedback_ready_job_for_user(
            user_id=user_id,
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )

        pending_response = client.get(
            f"/api/feedback/pending?job_id={first_job['id']}",
            headers=headers,
        )
        assert pending_response.status_code == 200
        pending_payload = pending_response.json()
        assert pending_payload["pending"] is True
        assert pending_payload["survey_type"] == "first_success"
        assert pending_payload["trigger_completed_jobs"] == 1
        assert pending_payload["success_ordinal"] == 1

        submission_response = client.post(
            "/api/feedback/submissions",
            headers=headers,
            json={
                "job_id": first_job["id"],
                "survey_type": "first_success",
                "hairstyle_expectation": "met",
                "hair_color_satisfaction": "satisfied",
                "scene_satisfaction": "neutral",
                "wait_time_feeling": "acceptable",
                "image_clarity_satisfaction": "clear",
                "ui_usability": "easy",
                "improvement_suggestion": "期待发型细节再自然一些",
            },
        )
        assert submission_response.status_code == 201
        submission_payload = submission_response.json()
        assert submission_payload["survey_type"] == "first_success"
        assert submission_payload["trigger_completed_jobs"] == 1

        duplicate_submission = client.post(
            "/api/feedback/submissions",
            headers=headers,
            json={
                "job_id": first_job["id"],
                "survey_type": "first_success",
                "hairstyle_expectation": "met",
                "hair_color_satisfaction": "satisfied",
                "scene_satisfaction": "satisfied",
                "wait_time_feeling": "acceptable",
                "image_clarity_satisfaction": "clear",
                "ui_usability": "easy",
            },
        )
        assert duplicate_submission.status_code == 409

        pending_after_submit = client.get(
            f"/api/feedback/pending?job_id={first_job['id']}",
            headers=headers,
        )
        assert pending_after_submit.status_code == 200
        pending_after_submit_payload = pending_after_submit.json()
        assert pending_after_submit_payload["pending"] is False
        assert pending_after_submit_payload["survey_type"] is None


def test_feedback_pending_only_on_first_and_fourth_success(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/api/auth/wechat/login", json={"code": "dev-feedback-ordinal"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        user_id = login.json()["user_id"]
        base_time = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)

        first_job = _create_feedback_ready_job_for_user(
            user_id=user_id,
            created_at=base_time.isoformat(),
        )
        second_job = _create_feedback_ready_job_for_user(
            user_id=user_id,
            created_at=(base_time + timedelta(minutes=5)).isoformat(),
        )
        third_job = _create_feedback_ready_job_for_user(
            user_id=user_id,
            created_at=(base_time + timedelta(minutes=10)).isoformat(),
        )
        fourth_job = _create_feedback_ready_job_for_user(
            user_id=user_id,
            created_at=(base_time + timedelta(minutes=15)).isoformat(),
        )
        failed_job = _create_feedback_ready_job_for_user(
            user_id=user_id,
            created_at=(base_time + timedelta(minutes=20)).isoformat(),
            status_name="failed",
        )

        first_pending = client.get(
            f"/api/feedback/pending?job_id={first_job['id']}",
            headers=headers,
        )
        assert first_pending.status_code == 200
        assert first_pending.json()["survey_type"] == "first_success"

        second_pending = client.get(
            f"/api/feedback/pending?job_id={second_job['id']}",
            headers=headers,
        )
        assert second_pending.status_code == 200
        second_pending_payload = second_pending.json()
        assert second_pending_payload["pending"] is False
        assert second_pending_payload["survey_type"] is None

        third_pending = client.get(
            f"/api/feedback/pending?job_id={third_job['id']}",
            headers=headers,
        )
        assert third_pending.status_code == 200
        third_pending_payload = third_pending.json()
        assert third_pending_payload["pending"] is False
        assert third_pending_payload["survey_type"] is None

        fourth_pending = client.get(
            f"/api/feedback/pending?job_id={fourth_job['id']}",
            headers=headers,
        )
        assert fourth_pending.status_code == 200
        fourth_payload = fourth_pending.json()
        assert fourth_payload["pending"] is True
        assert fourth_payload["survey_type"] == "fourth_success"
        assert fourth_payload["trigger_completed_jobs"] == 4
        assert fourth_payload["success_ordinal"] == 4

        failed_pending = client.get(
            f"/api/feedback/pending?job_id={failed_job['id']}",
            headers=headers,
        )
        assert failed_pending.status_code == 200
        failed_pending_payload = failed_pending.json()
        assert failed_pending_payload["pending"] is False
        assert failed_pending_payload["survey_type"] is None
