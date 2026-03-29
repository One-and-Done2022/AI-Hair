#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


TEMPLATE_PIPELINE_PATH = ROOT_DIR / "scripts" / "template_image_pipeline.py"
REVIEW_PIPELINE_PATH = ROOT_DIR / "scripts" / "review_template_image_pipeline.py"

DEFAULT_SAMPLE_IMAGES = {
    "female1": ROOT_DIR / "assets" / "female1.jpg",
    "female2": ROOT_DIR / "assets" / "female2.jpg",
    "female3": ROOT_DIR / "assets" / "female3.jpg",
    "male1": ROOT_DIR / "assets" / "male1.jpg",
    "male2": ROOT_DIR / "assets" / "male2.jpg",
    "male3": ROOT_DIR / "assets" / "male3.jpg",
}
DEFAULT_ASPECT_RATIO = "3:4"
DEFAULT_RESOLUTION = "2K"
DEFAULT_BACKENDS = {
    "hairstyles": "nano_banana_2",
    "scenes": "seedream_basic",
}
SUPPORTED_CATEGORIES = {"hairstyles", "scenes"}
DEFAULT_HAIRSTYLE_SAMPLE_IDS = {
    "female": "female3",
    "male": "male2",
}
LEGACY_SCENE_SAMPLE_FILENAMES = {"female.jpg", "male.jpg"}

SCENE_COVER_GENDER_MAP = {
    "indoor-film-lifestyle": "female",
    "morning-window-softlight": "female",
    "walnut-study-portrait": "male",
    "cafe-candid-seat": "female",
    "bathroom-mirror-morning": "female",
    "hotel-room-loose": "female",
    "sunset-home-backlight": "female",
    "hallway-quiet-frame": "male",
    "rainy-window-mood": "male",
    "studio-solid-backdrop": "male",
    "retro-cinema-box": "female",
    "city-neon-night": "male",
    "gallery-white-cube": "female",
    "dramatic-side-light": "male",
    "rooftop-wind": "male",
    "moody-bar-counter": "male",
    "backstage-vanity-mirror": "female",
}

template_pipeline = None
review_pipeline = None


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pipeline_modules() -> None:
    global template_pipeline
    global review_pipeline

    if template_pipeline is None:
        template_pipeline = _load_module(TEMPLATE_PIPELINE_PATH, "template_image_pipeline")
    if review_pipeline is None:
        review_pipeline = _load_module(REVIEW_PIPELINE_PATH, "review_template_image_pipeline")


def _needs_real_cover(template: dict[str, Any]) -> bool:
    cover_path = str(template.get("cover_image_path") or "").strip()
    cover_source = str(template.get("cover_image_source") or "").strip()
    return not cover_path or cover_source == "draft_pending_render"


def _catalog_templates(category: str) -> list[dict[str, Any]]:
    _load_pipeline_modules()
    template_pipeline._load_backend_dependencies()
    if category == "hairstyles":
        return list(template_pipeline.templates.HAIRSTYLES)
    if category == "scenes":
        return list(template_pipeline.templates.SCENES)
    raise ValueError(f"不支持的模板类型：{category}")


def _resolve_templates(
    category: str,
    *,
    selected_ids: set[str],
    only_unpublished: bool,
) -> list[dict[str, Any]]:
    items = _catalog_templates(category)
    if selected_ids:
        items = [item for item in items if item["id"] in selected_ids]
    if only_unpublished:
        items = [item for item in items if _needs_real_cover(item)]
    return items


def _cover_gender_for_template(category: str, template: dict[str, Any]) -> str:
    if category == "hairstyles":
        gender = str(template.get("gender") or "").strip()
        if gender not in {"male", "female"}:
            raise ValueError(f"发型模板缺少合法 gender：{template.get('id')}")
        return gender

    if category == "scenes":
        scene_id = str(template.get("id") or "").strip()
        gender = SCENE_COVER_GENDER_MAP.get(scene_id)
        if gender not in {"male", "female"}:
            raise ValueError(f"场景未配置封面性别映射：{scene_id}")
        return gender

    raise ValueError(f"不支持的模板类型：{category}")


