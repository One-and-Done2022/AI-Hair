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
REVIEW_ROOT = ROOT_DIR / "storage" / "scene_pipeline" / "review"
APPROVED_ROOT = ROOT_DIR / "storage" / "scene_pipeline" / "approved"
REJECTED_ROOT = ROOT_DIR / "storage" / "scene_pipeline" / "rejected"


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


def approve_scene_package(
    *,
    scene_id: str,
    review_root: Path,
    approved_root: Path,
    sync: bool = False,
    restart: bool = False,
) -> Path:
    package_dir = review_root / scene_id
    if not package_dir.exists():
        raise FileNotFoundError(f"找不到待审核包：{package_dir}")

    scene_draft_path = package_dir / "scene_draft.json"
    if not scene_draft_path.exists():
        raise FileNotFoundError(f"缺少 scene_draft.json：{scene_draft_path}")

    add_scene_draft = load_add_scene_draft_module()
    payload = json.loads(scene_draft_path.read_text(encoding="utf-8"))
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

    metadata = load_package_metadata(package_dir)
    metadata["status"] = "approved"
    metadata["approved_at"] = utc_now()
    metadata["approved_scene_id"] = normalized_scene["id"]
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
    _write_json(package_dir / "metadata.json", metadata)

    _ensure_dir(rejected_root)
    shutil.move(str(package_dir), str(destination))
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="审核 scene pipeline 生成的场景包。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    approve_parser = subparsers.add_parser("approve", help="通过审核并写入官方场景库。")
    approve_parser.add_argument("scene_id", help="审核包目录名，也就是 scene_draft 的 id。")
    approve_parser.add_argument("--review-root", default=str(REVIEW_ROOT), help="待审核包目录。")
    approve_parser.add_argument("--approved-root", default=str(APPROVED_ROOT), help="已通过归档目录。")
    approve_parser.add_argument("--sync", action="store_true", help="通过后同步到 backend/app/data/faceprompt。")
    approve_parser.add_argument("--restart", action="store_true", help="与 --sync 一起使用；同步后重启后端。")

    reject_parser = subparsers.add_parser("reject", help="驳回审核包。")
    reject_parser.add_argument("scene_id", help="审核包目录名，也就是 scene_draft 的 id。")
    reject_parser.add_argument("--reason", default="审核未通过", help="驳回原因。")
    reject_parser.add_argument("--review-root", default=str(REVIEW_ROOT), help="待审核包目录。")
    reject_parser.add_argument("--rejected-root", default=str(REJECTED_ROOT), help="驳回归档目录。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "approve":
            destination = approve_scene_package(
                scene_id=args.scene_id,
                review_root=Path(args.review_root).expanduser().resolve(),
                approved_root=Path(args.approved_root).expanduser().resolve(),
                sync=args.sync,
                restart=args.restart,
            )
            print(f"已通过审核并归档到：{destination}")
            return 0

        if args.command == "reject":
            destination = reject_scene_package(
                scene_id=args.scene_id,
                reason=args.reason,
                review_root=Path(args.review_root).expanduser().resolve(),
                rejected_root=Path(args.rejected_root).expanduser().resolve(),
            )
            print(f"已驳回并归档到：{destination}")
            return 0

        parser.error(f"不支持的命令：{args.command}")
    except Exception as exc:  # pragma: no cover
        print(f"[review_scene_pipeline] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
