#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT_DIR / "Faceprompt" / "src" / "faceprompt" / "data" / "scenes.json"
SYNC_SCRIPT_PATH = ROOT_DIR / "scripts" / "sync_faceprompt.sh"

VALID_STYLE_LINES = {"realistic_editorial", "fashion_editorial"}
VALID_WIND_LEVELS = {"still", "low", "medium", "high"}
VALID_HUMIDITY_LOOKS = {"dry", "balanced", "humid", "wet"}
VALID_BACKGROUND_COMPLEXITIES = {"low", "medium", "high"}
VALID_LIGHTING_HARDNESSES = {"soft", "balanced", "hard"}
VALID_MIRROR_RISKS = {"none", "low", "medium", "high"}
VALID_LIGHT_DIRECTIONS = {"front", "side", "back", "top", "mixed"}
VALID_LIGHT_QUALITIES = {"soft", "medium", "hard"}
VALID_COLOR_TEMPERATURES = {"cool", "neutral", "warm", "mixed"}
VALID_CONTRAST_LEVELS = {"low", "medium", "high"}
VALID_SHADOW_DENSITIES = {"light", "balanced", "deep"}
VALID_HAIR_HIGHLIGHT_MODES = {"soft_edge", "clean_rim", "controlled_specular", "none"}
VALID_SKIN_RENDERINGS = {"soft_texture", "clean_texture", "structured_texture"}
VALID_EXPOSURE_BIASES = {"slightly_under", "neutral", "slightly_over"}


def _normalize_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")
    return value.strip()


def _normalize_optional_text(value: Any, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串")
    return value.strip()


def _normalize_string_list(value: Any, field_name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} 必须是字符串数组")
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} 中存在非字符串元素")
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        items.append(cleaned)
    if not allow_empty and not items:
        raise ValueError(f"{field_name} 不能为空")
    return items


def _normalize_control_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("controlProfile 必须是对象")

    wind_level = _normalize_text(value.get("windLevel"), "controlProfile.windLevel")
    humidity_look = _normalize_text(value.get("humidityLook"), "controlProfile.humidityLook")
    background_complexity = _normalize_text(
        value.get("backgroundComplexity"), "controlProfile.backgroundComplexity"
    )
    lighting_hardness = _normalize_text(
        value.get("lightingHardness"), "controlProfile.lightingHardness"
    )
    mirror_risk = _normalize_text(value.get("mirrorRisk"), "controlProfile.mirrorRisk")

    if wind_level not in VALID_WIND_LEVELS:
        raise ValueError("controlProfile.windLevel 非法")
    if humidity_look not in VALID_HUMIDITY_LOOKS:
        raise ValueError("controlProfile.humidityLook 非法")
    if background_complexity not in VALID_BACKGROUND_COMPLEXITIES:
        raise ValueError("controlProfile.backgroundComplexity 非法")
    if lighting_hardness not in VALID_LIGHTING_HARDNESSES:
        raise ValueError("controlProfile.lightingHardness 非法")
    if mirror_risk not in VALID_MIRROR_RISKS:
        raise ValueError("controlProfile.mirrorRisk 非法")

    return {
        "windLevel": wind_level,
        "humidityLook": humidity_look,
        "backgroundComplexity": background_complexity,
        "lightingHardness": lighting_hardness,
        "mirrorRisk": mirror_risk,
        "compatibleHairstyleTags": _normalize_string_list(
            value.get("compatibleHairstyleTags", []),
            "controlProfile.compatibleHairstyleTags",
            allow_empty=True,
        ),
        "recommendedHairstyleIds": _normalize_string_list(
            value.get("recommendedHairstyleIds", []),
            "controlProfile.recommendedHairstyleIds",
            allow_empty=True,
        ),
    }


