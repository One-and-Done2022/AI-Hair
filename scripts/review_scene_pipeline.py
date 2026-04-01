#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
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

REVIEW_ROOT = ROOT_DIR / "storage" / "scene_pipeline" / "review"
APPROVED_ROOT = ROOT_DIR / "storage" / "scene_pipeline" / "approved"
REJECTED_ROOT = ROOT_DIR / "storage" / "scene_pipeline" / "rejected"

storage = None


def _load_backend_dependencies() -> None:
    global storage
    if storage is not None:
        return
    from app.services import storage as _storage

    storage = _storage


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_add_scene_draft_module():
    module_path = ROOT_DIR / "scripts" / "add_scene_draft.py"
    spec = importlib.util.spec_from_file_location("add_scene_draft", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 add_scene_draft.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_package_metadata(package_dir: Path) -> dict[str, Any]:
    metadata_path = package_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"缺少 metadata.json：{metadata_path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def list_review_packages(review_root: Path) -> list[dict[str, Any]]:
    if not review_root.exists():
        return []

    packages: list[dict[str, Any]] = []
    for package_dir in sorted(path for path in review_root.iterdir() if path.is_dir()):
        try:
            metadata = load_package_metadata(package_dir)
        except FileNotFoundError:
            continue

        recommended_cover = metadata.get("recommended_cover") or {}
        review_results = metadata.get("review_results") or {}
        packages.append(
            {
                "scene_id": package_dir.name,
                "scene_title": metadata.get("scene_title", ""),
                "status": metadata.get("status", ""),
                "subject_gender": metadata.get("subject_gender", "unknown"),
                "recommended_cover_gender": recommended_cover.get("gender", ""),
                "recommended_cover_image": recommended_cover.get("image", ""),
                "succeeded_genders": [
                    gender
                    for gender, result in review_results.items()
                    if result.get("status") == "succeeded"
                ],
                "path": str(package_dir),
            }
        )
    return packages


def render_review_package_lines(packages: list[dict[str, Any]]) -> list[str]:
    if not packages:
        return ["当前没有待审核场景包。"]

    lines: list[str] = []
    for item in packages:
        succeeded = "、".join(item.get("succeeded_genders", [])) or "无"
        lines.extend(
            [
                f"- {item['scene_id']} | {item.get('scene_title', '')}",
                f"  状态：{item.get('status', '')}；原图人物：{item.get('subject_gender', 'unknown')}；成功审核图：{succeeded}",
                "  推荐封面："
                f"{item.get('recommended_cover_gender', '')} / {item.get('recommended_cover_image', '')}",
                f"  路径：{item.get('path', '')}",
            ]
        )
    return lines


def _pick_cover_filename(package_dir: Path, metadata: dict[str, Any], cover_gender: str) -> str:
    if cover_gender != "auto":
        review_item = (metadata.get("review_results") or {}).get(cover_gender, {})
        filename = str(review_item.get("image") or "").strip()
        if not filename:
            raise FileNotFoundError(f"找不到 {cover_gender} 对应的审核图")
        if not (package_dir / filename).exists():
            raise FileNotFoundError(f"审核图不存在：{package_dir / filename}")
        return filename

    recommended = metadata.get("recommended_cover") or {}
    filename = str(recommended.get("image") or "").strip()
    if filename and (package_dir / filename).exists():
        return filename

    for gender in ("female", "male"):
        review_item = (metadata.get("review_results") or {}).get(gender, {})
        filename = str(review_item.get("image") or "").strip()
        if filename and (package_dir / filename).exists():
            return filename

    raise FileNotFoundError("审核包中没有可用的封面图")


def approve_scene_package(
    *,
    scene_id: str,
    review_root: Path,
    approved_root: Path,
    sync: bool = False,
    restart: bool = False,
    cover_gender: str = "auto",
    note: str = "",
) -> Path:
    _load_backend_dependencies()
    package_dir = review_root / scene_id
    if not package_dir.exists():
        raise FileNotFoundError(f"找不到待审核包：{package_dir}")

    scene_draft_path = package_dir / "scene_draft.json"
    if not scene_draft_path.exists():
        raise FileNotFoundError(f"缺少 scene_draft.json：{scene_draft_path}")

    add_scene_draft = load_add_scene_draft_module()
    payload = json.loads(scene_draft_path.read_text(encoding="utf-8"))
    metadata = load_package_metadata(package_dir)
    selected_cover_filename = _pick_cover_filename(package_dir, metadata, cover_gender)
    cover_object_key = storage.save_template_asset(
        "scenes",
        scene_id,
        (package_dir / selected_cover_filename).read_bytes(),
    )
    payload["coverImagePath"] = cover_object_key
    payload["coverImageUpdatedAt"] = utc_now()
    payload["coverImageSource"] = f"scene_pipeline:{selected_cover_filename}"
    normalized_scene = add_scene_draft.append_scene_draft(
        catalog_path=add_scene_draft.DEFAULT_CATALOG_PATH,
        payload=payload,
        dry_run=False,
    )
    if sync:
        add_scene_draft.run_sync(restart=restart)

    destination = approved_root / scene_id
    if destination.exists():
        raise FileExistsError(f"已存在已通过目录：{destination}")

    metadata["status"] = "approved"
    metadata["approved_at"] = utc_now()
    metadata["approved_scene_id"] = normalized_scene["id"]
    metadata["approved_cover_image"] = selected_cover_filename
    metadata["approved_cover_path"] = cover_object_key
    metadata["review_notes"] = note.strip()
    _write_json(package_dir / "metadata.json", metadata)

    _ensure_dir(approved_root)
    shutil.move(str(package_dir), str(destination))
    return destination


def reject_scene_package(
    *,
    scene_id: str,
    reason: str,
    review_root: Path,
    rejected_root: Path,
    note: str = "",
) -> Path:
    package_dir = review_root / scene_id
    if not package_dir.exists():
        raise FileNotFoundError(f"找不到待审核包：{package_dir}")

    destination = rejected_root / scene_id
    if destination.exists():
        raise FileExistsError(f"已存在驳回目录：{destination}")

    metadata = load_package_metadata(package_dir)
    metadata["status"] = "rejected"
    metadata["rejected_at"] = utc_now()
    metadata["rejected_reason"] = reason.strip() or "未填写原因"
    metadata["review_notes"] = note.strip()
    _write_json(package_dir / "metadata.json", metadata)

    _ensure_dir(rejected_root)
    shutil.move(str(package_dir), str(destination))
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="审核 scene pipeline 生成的场景包。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出当前待审核场景包。")
    list_parser.add_argument("--review-root", default=str(REVIEW_ROOT), help="待审核包目录。")
    list_parser.add_argument("--json", action="store_true", help="以 JSON 输出。")

    approve_parser = subparsers.add_parser("approve", help="通过审核并写入官方场景库。")
    approve_parser.add_argument("scene_id", help="审核包目录名，也就是 scene_draft 的 id。")
    approve_parser.add_argument("--review-root", default=str(REVIEW_ROOT), help="待审核包目录。")
    approve_parser.add_argument("--approved-root", default=str(APPROVED_ROOT), help="已通过归档目录。")
    approve_parser.add_argument("--sync", action="store_true", help="通过后同步到 backend/app/data/faceprompt。")
    approve_parser.add_argument("--restart", action="store_true", help="与 --sync 一起使用；同步后重启后端。")
    approve_parser.add_argument(
        "--cover-gender",
        default="auto",
        choices=["auto", "female", "male"],
        help="批准时采用哪张审核图作为正式场景封面，默认 auto 优先 female。",
    )
    approve_parser.add_argument("--note", default="", help="人工审核备注，会写入 metadata.json。")

    reject_parser = subparsers.add_parser("reject", help="驳回审核包。")
    reject_parser.add_argument("scene_id", help="审核包目录名，也就是 scene_draft 的 id。")
    reject_parser.add_argument("--reason", default="审核未通过", help="驳回原因。")
    reject_parser.add_argument("--review-root", default=str(REVIEW_ROOT), help="待审核包目录。")
    reject_parser.add_argument("--rejected-root", default=str(REJECTED_ROOT), help="驳回归档目录。")
    reject_parser.add_argument("--note", default="", help="人工审核备注，会写入 metadata.json。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            packages = list_review_packages(
                Path(args.review_root).expanduser().resolve(),
            )
            if args.json:
                print(json.dumps(packages, ensure_ascii=False, indent=2))
            else:
                print("\n".join(render_review_package_lines(packages)))
            return 0

        if args.command == "approve":
            destination = approve_scene_package(
                scene_id=args.scene_id,
                review_root=Path(args.review_root).expanduser().resolve(),
                approved_root=Path(args.approved_root).expanduser().resolve(),
                sync=args.sync,
                restart=args.restart,
                cover_gender=args.cover_gender,
                note=args.note,
            )
            print(f"已通过审核并归档到：{destination}")
            return 0

        if args.command == "reject":
            destination = reject_scene_package(
                scene_id=args.scene_id,
                reason=args.reason,
                review_root=Path(args.review_root).expanduser().resolve(),
                rejected_root=Path(args.rejected_root).expanduser().resolve(),
                note=args.note,
            )
            print(f"已驳回并归档到：{destination}")
            return 0

        parser.error(f"不支持的命令：{args.command}")
    except Exception as exc:  # pragma: no cover
        print(f"[review_scene_pipeline] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
