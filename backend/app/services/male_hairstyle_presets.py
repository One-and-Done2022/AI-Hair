from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

MALE_HAIRSTYLE_STRUCTURE_FILE = "hairstyle_structures_male.json"
MALE_HAIRSTYLE_MODIFIER_FILE = "hairstyle_modifiers_male.json"
MALE_HAIRSTYLE_TECHNIQUE_FILE = "hairstyle_techniques_male.json"
MALE_HAIRSTYLE_PRESET_FILE = "hairstyle_presets_male.json"

SAFE_TECHNIQUE_HAIR_SHAPE_FIELDS = {
    "hair_texture",
    "hair_volume",
    "hair_tail_finish",
}

MODIFIER_STRUCTURED_OVERRIDES = {
    "modifier_bracket_fringe": {
        "bangs": {
            "bangs_type": "括号刘海",
            "bangs_density": "轻薄到中等",
            "bangs_length": "眉骨到眼周附近",
            "bangs_split": "两侧向内包裹额头",
            "bangs_face_framing": "两侧弧形包裹额头并自然修饰脸型",
        },
        "constraints": [
            "括号刘海只允许作用于前区 opening，不得改写主结构长度、分线和两侧轮廓。",
            "前区弧线要自然包裹额头，不要变成厚重整片盖额。",
        ],
    },
    "modifier_comma_fringe": {
        "bangs": {
            "bangs_type": "逗号刘海",
            "bangs_density": "轻薄",
            "bangs_length": "眉骨附近",
            "bangs_split": "一侧弯出逗号形弧线",
            "bangs_face_framing": "以前区弧线轻修饰额角和脸侧",
        },
        "constraints": [
            "逗号刘海只做前区弧线修饰，不得把主结构改成完全不同的中长发。",
            "额前弧线要干净利落，不要卷成厚重大片刘海。",
        ],
    },
    "modifier_long_fringe": {
        "bangs": {
            "bangs_type": "长刘海",
            "bangs_density": "轻薄到中等",
            "bangs_length": "眼周到颧骨附近",
            "bangs_split": "自然中分或微分",
            "bangs_face_framing": "两侧长刘海自然修饰脸型",
        },
        "constraints": [
            "长刘海只允许延长前区修饰，不得把短发主轮廓改成长发披散结构。",
            "长刘海要保留轻薄流向，不要形成沉重遮挡。",
        ],
    },
    "modifier_side_fringe": {
        "bangs": {
            "bangs_type": "侧刘海",
            "bangs_density": "轻薄",
            "bangs_length": "眉骨至颧骨附近",
            "bangs_split": "沿一侧自然斜向带开",
            "bangs_face_framing": "以前区一侧修饰额角与脸侧",
        },
        "constraints": [
            "侧刘海只改变前区修饰方向，不得改写底层主结构和整体长度。",
            "一侧刘海流向必须自然贴合，不要形成生硬大面积遮挡。",
        ],
    },
    "modifier_hk_vibe": {
        "hair_shape": {
            "hair_texture": "在原结构基础上保留港风层次与随性流向",
            "hair_tail_finish": "整体氛围更松弛复古，但轮廓边界仍要清楚",
        },
        "constraints": [
            "港风氛围只能强化气质和流向，不能改掉主结构长度、分线和侧区处理。",
        ],
    },
    "modifier_messy_texture": {
        "hair_shape": {
            "hair_texture": "在原结构基础上增加轻微凌乱纹理与松散束感",
            "hair_tail_finish": "发尾保留自然散开和空气感，不要过度工整",
        },
        "constraints": [
            "凌乱纹理只允许增加局部松散感，不得把主结构做成失控炸乱。",
        ],
    },
    "modifier_commute_clean": {
        "hair_shape": {
            "hair_texture": "整体纹理更干净克制、通勤友好",
            "hair_tail_finish": "收尾利落、边界清晰、保持整洁度",
        },
        "constraints": [
            "通勤清爽只能提升整洁度和克制度，不得压塌主结构体积。",
        ],
    },
}


def _load_json(data_dir: Path, filename: str) -> list[dict]:
    return json.loads((data_dir / filename).read_text(encoding="utf-8"))



def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result



def _join_text(*parts: str) -> str:
    return " ".join(_dedupe([str(part or "").strip() for part in parts]))



