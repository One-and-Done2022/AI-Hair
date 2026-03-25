from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SCENE_PIPELINE_SCRIPT = ROOT_DIR / "scripts" / "scene_pipeline.py"
REVIEW_PIPELINE_SCRIPT = ROOT_DIR / "scripts" / "review_scene_pipeline.py"
ADD_SCENE_DRAFT_SCRIPT = ROOT_DIR / "scripts" / "add_scene_draft.py"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_image(color: str = "#ffd6e0") -> bytes:
    image = Image.new("RGB", (768, 1024), color)
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
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "vision-test-key")


def _clear_runtime_caches() -> None:
    from app.config import get_settings
    from app.db import get_engine, get_session_factory
    from app.services.storage import get_object_storage

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_object_storage.cache_clear()


def test_scene_pipeline_processes_inbox_item_and_generates_review_bundle(tmp_path, monkeypatch):
    _configure_runtime_env(tmp_path, monkeypatch)
    _clear_runtime_caches()

    scene_pipeline = _load_module(SCENE_PIPELINE_SCRIPT, "scene_pipeline")
    scene_pipeline._load_backend_dependencies()
    from app.services.generation import GenerationResult
    from app.services.image_understanding import SceneUnderstandingResult

    inbox_dir = tmp_path / "inbox"
    review_root = tmp_path / "review"
    sample_root = tmp_path / "assets"
    inbox_dir.mkdir()
    sample_root.mkdir()

    source_path = inbox_dir / "green-reference.png"
    source_path.write_bytes(_build_test_image("#98c379"))
    male_sample = sample_root / "male.jpg"
    female_sample = sample_root / "female.jpg"
    male_sample.write_bytes(_build_test_image("#6fa8dc"))
    female_sample.write_bytes(_build_test_image("#f4c2c2"))

    class FakeImageUnderstandingService:
        def extract_scene_blocks(self, image_bytes: bytes):
            assert image_bytes
            return SceneUnderstandingResult(
                blocks={
                    "shot": "3:4 竖构图，胸口以上近景，平视镜头。",
                    "scene_environment": "绿色植物虚化的户外场景，背景干净。",
                    "scene_lighting": "通透自然光从侧前方进入，发丝边缘有柔和高光。",
                    "scene_mood": "清新、轻盈、松弛。",
                    "expression": "自然看向镜头。",
                    "subject_action": "轻微侧身停顿。",
                    "outfit": "浅色上衣。",
                    "scene_constraints": "背景植物需要虚化；不要引入第二个人。",
                },
                raw_response='{"ok": true}',
                model_name="gemini-3-pro-preview",
            )

    class FakeGenerator:
        supports_key_pool = False

        def generate(self, source_image_path, prompt, context, provider_key=None, on_preview=None):
            assert Path(source_image_path).exists()
            assert "人物发型：保持参考图中已经生成完成的发型不变" in prompt
            image_bytes = _build_test_image("#264653")
            return GenerationResult(
                primary_image_bytes=image_bytes,
                candidate_image_bytes=[image_bytes],
            )

    monkeypatch.setattr(scene_pipeline, "ImageUnderstandingService", FakeImageUnderstandingService)
    monkeypatch.setattr(scene_pipeline, "build_generator", lambda backend=None: FakeGenerator())

    package_dir = scene_pipeline.process_inbox_item(
        source_path=source_path,
        review_root=review_root,
        sample_images={
            "male": male_sample,
            "female": female_sample,
        },
        generator_backend="seedream",
        aspect_ratio="3:4",
        resolution="4K",
    )

    assert package_dir.exists()
    assert not source_path.exists()
    assert (package_dir / "source.png").exists()
    assert (package_dir / "blocks.json").exists()
    assert (package_dir / "scene_draft.json").exists()
    assert (package_dir / "scene_only_prompt.txt").exists()
    assert (package_dir / "review_male.png").exists()
    assert (package_dir / "review_female.png").exists()

    metadata = json.loads((package_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "pending_review"
    assert metadata["scene_title"]
    assert metadata["image_understanding_model"] == "gemini-3-pro-preview"
    assert metadata["review_results"]["male"]["status"] == "succeeded"
    assert metadata["review_results"]["female"]["status"] == "succeeded"


def test_review_scene_pipeline_approve_moves_package_and_appends_catalog(tmp_path, monkeypatch):
    review_pipeline = _load_module(REVIEW_PIPELINE_SCRIPT, "review_scene_pipeline")
    add_scene_draft = _load_module(ADD_SCENE_DRAFT_SCRIPT, "add_scene_draft")

    review_root = tmp_path / "review"
    approved_root = tmp_path / "approved"
    review_package = review_root / "window-softlight-demo"
    review_package.mkdir(parents=True)

    scene_payload = {
        "id": "window-softlight-demo",
        "title": "窗边自然光人像",
        "styleLine": "realistic_editorial",
        "summary": "窗边自然光与留白背景构成稳定的人像场景。",
        "environment": "室内留白墙面与木质家具背景，窗边区域干净克制。",
        "lighting": "窗边柔和自然光从侧前方进入，整体亮部通透。",
        "styleMood": "安静、松弛、生活感高级。",
        "detailTags": ["室内", "窗边", "自然光"],
        "expressions": ["温和看向镜头"],
        "actions": ["靠坐在椅子上轻微侧身"],
        "outfitHints": ["米白色针织上衣"],
        "pairingAdvice": ["法式慵懒卷", "蓬松锁骨发"],
        "shotAdvice": "3:4 竖构图，胸口以上近景，平视镜头。",
        "constraints": ["背景保持简洁留白", "不要加入复杂前景"],
        "controlProfile": {
            "windLevel": "still",
            "humidityLook": "balanced",
            "backgroundComplexity": "low",
            "lightingHardness": "soft",
            "mirrorRisk": "none",
            "compatibleHairstyleTags": ["lifestyle_softlight"],
            "recommendedHairstyleIds": [],
        },
        "referenceNotes": "内部审核通过。",
        "referenceSourceIds": ["scene-pipeline"],
    }
    (review_package / "scene_draft.json").write_text(
        json.dumps(scene_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (review_package / "metadata.json").write_text(
        json.dumps({"status": "pending_review"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    catalog_path = tmp_path / "scenes.json"
    catalog_path.write_text("[]\n", encoding="utf-8")
    sync_calls = []

    fake_module = SimpleNamespace(
        DEFAULT_CATALOG_PATH=catalog_path,
        append_scene_draft=add_scene_draft.append_scene_draft,
        run_sync=lambda restart=False: sync_calls.append(restart),
    )
    monkeypatch.setattr(review_pipeline, "load_add_scene_draft_module", lambda: fake_module)

    destination = review_pipeline.approve_scene_package(
        scene_id="window-softlight-demo",
        review_root=review_root,
        approved_root=approved_root,
        sync=True,
        restart=True,
    )

    assert destination == approved_root / "window-softlight-demo"
    assert destination.exists()
    assert not review_package.exists()
    saved_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert len(saved_catalog) == 1
    assert saved_catalog[0]["id"] == "window-softlight-demo"
    approved_metadata = json.loads((destination / "metadata.json").read_text(encoding="utf-8"))
    assert approved_metadata["status"] == "approved"
    assert sync_calls == [True]


def test_review_scene_pipeline_reject_moves_package_with_reason(tmp_path):
    review_pipeline = _load_module(REVIEW_PIPELINE_SCRIPT, "review_scene_pipeline_reject")

    review_root = tmp_path / "review"
    rejected_root = tmp_path / "rejected"
    review_package = review_root / "green-outdoor-demo"
    review_package.mkdir(parents=True)
    (review_package / "metadata.json").write_text(
        json.dumps({"status": "pending_review"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    destination = review_pipeline.reject_scene_package(
        scene_id="green-outdoor-demo",
        reason="场景不稳定，审核图效果不达标",
        review_root=review_root,
        rejected_root=rejected_root,
    )

    assert destination == rejected_root / "green-outdoor-demo"
    assert destination.exists()
    assert not review_package.exists()
    rejected_metadata = json.loads((destination / "metadata.json").read_text(encoding="utf-8"))
    assert rejected_metadata["status"] == "rejected"
    assert rejected_metadata["rejected_reason"] == "场景不稳定，审核图效果不达标"
