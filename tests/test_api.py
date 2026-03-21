from __future__ import annotations

import io
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
    prompt = templates.build_prompt(hairstyle, scene, seed_source="job-fixture")
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
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")

    from app.config import get_settings
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
        ):
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

    _clear_runtime_caches()
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
    _configure_runtime_env(tmp_path, monkeypatch, use_mock_generator="false")
    monkeypatch.setenv("ARK_API_KEY", "test-key")

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

    def fake_collect(self, *, client, prompt, image_data, max_images, on_first_candidate=None):
        call_log.append(("collect", max_images))
        if on_first_candidate is not None:
            on_first_candidate(preview_image)
            preview_events.append("preview")
        return [preview_image]

    def fake_top_up(
        self,
        *,
        client,
        prompt,
        image_data,
        existing_count,
        on_first_candidate=None,
    ):
        call_log.append(("top_up", existing_count))
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

    assert call_log == [("collect", 1), ("top_up", 1)]
    assert preview_events == ["callback", "preview"]
    assert len(result.candidate_image_bytes) == 3


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
            third = _build_colored_image("#e9c46a")
            if on_preview is not None:
                on_preview(first)
            return GenerationResult(
                primary_image_bytes=first,
                candidate_image_bytes=[first, second, third],
            )

    worker = JobWorker(
        FailoverGenerator(),
        key_pool=ApiKeyPool(
            fixture["settings"].ark_api_keys,
            default_cooldown_seconds=fixture["settings"].ark_key_cooldown_seconds,
        ),
        concurrency=1,
    )

    worker._process(fixture["job"]["id"])

    job = repository.get_job(fixture["job"]["id"])
    assert job is not None
    assert call_order == ["key-a", "key-b"]
    assert job["status"] == "succeeded"
    assert job["assigned_key_id"] == "key-b"
    assert len(storage.list_result_candidates(job["id"], job["result_path"])) == 3


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
            third = _build_colored_image("#e9c46a")
            if on_preview is not None:
                on_preview(first)
            return GenerationResult(
                primary_image_bytes=first,
                candidate_image_bytes=[first, second, third],
            )

    worker = JobWorker(
        DisableThenFallbackGenerator(),
        key_pool=key_pool,
        concurrency=1,
    )

    worker._process(fixture["job"]["id"])

    job = repository.get_job(fixture["job"]["id"])
    assert job is not None
    assert call_order == ["key-a", "key-b"]
    assert job["status"] == "succeeded"
    assert job["assigned_key_id"] == "key-b"
    assert key_pool.is_disabled("key-a") is True
    assert key_pool.active_size == 1
    assert len(storage.list_result_candidates(job["id"], job["result_path"])) == 3


def test_job_worker_keeps_preview_result_when_error_happens_after_preview(
    tmp_path, monkeypatch
):
    fixture = _create_job_fixture(
        tmp_path,
        monkeypatch,
        ark_api_keys="key-a:alpha,key-b:beta",
    )

    from app.services import repository, storage
    from app.services.generation import ImageGenerationError
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
        ):
            assert provider_key is not None
            call_order.append(provider_key.key_id)
            preview = _build_colored_image("#264653")
            if on_preview is not None:
                on_preview(preview)
            raise ImageGenerationError(
                "rate_limited",
                "provider busy after preview",
                retryable=True,
                retry_after_seconds=1,
            )

    worker = JobWorker(
        PreviewThenFailGenerator(),
        key_pool=ApiKeyPool(
            fixture["settings"].ark_api_keys,
            default_cooldown_seconds=fixture["settings"].ark_key_cooldown_seconds,
        ),
        concurrency=1,
    )

    worker._process(fixture["job"]["id"])

    job = repository.get_job(fixture["job"]["id"])
    assert job is not None
    assert call_order == ["key-a"]
    assert job["status"] == "succeeded"
    assert job["assigned_key_id"] == "key-a"
    assert len(storage.list_result_candidates(job["id"], job["result_path"])) == 1


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