def _resolve_source_hairstyle_id(structure: dict, legacy_index: dict[str, dict]) -> str:
    bridge = structure.get("backendBridge") or {}
    for bridge_id in bridge.get("backend_ids", []):
        candidate = str(bridge_id or "").strip()
        if candidate and candidate in legacy_index:
            return candidate
    structure_id = str(structure.get("id") or "").strip()
    if structure_id and structure_id in legacy_index:
        return structure_id
    return ""



def _merge_preset_blocks(structure: dict, modifiers: list[dict], techniques: list[dict]) -> dict:
    merged = deepcopy(structure.get("presetBlocks") or {})
    hair_shape = merged.setdefault("hair_shape", {})
    bangs = merged.setdefault("bangs", {})
    recommended_hair_color = merged.setdefault("recommended_hair_color", {})

    for modifier in modifiers:
        override = MODIFIER_STRUCTURED_OVERRIDES.get(modifier["id"], {})
        for key, value in (override.get("hair_shape") or {}).items():
            if str(value or "").strip():
                hair_shape[key] = value
        for key, value in (override.get("bangs") or {}).items():
            if str(value or "").strip():
                bangs[key] = value

    for technique in techniques:
        technique_blocks = technique.get("presetBlocks") or {}
        for key, value in (technique_blocks.get("hair_shape") or {}).items():
            if key in SAFE_TECHNIQUE_HAIR_SHAPE_FIELDS and str(value or "").strip():
                hair_shape[key] = value
        for key, value in (technique_blocks.get("recommended_hair_color") or {}).items():
            if str(value or "").strip():
                recommended_hair_color[key] = value

    return merged



