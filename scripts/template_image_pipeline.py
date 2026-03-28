#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_REVIEW_ROOT = ROOT_DIR / "storage" / "template_image_pipeline" / "review"
DEFAULT_SAMPLE_IMAGES = {
    "female1": ROOT_DIR / "assets" / "female1.jpg",
    "female2": ROOT_DIR / "assets" / "female2.jpg",
    "female3": ROOT_DIR / "assets" / "female3.jpg",
    "male1": ROOT_DIR / "assets" / "male1.jpg",
    "male2": ROOT_DIR / "assets" / "male2.jpg",
    "male3": ROOT_DIR / "assets" / "male3.jpg",
}
DEFAULT_ASPECT_RATIO = "3:4"
DEFAULT_RESOLUTION = "4K"
DEFAULT_BACKEND = "seedream"
SUPPORTED_CATEGORIES = {"hairstyles", "scenes"}
HAIRSTYLE_COVER_WHITE_BG_SUFFIX = (
    "用于官方发型模板封面图。"
    "背景必须保持纯白或接近纯白的干净影棚白底，不要加入任何场景元素、道具、文字、水印或装饰。"
    "人物保持胸口以上近景、居中、正面或轻微偏正面构图，服饰维持简洁浅色上衣即可，不要夸张改动。"
    "画面重点只展示发型轮廓、刘海、顶部体积、两侧结构与发尾细节，整体干净、标准、适合前端模板卡片展示。"
)
DEFAULT_HAIRSTYLE_SAMPLE_IDS = {
    "female": "female3",
    "male": "male2",
}

get_settings = None
GenerationContext = None
ImageGenerationError = None
build_generator = None
ApiKeyPool = None
templates = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_backend_dependencies() -> None:
    global get_settings
    global GenerationContext
    global ImageGenerationError
    global build_generator
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
    from app.services.key_pool import ApiKeyPool as _ApiKeyPool
    from app.services import templates as _templates

    get_settings = _get_settings
    GenerationContext = _GenerationContext
    ImageGenerationError = _ImageGenerationError
    build_generator = _build_generator
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


def _save_review_image(package_dir: Path, gender: str, image_bytes: bytes) -> str:
    extension = _detect_result_extension(image_bytes)
    filename = f"review_{gender}{extension}"
    destination = package_dir / filename
    destination.write_bytes(image_bytes)
    return filename


