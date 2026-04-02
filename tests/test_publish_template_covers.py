from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "scripts" / "publish_template_covers.py"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_publish_scene_covers_uses_single_mapped_gender_and_syncs_once(tmp_path, monkeypatch):
    publish = _load_module(SCRIPT_PATH, "publish_template_covers_scene")

    male_sample = tmp_path / "male2.jpg"
    female_sample = tmp_path / "female3.jpg"
    male_sample.write_bytes(b"male")
    female_sample.write_bytes(b"female")

    process_calls = []
    approve_calls = []
    sync_calls = []

    fake_template_pipeline = SimpleNamespace(
        _load_backend_dependencies=lambda: None,
        templates=SimpleNamespace(
            SCENES=[
                {
                    "id": "indoor-film-lifestyle",
                    "cover_image_path": "",
                    "cover_image_source": "",
                },
                {
                    "id": "city-neon-night",
                    "cover_image_path": "",
                    "cover_image_source": "",
                },
            ],
            HAIRSTYLES=[],
        ),
        process_template=lambda **kwargs: process_calls.append(kwargs),
    )
    fake_review_pipeline = SimpleNamespace(
        approve_template_package=lambda **kwargs: approve_calls.append(kwargs),
        run_sync=lambda restart=False: sync_calls.append(restart),
    )

    monkeypatch.setattr(
        publish,
        "DEFAULT_SAMPLE_IMAGES",
        {"male2": male_sample, "female3": female_sample},
    )
    monkeypatch.setattr(publish, "template_pipeline", fake_template_pipeline)
    monkeypatch.setattr(publish, "review_pipeline", fake_review_pipeline)

    result = publish.publish_category(
        category="scenes",
        selected_ids=set(),
        only_unpublished=True,
        backend="seedream",
        aspect_ratio="3:4",
        resolution="2K",
        review_root=tmp_path / "review",
        approved_root=tmp_path / "approved",
        restart=True,
        note="scene covers",
    )

    assert result == {
        "category": "scenes",
        "processed": 2,
        "approved": 2,
        "failed": [],
    }
    assert len(process_calls) == 2
    assert list(process_calls[0]["sample_images"].keys()) == ["female"]
    assert list(process_calls[1]["sample_images"].keys()) == ["male"]
    assert approve_calls[0]["cover_gender"] == "female"
    assert approve_calls[1]["cover_gender"] == "male"
    assert sync_calls == [True]


def test_publish_hairstyle_covers_only_processes_unpublished_or_draft_items(tmp_path, monkeypatch):
    publish = _load_module(SCRIPT_PATH, "publish_template_covers_hairstyles")

    male_sample = tmp_path / "male2.jpg"
    female_sample = tmp_path / "female3.jpg"
    male_sample.write_bytes(b"male")
    female_sample.write_bytes(b"female")

    process_calls = []
    approve_calls = []
    sync_calls = []

    fake_template_pipeline = SimpleNamespace(
        _load_backend_dependencies=lambda: None,
        templates=SimpleNamespace(
            SCENES=[],
            HAIRSTYLES=[
                {
                    "id": "male-forward-spikes",
                    "gender": "male",
                    "cover_image_path": "template_assets/hairstyles/male-forward-spikes.jpg",
                    "cover_image_source": "template_image_pipeline:review_male.jpg",
                },
                {
                    "id": "male-fade-buzz",
                    "gender": "male",
                    "cover_image_path": "template_assets/hairstyles/male-fade-buzz.jpg",
                    "cover_image_source": "draft_pending_render",
                },
                {
                    "id": "female-audrey-short",
                    "gender": "female",
                    "cover_image_path": "",
                    "cover_image_source": "",
                },
            ],
        ),
        process_template=lambda **kwargs: process_calls.append(kwargs),
    )
    fake_review_pipeline = SimpleNamespace(
        approve_template_package=lambda **kwargs: approve_calls.append(kwargs),
        run_sync=lambda restart=False: sync_calls.append(restart),
    )

    monkeypatch.setattr(
        publish,
        "DEFAULT_SAMPLE_IMAGES",
        {"male2": male_sample, "female3": female_sample},
    )
    monkeypatch.setattr(publish, "template_pipeline", fake_template_pipeline)
    monkeypatch.setattr(publish, "review_pipeline", fake_review_pipeline)

    result = publish.publish_category(
        category="hairstyles",
        selected_ids=set(),
        only_unpublished=True,
        backend="nano_banana_2",
        aspect_ratio="3:4",
        resolution="2K",
        review_root=tmp_path / "review",
        approved_root=tmp_path / "approved",
        restart=False,
        note="hair covers",
    )

    assert result == {
        "category": "hairstyles",
        "processed": 2,
        "approved": 2,
        "failed": [],
    }
    assert [call["template"]["id"] for call in process_calls] == [
        "male-fade-buzz",
        "female-audrey-short",
    ]
    assert list(process_calls[0]["sample_images"].keys()) == ["male"]
    assert list(process_calls[1]["sample_images"].keys()) == ["female"]
    assert [call["cover_gender"] for call in approve_calls] == ["male", "female"]
    assert sync_calls == [False]
