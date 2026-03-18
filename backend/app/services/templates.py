from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "faceprompt"

STYLE_LINE_LABELS = {
    "realistic_editorial": "写实写真",
    "fashion_editorial": "时尚大片",
}

GENDER_LABELS = {
    "male": "男发",
    "female": "女发",
    "unisex": "通用",
}

STYLE_LINE_PALETTES = {
    "realistic_editorial": ("#6b4f3a", "#dcc3a5"),
    "fashion_editorial": ("#1f2937", "#8ec5fc"),
}

HAIRSTYLE_PALETTES = {
    "male": ("#1f3c88", "#6fa8dc"),
    "female": ("#7a2848", "#f7b7d2"),
    "unisex": ("#495057", "#ced4da"),
}

LEGACY_HAIRSTYLE_ALIASES = {
    "american-spiky": "male-forward-spikes",
    "short-texture": "male-french-short-texture",
    "korean-middle-part": "male-middle-micro-part",
    "french-curl": "female-french-lazy-waves",
    "wolf-cut": "male-wolf-tail",
}

LEGACY_SCENE_ALIASES = {
    "lifestyle-interior": "indoor-film-lifestyle",
    "cafe": "cafe-candid-seat",
    "studio": "studio-solid-backdrop",
    "city-night": "city-neon-night",
}

IDENTITY_LOCK_SECTION = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真。"
    "第一优先级是严格保留参考人物的真实身份特征，保证一眼看出是同一个人。"
    "以上传照片中的人物为原型，不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质，"
    "不改变性别表达，不换脸，不生成第二个人。"
    "忽略原照片中的背景、原服饰、原发型和原有动作，仅保留参考人物本身，进行换发和换背景创作。"
    "主体必须始终是同一位单人肖像，仅对发型、场景、动作、表情和服装进行艺术化创作。"
)

OUTPUT_FORMAT_SECTION = (
    "只输出 1 张完整成片，不要拼图，不要多宫格，不要在同一画面里同时展示多个动作版本或多个发型版本。"
)

QUALITY_SECTION = (
    "皮肤质感真实自然，不过度磨皮，不过度妆感，保留真实面部纹理与发丝细节，"
    "脸部清晰对焦，光影过渡自然，整体高级、自然、和谐。"
)

NEGATIVE_CONSTRAINTS_SECTION = (
    "不要换脸、不要改变性别表达、不要生成第二个人、不要多人同框、不要双脸、不要身份漂移、"
    "不要整容感、AI 脸、过度磨皮、塑料皮肤、五官漂移、错位眼睛、手指异常、耳朵变形、"
    "发际线异常、假发感、不要背景杂乱、光影冲突、不要过强滤镜、过度锐化、不要文字水印、不要拼图排版。"
)