def _generate_review_image(
    *,
    category: str,
    template_name: str,
    source_image_path: Path,
    prompt: str,
    sample_label: str,
    aspect_ratio: str,
    resolution: str,
    generator_backend: str,
):
    _load_backend_dependencies()
    generator = build_generator(generator_backend)
    context = GenerationContext(
        hairstyle_name=template_name if category == "hairstyles" else f"官方示例{sample_label}",
        scene_name=template_name if category == "scenes" else f"官方示例{sample_label}",
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        hairstyle_only_prompt=prompt if category == "hairstyles" else "",
        scene_only_prompt=prompt if category == "scenes" else "",
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
                key_pool.release_error(lease.key_id, cooldown_seconds=exc.retry_after_seconds)
            raise
        else:
            key_pool.release_success(lease.key_id)
            return result

    return generator.generate(
        source_image_path=str(source_image_path),
        prompt=prompt,
        context=context,
    )


def _build_review_metadata(
    *,
    category: str,
    template: dict[str, Any],
    prompt_mode: str,
    generator_backend: str,
    prompt: str,
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
    preferred_genders = ("female", "male") if category == "scenes" else (template.get("gender"),)
    for gender in preferred_genders:
        candidate = review_results.get(gender or "")
        if candidate and candidate.get("status") == "succeeded" and candidate.get("image"):
            recommended_cover = {
                "gender": gender,
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
        "category": category,
        "template_id": template["id"],
        "template_name": template["name"],
        "prompt_mode": prompt_mode,
        "generator_backend": generator_backend,
        "sample_assets": source_asset_paths,
        "review_results": review_results,
        "recommended_cover": recommended_cover,
        "review_notes": "",
        "review_checklist": {
            "identity_stable": "pending",
            "physical_logic_ok": "pending",
            "template_readability": "pending",
            "cover_ready": "yes" if recommended_cover else "no",
        },
        "prompt_excerpt": prompt[:280],
    }


def _resolve_templates(category: str, selected_ids: set[str]) -> list[dict]:
    _load_backend_dependencies()
    if category == "hairstyles":
        items = templates.HAIRSTYLES
    elif category == "scenes":
        items = templates.SCENES
    else:  # pragma: no cover
        raise ValueError(f"unsupported category: {category}")

    if not selected_ids:
        return list(items)
    return [item for item in items if item["id"] in selected_ids]


def _selected_samples_for_template(
    category: str,
    template: dict[str, Any],
    sample_images: dict[str, Path],
) -> dict[str, Path]:
    if category == "scenes":
        selected: dict[str, Path] = {}
        for gender in ("female", "male"):
            direct_override = sample_images.get(gender)
            if direct_override is not None:
                selected[gender] = direct_override
                continue
            sample_image_id = templates.resolve_scene_sample_image_id(
                template,
                gender,
                seed_source=f"{template['id']}:template-cover:{gender}",
            )
            if not sample_image_id:
                continue
            sample_path = sample_images.get(sample_image_id)
            if sample_path is None:
                raise FileNotFoundError(
                    f"找不到官方示例人物图：{sample_image_id}（scene={template['id']} gender={gender}）"
                )
            selected[gender] = sample_path
        return selected
    gender = str(template.get("gender") or "").strip()
    sample_path = sample_images.get(gender)
    if sample_path is None:
        fallback_asset_id = DEFAULT_HAIRSTYLE_SAMPLE_IDS.get(gender, "")
        sample_path = sample_images.get(fallback_asset_id)
    if not sample_path:
        raise FileNotFoundError(f"找不到 {gender} 对应的官方示例人物图")
    return {gender: sample_path}


def _build_template_prompt(category: str, template: dict[str, Any]) -> tuple[str, str]:
    if category == "hairstyles":
        base_prompt = templates.build_hairstyle_only_prompt(template)
        prompt = f"{base_prompt}\n{HAIRSTYLE_COVER_WHITE_BG_SUFFIX}"
        return "hairstyle_only", prompt
    if category == "scenes":
        prompt = templates.build_scene_only_prompt(
            template,
            seed_source=f"{template['id']}:template-cover",
        )
        return "scene_only", prompt
    raise ValueError(f"unsupported category: {category}")


def process_template(
    *,
    category: str,
    template: dict[str, Any],
    review_root: Path,
    sample_images: dict[str, Path],
    generator_backend: str,
    aspect_ratio: str,
    resolution: str,
) -> Path:
    _load_backend_dependencies()
    package_dir = review_root / category / template["id"]
    if package_dir.exists():
        raise FileExistsError(f"审核包目录已存在：{package_dir}")
    _ensure_dir(package_dir)

    prompt_mode, prompt = _build_template_prompt(category, template)

    (package_dir / "template_snapshot.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (package_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    selected_samples = _selected_samples_for_template(category, template, sample_images)
    review_results: dict[str, dict[str, Any]] = {}
    source_asset_paths: dict[str, str] = {}

    for gender, sample_path in selected_samples.items():
        source_asset_paths[gender] = str(sample_path)
        if not sample_path.exists():
            review_results[gender] = {
                "status": "failed",
                "error": f"找不到示例人物图：{sample_path}",
            }
            continue

        try:
            generation_result = _generate_review_image(
                category=category,
                template_name=template["name"],
                source_image_path=sample_path,
                prompt=prompt,
                sample_label="男生" if gender == "male" else "女生",
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                generator_backend=generator_backend,
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

    metadata = _build_review_metadata(
        category=category,
        template=template,
        prompt_mode=prompt_mode,
        generator_backend=generator_backend,
        prompt=prompt,
        review_results=review_results,
        source_asset_paths=source_asset_paths,
    )
    _write_json(package_dir / "metadata.json", metadata)
    return package_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量生成模板真实样片审核包。")
    parser.add_argument("category", choices=sorted(SUPPORTED_CATEGORIES), help="模板类型。")
    parser.add_argument("--review-root", default=str(DEFAULT_REVIEW_ROOT), help="审核包输出目录。")
    parser.add_argument("--ids", default="", help="逗号分隔的模板 id 列表；为空表示全部。")
    parser.add_argument("--limit", type=int, default=0, help="限制本次最多处理多少个模板。0 表示不限制。")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="用于生成样片的后端。")
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, help="模板样片画幅。")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="模板样片清晰度。")
    parser.add_argument(
        "--assets-dir",
        default=str(ROOT_DIR / "assets"),
        help="官方示例人物图目录，默认使用 assets/female1~3.jpg 和 assets/male1~3.jpg。",
    )
    parser.add_argument("--male-image", default="", help="手工指定男生示例人物图路径，优先级高于自动选择。")
    parser.add_argument("--female-image", default="", help="手工指定女生示例人物图路径，优先级高于自动选择。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _load_backend_dependencies()

    review_root = Path(args.review_root).expanduser().resolve()
    _ensure_dir(review_root)

    selected_ids = {
        item.strip()
        for item in args.ids.split(",")
        if item.strip()
    }
    templates_to_process = _resolve_templates(args.category, selected_ids)
    if args.limit > 0:
        templates_to_process = templates_to_process[: args.limit]

    if not templates_to_process:
        print("没有匹配到需要处理的模板。")
        return 0

    assets_dir = Path(args.assets_dir).expanduser().resolve()
    sample_images = {
        asset_id: assets_dir / f"{asset_id}.jpg" for asset_id in DEFAULT_SAMPLE_IMAGES
    }
    if args.male_image.strip():
        sample_images["male"] = Path(args.male_image).expanduser().resolve()
    if args.female_image.strip():
        sample_images["female"] = Path(args.female_image).expanduser().resolve()

    failures: list[str] = []
    for template in templates_to_process:
        try:
            package_dir = process_template(
                category=args.category,
                template=template,
                review_root=review_root,
                sample_images=sample_images,
                generator_backend=args.backend,
                aspect_ratio=args.aspect_ratio,
                resolution=args.resolution,
            )
            print(f"已生成模板审核包：{package_dir}")
        except Exception as exc:
            failures.append(f"{template['id']}: {exc}")

    if failures:
        for item in failures:
            print(f"[template_image_pipeline] {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
