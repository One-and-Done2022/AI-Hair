#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_INBOX_DIR = ROOT_DIR / "storage" / "scene_pipeline" / "inbox"
DEFAULT_REVIEW_DIR = ROOT_DIR / "storage" / "scene_pipeline" / "review"
DEFAULT_SAMPLE_IMAGES = {
    "male": ROOT_DIR / "assets" / "male.jpg",
    "female": ROOT_DIR / "assets" / "female.jpg",
}
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_ASPECT_RATIO = "3:4"
DEFAULT_RESOLUTION = "4K"
DEFAULT_BACKEND = "seedream"

get_settings = None
GenerationContext = None
ImageGenerationError = None
build_generator = None
ImageUnderstandingService = None
SceneDraftOptions = None
build_scene_draft = None
ApiKeyPool = None
templates = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_backend_dependencies() -> None:
    global get_settings
    global GenerationContext
    global ImageGenerationError
    global build_generator
    global ImageUnderstandingService
    global SceneDraftOptions
    global build_scene_draft
    global ApiKeyPool
    global templates

    if get_settings is not None:
        return

    from app.config import get_settings as _get_settings
    from app.services.generation import (
        GenerationContext as _GenerationContext,
        ImageGenerationError as _ImageGenerationError,
        build_generator as _build_generator,
    )
    from app.services.image_understanding import (
        ImageUnderstandingService as _ImageUnderstandingService,
        SceneDraftOptions as _SceneDraftOptions,
        build_scene_draft as _build_scene_draft,
    )
    from app.services.key_pool import ApiKeyPool as _ApiKeyPool
    from app.services import templates as _templates

    get_settings = _get_settings
    GenerationContext = _GenerationContext
    ImageGenerationError = _ImageGenerationError
    build_generator = _build_generator
    ImageUnderstandingService = _ImageUnderstandingService
    SceneDraftOptions = _SceneDraftOptions
    build_scene_draft = _build_scene_draft
    ApiKeyPool = _ApiKeyPool
    templates = _templates


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _detect_result_extension(image_bytes: bytes) -> str:
    try:
        from io import BytesIO
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as image:
            image_format = (image.format or "").lower()
    except Exception:
        image_format = "png"

    if image_format in {"jpeg", "jpg"}:
        return ".jpg"
    if image_format == "webp":
        return ".webp"
    return ".png"


