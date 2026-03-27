#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

FACEPROMPT_DATA_DIR = ROOT_DIR / "Faceprompt" / "src" / "faceprompt" / "data"
SCENES_CATALOG_PATH = FACEPROMPT_DATA_DIR / "scenes.json"
HAIRSTYLES_MALE_CATALOG_PATH = FACEPROMPT_DATA_DIR / "hairstyles_male.json"
HAIRSTYLES_FEMALE_CATALOG_PATH = FACEPROMPT_DATA_DIR / "hairstyles_female.json"
SYNC_SCRIPT_PATH = ROOT_DIR / "scripts" / "sync_faceprompt.sh"

REVIEW_ROOT = ROOT_DIR / "storage" / "template_image_pipeline" / "review"
APPROVED_ROOT = ROOT_DIR / "storage" / "template_image_pipeline" / "approved"
REJECTED_ROOT = ROOT_DIR / "storage" / "template_image_pipeline" / "rejected"

SUPPORTED_CATEGORIES = {"hairstyles", "scenes"}
SUPPORTED_COVER_GENDERS = {"auto", "female", "male"}

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


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到目录文件：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} 根节点必须是数组")
    return payload


def load_package_metadata(package_dir: Path) -> dict[str, Any]:
    metadata_path = package_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"缺少 metadata.json：{metadata_path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def load_template_snapshot(package_dir: Path) -> dict[str, Any]:
    snapshot_path = package_dir / "template_snapshot.json"
    if not snapshot_path.exists():
        raise FileNotFoundError(f"缺少 template_snapshot.json：{snapshot_path}")
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("template_snapshot.json 必须是对象")
    return payload


def _pick_cover_filename(package_dir: Path, metadata: dict[str, Any], cover_gender: str) -> str:
    review_results = metadata.get("review_results") or {}
    if not isinstance(review_results, dict):
        raise ValueError("metadata.review_results 必须是对象")

    if cover_gender != "auto":
        review_item = review_results.get(cover_gender, {})
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
        review_item = review_results.get(gender, {})
        filename = str(review_item.get("image") or "").strip()
        if filename and (package_dir / filename).exists():
            return filename

    for review_item in review_results.values():
        filename = str((review_item or {}).get("image") or "").strip()
        if filename and (package_dir / filename).exists():
            return filename

    raise FileNotFoundError("审核包中没有可用的封面图")


def _catalog_path_for_template(category: str, template_snapshot: dict[str, Any]) -> Path:
    if category == "scenes":
        return SCENES_CATALOG_PATH
    if category != "hairstyles":
        raise ValueError(f"不支持的模板类型：{category}")

    gender = str(template_snapshot.get("gender") or "").strip()
    if gender == "male":
        return HAIRSTYLES_MALE_CATALOG_PATH
    if gender == "female":
        return HAIRSTYLES_FEMALE_CATALOG_PATH
    raise ValueError(f"hairstyle 模板缺少合法 gender：{template_snapshot.get('gender')!r}")


def update_template_cover_record(
    *,
    category: str,
    template_snapshot: dict[str, Any],
    cover_object_key: str,
    cover_image_source: str,
) -> Path:
    catalog_path = _catalog_path_for_template(category, template_snapshot)
    catalog = _load_json_list(catalog_path)
    template_id = str(template_snapshot.get("id") or "").strip()
    if not template_id:
        raise ValueError("template_snapshot.id 不能为空")

    matched = next((item for item in catalog if item.get("id") == template_id), None)
    if matched is None:
        raise ValueError(f"目录里找不到模板 id：{template_id}")

    matched["coverImagePath"] = cover_object_key
    matched["coverImageUpdatedAt"] = utc_now()
    matched["coverImageSource"] = cover_image_source
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return catalog_path


def run_sync(*, restart: bool) -> None:
    command = [str(SYNC_SCRIPT_PATH)]
    if restart:
        command.append("--restart")
    subprocess.run(command, check=True, cwd=str(ROOT_DIR))


