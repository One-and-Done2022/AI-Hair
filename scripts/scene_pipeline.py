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
    "female1": ROOT_DIR / "assets" / "female1.jpg",
    "female2": ROOT_DIR / "assets" / "female2.jpg",
    "female3": ROOT_DIR / "assets" / "female3.jpg",
    "male1": ROOT_DIR / "assets" / "male1.jpg",
    "male2": ROOT_DIR / "assets" / "male2.jpg",
    "male3": ROOT_DIR / "assets" / "male3.jpg",
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
_SEEDREAM_KEY_POOL = None


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


def _shared_seedream_key_pool():
    global _SEEDREAM_KEY_POOL
    _load_backend_dependencies()
    if _SEEDREAM_KEY_POOL is not None:
        return _SEEDREAM_KEY_POOL

    settings = get_settings()
    if not settings.ark_api_keys:
        raise ImageGenerationError("missing_api_key", "当前没有可用的 Ark API key。")

    _SEEDREAM_KEY_POOL = ApiKeyPool(
        settings.ark_api_keys,
        default_cooldown_seconds=settings.ark_key_cooldown_seconds,
        disabled_key_ids=settings.ark_api_disabled_key_ids,
    )
    return _SEEDREAM_KEY_POOL


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_list(items: list[str] | tuple[str, ...]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return "；".join(cleaned) if cleaned else "无"


def _write_review_summary(
    *,
    package_dir: Path,
    scene_draft: dict[str, Any],
    metadata: dict[str, Any],
    blocks: dict[str, str],
) -> None:
    recommended_cover = metadata.get("recommended_cover") or {}
    review_results = metadata.get("review_results") or {}
    prompt_files = metadata.get("prompt_files") or {}
    sample_assets = metadata.get("sample_assets") or {}
    review_checklist = metadata.get("review_checklist") or {}

    lines = [
        f"# 场景审核包：{scene_draft['title']}",
        "",
        f"- scene_id：`{scene_draft['id']}`",
        f"- 当前状态：`{metadata.get('status', 'unknown')}`",
        f"- 原图文件：`{metadata.get('source_name', '')}`",
        f"- 图片理解模型：`{metadata.get('image_understanding_model', '')}`",
        f"- 原图人物性别判断：`{metadata.get('subject_gender', 'unknown')}`",
        f"- 审核生图后端：`{metadata.get('generator_backend', '')}`",
        "",
        "## 提取的 scene_only blocks",
        "",
    ]

    for key, value in blocks.items():
        lines.extend([f"- `{key}`：{value}", ""])

    lines.extend(
        [
            "## 自动生成的场景草案",
            "",
            f"- 标题：{scene_draft['title']}",
            f"- 风格线：{scene_draft['styleLine']}",
            f"- 摘要：{scene_draft['summary']}",
            f"- 环境：{scene_draft['environment']}",
            f"- 光线：{scene_draft['lighting']}",
            f"- 氛围：{scene_draft['styleMood']}",
            f"- 标签：{_format_list(scene_draft.get('detailTags', []))}",
            f"- 表情：{_format_list(scene_draft.get('expressions', []))}",
            f"- 动作：{_format_list(scene_draft.get('actions', []))}",
            f"- 服饰建议：{_format_list(scene_draft.get('outfitHints', []))}",
            f"- 搭配建议：{_format_list(scene_draft.get('pairingAdvice', []))}",
            f"- 构图建议：{scene_draft['shotAdvice']}",
            f"- 约束：{_format_list(scene_draft.get('constraints', []))}",
            "",
            "## 审核图结果",
            "",
        ]
    )

    for gender in (
        gender
        for gender in ("female", "male")
        if gender in sample_assets or gender in review_results or gender in prompt_files
    ):
        result = review_results.get(gender) or {}
        lines.append(f"### {gender}")
        lines.append("")
        lines.append(f"- 示例人物图：`{sample_assets.get(gender, '')}`")
        lines.append(f"- prompt 文件：`{prompt_files.get(gender, '')}`")
        if result.get("status") == "succeeded":
            lines.append(f"- 审核图：`{result.get('image', '')}`")
        else:
            lines.append(f"- 失败原因：`{result.get('error', 'unknown error')}`")
        lines.append("")

    lines.extend(
        [
            "## 审核建议",
            "",
            f"- 推荐封面：`{recommended_cover.get('gender', '')}` / `{recommended_cover.get('image', '')}`",
            f"- scene_scope_clean：`{review_checklist.get('scene_scope_clean', 'pending')}`",
            f"- identity_stable：`{review_checklist.get('identity_stable', 'pending')}`",
            f"- physical_logic_ok：`{review_checklist.get('physical_logic_ok', 'pending')}`",
            f"- styling_harmony：`{review_checklist.get('styling_harmony', 'pending')}`",
            f"- lighting_face_ok：`{review_checklist.get('lighting_face_ok', 'pending')}`",
            f"- outfit_scene_consistent：`{review_checklist.get('outfit_scene_consistent', 'pending')}`",
            "",
            "## 常用命令",
            "",
            "```bash",
            f"python3 scripts/review_scene_pipeline.py approve {scene_draft['id']} --sync",
            f"python3 scripts/review_scene_pipeline.py approve {scene_draft['id']} --cover-gender female --sync",
            f"python3 scripts/review_scene_pipeline.py approve {scene_draft['id']} --cover-gender male --sync",
            f"python3 scripts/review_scene_pipeline.py reject {scene_draft['id']} --reason \"审核图不稳定\"",
            "```",
            "",
        ]
    )

    (package_dir / "review_summary.md").write_text(
        "\n".join(lines).strip() + "\n",
        encoding="utf-8",
    )


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
    subject_gender: str,
    generator_backend: str,
    review_results: dict[str, dict[str, Any]],
    source_asset_paths: dict[str, str],
    prompt_files: dict[str, str],
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
        "subject_gender": subject_gender,
        "generator_backend": generator_backend,
        "sample_assets": source_asset_paths,
        "prompt_files": prompt_files,
        "review_results": review_results,
        "recommended_cover": recommended_cover,
        "review_notes": "",
        "review_checklist": {
            "scene_scope_clean": "pending",
            "identity_stable": "pending",
            "physical_logic_ok": "pending",
            "styling_harmony": "pending",
            "lighting_face_ok": "pending",
            "outfit_scene_consistent": "pending",
            "cover_ready": "yes" if recommended_cover else "no",
        },
    }