def list_inbox_images(inbox_dir: Path) -> list[Path]:
    if not inbox_dir.exists():
        return []
    return sorted(
        path
        for path in inbox_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def _load_add_scene_draft_module():
    import importlib.util

    module_path = ROOT_DIR / "scripts" / "add_scene_draft.py"
    spec = importlib.util.spec_from_file_location("add_scene_draft", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 add_scene_draft.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_review_metadata(
    *,
    source_name: str,
    scene_draft: dict[str, Any],
    image_understanding_model: str,
    generator_backend: str,
    review_results: dict[str, dict[str, Any]],
    source_asset_paths: dict[str, str],
) -> dict[str, Any]:
    all_succeeded = review_results and all(
        item.get("status") == "succeeded" for item in review_results.values()
    )
    any_succeeded = any(item.get("status") == "succeeded" for item in review_results.values())
    if all_succeeded:
        status = "pending_review"
    elif any_succeeded:
        status = "partial_review"
    else:
        status = "failed"

    recommended_cover: dict[str, Any] | None = None
    for preferred_gender in ("female", "male"):
        candidate = review_results.get(preferred_gender)
        if candidate and candidate.get("status") == "succeeded" and candidate.get("image"):
            recommended_cover = {
                "gender": preferred_gender,
                "image": candidate["image"],
            }
            break
    if recommended_cover is None:
        for gender, candidate in review_results.items():
            if candidate.get("status") == "succeeded" and candidate.get("image"):
                recommended_cover = {
                    "gender": gender,
                    "image": candidate["image"],
                }
                break

    return {
        "version": 1,
        "status": status,
        "created_at": utc_now(),
        "source_name": source_name,
        "scene_id": scene_draft["id"],
        "scene_title": scene_draft["title"],
        "image_understanding_model": image_understanding_model,
        "generator_backend": generator_backend,
        "sample_assets": source_asset_paths,
        "review_results": review_results,
        "recommended_cover": recommended_cover,
        "review_notes": "",
        "review_checklist": {
            "scene_scope_clean": "pending",
            "identity_stable": "pending",
            "physical_logic_ok": "pending",
            "cover_ready": "yes" if recommended_cover else "no",
        },
    }


def _save_review_image(package_dir: Path, gender: str, image_bytes: bytes) -> str:
    extension = _detect_result_extension(image_bytes)
    filename = f"review_{gender}{extension}"
    destination = package_dir / filename
    destination.write_bytes(image_bytes)
    return filename


def _generate_review_image(
    *,
    generator_backend: str,
    source_image_path: Path,
    prompt: str,
    scene_title: str,
    sample_label: str,
    aspect_ratio: str,
    resolution: str,
):
    _load_backend_dependencies()
    generator = build_generator(generator_backend)
    context = GenerationContext(
        hairstyle_name=f"官方示例{sample_label}",
        scene_name=scene_title,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        scene_only_prompt=prompt,
    )

    if getattr(generator, "supports_key_pool", False):
        settings = get_settings()
        if not settings.ark_api_keys:
            raise ImageGenerationError("missing_api_key", "当前没有可用的 Ark API key。")
        key_pool = ApiKeyPool(
            settings.ark_api_keys,
            default_cooldown_seconds=settings.ark_key_cooldown_seconds,
        )
        lease = key_pool.acquire(timeout=1.0)
        if lease is None:
            raise ImageGenerationError("no_available_key", "当前没有可用的 Seedream key。")
        try:
            result = generator.generate(
                source_image_path=str(source_image_path),
                prompt=prompt,
                context=context,
                provider_key=lease,
            )
        except ImageGenerationError as exc:
            if exc.disable_key:
                key_pool.disable_key(lease.key_id, reason=exc.code)
            else:
                key_pool.release_error(
                    lease.key_id,
                    cooldown_seconds=exc.retry_after_seconds,
                )
            raise
        else:
            key_pool.release_success(lease.key_id)
            return result

    return generator.generate(
        source_image_path=str(source_image_path),
        prompt=prompt,
        context=context,
    )


def process_inbox_item(
    *,
    source_path: Path,
    review_root: Path,
    sample_images: dict[str, Path],
    generator_backend: str = DEFAULT_BACKEND,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    resolution: str = DEFAULT_RESOLUTION,
) -> Path:
    _load_backend_dependencies()
    source_bytes = source_path.read_bytes()
    understanding_service = ImageUnderstandingService()
    understanding_result = understanding_service.extract_scene_blocks(source_bytes)
    scene_draft = build_scene_draft(
        understanding_result.blocks,
        options=SceneDraftOptions(
            reference_source_ids=("scene-pipeline",),
            reference_notes=(
                "由内部 scene pipeline 自动拆解并生成审核图，"
                "请人工确认审核图效果后再决定是否加入官方场景库"
            ),
        ),
    )
    scene_template = templates.build_scene_template_from_record(scene_draft)
    scene_id = scene_draft["id"]
    package_dir = review_root / scene_id
    if package_dir.exists():
        raise ValueError(f"审核包目录已存在：{package_dir}")

    _ensure_dir(package_dir)
    moved_source_path = package_dir / f"source{source_path.suffix.lower()}"
    shutil.move(str(source_path), moved_source_path)

    prompt = templates.build_scene_only_prompt(
        scene_template,
        seed_source=f"{scene_id}:review",
    )
    (package_dir / "blocks.json").write_text(
        json.dumps(understanding_result.blocks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (package_dir / "scene_draft.json").write_text(
        json.dumps(scene_draft, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (package_dir / "scene_only_prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    (package_dir / "raw_model_response.txt").write_text(
        understanding_result.raw_response.strip() + "\n",
        encoding="utf-8",
    )

    review_results: dict[str, dict[str, Any]] = {}
    source_asset_paths: dict[str, str] = {}
    for gender, sample_path in sample_images.items():
        source_asset_paths[gender] = str(sample_path)
        if not sample_path.exists():
            review_results[gender] = {
                "status": "failed",
                "error": f"找不到示例人物图：{sample_path}",
            }
            continue

        try:
            generation_result = _generate_review_image(
                generator_backend=generator_backend,
                source_image_path=sample_path,
                prompt=prompt,
                scene_title=scene_template["name"],
                sample_label="男生" if gender == "male" else "女生",
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )
            filename = _save_review_image(
                package_dir,
                gender,
                generation_result.primary_image_bytes,
            )
            review_results[gender] = {
                "status": "succeeded",
                "image": filename,
            }
        except Exception as exc:
            review_results[gender] = {
                "status": "failed",
                "error": str(exc),
            }

    metadata = build_review_metadata(
        source_name=source_path.name,
        scene_draft=scene_draft,
        image_understanding_model=understanding_result.model_name,
        generator_backend=generator_backend,
        review_results=review_results,
        source_asset_paths=source_asset_paths,
    )
    _write_json(package_dir / "metadata.json", metadata)
    return package_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="扫描 inbox 场景图并生成内部审核包。")
    parser.add_argument("--inbox", default=str(DEFAULT_INBOX_DIR), help="场景参考图入箱目录。")
    parser.add_argument("--review-root", default=str(DEFAULT_REVIEW_DIR), help="审核包输出目录。")
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        help="用于审核图生成的后端，默认 seedream。",
    )
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, help="审核图画幅。")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="审核图清晰度。")
    parser.add_argument("--limit", type=int, default=0, help="限制本次最多处理多少张图。0 表示不限制。")
    parser.add_argument(
        "--sample-genders",
        default="male,female",
        help="要生成审核图的示例人物，逗号分隔，默认 male,female。",
    )
    parser.add_argument("--male-image", default=str(DEFAULT_SAMPLE_IMAGES["male"]), help="男生示例人物图路径。")
    parser.add_argument("--female-image", default=str(DEFAULT_SAMPLE_IMAGES["female"]), help="女生示例人物图路径。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _load_backend_dependencies()

    inbox_dir = Path(args.inbox).expanduser().resolve()
    review_root = Path(args.review_root).expanduser().resolve()
    _ensure_dir(inbox_dir)
    _ensure_dir(review_root)

    gender_items = [item.strip() for item in args.sample_genders.split(",") if item.strip()]
    sample_images: dict[str, Path] = {}
    for gender in gender_items:
        if gender == "male":
            sample_images[gender] = Path(args.male_image).expanduser().resolve()
        elif gender == "female":
            sample_images[gender] = Path(args.female_image).expanduser().resolve()
        else:
            parser.error(f"不支持的 sample gender: {gender}")

    source_images = list_inbox_images(inbox_dir)
    if args.limit > 0:
        source_images = source_images[: args.limit]

    if not source_images:
        print("inbox 中没有待处理的场景参考图。")
        return 0

    failures: list[str] = []
    for source_path in source_images:
        try:
            package_dir = process_inbox_item(
                source_path=source_path,
                review_root=review_root,
                sample_images=sample_images,
                generator_backend=args.backend,
                aspect_ratio=args.aspect_ratio,
                resolution=args.resolution,
            )
            print(f"已生成审核包：{package_dir}")
        except Exception as exc:
            failures.append(f"{source_path.name}: {exc}")

    if failures:
        for item in failures:
            print(f"[scene_pipeline] {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