def _load_json(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _normalize_sentence(text: str) -> str:
    return text.strip().rstrip("。；,.，")


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _resolve_alias(category: str, template_id: str) -> str:
    if category == "hairstyle":
        return LEGACY_HAIRSTYLE_ALIASES.get(template_id, template_id)
    if category == "scene":
        return LEGACY_SCENE_ALIASES.get(template_id, template_id)
    return template_id


def _pick_palette(category: str, gender: str, style_line: str) -> tuple[str, str]:
    base_a, base_b = STYLE_LINE_PALETTES.get(style_line, ("#334155", "#cbd5e1"))
    accent_a, accent_b = HAIRSTYLE_PALETTES.get(gender, HAIRSTYLE_PALETTES["unisex"])
    if category == "scene":
        return base_a, base_b
    return accent_a, accent_b


def _build_scene_template(raw: dict) -> dict:
    style_line = raw["styleLine"]
    return {
        "id": raw["id"],
        "name": raw["title"],
        "description": raw["summary"],
        "gender": "unisex",
        "gender_label": GENDER_LABELS["unisex"],
        "style_line": style_line,
        "style_line_label": STYLE_LINE_LABELS.get(style_line, style_line),
        "tags": raw.get("detailTags", []),
        "environment": raw["environment"],
        "lighting": raw["lighting"],
        "style_mood": raw["styleMood"],
        "expressions": raw.get("expressions", []),
        "actions": raw.get("actions", []),
        "outfit_hints": raw.get("outfitHints", []),
        "constraints": raw.get("constraints", []),
        "pairing_advice": raw.get("pairingAdvice", []),
        "shot_advice": raw["shotAdvice"],
        "palette": _pick_palette("scene", "unisex", style_line),
    }


def _build_hairstyle_template(raw: dict) -> dict:
    gender = raw["gender"]
    style_line = raw["styleLine"]
    return {
        "id": raw["id"],
        "name": raw["title"],
        "description": raw["summary"],
        "gender": gender,
        "gender_label": GENDER_LABELS.get(gender, gender),
        "style_line": style_line,
        "style_line_label": STYLE_LINE_LABELS.get(style_line, style_line),
        "tags": raw.get("detailTags", []),
        "prompt_core": raw["promptCore"],
        "constraints": raw.get("constraints", []),
        "pairing_advice": raw.get("pairingAdvice", []),
        "shot_advice": raw["shotAdvice"],
        "expression_action": raw.get("expressionAction", []),
        "palette": _pick_palette("hairstyle", gender, style_line),
    }


@lru_cache(maxsize=1)
def _catalog() -> dict[str, list[dict]]:
    scenes = [_build_scene_template(item) for item in _load_json("scenes.json")]
    male_hairstyles = [
        _build_hairstyle_template(item) for item in _load_json("hairstyles_male.json")
    ]
    female_hairstyles = [
        _build_hairstyle_template(item) for item in _load_json("hairstyles_female.json")
    ]
    return {
        "scenes": scenes,
        "hairstyles": [*male_hairstyles, *female_hairstyles],
    }


SCENES = _catalog()["scenes"]
HAIRSTYLES = _catalog()["hairstyles"]


def _find_template(items: Iterable[dict], template_id: str) -> dict | None:
    for item in items:
        if item["id"] == template_id:
            return item
    return None


def get_hairstyle(template_id: str) -> dict | None:
    resolved_id = _resolve_alias("hairstyle", template_id)
    return _find_template(HAIRSTYLES, resolved_id)


def get_scene(template_id: str) -> dict | None:
    resolved_id = _resolve_alias("scene", template_id)
    return _find_template(SCENES, resolved_id)


def build_prompt(hairstyle: dict, scene: dict) -> str:
    expression_text = "、".join(_dedupe_keep_order(scene.get("expressions", []))[:3])
    action_items = _dedupe_keep_order(
        [*scene.get("actions", []), *hairstyle.get("expression_action", [])]
    )
    outfit_text = "；".join(_dedupe_keep_order(scene.get("outfit_hints", []))[:2])
    constraint_text = "；".join(
        _dedupe_keep_order([*scene.get("constraints", []), *hairstyle.get("constraints", [])])
    )

    return "\n".join(
        [
            IDENTITY_LOCK_SECTION,
            OUTPUT_FORMAT_SECTION,
            f"构图：{_normalize_sentence(scene['shot_advice'])}。",
            (
                f"场景：{_normalize_sentence(scene['environment'])}。"
                f" 光线：{_normalize_sentence(scene['lighting'])}。"
                f" 风格氛围：{_normalize_sentence(scene['style_mood'])}。"
            ),
            f"人物表情：{expression_text}。",
            f"人物动作：{'、'.join(action_items[:5])}。",
            f"服饰：{outfit_text or '白色宽松衬衫，内搭浅色背心或吊带'}。",
            f"人物发型：{_normalize_sentence(hairstyle['prompt_core'])}。",
            f"关键约束：{constraint_text}。",
            QUALITY_SECTION,
            f"负面约束：{NEGATIVE_CONSTRAINTS_SECTION}",
        ]
    )


def template_cover_svg(category: str, template: dict) -> str:
    color_a, color_b = template["palette"]
    title = template["name"]
    label = "HAIR" if category == "hairstyles" else "SCENE"
    meta = template.get("gender_label") if category == "hairstyles" else template.get("style_line_label")
    description = template["description"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="480" viewBox="0 0 720 480">
  <defs>
    <linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="{color_a}" />
      <stop offset="100%" stop-color="{color_b}" />
    </linearGradient>
  </defs>
  <rect width="720" height="480" rx="32" fill="url(#bg)" />
  <circle cx="580" cy="120" r="92" fill="rgba(255,255,255,0.12)" />
  <circle cx="140" cy="380" r="120" fill="rgba(255,255,255,0.08)" />
  <text x="56" y="88" fill="#ffffff" font-size="28" font-family="Arial, sans-serif" opacity="0.82">{label}</text>
  <text x="56" y="140" fill="#ffffff" font-size="24" font-family="Arial, sans-serif" opacity="0.9">{meta}</text>
  <text x="56" y="220" fill="#ffffff" font-size="52" font-family="Arial, sans-serif" font-weight="700">{title}</text>
  <text x="56" y="286" fill="#ffffff" font-size="24" font-family="Arial, sans-serif" opacity="0.85">{description}</text>
  <rect x="56" y="346" width="188" height="52" rx="26" fill="rgba(255,255,255,0.18)" />
  <text x="90" y="380" fill="#ffffff" font-size="22" font-family="Arial, sans-serif">Faceprompt</text>
</svg>"""