def _normalize_lighting_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("lightingProfile 必须是对象")

    light_direction = _normalize_text(value.get("lightDirection"), "lightingProfile.lightDirection")
    light_quality = _normalize_text(value.get("lightQuality"), "lightingProfile.lightQuality")
    color_temperature = _normalize_text(
        value.get("colorTemperature"), "lightingProfile.colorTemperature"
    )
    contrast_level = _normalize_text(value.get("contrastLevel"), "lightingProfile.contrastLevel")
    shadow_density = _normalize_text(value.get("shadowDensity"), "lightingProfile.shadowDensity")
    hair_highlight_mode = _normalize_text(
        value.get("hairHighlightMode"), "lightingProfile.hairHighlightMode"
    )
    skin_rendering = _normalize_text(value.get("skinRendering"), "lightingProfile.skinRendering")
    exposure_bias = _normalize_text(value.get("exposureBias"), "lightingProfile.exposureBias")
    practical_lights_allowed = bool(value.get("practicalLightsAllowed"))

    if light_direction not in VALID_LIGHT_DIRECTIONS:
        raise ValueError("lightingProfile.lightDirection 非法")
    if light_quality not in VALID_LIGHT_QUALITIES:
        raise ValueError("lightingProfile.lightQuality 非法")
    if color_temperature not in VALID_COLOR_TEMPERATURES:
        raise ValueError("lightingProfile.colorTemperature 非法")
    if contrast_level not in VALID_CONTRAST_LEVELS:
        raise ValueError("lightingProfile.contrastLevel 非法")
    if shadow_density not in VALID_SHADOW_DENSITIES:
        raise ValueError("lightingProfile.shadowDensity 非法")
    if hair_highlight_mode not in VALID_HAIR_HIGHLIGHT_MODES:
        raise ValueError("lightingProfile.hairHighlightMode 非法")
    if skin_rendering not in VALID_SKIN_RENDERINGS:
        raise ValueError("lightingProfile.skinRendering 非法")
    if exposure_bias not in VALID_EXPOSURE_BIASES:
        raise ValueError("lightingProfile.exposureBias 非法")

    return {
        "lightDirection": light_direction,
        "lightQuality": light_quality,
        "colorTemperature": color_temperature,
        "contrastLevel": contrast_level,
        "shadowDensity": shadow_density,
        "hairHighlightMode": hair_highlight_mode,
        "skinRendering": skin_rendering,
        "exposureBias": exposure_bias,
        "practicalLightsAllowed": practical_lights_allowed,
    }


