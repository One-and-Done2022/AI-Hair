from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMPLATE_PIPELINE_SCRIPT = ROOT_DIR / "scripts" / "template_image_pipeline.py"
REVIEW_TEMPLATE_PIPELINE_SCRIPT = ROOT_DIR / "scripts" / "review_template_image_pipeline.py"


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


def _clear_runtime_caches() -> None:
    from app.config import get_settings
    from app.db import get_engine, get_session_factory
    from app.services.storage import get_object_storage

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_object_storage.cache_clear()


def test_template_image_pipeline_processes_scene_template_and_generates_review_bundle(
    tmp_path,
    monkeypatch,
):
    _configure_runtime_env(tmp_path, monkeypatch)
    _clear_runtime_caches()

    template_pipeline = _load_module(TEMPLATE_PIPELINE_SCRIPT, "template_image_pipeline")
    template_pipeline._load_backend_dependencies()
    from app.services.generation import GenerationResult

    class FakeGenerator:
        supports_key_pool = False

        def generate(self, source_image_path, prompt, context, provider_key=None):
            assert Path(source_image_path).exists()
            assert "人物发型：保持参考图中已经生成完成的发型不变" in prompt
            return GenerationResult(
                primary_image_bytes=_build_test_image("#264653"),
                candidate_image_bytes=[_build_test_image("#264653")],
            )

    monkeypatch.setattr(template_pipeline, "build_generator", lambda backend=None: FakeGenerator())

    review_root = tmp_path / "review"
    sample_root = tmp_path / "assets"
    sample_root.mkdir()
    male_sample = sample_root / "male.jpg"
    female_sample = sample_root / "female.jpg"
    male_sample.write_bytes(_build_test_image("#6fa8dc"))
    female_sample.write_bytes(_build_test_image("#f4c2c2"))

    scene = template_pipeline.templates.get_scene("morning-window-softlight")
    assert scene is not None

    package_dir = template_pipeline.process_template(
        category="scenes",
        template=scene,
        review_root=review_root,
        sample_images={"male": male_sample, "female": female_sample},
        generator_backend="seedream",
        aspect_ratio="3:4",
        resolution="4K",
    )

    assert package_dir.exists()
    assert (package_dir / "template_snapshot.json").exists()
    assert (package_dir / "prompt.txt").exists()
    assert (package_dir / "review_male.png").exists()
    assert (package_dir / "review_female.png").exists()

    metadata = json.loads((package_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "pending_review"
    assert metadata["category"] == "scenes"
    assert metadata["template_id"] == scene["id"]
    assert metadata["recommended_cover"]["gender"] == "female"
    assert metadata["review_checklist"]["cover_ready"] == "yes"


def test_template_image_pipeline_hairstyle_prompt_adds_white_background_cover_suffix():
    template_pipeline = _load_module(
        TEMPLATE_PIPELINE_SCRIPT,
        "template_image_pipeline_hairstyle_cover",
    )
    template_pipeline._load_backend_dependencies()
    hairstyle = template_pipeline.templates.get_hairstyle("male-forward-spikes")
    assert hairstyle is not None

    prompt_mode, prompt = template_pipeline._build_template_prompt("hairstyles", hairstyle)

    assert prompt_mode == "hairstyle_only"
    assert "换发目标：只更换图中人物的发型为：前刺头" in prompt
    assert "官方发型模板封面图" in prompt
    assert "背景必须保持纯白或接近纯白的干净影棚白底" in prompt
    assert "适合前端模板卡片展示" in prompt


def test_scene_template_uses_scene_sample_image_ids_when_no_gender_override():
    template_pipeline = _load_module(
        TEMPLATE_PIPELINE_SCRIPT,
        "template_image_pipeline_scene_sample_ids",
    )
    template_pipeline._load_backend_dependencies()

    scene = template_pipeline.templates.get_scene("city-neon-night")
    assert scene is not None

    female2 = Path("/tmp/female2.jpg")
    male1 = Path("/tmp/male1.jpg")
    selected = template_pipeline._selected_samples_for_template(
        "scenes",
        scene,
        {
            "female2": female2,
            "male1": male1,
        },
    )

    assert selected == {
        "female": female2,
        "male": male1,
    }


def test_review_template_image_pipeline_approve_updates_hairstyle_catalog_and_moves_package(
    tmp_path,
    monkeypatch,
):
    review_pipeline = _load_module(
        REVIEW_TEMPLATE_PIPELINE_SCRIPT,
        "review_template_image_pipeline",
    )

    review_root = tmp_path / "review"
    approved_root = tmp_path / "approved"
    package_dir = review_root / "hairstyles" / "male-forward-spikes"
    package_dir.mkdir(parents=True)
    (package_dir / "template_snapshot.json").write_text(
        json.dumps(
            {
                "id": "male-forward-spikes",
                "name": "前刺头",
                "gender": "male",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (package_dir / "metadata.json").write_text(
        json.dumps(
            {
                "status": "pending_review",
                "review_results": {
                    "male": {"status": "succeeded", "image": "review_male.png"},
                },
                "recommended_cover": {"gender": "male", "image": "review_male.png"},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (package_dir / "review_male.png").write_bytes(_build_test_image("#264653"))

    male_catalog_path = tmp_path / "hairstyles_male.json"
    male_catalog_path.write_text(
        json.dumps(
            [
                {
                    "id": "male-forward-spikes",
                    "gender": "male",
                    "title": "前刺头",
                    "styleLine": "realistic_editorial",
                    "summary": "测试模板",
                    "promptCore": "发型改为前刺头",
                    "detailTags": ["清爽"],
                    "constraints": ["顶部保留刺感"],
                    "pairingAdvice": ["晨光窗边"],
                    "shotAdvice": "3:4 竖构图",
                    "expressionAction": ["看镜头微抬下巴"],
                    "controlProfile": {
                        "windLevel": "still",
                        "humidityLook": "balanced",
                        "backgroundComplexity": "low",
                        "lightingHardness": "soft",
                        "mirrorRisk": "none",
                        "compatibleSceneTags": [],
                        "recommendedSceneIds": [],
                    },
                    "referenceNotes": "测试",
                    "referenceSourceIds": ["test"],
                    "categoryKey": "clean_short",
                    "categoryLabel": "清爽短发",
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    female_catalog_path = tmp_path / "hairstyles_female.json"
    female_catalog_path.write_text("[]\n", encoding="utf-8")

    sync_calls = []
    monkeypatch.setattr(review_pipeline, "HAIRSTYLES_MALE_CATALOG_PATH", male_catalog_path)
    monkeypatch.setattr(review_pipeline, "HAIRSTYLES_FEMALE_CATALOG_PATH", female_catalog_path)
    monkeypatch.setattr(review_pipeline, "run_sync", lambda restart=False: sync_calls.append(restart))
    monkeypatch.setattr(
        review_pipeline,
        "_load_backend_dependencies",
        lambda: setattr(
            review_pipeline,
            "storage",
            type(
                "FakeStorage",
                (),
                {
                    "save_template_asset": staticmethod(
                        lambda category, template_id, image_bytes: f"template_assets/{category}/{template_id}.png"
                    )
                },
            )(),
        ),
    )

    destination = review_pipeline.approve_template_package(
        category="hairstyles",
        template_id="male-forward-spikes",
        review_root=review_root,
        approved_root=approved_root,
        sync=True,
        restart=True,
        note="封面样片可用",
    )

    assert destination == approved_root / "hairstyles" / "male-forward-spikes"
    assert destination.exists()
    assert not package_dir.exists()
    assert sync_calls == [True]

    updated_catalog = json.loads(male_catalog_path.read_text(encoding="utf-8"))
    assert updated_catalog[0]["coverImagePath"] == "template_assets/hairstyles/male-forward-spikes.png"
    assert updated_catalog[0]["coverImageSource"] == "template_image_pipeline:review_male.png"

    approved_metadata = json.loads((destination / "metadata.json").read_text(encoding="utf-8"))
    assert approved_metadata["status"] == "approved"
    assert approved_metadata["approved_cover_image"] == "review_male.png"
    assert approved_metadata["approved_cover_path"] == "template_assets/hairstyles/male-forward-spikes.png"
    assert approved_metadata["review_notes"] == "封面样片可用"


def test_review_template_image_pipeline_reject_moves_package_with_reason(tmp_path):
    review_pipeline = _load_module(
        REVIEW_TEMPLATE_PIPELINE_SCRIPT,
        "review_template_image_pipeline_reject",
    )

    review_root = tmp_path / "review"
    rejected_root = tmp_path / "rejected"
    package_dir = review_root / "scenes" / "morning-window-softlight"
    package_dir.mkdir(parents=True)
    (package_dir / "metadata.json").write_text(
        json.dumps({"status": "pending_review"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    destination = review_pipeline.reject_template_package(
        category="scenes",
        template_id="morning-window-softlight",
        reason="样片风格不稳定",
        review_root=review_root,
        rejected_root=rejected_root,
        note="先不入库",
    )

    assert destination == rejected_root / "scenes" / "morning-window-softlight"
    assert destination.exists()
    assert not package_dir.exists()
    metadata = json.loads((destination / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "rejected"
    assert metadata["rejected_reason"] == "样片风格不稳定"
    assert metadata["review_notes"] == "先不入库"