def _selected_sample_images(category: str, template: dict[str, Any]) -> tuple[str, dict[str, Path]]:
    cover_gender = _cover_gender_for_template(category, template)
    if category == "scenes":
        resolver = getattr(template_pipeline.templates, "resolve_scene_sample_image_id", None)
        if callable(resolver):
            sample_image_id = resolver(
                template,
                cover_gender,
                seed_source=f"{template['id']}:publish-cover:{cover_gender}",
            )
        else:
            sample_image_id = DEFAULT_HAIRSTYLE_SAMPLE_IDS.get(cover_gender, "")
    else:
        sample_image_id = DEFAULT_HAIRSTYLE_SAMPLE_IDS.get(cover_gender, "")

    sample_path = DEFAULT_SAMPLE_IMAGES.get(sample_image_id)
    if sample_path is None:
        raise FileNotFoundError(
            f"找不到 {category}/{template.get('id')} 对应的官方示例人物图配置：{sample_image_id}"
        )
    if category == "scenes" and sample_path.name.lower() in LEGACY_SCENE_SAMPLE_FILENAMES:
        raise ValueError(
            f"场景 {template.get('id')} 仍在使用旧示例人物图 {sample_path.name}，"
            "请改用 assets/female1~3.jpg 或 assets/male1~3.jpg。"
        )
    if not sample_path.exists():
        raise FileNotFoundError(f"找不到示例人物图：{sample_path}")
    return cover_gender, {cover_gender: sample_path}


def publish_category(
    *,
    category: str,
    selected_ids: set[str],
    only_unpublished: bool,
    backend: str,
    aspect_ratio: str,
    resolution: str,
    review_root: Path,
    approved_root: Path,
    restart: bool,
    note: str,
) -> dict[str, Any]:
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"不支持的模板类型：{category}")

    _load_pipeline_modules()
    templates_to_process = _resolve_templates(
        category,
        selected_ids=selected_ids,
        only_unpublished=only_unpublished,
    )
    if not templates_to_process:
        return {
            "category": category,
            "processed": 0,
            "approved": 0,
            "failed": [],
        }

    failures: list[str] = []
    approved_count = 0
    review_root = review_root.expanduser().resolve()
    approved_root = approved_root.expanduser().resolve()

    for template in templates_to_process:
        template_id = template["id"]
        try:
            cover_gender, sample_images = _selected_sample_images(category, template)
            template_pipeline.process_template(
                category=category,
                template=template,
                review_root=review_root,
                sample_images=sample_images,
                generator_backend=backend,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                review_genders=(cover_gender,) if category == "scenes" else None,
            )
            review_pipeline.approve_template_package(
                category=category,
                template_id=template_id,
                review_root=review_root,
                approved_root=approved_root,
                sync=False,
                restart=False,
                cover_gender=cover_gender,
                note=note,
            )
            approved_count += 1
            print(f"[publish_template_covers] 已发布：{category}/{template_id} ({cover_gender})")
        except Exception as exc:
            failures.append(f"{template_id}: {exc}")
            print(f"[publish_template_covers] 失败：{category}/{template_id} -> {exc}", file=sys.stderr)

    if approved_count > 0:
        review_pipeline.run_sync(restart=restart)

    return {
        "category": category,
        "processed": len(templates_to_process),
        "approved": approved_count,
        "failed": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量生成并直接发布正式模板封面图。")
    parser.add_argument("category", choices=sorted(SUPPORTED_CATEGORIES), help="模板类型。")
    parser.add_argument("--ids", default="", help="逗号分隔的模板 id 列表；为空表示按条件自动筛选。")
    parser.add_argument(
        "--all",
        action="store_true",
        help="忽略“未正式发布封面”筛选，直接处理所有匹配模板。",
    )
    parser.add_argument(
        "--backend",
        default="",
        help="生成后端；为空时发型默认 nano_banana_2，场景默认 seedream_basic（Seedream 4.5）。",
    )
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, help="封面画幅。")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="封面清晰度。")
    parser.add_argument(
        "--review-root",
        default=str(ROOT_DIR / "storage" / "template_image_pipeline" / "review"),
        help="模板审核包输出目录。",
    )
    parser.add_argument(
        "--approved-root",
        default=str(ROOT_DIR / "storage" / "template_image_pipeline" / "approved"),
        help="模板已发布归档目录。",
    )
    parser.add_argument("--restart", action="store_true", help="发布完成后同步并重启后端服务。")
    parser.add_argument(
        "--note",
        default="批量发布官方模板封面",
        help="写入审核 metadata 的备注。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    selected_ids = {item.strip() for item in args.ids.split(",") if item.strip()}
    backend = args.backend.strip() or DEFAULT_BACKENDS[args.category]

    result = publish_category(
        category=args.category,
        selected_ids=selected_ids,
        only_unpublished=not args.all,
        backend=backend,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        review_root=Path(args.review_root),
        approved_root=Path(args.approved_root),
        restart=args.restart,
        note=args.note,
    )

    print(
        f"[publish_template_covers] 完成：category={result['category']} "
        f"processed={result['processed']} approved={result['approved']} failed={len(result['failed'])}"
    )
    if result["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