def _resolve_preset(
    raw_preset: dict,
    *,
    structures_index: dict[str, dict],
    modifiers_index: dict[str, dict],
    techniques_index: dict[str, dict],
    legacy_index: dict[str, dict],
) -> dict:
    structure_id = str(raw_preset.get("structureId") or "").strip()
    structure = structures_index.get(structure_id) or legacy_index.get(structure_id)
    if structure is None:
        raise ValueError(f"Unknown male hairstyle structure: {structure_id}")

    modifier_ids = _dedupe([str(item).strip() for item in raw_preset.get("modifierIds", []) if str(item).strip()])
    modifiers: list[dict] = []
    for modifier_id in modifier_ids:
        modifier = modifiers_index.get(modifier_id)
        if modifier is None:
            raise ValueError(f"Unknown male hairstyle modifier: {modifier_id}")
        modifiers.append(modifier)

    technique_ids = _dedupe([str(item).strip() for item in raw_preset.get("techniqueIds", []) if str(item).strip()])
    techniques: list[dict] = []
    for technique_id in technique_ids:
        technique = techniques_index.get(technique_id)
        if technique is None:
            raise ValueError(f"Unknown male hairstyle technique: {technique_id}")
        techniques.append(technique)

    source_hairstyle_id = _resolve_source_hairstyle_id(structure, legacy_index)
    source_hairstyle = legacy_index.get(source_hairstyle_id)
    fallback_cover_source = source_hairstyle or (techniques[0] if techniques else None)
    modifier_labels = [str(item.get("label") or item["id"]).strip() for item in modifiers]
    technique_labels = [str(item.get("label") or item["id"]).strip() for item in techniques]
    preset_blocks = _merge_preset_blocks(structure, modifiers, techniques)

    constraints = list(structure.get("constraints") or [])
    for modifier in modifiers:
        constraints.extend((MODIFIER_STRUCTURED_OVERRIDES.get(modifier["id"], {}) or {}).get("constraints") or [])
    for technique in techniques:
        constraints.extend(technique.get("constraints") or [])

    resolved_name = (
        str(source_hairstyle.get("title") or "").strip()
        if source_hairstyle is not None
        else str(structure.get("title") or raw_preset.get("displayName") or "").strip()
    )
    summary = str(raw_preset.get("notes") or "").strip() or str(structure.get("summary") or "").strip()
    style_line = (
        str(techniques[0].get("styleLine") or "").strip()
        if techniques
        else str(structure.get("styleLine") or "").strip()
    )

    return {
        "id": raw_preset["id"],
        "gender": "male",
        "displayName": raw_preset["displayName"],
        "displayGroup": raw_preset.get("displayGroup", ""),
        "displayGroupKey": raw_preset.get("displayGroupKey", ""),
        "categoryKey": raw_preset.get("categoryKey", ""),
        "categoryLabel": raw_preset.get("categoryLabel", ""),
        "structureId": structure_id,
        "modifierIds": modifier_ids,
        "techniqueIds": technique_ids,
        "sourceHairstyleId": source_hairstyle_id,
        "resolvedHairstyleName": resolved_name,
        "styleLine": style_line,
        "summary": summary,
        "promptCore": _join_text(
            str(structure.get("promptCore") or "").strip(),
            *[str(item.get("prompt_addition_cn") or "").strip() for item in modifiers],
            *[str(item.get("promptAddition") or "").strip() for item in techniques],
        ),
        "detailTags": _dedupe(
            [
                *structure.get("detailTags", []),
                raw_preset.get("displayName", ""),
                raw_preset.get("displayGroup", ""),
                *modifier_labels,
                *technique_labels,
            ]
        ),
        "constraints": _dedupe(constraints),
        "pairingAdvice": _dedupe(
            [
                *structure.get("pairingAdvice", []),
                *[item for technique in techniques for item in technique.get("pairingAdvice", [])],
            ]
        ),
        "shotAdvice": str(structure.get("shotAdvice") or "").strip(),
        "expressionAction": _dedupe(
            [
                *structure.get("expressionAction", []),
                *[item for technique in techniques for item in technique.get("expressionAction", [])],
            ]
        ),
        "controlProfile": structure.get("controlProfile"),
        "referenceNotes": _join_text(
            str(structure.get("referenceNotes") or "").strip(),
            *[str(item.get("referenceNotes") or "").strip() for item in techniques],
        ),
        "referenceSourceIds": _dedupe(
            [
                *structure.get("referenceSourceIds", []),
                *[item for technique in techniques for item in technique.get("referenceSourceIds", [])],
            ]
        ),
        "presetBlocks": preset_blocks,
        "modifierLabels": modifier_labels,
        "techniqueLabels": technique_labels,
        "coverImagePath": str(structure.get("coverImagePath") or "").strip()
        or (str(fallback_cover_source.get("coverImagePath") or "").strip() if fallback_cover_source else ""),
        "coverImageUpdatedAt": str(structure.get("coverImageUpdatedAt") or "").strip()
        or (str(fallback_cover_source.get("coverImageUpdatedAt") or "").strip() if fallback_cover_source else ""),
        "coverImageSource": str(structure.get("coverImageSource") or "").strip()
        or (str(fallback_cover_source.get("coverImageSource") or "").strip() if fallback_cover_source else ""),
        "notes": str(raw_preset.get("notes") or "").strip(),
    }



def load_catalog(data_dir: Path, legacy_male_raw: list[dict]) -> dict[str, list[dict]]:
    structures = _load_json(data_dir, MALE_HAIRSTYLE_STRUCTURE_FILE)
    modifiers = _load_json(data_dir, MALE_HAIRSTYLE_MODIFIER_FILE)
    techniques = _load_json(data_dir, MALE_HAIRSTYLE_TECHNIQUE_FILE)
    presets = _load_json(data_dir, MALE_HAIRSTYLE_PRESET_FILE)

    structures_index = {item["id"]: item for item in structures}
    modifiers_index = {item["id"]: item for item in modifiers}
    techniques_index = {item["id"]: item for item in techniques}
    legacy_index = {item["id"]: item for item in legacy_male_raw}

    for preset in presets:
        structure_id = str(preset.get("structureId") or "").strip()
        if structure_id and structure_id not in structures_index and structure_id in legacy_index:
            structures.append(legacy_index[structure_id])
            structures_index[structure_id] = legacy_index[structure_id]

    resolved_presets = [
        _resolve_preset(
            item,
            structures_index=structures_index,
            modifiers_index=modifiers_index,
            techniques_index=techniques_index,
            legacy_index=legacy_index,
        )
        for item in presets
    ]

    return {
        "structures": structures,
        "modifiers": modifiers,
        "techniques": techniques,
        "presets": resolved_presets,
    }