def _normalize_sample_image_ids(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise ValueError("sampleImageIds 必须是对象")
    return {
        "female": _normalize_string_list(
            value.get("female", []),
            "sampleImageIds.female",
            allow_empty=True,
        ),
        "male": _normalize_string_list(
            value.get("male", []),
            "sampleImageIds.male",
            allow_empty=True,
        ),
    }


def extract_scene_draft(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("输入内容必须是 JSON 对象")

    if isinstance(payload.get("scene_draft"), dict):
        return payload["scene_draft"]
    return payload


def normalize_scene_draft(raw: dict[str, Any]) -> dict[str, Any]:
    style_line = _normalize_text(raw.get("styleLine"), "styleLine")
    if style_line not in VALID_STYLE_LINES:
        raise ValueError("styleLine 非法")

    normalized = {
        "id": _normalize_text(raw.get("id"), "id"),
        "title": _normalize_text(raw.get("title"), "title"),
        "styleLine": style_line,
        "summary": _normalize_text(raw.get("summary"), "summary"),
        "environment": _normalize_text(raw.get("environment"), "environment"),
        "lighting": _normalize_text(raw.get("lighting"), "lighting"),
        "lightingProfile": _normalize_lighting_profile(raw.get("lightingProfile")),
        "styleMood": _normalize_text(raw.get("styleMood"), "styleMood"),
        "detailTags": _normalize_string_list(raw.get("detailTags"), "detailTags"),
        "expressions": _normalize_string_list(raw.get("expressions"), "expressions"),
        "actions": _normalize_string_list(raw.get("actions"), "actions"),
        "outfitHints": _normalize_string_list(raw.get("outfitHints"), "outfitHints"),
        "outfitPalette": _normalize_string_list(
            raw.get("outfitPalette", []),
            "outfitPalette",
            allow_empty=True,
        ),
        "outfitMaterials": _normalize_string_list(
            raw.get("outfitMaterials", []),
            "outfitMaterials",
            allow_empty=True,
        ),
        "outfitShapes": _normalize_string_list(
            raw.get("outfitShapes", []),
            "outfitShapes",
            allow_empty=True,
        ),
        "outfitAvoids": _normalize_string_list(
            raw.get("outfitAvoids", []),
            "outfitAvoids",
            allow_empty=True,
        ),
        "pairingAdvice": _normalize_string_list(raw.get("pairingAdvice"), "pairingAdvice"),
        "shotAdvice": _normalize_text(raw.get("shotAdvice"), "shotAdvice"),
        "constraints": _normalize_string_list(raw.get("constraints"), "constraints"),
        "controlProfile": _normalize_control_profile(raw.get("controlProfile")),
        "sampleImageIds": _normalize_sample_image_ids(raw.get("sampleImageIds")),
        "referenceNotes": _normalize_text(raw.get("referenceNotes"), "referenceNotes"),
        "referenceSourceIds": _normalize_string_list(
            raw.get("referenceSourceIds"), "referenceSourceIds"
        ),
    }
    if raw.get("coverImagePath") is not None:
        normalized["coverImagePath"] = _normalize_optional_text(
            raw.get("coverImagePath"),
            "coverImagePath",
        )
    if raw.get("coverImageUpdatedAt") is not None:
        normalized["coverImageUpdatedAt"] = _normalize_optional_text(
            raw.get("coverImageUpdatedAt"),
            "coverImageUpdatedAt",
        )
    if raw.get("coverImageSource") is not None:
        normalized["coverImageSource"] = _normalize_optional_text(
            raw.get("coverImageSource"),
            "coverImageSource",
        )
    return normalized


def load_payload(input_path: str) -> dict[str, Any]:
    if input_path == "-":
        raw = sys.stdin.read().strip()
        if not raw:
            raise ValueError("stdin 没有接收到 JSON 内容")
        return json.loads(raw)

    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到输入文件：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def append_scene_draft(
    *,
    catalog_path: Path,
    payload: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    if not catalog_path.exists():
        raise FileNotFoundError(f"找不到场景目录文件：{catalog_path}")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        raise ValueError("scenes.json 根节点必须是数组")

    scene_draft = normalize_scene_draft(extract_scene_draft(payload))
    duplicated = next((item for item in catalog if item.get("id") == scene_draft["id"]), None)
    if duplicated is not None:
        raise ValueError(f"场景 id 已存在：{scene_draft['id']}")

    if dry_run:
        return scene_draft

    catalog.append(scene_draft)
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return scene_draft


def run_sync(*, restart: bool) -> None:
    command = [str(SYNC_SCRIPT_PATH)]
    if restart:
        command.append("--restart")
    subprocess.run(command, check=True, cwd=str(ROOT_DIR))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把 scene-understanding 接口返回的 scene_draft 追加到 Faceprompt 的 scenes.json。"
    )
    parser.add_argument(
        "--input",
        default="-",
        help="输入 JSON 文件路径，默认从 stdin 读取。支持完整接口响应或纯 scene_draft JSON。",
    )
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG_PATH),
        help="目标 scenes.json 路径。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印标准化后的 scene_draft，不写入文件。",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="写入成功后执行 scripts/sync_faceprompt.sh 同步到后端数据目录。",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="与 --sync 一起使用；同步后额外传递 --restart。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = load_payload(args.input)
        scene = append_scene_draft(
            catalog_path=Path(args.catalog).expanduser().resolve(),
            payload=payload,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print(json.dumps(scene, ensure_ascii=False, indent=2))
            return 0

        print(f"已写入场景：{scene['id']} / {scene['title']}")
        if args.sync:
            run_sync(restart=args.restart)
            print("已同步到 backend/app/data/faceprompt")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"[add_scene_draft] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