def _select_review_genders(
    review_genders: tuple[str, ...],
    *,
    subject_gender: str,
) -> list[str]:
    candidates = [gender for gender in review_genders if gender in {"male", "female"}]
    if subject_gender in {"male", "female"} and subject_gender in candidates:
        return [subject_gender]
    return candidates


def _resolve_review_sample_path(
    *,
    scene_template: dict[str, Any],
    gender: str,
    sample_images: dict[str, Path],
) -> Path:
    direct_override = sample_images.get(gender)
    if direct_override is not None:
        return direct_override

    sample_image_id = templates.resolve_scene_sample_image_id(
        scene_template,
        gender,
        seed_source=f"{scene_template['id']}:review:{gender}",
    )
    if not sample_image_id:
        raise FileNotFoundError(f"场景 {scene_template['id']} 未配置 {gender} 的官方示例人物图")

    sample_path = sample_images.get(sample_image_id)
    if sample_path is None:
        raise FileNotFoundError(
            f"找不到官方示例人物图：{sample_image_id}（scene={scene_template['id']} gender={gender}）"
        )
    return sample_path


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
        key_pool = _shared_seedream_key_pool()
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
    review_genders: tuple[str, ...] = ("male", "female"),
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

    (package_dir / "blocks.json").write_text(
        json.dumps(understanding_result.blocks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (package_dir / "scene_draft.json").write_text(
        json.dumps(scene_draft, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (package_dir / "raw_model_response.txt").write_text(
        understanding_result.raw_response.strip() + "\n",
        encoding="utf-8",
    )

    review_results: dict[str, dict[str, Any]] = {}
    source_asset_paths: dict[str, str] = {}
    prompt_files: dict[str, str] = {}
    selected_review_genders = _select_review_genders(
        review_genders,
        subject_gender=understanding_result.subject_gender,
    )
    for gender in selected_review_genders:
        try:
            sample_path = _resolve_review_sample_path(
                scene_template=scene_template,
                gender=gender,
                sample_images=sample_images,
            )
        except FileNotFoundError as exc:
            review_results[gender] = {
                "status": "failed",
                "error": str(exc),
            }
            continue
        source_asset_paths[gender] = str(sample_path)
        if not sample_path.exists():
            review_results[gender] = {
                "status": "failed",
                "error": f"找不到示例人物图：{sample_path}",
            }
            continue

        prompt = templates.build_scene_only_prompt(
            scene_template,
            preferred_gender=gender,
            seed_source=f"{scene_id}:review:{gender}",
        )
        prompt_filename = f"scene_only_prompt_{gender}.txt"
        (package_dir / prompt_filename).write_text(prompt + "\n", encoding="utf-8")
        prompt_files[gender] = prompt_filename

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
        subject_gender=understanding_result.subject_gender,
        generator_backend=generator_backend,
        review_results=review_results,
        source_asset_paths=source_asset_paths,
        prompt_files=prompt_files,
    )
    _write_json(package_dir / "metadata.json", metadata)
    _write_review_summary(
        package_dir=package_dir,
        scene_draft=scene_draft,
        metadata=metadata,
        blocks=understanding_result.blocks,
    )
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

    inbox_dir = Path(args.inbox).expanduser().resolve()
    review_root = Path(args.review_root).expanduser().resolve()
    _ensure_dir(inbox_dir)
    _ensure_dir(review_root)

    gender_items = [item.strip() for item in args.sample_genders.split(",") if item.strip()]
    assets_dir = Path(args.assets_dir).expanduser().resolve()
    sample_images: dict[str, Path] = {
        asset_id: assets_dir / f"{asset_id}.jpg" for asset_id in DEFAULT_SAMPLE_IMAGES
    }
    for gender in gender_items:
        if gender not in {"male", "female"}:
            parser.error(f"不支持的 sample gender: {gender}")

    if args.male_image.strip():
        sample_images["male"] = Path(args.male_image).expanduser().resolve()
    if args.female_image.strip():
        sample_images["female"] = Path(args.female_image).expanduser().resolve()

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
                review_genders=tuple(gender_items),
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