def approve_template_package(
    *,
    category: str,
    template_id: str,
    review_root: Path,
    approved_root: Path,
    sync: bool = False,
    restart: bool = False,
    cover_gender: str = "auto",
    note: str = "",
) -> Path:
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"不支持的模板类型：{category}")
    if cover_gender not in SUPPORTED_COVER_GENDERS:
        raise ValueError(f"不支持的 cover_gender：{cover_gender}")

    _load_backend_dependencies()
    package_dir = review_root / category / template_id
    if not package_dir.exists():
        raise FileNotFoundError(f"找不到待审核包：{package_dir}")

    template_snapshot = load_template_snapshot(package_dir)
    if str(template_snapshot.get("id") or "").strip() != template_id:
        raise ValueError("template_snapshot.json 中的模板 id 与目录名不一致")

    metadata = load_package_metadata(package_dir)
    selected_cover_filename = _pick_cover_filename(package_dir, metadata, cover_gender)
    cover_object_key = storage.save_template_asset(
        category,
        template_id,
        (package_dir / selected_cover_filename).read_bytes(),
    )
    cover_source = f"template_image_pipeline:{selected_cover_filename}"
    catalog_path = update_template_cover_record(
        category=category,
        template_snapshot=template_snapshot,
        cover_object_key=cover_object_key,
        cover_image_source=cover_source,
    )
    if sync:
        run_sync(restart=restart)

    destination = approved_root / category / template_id
    if destination.exists():
        raise FileExistsError(f"已存在已通过目录：{destination}")

    metadata["status"] = "approved"
    metadata["approved_at"] = utc_now()
    metadata["approved_template_id"] = template_id
    metadata["approved_cover_image"] = selected_cover_filename
    metadata["approved_cover_path"] = cover_object_key
    metadata["approved_catalog_path"] = str(catalog_path)
    metadata["review_notes"] = note.strip()
    _write_json(package_dir / "metadata.json", metadata)

    _ensure_dir(destination.parent)
    shutil.move(str(package_dir), str(destination))
    return destination


def reject_template_package(
    *,
    category: str,
    template_id: str,
    reason: str,
    review_root: Path,
    rejected_root: Path,
    note: str = "",
) -> Path:
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"不支持的模板类型：{category}")

    package_dir = review_root / category / template_id
    if not package_dir.exists():
        raise FileNotFoundError(f"找不到待审核包：{package_dir}")

    destination = rejected_root / category / template_id
    if destination.exists():
        raise FileExistsError(f"已存在驳回目录：{destination}")

    metadata = load_package_metadata(package_dir)
    metadata["status"] = "rejected"
    metadata["rejected_at"] = utc_now()
    metadata["rejected_reason"] = reason.strip() or "审核未通过"
    metadata["review_notes"] = note.strip()
    _write_json(package_dir / "metadata.json", metadata)

    _ensure_dir(destination.parent)
    shutil.move(str(package_dir), str(destination))
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="审核模板真实样片流水线输出。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    approve_parser = subparsers.add_parser("approve", help="通过审核并写入模板封面。")
    approve_parser.add_argument("category", choices=sorted(SUPPORTED_CATEGORIES), help="模板类型。")
    approve_parser.add_argument("template_id", help="模板 id。")
    approve_parser.add_argument("--review-root", default=str(REVIEW_ROOT), help="待审核包目录。")
    approve_parser.add_argument("--approved-root", default=str(APPROVED_ROOT), help="已通过归档目录。")
    approve_parser.add_argument("--sync", action="store_true", help="通过后同步到 backend/app/data/faceprompt。")
    approve_parser.add_argument("--restart", action="store_true", help="与 --sync 一起使用；同步后重启后端。")
    approve_parser.add_argument(
        "--cover-gender",
        default="auto",
        choices=sorted(SUPPORTED_COVER_GENDERS),
        help="优先采用哪张审核图作为正式模板封面。",
    )
    approve_parser.add_argument("--note", default="", help="人工审核备注，会写入 metadata.json。")

    reject_parser = subparsers.add_parser("reject", help="驳回模板审核包。")
    reject_parser.add_argument("category", choices=sorted(SUPPORTED_CATEGORIES), help="模板类型。")
    reject_parser.add_argument("template_id", help="模板 id。")
    reject_parser.add_argument("--reason", default="审核未通过", help="驳回原因。")
    reject_parser.add_argument("--review-root", default=str(REVIEW_ROOT), help="待审核包目录。")
    reject_parser.add_argument("--rejected-root", default=str(REJECTED_ROOT), help="驳回归档目录。")
    reject_parser.add_argument("--note", default="", help="人工审核备注，会写入 metadata.json。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "approve":
            destination = approve_template_package(
                category=args.category,
                template_id=args.template_id,
                review_root=Path(args.review_root).expanduser().resolve(),
                approved_root=Path(args.approved_root).expanduser().resolve(),
                sync=args.sync,
                restart=args.restart,
                cover_gender=args.cover_gender,
                note=args.note,
            )
            print(f"已通过模板审核并归档到：{destination}")
            return 0

        if args.command == "reject":
            destination = reject_template_package(
                category=args.category,
                template_id=args.template_id,
                reason=args.reason,
                review_root=Path(args.review_root).expanduser().resolve(),
                rejected_root=Path(args.rejected_root).expanduser().resolve(),
                note=args.note,
            )
            print(f"已驳回模板审核包并归档到：{destination}")
            return 0

        parser.error(f"不支持的命令：{args.command}")
    except Exception as exc:  # pragma: no cover
        print(f"[review_template_image_pipeline] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
