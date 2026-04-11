from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.services import male_hairstyle_presets

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "faceprompt"
TEMPLATE_COVER_VERSION = "visual-v2"
SUPPORTED_ASPECT_RATIOS = (
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "21:9",
    "5:4",
    "4:5",
    "1:4",
    "4:1",
    "1:8",
    "8:1",
)
SUPPORTED_RESOLUTIONS = ("512px", "1K", "2K", "4K")
PLAN_SAFE_ASPECT_RATIOS = (
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "21:9",
    "5:4",
    "4:5",
)
UNIFIED_PLAN_RESOLUTIONS = ("2K",)
DEFAULT_GENERATOR_BACKEND = "premium"
DEFAULT_ASPECT_RATIO = "3:4"
DEFAULT_RESOLUTION = "2K"
DEFAULT_HAIR_COLOR_TONE = "natural_black"
DEFAULT_HAIR_COLOR_TECHNIQUE = "solid"
PROFESSIONAL_HAIR_COLOR_DATA_FILE = "hair_color_professional_solutor.json"

GENERATOR_BACKEND_CAPABILITIES = {
    "premium": {
        "label": "默认方案",
        "description": "固定返回 1 张换发预览和 2 张场景成片，支持常用画幅，清晰度统一为 2K。",
        "supports_reference_image": True,
        "aspect_ratios": PLAN_SAFE_ASPECT_RATIOS,
        "resolutions": UNIFIED_PLAN_RESOLUTIONS,
        "default_aspect_ratio": "3:4",
        "default_resolution": "2K",
        "hair_backend": "nano_banana_pro",
        "scene_backend": "seedream",
        "scene_model_tier": "premium",
        "badge": "Nano Banana Pro + Seedream 4.5",
    },
}

CURATED_SHOWCASES = (
    {
        "id": "showcase-morning-soft-bob",
        "title": "清晨软光锁骨发",
        "summary": "柔和窗光配锁骨层次，适合自然松弛的日常写真。",
        "hairstyle_id": "female-collarbone-xinzhilei",
        "scene_id": "morning-window-softlight",
        "generator_backend": "premium",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    },
    {
        "id": "showcase-cafe-wave",
        "title": "咖啡馆微卷长发",
        "summary": "轻卷发尾搭配咖啡馆抓拍，氛围柔软又显精致。",
        "hairstyle_id": "female-soft-wave-collarbone",
        "scene_id": "cafe-candid-seat",
        "generator_backend": "premium",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    },
    {
        "id": "showcase-rainy-straight",
        "title": "雨窗黑长直氛围",
        "summary": "黑长直与雨天窗边更容易做出安静情绪感。",
        "hairstyle_id": "female-black-long-straight",
        "scene_id": "rainy-window-mood",
        "generator_backend": "premium",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    },
    {
        "id": "showcase-study-forward-spikes",
        "title": "书房前刺头人像",
        "summary": "利落短发配木质书房，整体会更干净有精神。",
        "hairstyle_id": "male-forward-spikes",
        "scene_id": "walnut-study-portrait",
        "generator_backend": "premium",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    },
    {
        "id": "showcase-film-parted",
        "title": "室内生活感三七分",
        "summary": "韩系三七分适合自然生活流场景，完成度更稳定。",
        "hairstyle_id": "male-korean-37-part",
        "scene_id": "indoor-film-lifestyle",
        "generator_backend": "premium",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    },
    {
        "id": "showcase-side-light-vintage",
        "title": "强侧光复古背头",
        "summary": "侧光结构和复古背头更适合偏时尚的大片氛围。",
        "hairstyle_id": "male-vintage-slick-back",
        "scene_id": "dramatic-side-light",
        "generator_backend": "premium",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    },
)

LEGACY_GENERATOR_BACKEND_ALIASES = {
    "seedream": "premium",
    "nano_banana_pro": "premium",
    "nano_banana_2": "premium",
    "basic": "premium",
    "sora_image": "premium",
}

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
PROMPT_MODE_ALIASES = {
    "hair_only": "hair_only",
    "hairstyle_only": "hair_only",
    "scene_only": "scene_only",
    "full_stylize": "full_stylize",
}
VALID_PROMPT_MODES = set(PROMPT_MODE_ALIASES)
DEFAULT_STYLING_BY_STYLE_LINE = {
    "realistic_editorial": "unisex-natural-soft",
    "fashion_editorial": "unisex-structured-editorial",
}

IDENTITY_LOCK_SECTION = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真。"
    "第一优先级是严格保留参考人物的真实身份特征，保证一眼看出是同一个人。"
    "以上传照片中的人物为原型，不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质，"
    "不改变性别表达，不换脸，不生成第二个人。"
    "忽略原照片中的背景、原服饰、原发型和原有动作，仅保留参考人物本身，进行换发和换背景创作。"
    "主体必须始终是同一位单人肖像，仅对发型、场景、动作、表情和服装进行艺术化创作。"
)

HAIRSTYLE_ONLY_IDENTITY_LOCK_SECTION = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像图。"
    "第一优先级是严格保留参考人物的真实身份特征，保证一眼看出是同一个人。"
    "以上传照片中的人物为原型，不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质，"
    "不改变性别表达，不换脸，不生成第二个人。"
    "不改变人物原始肤色倾向、年龄感和五官结构；允许做轻度肤色均匀化、瑕疵弱化和通透度优化，但仍需保证一眼看出是同一人。"
    "只更换图中人物的发型和发色，除头发、刘海、鬓角、后颈发区和发际线相关区域外，"
    "尽量保持原图中的背景、服饰、姿态、表情、构图、镜头距离、光线和氛围不变。"
)

SCENE_ONLY_IDENTITY_LOCK_SECTION = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真。"
    "第一优先级是严格保留参考人物的真实身份特征，保证一眼看出是同一个人。"
    "以上传照片中的人物为原型，不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质和发型，"
    "不改变性别表达，不换脸，不生成第二个人。"
    "忽略原照片中的背景、原服饰、原有动作，仅保留参考人物本身，进行换背景创作。"
    "主体必须始终是同一位单人肖像，仅对场景、动作、表情和服装进行艺术化创作。"
)

OUTPUT_FORMAT_SECTION = (
    "只输出 1 张完整成片，不要拼图，不要多宫格，不要在同一画面里同时展示多个动作版本或多个发型版本。"
)

QUALITY_SKIN_TEXTURE_SECTION = (
    "皮肤观感自然干净、细腻通透，面部瑕疵适度收敛，肤色均匀，保留少量真实纹理与正常皮肤质感；"
    "五官边界清楚，面部光影过渡柔和，不出现明显痘坑、脏感毛孔或粗糙颗粒感。"
)

QUALITY_IMAGE_FINISH_SECTION = (
    "脸部清晰对焦，光影过渡自然，整体高级、自然、和谐。"
)

QUALITY_SECTION = QUALITY_SKIN_TEXTURE_SECTION + QUALITY_IMAGE_FINISH_SECTION

HAIRSTYLE_ONLY_CONSTRAINTS_SECTION = (
    "仅允许修改头发、刘海、鬓角、后颈发区和发际线相关视觉效果，以及这些区域内的发色、明暗层次与染发细节，不要改动背景、服饰、表情、动作和构图；"
    "发型必须贴合原人物头骨结构、头部朝向、耳位位置、肩颈遮挡关系与镜头透视；"
    "不能把新发型做成悬浮假发、错位发片或不贴合头皮的假发套效果。"
)

SCENE_ONLY_CONSTRAINTS_SECTION = (
    "人物发型必须保持参考图中已经生成完成的现有发型，不要二次修改发型种类；"
    "不要改变发长、顶部体积、刘海、分线、鬓角、后颈发区、卷度、发色和整体轮廓；"
    "动作、表情、服装、场景和布光变化不能破坏既有发型结构、头皮贴合关系、发丝走向和发色过渡。"
)

NEGATIVE_IDENTITY_ARTIFACT_SECTION = (
    "不要换脸、不要改变性别表达、不要生成第二个人、不要多人同框、不要双脸、不要身份漂移、"
    "不要整容感、AI 脸、过度磨皮、塑料皮肤、五官漂移、错位眼睛、手指异常、耳朵变形、"
    "发际线异常、假发感、不要背景杂乱、光影冲突、不要过强滤镜、过度锐化、不要文字水印、不要拼图排版、"
    "不要过度放大毛孔、痘印、痘坑、闭口、黑头、泛红和皮肤粗糙颗粒感；"
    "不要蜡像皮、假面感、失去皮肤体积。"
)

NEGATIVE_PHYSICAL_LOGIC_SECTION = (
    "图片需要符合物理逻辑，不要在画面中多出不合逻辑的手和身体部位。"
    "不可以有不符合物理逻辑的身体部位（例如同时出现多于两只手的情况）。"
)

NEGATIVE_CONSTRAINTS_SECTION = (
    NEGATIVE_IDENTITY_ARTIFACT_SECTION + NEGATIVE_PHYSICAL_LOGIC_SECTION
)
HAND_ACTION_KEYWORDS = (
    "单手",
    "双手",
    "抬手",
    "扶住",
    "扶额",
    "扶椅",
    "扶背",
    "手扶",
    "手指",
    "指尖",
    "轻握",
    "握住",
    "握杯",
    "托住",
    "撑住",
    "抓起",
    "抓头发",
    "抓头顶",
    "拨开",
    "拨动",
    "拨到",
    "拨发",
    "拢住",
    "拢起",
    "拿起",
    "拿着",
    "碰触",
    "触碰",
    "按住",
    "挡住",
    "压住",
    "捏",
    "整理",
    "挂到耳后",
    "挂在耳后",
    "抱臂",
)

HAIR_TOUCH_ACTION_KEYWORDS = (
    "发丝",
    "头发",
    "碎发",
    "抓头发",
    "抓起头顶",
    "抓起顶部",
    "拨开发丝",
    "拨开脸侧",
    "拨发",
    "整理额前",
    "整理耳侧",
    "整理窗边发丝",
    "轻碰发型",
    "触碰耳侧发丝",
)

HAIR_MOTION_REDEFINITION_KEYWORDS = (
    "发丝被风",
    "风掀起",
    "吹起发丝",
    "吹散",
    "吹乱",
    "甩发",
    "甩动头发",
    "前落刘海",
    "掀起刘海",
)

LOCKED_HAIR_TEXT_REPLACEMENTS = (
    ("发型动态是视觉关键", "服装动态与空气流动感是视觉重点，主发型结构必须严格锁定为参考图中的静态完成状态"),
    ("突出风感发丝", "突出空气流动感与人物轮廓"),
    ("风吹起发丝和衣角", "风主要作用于衣角与空气流动，只允许极少量边缘碎发轻微摆动"),
    ("风吹起发丝", "风主要作用于空气流动，只允许极少量边缘碎发轻微摆动"),
    ("天台风感能让发型动态更强", "天台风感能强化服装动态与空气流动张力"),
    ("发型不能被风吹散到失去结构", "主发型结构必须严格锁定，不允许被风力吹散或改写"),
    ("局部发丝被边缘光勾亮", "人物轮廓边缘被柔和边缘光勾亮"),
    ("头发边缘出现暖色轮廓光", "人物轮廓边缘出现暖色轮廓光"),
    ("让头发和脸的分离清楚", "让人物轮廓和面部的分离清楚"),
    ("单侧硬光切过脸部和发型，亮暗分区明确，鼻梁、颧骨和发丝纹理被明显勾出", "单侧硬光切过脸部与肩颈轮廓，亮暗分区明确，鼻梁、颧骨和服装纹理被明显勾出"),
    ("强侧光最适合做结构型发型展示，尤其能放大发丝纹理", "强侧光最适合做结构型轮廓展示，尤其能强化面部与肩颈的立体感"),
    ("强调发型定型后的精致状态和明星感", "强调妆造完成后的精致状态和明星感"),
)

LIGHT_DIRECTION_LABELS = {
    "front": "正面定向入光",
    "side": "侧向入光",
    "back": "背后或侧后方入光",
    "top": "顶部下落光",
    "mixed": "多方向混合入光",
}

LIGHT_QUALITY_LABELS = {
    "soft": "柔光",
    "medium": "中等硬度光线",
    "hard": "偏硬光线",
}

COLOR_TEMPERATURE_LABELS = {
    "cool": "冷色温",
    "neutral": "中性色温",
    "warm": "暖色温",
    "mixed": "冷暖混合色温",
}

CONTRAST_LEVEL_LABELS = {
    "low": "低反差",
    "medium": "中等反差",
    "high": "高反差",
}

SHADOW_DENSITY_LABELS = {
    "light": "轻薄柔和",
    "balanced": "保留明暗层次",
    "deep": "更深但可读",
}

HAIR_HIGHLIGHT_LABELS = {
    "soft_edge": "柔和贴边",
    "clean_rim": "清晰但受控",
    "controlled_specular": "受控且具有精致反射感",
    "none": "不额外强调",
}

SKIN_RENDERING_LABELS = {
    "soft_texture": "柔和真实纹理",
    "clean_texture": "干净清晰纹理",
    "structured_texture": "更强调骨相与结构纹理",
}

EXPOSURE_BIAS_LABELS = {
    "slightly_under": "略微压曝光以保留氛围",
    "neutral": "标准曝光",
    "slightly_over": "轻微提亮但不过曝",
}

SCENE_SAMPLE_IMAGE_FALLBACKS = {
    "lifestyle": {
        "female": ("female3",),
        "male": ("male2",),
    },
    "fashion": {
        "female": ("female2",),
        "male": ("male1",),
    },
    "outdoor": {
        "female": ("female1",),
        "male": ("male3",),
    },
}


@dataclass(frozen=True)
class PromptBlock:
    key: str
    label: str
    text: str


@dataclass(frozen=True)
class PromptAssembly:
    mode: str
    blocks: tuple[PromptBlock, ...]

    def render(self) -> str:
        return "\n".join(block.text for block in self.blocks if block.text.strip())


@dataclass(frozen=True)
class PromptRule:
    mode: str
    required_blocks: tuple[str, ...]
    optional_blocks: tuple[str, ...] = ()
    forbidden_blocks: tuple[str, ...] = ()
    description: str = ""


def get_prompt_block_labels() -> dict[str, str]:
    return {
        "identity_lock": "身份锁定",
        "output_spec": "输出规格",
        "edit_scope": "编辑范围",
        "hair_shape": "主发型结构",
        "bangs": "刘海系统",
        "hair_color": "发色系统",
        "hair_constraints": "发型关键约束",
        "scene": "场景系统",
        "styling": "妆造系统",
        "subject_performance": "人物表现系统",
        "quality_control": "质量控制",
        "negative_constraints": "负面约束",
        "hair_shape_lock": "发型锁定",
        "bangs_lock": "刘海锁定",
        "hair_color_lock": "发色锁定",
        "hair_motion_constraint": "风感约束",
        "output_format": "输出规格",
        "hair_target": "主发型结构",
        "hair_color_target": "发色系统",
        "hair_color_technique": "发色系统",
        "hair_lock": "发型锁定",
        "makeup": "妆造系统",
        "outfit": "妆造系统",
        "shot": "场景系统",
        "scene_environment": "场景系统",
        "scene_lighting": "场景系统",
        "scene_mood": "场景系统",
        "expression": "人物表现系统",
        "subject_action": "人物表现系统",
        "styling_constraints": "妆造系统",
        "quality_skin_texture": "质量控制",
        "quality_image_finish": "质量控制",
        "negative_identity_artifact": "负面约束",
        "negative_physical_logic": "负面约束",
    }


def _normalize_prompt_mode(mode: str) -> str:
    normalized = PROMPT_MODE_ALIASES.get(mode.strip().lower())
    if normalized is None:
        raise ValueError(f"Unsupported prompt mode: {mode}")
    return normalized


def _normalize_generator_backend(backend_id: str | None) -> str:
    raw = (backend_id or DEFAULT_GENERATOR_BACKEND).strip().lower()
    return LEGACY_GENERATOR_BACKEND_ALIASES.get(raw, raw)


def get_generation_plan(backend_id: str | None) -> dict | None:
    resolved_backend = _normalize_generator_backend(backend_id)
    capability = GENERATOR_BACKEND_CAPABILITIES.get(resolved_backend)
    if capability is None:
        return None
    settings = get_settings()
    scene_model_name = settings.seedream_premium_model
    return {
        "id": resolved_backend,
        **capability,
        "scene_model_name": scene_model_name,
    }


def _backend_enabled(backend_id: str) -> bool:
    settings = get_settings()
    if settings.use_mock_generator:
        return True
    plan = get_generation_plan(backend_id)
    if plan is None:
        return False
    if not settings.ark_api_keys:
        return False
    if plan["hair_backend"] == "nano_banana_pro":
        return settings.has_nano_banana_pro()
    return False


def get_generation_backend_catalog() -> list[dict]:
    return [
        {
            "id": backend_id,
            "name": config["label"],
            "description": config["description"],
            "enabled": _backend_enabled(backend_id),
            "supports_reference_image": bool(config["supports_reference_image"]),
            "aspect_ratios": list(config["aspect_ratios"]),
            "resolutions": list(config["resolutions"]),
            "default_aspect_ratio": config["default_aspect_ratio"],
            "default_resolution": config["default_resolution"],
        }
        for backend_id, config in GENERATOR_BACKEND_CAPABILITIES.items()
    ]


def get_curated_showcases() -> list[dict]:
    return [dict(item) for item in CURATED_SHOWCASES]


def _load_json(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _build_hair_color_tone(raw: dict) -> dict:
    allowed_techniques = list(
        dict.fromkeys(str(item).strip() for item in raw.get("allowedTechniques", []) if str(item).strip())
    )
    default_technique = str(raw.get("defaultTechnique") or DEFAULT_HAIR_COLOR_TECHNIQUE).strip()
    if default_technique not in allowed_techniques:
        default_technique = allowed_techniques[0] if allowed_techniques else DEFAULT_HAIR_COLOR_TECHNIQUE
    return {
        "id": raw["id"],
        "label": raw["label"],
        "hex": raw["hex"],
        "description": raw["description"],
        "allowed_techniques": allowed_techniques,
        "default_technique": default_technique,
        "display_priority": int(raw.get("displayPriority") or 999),
    }


def _build_hair_color_technique(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "label": raw["label"],
        "description": raw["description"],
        "display_priority": int(raw.get("displayPriority") or 999),
    }


@lru_cache(maxsize=1)
def _hair_color_catalog() -> dict[str, list[dict]]:
    tones = sorted(
        (_build_hair_color_tone(item) for item in _load_json("hair_colors.json")),
        key=lambda item: (item["display_priority"], item["label"]),
    )
    techniques = sorted(
        (_build_hair_color_technique(item) for item in _load_json("hair_color_techniques.json")),
        key=lambda item: (item["display_priority"], item["label"]),
    )
    return {
        "tones": tones,
        "techniques": techniques,
    }


HAIR_COLOR_TONES = _hair_color_catalog()["tones"]
HAIR_COLOR_TECHNIQUES = _hair_color_catalog()["techniques"]


def get_hair_color_tone(tone_id: str | None) -> dict | None:
    if not tone_id:
        return None
    return _find_template(HAIR_COLOR_TONES, tone_id)


def get_hair_color_technique(technique_id: str | None) -> dict | None:
    if not technique_id:
        return None
    return _find_template(HAIR_COLOR_TECHNIQUES, technique_id)


def _build_professional_hair_color(raw: dict) -> dict:
    hair_color_maps = {
        "tones": {item["id"]: item["label"] for item in HAIR_COLOR_TONES},
        "techniques": {item["id"]: item["label"] for item in HAIR_COLOR_TECHNIQUES},
    }
    keywords = list(
        dict.fromkeys(str(item).strip() for item in raw.get("keywords", []) if str(item).strip())
    )
    mapped_technique_ids = list(
        dict.fromkeys(str(item).strip() for item in raw.get("mapped_technique_ids", []) if str(item).strip())
    )
    mapped_tone_id = str(raw.get("mapped_tone_id") or "").strip()
    series_name = str(raw.get("series_name") or "").strip()
    code = str(raw.get("code") or "").strip()
    visual_note = str(raw.get("visual_note") or "").strip()
    return {
        "id": str(raw.get("id") or "").strip(),
        "brand": str(raw.get("brand") or "SOLUTOR").strip(),
        "series_name": series_name,
        "series_type": str(raw.get("series_type") or series_name).strip(),
        "series_description": str(raw.get("series_description") or "").strip(),
        "code": code,
        "label": f"{code} · {series_name}" if code and series_name else code or series_name,
        "depth_prefix": str(raw.get("depth_prefix") or "").strip(),
        "depth_level": int(raw["depth_level"]) if raw.get("depth_level") not in (None, "") else None,
        "tone_primary": str(raw.get("tone_primary") or "").strip() or None,
        "tone_secondary": str(raw.get("tone_secondary") or "").strip() or None,
        "visual_note": visual_note,
        "hex_estimate": str(raw.get("hex_estimate") or "").strip(),
        "rgb_estimate": str(raw.get("rgb_estimate") or "").strip() or None,
        "keywords": keywords,
        "mapped_tone_id": mapped_tone_id,
        "mapped_tone_label": hair_color_maps["tones"].get(mapped_tone_id, mapped_tone_id or None),
        "mapped_technique_ids": mapped_technique_ids,
        "mapped_technique_labels": [
            hair_color_maps["techniques"].get(item, item) for item in mapped_technique_ids
        ],
        "mapped_temperature": str(raw.get("mapped_temperature") or "").strip() or None,
        "mapped_depth_bucket": str(raw.get("mapped_depth_bucket") or "").strip() or None,
        "prompt_alias": str(raw.get("prompt_alias") or "").strip() or None,
        "display_priority": int(raw.get("display_priority") or raw.get("displayPriority") or 999),
        "is_recommended_for_generation": bool(raw.get("is_recommended_for_generation", True)),
        "sort_key": str(raw.get("sort_key") or code or series_name).strip(),
    }


@lru_cache(maxsize=1)
def _professional_hair_color_catalog() -> dict[str, list[dict]]:
    options = sorted(
        (_build_professional_hair_color(item) for item in _load_json(PROFESSIONAL_HAIR_COLOR_DATA_FILE)),
        key=lambda item: (item["display_priority"], item["sort_key"], item["label"]),
    )
    series_map: dict[str, dict] = {}
    for item in options:
        series_id = item["series_type"]
        current = series_map.setdefault(
            series_id,
            {
                "id": series_id,
                "label": item["series_name"],
                "description": item["series_description"],
                "brand": item["brand"],
                "option_count": 0,
                "recommended_option_count": 0,
                "cover_hex": item["hex_estimate"] or None,
                "display_priority": item["display_priority"],
                "is_recommended_for_generation": False,
            },
        )
        current["option_count"] += 1
        if item["is_recommended_for_generation"]:
            current["recommended_option_count"] += 1
            current["is_recommended_for_generation"] = True
        current["display_priority"] = min(current["display_priority"], item["display_priority"])
        if not current["cover_hex"] and item["hex_estimate"]:
            current["cover_hex"] = item["hex_estimate"]
    series = sorted(
        series_map.values(),
        key=lambda item: (item["display_priority"], item["label"]),
    )
    return {"series": series, "options": options}


PROFESSIONAL_HAIR_COLOR_OPTIONS = _professional_hair_color_catalog()["options"]
PROFESSIONAL_HAIR_COLOR_SERIES = _professional_hair_color_catalog()["series"]


def get_professional_hair_color(professional_id: str | None) -> dict | None:
    if not professional_id:
        return None
    return _find_template(PROFESSIONAL_HAIR_COLOR_OPTIONS, professional_id)


def get_professional_hair_color_catalog() -> list[dict]:
    return [dict(item) for item in PROFESSIONAL_HAIR_COLOR_OPTIONS]


def get_professional_hair_color_series_catalog() -> list[dict]:
    return [dict(item) for item in PROFESSIONAL_HAIR_COLOR_SERIES]


def _infer_default_hair_color_tone(prompt_text: str, gender: str | None = None) -> str:
    blob = prompt_text.lower()
    if any(keyword in blob for keyword in ("蓝黑",)):
        return "blue_black"
    if any(keyword in blob for keyword in ("亚麻", "浅金", "金色", "金棕")):
        return "linen_blonde"
    if any(keyword in blob for keyword in ("雾灰", "灰棕", "冷棕", "青木灰", "冷深棕")):
        return "ash_brown"
    if any(keyword in blob for keyword in ("蜂蜜", "奶茶", "茶棕", "焦糖")):
        return "honey_brown"
    if any(keyword in blob for keyword in ("摩卡", "可可", "巧克力")):
        return "mocha_brown"
    if any(keyword in blob for keyword in ("栗棕", "栗色")):
        return "chestnut_brown"
    if any(keyword in blob for keyword in ("深棕", "黑棕", "极深棕", "复古深色")):
        return "dark_brown"
    if any(keyword in blob for keyword in ("乌黑", "自然黑", "黑色")):
        return "natural_black"
    return "dark_brown" if gender == "female" else DEFAULT_HAIR_COLOR_TONE


def _empty_hair_color_selection() -> dict[str, str]:
    return {
        "tone_id": "",
        "tone_label": "",
        "tone_hex": "",
        "technique_id": "",
        "technique_label": "",
        "technique_description": "",
        "professional_id": "",
        "professional_brand": "",
        "professional_series": "",
        "professional_series_label": "",
        "professional_code": "",
        "professional_note": "",
        "professional_hex_estimate": "",
        "professional_prompt_alias": "",
    }


def _build_professional_selection_fields(professional: dict | None) -> dict[str, str]:
    empty_fields = _empty_hair_color_selection()
    if professional is None:
        return {
            key: empty_fields[key]
            for key in (
                "professional_id",
                "professional_brand",
                "professional_series",
                "professional_series_label",
                "professional_code",
                "professional_note",
                "professional_hex_estimate",
                "professional_prompt_alias",
            )
        }
    return {
        "professional_id": professional["id"],
        "professional_brand": professional["brand"],
        "professional_series": professional["series_type"],
        "professional_series_label": professional["series_name"],
        "professional_code": professional["code"],
        "professional_note": professional["visual_note"],
        "professional_hex_estimate": professional["hex_estimate"],
        "professional_prompt_alias": professional.get("prompt_alias") or "",
    }


def normalize_hair_color_selection(
    *,
    tone_id: str | None = None,
    technique_id: str | None = None,
    professional_id: str | None = None,
    hairstyle: dict | None = None,
    detected_tone_id: str | None = None,
    strict_professional: bool = True,
) -> dict[str, str]:
    requested_professional = get_professional_hair_color(professional_id)
    if professional_id and requested_professional is None and strict_professional:
        raise ValueError(f"Unknown professional hair color: {professional_id}")
    if requested_professional and not requested_professional.get("is_recommended_for_generation"):
        if strict_professional:
            raise ValueError("Selected professional hair color is not available for generation.")
        requested_professional = None

    requested_tone = get_hair_color_tone(tone_id)
    detected_tone = get_hair_color_tone(detected_tone_id)
    hairstyle_default_tone = get_hair_color_tone(
        hairstyle.get("default_hair_color_tone") if hairstyle else None
    )
    professional_tone = get_hair_color_tone(
        requested_professional.get("mapped_tone_id") if requested_professional else None
    )
    selected_tone = (
        professional_tone
        or requested_tone
        or detected_tone
        or hairstyle_default_tone
        or get_hair_color_tone(DEFAULT_HAIR_COLOR_TONE)
        or HAIR_COLOR_TONES[0]
    )

    allowed_techniques = selected_tone.get("allowed_techniques", [])
    requested_technique = get_hair_color_technique(technique_id)
    selected_technique = None
    if requested_professional is not None:
        professional_candidates = []
        if requested_technique is not None:
            professional_candidates.append(requested_technique["id"])
        professional_candidates.extend(requested_professional.get("mapped_technique_ids", []))
        professional_candidates.append(selected_tone.get("default_technique"))
        professional_candidates.extend(allowed_techniques)
        for candidate_id in professional_candidates:
            if candidate_id not in allowed_techniques:
                continue
            candidate = get_hair_color_technique(candidate_id)
            if candidate is not None:
                selected_technique = candidate
                break
    else:
        if requested_technique and requested_technique["id"] in allowed_techniques:
            selected_technique = requested_technique
        if selected_technique is None:
            selected_technique = get_hair_color_technique(selected_tone.get("default_technique"))
        if selected_technique is None or selected_technique["id"] not in allowed_techniques:
            selected_technique = get_hair_color_technique(
                allowed_techniques[0] if allowed_techniques else DEFAULT_HAIR_COLOR_TECHNIQUE
            )
    if selected_technique is None:
        selected_technique = HAIR_COLOR_TECHNIQUES[0]

    selection = _empty_hair_color_selection()
    selection.update(
        {
            "tone_id": selected_tone["id"],
            "tone_label": selected_tone["label"],
            "tone_hex": selected_tone["hex"],
            "technique_id": selected_technique["id"],
            "technique_label": selected_technique["label"],
            "technique_description": selected_technique["description"],
        }
    )
    selection.update(_build_professional_selection_fields(requested_professional))
    return selection


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


def _make_prompt_block(key: str, text: str) -> PromptBlock | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    labels = get_prompt_block_labels()
    return PromptBlock(key=key, label=labels.get(key, key), text=cleaned)


def _assemble_prompt(mode: str, blocks: list[PromptBlock | None]) -> PromptAssembly:
    normalized_mode = _normalize_prompt_mode(mode)
    assembly = PromptAssembly(
        mode=normalized_mode,
        blocks=tuple(block for block in blocks if block is not None),
    )
    _validate_prompt_assembly(assembly)
    return assembly


def _build_quality_blocks(*, mode: str = "full_stylize") -> list[PromptBlock | None]:
    detail_text = "同时保持发丝清晰分明、边缘自然贴合头皮、光影过渡真实可读。"
    if mode == "scene_only":
        detail_text += (
            "主体人物必须始终作为清晰近景主体，脸部解析度优先于背景氛围。"
            "五官边界、眉毛、睫毛、瞳孔边缘、鼻梁线、唇线与发际线要自然清晰可辨。"
            "皮肤保留细腻真实纹理与干净明暗层次，不要出现低清糊脸、压缩涂抹感、脏噪点或蜡感磨皮。"
            "发丝边缘与额头、耳侧、颈侧、衣领的遮挡关系必须准确自然，不要出现发块粘连、边缘断裂、局部漂浮或假发感。"
        )
    return [
        _make_prompt_block(
            "quality_control",
            "质量控制："
            f"{QUALITY_SKIN_TEXTURE_SECTION}"
            f"{QUALITY_IMAGE_FINISH_SECTION}"
            f"{detail_text}",
        ),
    ]


def _build_negative_blocks() -> list[PromptBlock | None]:
    return [
        _make_prompt_block(
            "negative_constraints",
            f"负面约束：{NEGATIVE_IDENTITY_ARTIFACT_SECTION}{NEGATIVE_PHYSICAL_LOGIC_SECTION}",
        ),
    ]


def get_prompt_rule_table() -> dict[str, PromptRule]:
    hair_only_rule = PromptRule(
        mode="hair_only",
        required_blocks=(
            "identity_lock",
            "output_spec",
            "edit_scope",
            "hair_shape",
            "bangs",
            "hair_color",
            "quality_control",
            "negative_constraints",
        ),
        forbidden_blocks=(
            "scene",
            "styling",
            "subject_performance",
            "hair_shape_lock",
            "bangs_lock",
            "hair_color_lock",
        ),
        description="只改头发系统，不改场景、服饰、表情、动作和构图。",
    )
    scene_only_rule = PromptRule(
        mode="scene_only",
        required_blocks=(
            "identity_lock",
            "output_spec",
            "edit_scope",
            "hair_shape_lock",
            "bangs_lock",
            "hair_color_lock",
            "hair_motion_constraint",
            "scene",
            "styling",
            "subject_performance",
            "quality_control",
            "negative_constraints",
        ),
        forbidden_blocks=("hair_shape", "bangs", "hair_color"),
        description="只改场景与妆造，锁定已经完成的头发系统。",
    )
    full_stylize_rule = PromptRule(
        mode="full_stylize",
        required_blocks=(
            "identity_lock",
            "output_spec",
            "edit_scope",
            "hair_shape",
            "bangs",
            "hair_color",
            "scene",
            "styling",
            "subject_performance",
            "quality_control",
            "negative_constraints",
        ),
        forbidden_blocks=("hair_shape_lock", "bangs_lock", "hair_color_lock"),
        description="一次完成头发、场景、妆造与人物表现的组合创作。",
    )
    return {
        "hair_only": hair_only_rule,
        "hairstyle_only": hair_only_rule,
        "scene_only": scene_only_rule,
        "full_stylize": full_stylize_rule,
    }


def _validate_prompt_assembly(assembly: PromptAssembly) -> None:
    rule = get_prompt_rule_table()[assembly.mode]
    keys = [block.key for block in assembly.blocks]
    missing = [key for key in rule.required_blocks if key not in keys]
    if missing:
        raise ValueError(f"{assembly.mode}: missing required prompt blocks {missing}")

    forbidden = [key for key in keys if key in rule.forbidden_blocks]
    if forbidden:
        raise ValueError(f"{assembly.mode}: forbidden prompt blocks present {forbidden}")

    duplicates = [key for key in set(keys) if keys.count(key) > 1]
    if duplicates:
        raise ValueError(f"{assembly.mode}: duplicate prompt blocks {sorted(duplicates)}")


def _format_option_list(items: Iterable[str]) -> str:
    return "；".join(_dedupe_keep_order(items))


def _action_uses_hands(action: str) -> bool:
    cleaned = action.strip()
    if not cleaned:
        return False
    return cleaned.startswith("手") or any(keyword in cleaned for keyword in HAND_ACTION_KEYWORDS)


def _select_one(items: Iterable[str], *, seed_source: str, label: str) -> str:
    choices = _dedupe_keep_order(items)
    if not choices:
        return ""
    if len(choices) == 1:
        return choices[0]
    digest = hashlib.sha256(f"{seed_source}:{label}".encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(choices)
    return choices[index]


def _filter_compatible_hairstyle_actions(
    subject_action: str, hairstyle_actions: Iterable[str]
) -> list[str]:
    actions = _dedupe_keep_order(hairstyle_actions)
    if not subject_action or not _action_uses_hands(subject_action):
        return actions
    return [action for action in actions if not _action_uses_hands(action)]


def _is_locked_hair_conflicting_action(action: str) -> bool:
    cleaned = action.strip()
    if not cleaned:
        return False
    return any(keyword in cleaned for keyword in HAIR_TOUCH_ACTION_KEYWORDS) or any(
        keyword in cleaned for keyword in HAIR_MOTION_REDEFINITION_KEYWORDS
    )


def _normalize_locked_hair_action_override(action: str | None) -> str | None:
    if not action:
        return None
    cleaned = action.strip()
    if not cleaned or _is_locked_hair_conflicting_action(cleaned):
        return None
    return cleaned


def _filter_scene_actions_for_locked_hairstyle(actions: Iterable[str]) -> list[str]:
    candidates = _dedupe_keep_order(actions)
    filtered = [action for action in candidates if not _is_locked_hair_conflicting_action(action)]
    return filtered


def _styling_scope_matches(styling: dict, preferred_gender: str | None) -> bool:
    if not preferred_gender:
        return True
    scope = str(styling.get("gender_scope") or styling.get("gender") or "unisex").strip()
    return scope in {preferred_gender, "unisex"}


def _scene_lighting_tags(scene: dict) -> list[str]:
    profile = scene.get("lighting_profile") or {}
    tags: list[str] = []
    quality = str(profile.get("light_quality") or "").strip()
    temperature = str(profile.get("color_temperature") or "").strip()
    contrast = str(profile.get("contrast_level") or "").strip()
    skin = str(profile.get("skin_rendering") or "").strip()
    exposure = str(profile.get("exposure_bias") or "").strip()
    if quality:
        tags.append(f"{quality}_light")
    if temperature:
        tags.append(f"{temperature}_light")
    if contrast:
        tags.append(f"{contrast}_contrast")
    if skin:
        tags.append(
            {
                "soft_texture": "soft_skin",
                "clean_texture": "clean_skin",
                "structured_texture": "structured_skin",
            }.get(skin, skin)
        )
    if exposure:
        tags.append(exposure)
    return _dedupe_keep_order(tags)


def _styling_supports_scene(styling: dict, scene: dict | None) -> bool:
    if scene is None:
        return True
    scene_id = str(scene.get("id") or "").strip()
    reference_source_ids = {
        str(item).strip()
        for item in scene.get("reference_source_ids", [])
        if str(item).strip()
    }
    is_scene_pipeline_draft = "scene-pipeline" in reference_source_ids
    incompatible_scene_ids = {
        str(item).strip()
        for item in styling.get("incompatible_scene_ids", [])
        if str(item).strip()
    }
    if scene_id and scene_id in incompatible_scene_ids:
        return False

    compatible_scene_ids = {
        str(item).strip()
        for item in styling.get("compatible_scene_ids", [])
        if str(item).strip()
    }
    if (
        compatible_scene_ids
        and scene_id
        and scene_id not in compatible_scene_ids
        and not is_scene_pipeline_draft
    ):
        return False

    lighting_tags = set(_scene_lighting_tags(scene))
    compatible_lighting_tags = {
        str(item).strip()
        for item in styling.get("compatible_lighting_tags", [])
        if str(item).strip()
    }
    if compatible_lighting_tags and lighting_tags and not (lighting_tags & compatible_lighting_tags):
        return False
    return True


def _matching_stylings(
    style_line: str,
    preferred_gender: str | None = None,
    scene: dict | None = None,
) -> list[dict]:
    candidates = [item for item in STYLINGS if item.get("style_line") == style_line]
    candidates = [item for item in candidates if _styling_supports_scene(item, scene)]
    if preferred_gender:
        exact = [
            item
            for item in candidates
            if str(item.get("gender_scope") or item.get("gender") or "").strip() == preferred_gender
        ]
        unisex = [
            item
            for item in candidates
            if str(item.get("gender_scope") or item.get("gender") or "").strip() == "unisex"
        ]
        fallback = [
            item
            for item in candidates
            if str(item.get("gender_scope") or item.get("gender") or "").strip()
            not in {preferred_gender, "unisex"}
        ]
        ordered = [*exact, *unisex, *fallback]
        if ordered:
            return ordered
    return candidates


def _default_styling(
    style_line: str,
    preferred_gender: str | None,
    seed_source: str,
    scene: dict | None = None,
) -> dict:
    style_line_candidates = [item for item in STYLINGS if item.get("style_line") == style_line]
    if not style_line_candidates:
        fallback_id = DEFAULT_STYLING_BY_STYLE_LINE.get(style_line)
        fallback = get_styling(fallback_id) if fallback_id else None
        if fallback is not None:
            return fallback
        raise ValueError(f"No styling template available for style line: {style_line}")

    candidates = _matching_stylings(style_line, preferred_gender, scene=scene)
    if preferred_gender:
        exact = [
            item
            for item in candidates
            if str(item.get("gender_scope") or item.get("gender") or "").strip() == preferred_gender
        ]
        if exact:
            candidates = exact
        else:
            unisex = [
                item
                for item in candidates
                if str(item.get("gender_scope") or item.get("gender") or "").strip() == "unisex"
            ]
            if unisex:
                candidates = unisex
            else:
                candidates = _matching_stylings(style_line, None, scene=scene) or style_line_candidates

    selected_id = _select_one(
        [item["id"] for item in candidates],
        seed_source=seed_source,
        label=f"styling:{preferred_gender or 'unisex'}:{style_line}",
    )
    selected = get_styling(selected_id)
    if selected is None:
        raise ValueError(f"Unknown styling template: {selected_id}")
    return selected


def _resolve_styling(
    *,
    style_line: str,
    preferred_gender: str | None,
    seed_source: str,
    scene: dict | None = None,
    styling: dict | None = None,
    scene_rule: dict | None = None,
) -> dict:
    if styling is not None:
        return styling
    if scene_rule is not None:
        selected = _scene_rule_styling_candidates(
            style_line,
            preferred_gender,
            seed_source,
            scene,
            scene_rule,
        )
        if selected is not None:
            return selected
    return _default_styling(style_line, preferred_gender, seed_source, scene)


def _resolve_scene_lighting_text(scene: dict, scene_rule: dict | None = None) -> str:
    profile = scene.get("lighting_profile") or {}
    if not profile or not any(str(value).strip() for value in profile.values()):
        base_text = _normalize_sentence(scene.get("lighting", ""))
    else:
        base_parts = [
            f"主光为{LIGHT_DIRECTION_LABELS.get(profile.get('light_direction'), '自然入光')}",
            f"整体为{LIGHT_QUALITY_LABELS.get(profile.get('light_quality'), '自然光线')}、"
            f"{COLOR_TEMPERATURE_LABELS.get(profile.get('color_temperature'), '自然色温')}、"
            f"{CONTRAST_LEVEL_LABELS.get(profile.get('contrast_level'), '适中反差')}",
            f"阴影层次{SHADOW_DENSITY_LABELS.get(profile.get('shadow_density'), '自然可读')}",
            f"发丝高光{HAIR_HIGHLIGHT_LABELS.get(profile.get('hair_highlight_mode'), '受控自然')}",
            f"皮肤呈现{SKIN_RENDERING_LABELS.get(profile.get('skin_rendering'), '真实肌理')}",
            f"曝光控制为{EXPOSURE_BIAS_LABELS.get(profile.get('exposure_bias'), '标准曝光')}",
        ]
        if profile.get("practical_lights_allowed"):
            base_parts.append("允许少量环境实用光参与层次补光")
        base_text = "，".join(base_parts)

    adjustment_items = _dedupe_keep_order(
        _resolve_rule_sentences(
            (scene_rule or {}).get("lighting_adjustment")
            or (scene_rule or {}).get("lighting_guardrails"),
            None,
        )
    )
    if adjustment_items:
        return "；".join([base_text, f"关键补充：{'；'.join(_normalize_sentence(item) for item in adjustment_items)}"])
    return base_text


def _resolve_scene_outfit_guidance(scene: dict) -> str:
    palette = _dedupe_keep_order(scene.get("outfit_palette", []))
    materials = _dedupe_keep_order(scene.get("outfit_materials", []))
    shapes = _dedupe_keep_order(scene.get("outfit_shapes", []))
    avoids = _dedupe_keep_order(scene.get("outfit_avoids", []))

    if not any((palette, materials, shapes, avoids)):
        return "；".join(_normalize_sentence(item) for item in scene.get("outfit_hints", [])[:2])

    segments: list[str] = []
    if palette:
        segments.append(f"优先{_format_option_list(palette)}")
    if materials:
        segments.append(f"材质以{_format_option_list(materials)}为主")
    if shapes:
        segments.append(f"版型以{_format_option_list(shapes)}为主")
    if avoids:
        segments.append(f"避免{_format_option_list(avoids)}")
    return "，".join(segments)


def _resolve_styling_constraints_text(
    *,
    scene: dict,
    styling: dict,
    scene_rule: dict | None,
    preferred_gender: str | None,
) -> str:
    items = [
        *styling.get("constraints", []),
        *_resolve_rule_sentences(
            (scene_rule or {}).get("styling_constraints")
            or (scene_rule or {}).get("styling_constraint_additions"),
            preferred_gender,
        ),
    ]
    required_tags = _dedupe_keep_order(
        str(item).strip()
        for item in (scene_rule or {}).get("required_outfit_tags", [])
        if str(item).strip()
    )
    forbidden_tags = _dedupe_keep_order(
        str(item).strip()
        for item in (scene_rule or {}).get("forbidden_outfit_tags", [])
        if str(item).strip()
    )
    if required_tags:
        items.append(f"服饰关键词优先：{_format_option_list(required_tags)}")
    if forbidden_tags:
        items.append(f"服饰禁忌：{_format_option_list(forbidden_tags)}")
    if not items:
        scene_outfit_avoids = _dedupe_keep_order(scene.get("outfit_avoids", []))
        if scene_outfit_avoids:
            items.append(f"避免{_format_option_list(scene_outfit_avoids)}")
    return "；".join(_normalize_sentence(item) for item in _dedupe_keep_order(items) if item)


def _scene_is_outdoor(scene: dict) -> bool:
    blob = " ".join(
        [
            str(scene.get("id", "")),
            str(scene.get("name", "")),
            str(scene.get("environment", "")),
            " ".join(scene.get("tags", [])),
        ]
    )
    return any(keyword in blob for keyword in ("rooftop", "天台", "户外", "树林", "植物", "风场"))


def resolve_scene_sample_image_ids(scene: dict, gender: str) -> list[str]:
    sample_image_ids = scene.get("sample_image_ids", {})
    if isinstance(sample_image_ids, dict):
        selected = _dedupe_keep_order(sample_image_ids.get(gender, []))
        if selected:
            return selected

    if _scene_is_outdoor(scene):
        return list(SCENE_SAMPLE_IMAGE_FALLBACKS["outdoor"].get(gender, ()))
    style_line = str(scene.get("style_line") or "").strip()
    family = "fashion" if style_line == "fashion_editorial" else "lifestyle"
    return list(SCENE_SAMPLE_IMAGE_FALLBACKS[family].get(gender, ()))


def resolve_scene_sample_image_id(
    scene: dict,
    gender: str,
    *,
    seed_source: str | None = None,
) -> str:
    options = resolve_scene_sample_image_ids(scene, gender)
    if not options:
        return ""
    return _select_one(
        options,
        seed_source=seed_source or f"{scene.get('id', 'scene')}:{gender}:sample-image",
        label=f"sample-image:{gender}",
    )


def _build_styling_prompt_values(
    *,
    scene: dict,
    styling: dict,
    scene_rule: dict | None = None,
    preferred_gender: str | None = None,
    makeup_override: str | None = None,
    outfit_override: str | None = None,
) -> dict[str, str]:
    makeup_text = _normalize_sentence(makeup_override or styling.get("makeup_prompt", ""))
    structured_outfit_text = _resolve_scene_outfit_guidance(scene)
    outfit_segments = _dedupe_keep_order(
        [
            _normalize_sentence(outfit_override or ""),
            _normalize_sentence(styling.get("outfit_prompt", "")),
            _normalize_sentence(structured_outfit_text),
        ]
    )
    outfit_text = "；".join(segment for segment in outfit_segments if segment)
    styling_constraints = _resolve_styling_constraints_text(
        scene=scene,
        styling=styling,
        scene_rule=scene_rule,
        preferred_gender=preferred_gender,
    )
    return {
        "makeup_text": makeup_text,
        "outfit_text": outfit_text,
        "styling_constraints": styling_constraints,
    }


def _select_prompt_details(
    hairstyle: dict, scene: dict, *, seed_source: str
) -> dict[str, str]:
    selected_expression = _select_one(
        scene.get("expressions", []),
        seed_source=seed_source,
        label=f"{scene['id']}:expression",
    )
    selected_scene_action = _select_one(
        scene.get("actions", []),
        seed_source=seed_source,
        label=f"{scene['id']}:subject-action",
    )
    compatible_hairstyle_actions = _filter_compatible_hairstyle_actions(
        selected_scene_action,
        hairstyle.get("expression_action", []),
    )
    selected_hairstyle_action = _select_one(
        compatible_hairstyle_actions,
        seed_source=seed_source,
        label=f"{hairstyle['id']}:detail-action",
    )
    return {
        "expression": selected_expression,
        "subject_action": selected_scene_action,
        "hairstyle_action": selected_hairstyle_action,
    }


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
    lighting_profile_raw = raw.get("lightingProfile") or {}
    sample_image_ids_raw = raw.get("sampleImageIds") or {}
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
        "lighting_profile": {
            "light_direction": str(lighting_profile_raw.get("lightDirection") or "").strip(),
            "light_quality": str(lighting_profile_raw.get("lightQuality") or "").strip(),
            "color_temperature": str(lighting_profile_raw.get("colorTemperature") or "").strip(),
            "contrast_level": str(lighting_profile_raw.get("contrastLevel") or "").strip(),
            "shadow_density": str(lighting_profile_raw.get("shadowDensity") or "").strip(),
            "hair_highlight_mode": str(lighting_profile_raw.get("hairHighlightMode") or "").strip(),
            "skin_rendering": str(lighting_profile_raw.get("skinRendering") or "").strip(),
            "exposure_bias": str(lighting_profile_raw.get("exposureBias") or "").strip(),
            "practical_lights_allowed": bool(lighting_profile_raw.get("practicalLightsAllowed")),
        },
        "style_mood": raw["styleMood"],
        "expressions": raw.get("expressions", []),
        "actions": raw.get("actions", []),
        "outfit_hints": raw.get("outfitHints", []),
        "outfit_palette": raw.get("outfitPalette", []),
        "outfit_materials": raw.get("outfitMaterials", []),
        "outfit_shapes": raw.get("outfitShapes", []),
        "outfit_avoids": raw.get("outfitAvoids", []),
        "constraints": raw.get("constraints", []),
        "pairing_advice": raw.get("pairingAdvice", []),
        "shot_advice": raw["shotAdvice"],
        "sample_image_ids": {
            "female": _dedupe_keep_order(sample_image_ids_raw.get("female", [])),
            "male": _dedupe_keep_order(sample_image_ids_raw.get("male", [])),
        },
        "preset_blocks": raw.get("presetBlocks") or {},
        "reference_source_ids": _dedupe_keep_order(raw.get("referenceSourceIds", [])),
        "cover_image_path": raw.get("coverImagePath", ""),
        "cover_image_updated_at": raw.get("coverImageUpdatedAt", ""),
        "cover_image_source": raw.get("coverImageSource", ""),
        "palette": _pick_palette("scene", "unisex", style_line),
    }


def build_scene_template_from_record(raw: dict) -> dict:
    return _build_scene_template(raw)


def _build_hairstyle_template(raw: dict) -> dict:
    gender = raw["gender"]
    style_line = raw["styleLine"]
    preset_blocks = raw.get("presetBlocks") or {}
    recommended_hair_color = preset_blocks.get("recommended_hair_color") or {}
    default_hair_color_tone = str(
        recommended_hair_color.get("hair_color_tone")
        or _infer_default_hair_color_tone(
            " ".join(
                [
                    str(raw.get("promptCore") or ""),
                    *[str(item) for item in raw.get("constraints", [])],
                ]
            ),
            gender,
        )
    ).strip()
    return {
        "id": raw["id"],
        "name": raw["title"],
        "description": raw["summary"],
        "gender": gender,
        "gender_label": GENDER_LABELS.get(gender, gender),
        "category_key": raw.get("categoryKey"),
        "category_label": raw.get("categoryLabel"),
        "style_line": style_line,
        "style_line_label": STYLE_LINE_LABELS.get(style_line, style_line),
        "tags": raw.get("detailTags", []),
        "prompt_core": raw["promptCore"],
        "default_hair_color_tone": default_hair_color_tone,
        "preset_blocks": preset_blocks,
        "constraints": raw.get("constraints", []),
        "pairing_advice": raw.get("pairingAdvice", []),
        "shot_advice": raw["shotAdvice"],
        "expression_action": raw.get("expressionAction", []),
        "control_profile": raw.get("controlProfile"),
        "cover_image_path": raw.get("coverImagePath", ""),
        "cover_image_updated_at": raw.get("coverImageUpdatedAt", ""),
        "cover_image_source": raw.get("coverImageSource", ""),
        "palette": _pick_palette("hairstyle", gender, style_line),
    }


def _build_styling_template(raw: dict) -> dict:
    gender = raw.get("gender", "unisex")
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
        "makeup_prompt": raw["makeupPrompt"],
        "outfit_prompt": raw["outfitPrompt"],
        "preset_blocks": raw.get("presetBlocks") or {},
        "constraints": raw.get("constraints", []),
        "pairing_advice": raw.get("pairingAdvice", []),
        "gender_scope": raw.get("genderScope", gender),
        "makeup_intensity": raw.get("makeupIntensity", ""),
        "outfit_structure": raw.get("outfitStructure", ""),
        "palette_tags": raw.get("paletteTags", []),
        "compatible_scene_ids": raw.get("compatibleSceneIds", []),
        "incompatible_scene_ids": raw.get("incompatibleSceneIds", []),
        "compatible_lighting_tags": raw.get("compatibleLightingTags", []),
        "palette": _pick_palette("scene", gender, style_line),
    }


def _build_scene_styling_rule(raw: dict) -> dict:
    return {
        "id": raw["sceneId"],
        "scene_family": raw.get("sceneFamily", ""),
        "default_styling_id": raw.get("defaultStylingId", ""),
        "default_styling_ids": raw.get("defaultStylingIds", []),
        "fallback_styling_ids": raw.get("fallbackStylingIds", []),
        "forbidden_styling_ids": raw.get("forbiddenStylingIds", []),
        "gender_styling_ids": raw.get("genderStylingIds", {}),
        "allowed_styling_ids": raw.get("allowedStylingIds", []),
        "makeup_override": raw.get("makeupOverride"),
        "outfit_override": raw.get("outfitOverride"),
        "styling_constraint_additions": raw.get("stylingConstraintAdditions"),
        "styling_constraints": raw.get("stylingConstraints"),
        "lighting_guardrails": raw.get("lightingGuardrails"),
        "lighting_adjustment": raw.get("lightingAdjustment"),
        "required_outfit_tags": raw.get("requiredOutfitTags", []),
        "forbidden_outfit_tags": raw.get("forbiddenOutfitTags", []),
        "recommended_hairstyle_category_keys": raw.get("recommendedHairstyleCategoryKeys", {}),
    }


def _build_male_hairstyle_structure_template(raw: dict) -> dict:
    base = _build_hairstyle_template(raw)
    base.update(
        {
            "family_key": raw.get("familyKey"),
            "family_label": raw.get("familyLabel"),
            "subtype_key": raw.get("subtypeKey"),
            "raw_aliases": raw.get("rawAliases", []),
            "default_modifier_ids": raw.get("defaultModifierIds", []),
            "backend_bridge_ids": list(
                dict.fromkeys(
                    str(item).strip()
                    for item in (raw.get("backendBridge") or {}).get("backend_ids", [])
                    if str(item).strip()
                )
            ),
        }
    )
    return base


def _build_male_hairstyle_modifier_template(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "name": raw.get("label") or raw["id"],
        "description": raw.get("description") or raw.get("usage_notes") or "",
        "modifier_type": raw.get("modifier_type") or "style",
        "prompt_addition": raw.get("prompt_addition_cn") or "",
        "usage_notes": raw.get("usage_notes") or "",
        "tags": [str(raw.get("label") or raw["id"])],
    }


def _build_male_hairstyle_technique_template(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "name": raw.get("label") or raw["id"],
        "description": raw.get("summary") or "",
        "style_line": raw.get("styleLine") or "",
        "prompt_addition": raw.get("promptAddition") or "",
        "constraints": raw.get("constraints", []),
        "pairing_advice": raw.get("pairingAdvice", []),
        "expression_action": raw.get("expressionAction", []),
        "preset_blocks": raw.get("presetBlocks") or {},
        "cover_image_path": raw.get("coverImagePath", ""),
        "cover_image_updated_at": raw.get("coverImageUpdatedAt", ""),
        "cover_image_source": raw.get("coverImageSource", ""),
        "legacy": bool(raw.get("legacy")),
        "tags": raw.get("detailTags", []),
    }


def _build_male_hairstyle_preset_template(raw: dict) -> dict:
    gender = raw.get("gender", "male")
    style_line = raw["styleLine"]
    preset_blocks = deepcopy(raw.get("presetBlocks") or {})
    recommended_hair_color = preset_blocks.get("recommended_hair_color") or {}
    default_hair_color_tone = str(
        recommended_hair_color.get("hair_color_tone")
        or _infer_default_hair_color_tone(raw.get("promptCore") or "", gender)
    ).strip()
    return {
        "id": raw["id"],
        "preset_id": raw["id"],
        "selection_source": "male_preset",
        "name": raw["displayName"],
        "preset_name": raw["displayName"],
        "description": raw.get("summary") or raw.get("notes") or raw["displayName"],
        "gender": gender,
        "gender_label": GENDER_LABELS.get(gender, gender),
        "category_key": raw.get("displayGroupKey"),
        "category_label": raw.get("displayGroup"),
        "source_category_key": raw.get("categoryKey"),
        "source_category_label": raw.get("categoryLabel"),
        "display_group": raw.get("displayGroup"),
        "display_group_key": raw.get("displayGroupKey"),
        "style_line": style_line,
        "style_line_label": STYLE_LINE_LABELS.get(style_line, style_line),
        "tags": raw.get("detailTags", []),
        "prompt_core": raw.get("promptCore") or raw["displayName"],
        "default_hair_color_tone": default_hair_color_tone,
        "preset_blocks": preset_blocks,
        "constraints": raw.get("constraints", []),
        "pairing_advice": raw.get("pairingAdvice", []),
        "shot_advice": raw.get("shotAdvice") or "",
        "expression_action": raw.get("expressionAction", []),
        "control_profile": raw.get("controlProfile"),
        "cover_image_path": raw.get("coverImagePath", ""),
        "cover_image_updated_at": raw.get("coverImageUpdatedAt", ""),
        "cover_image_source": raw.get("coverImageSource", ""),
        "palette": _pick_palette("hairstyle", gender, style_line),
        "structure_id": raw.get("structureId") or "",
        "modifier_ids": raw.get("modifierIds", []),
        "technique_ids": raw.get("techniqueIds", []),
        "source_hairstyle_id": raw.get("sourceHairstyleId") or "",
        "resolved_hairstyle_id": raw.get("sourceHairstyleId") or raw.get("structureId") or raw["id"],
        "resolved_hairstyle_name": raw.get("resolvedHairstyleName") or raw["displayName"],
    }


@lru_cache(maxsize=1)
def _male_hairstyle_catalog() -> dict[str, list[dict]]:
    legacy_male_raw = _load_json("hairstyles_male.json")
    legacy_male_templates = [
        _build_hairstyle_template(item) for item in legacy_male_raw
    ]
    raw_catalog = male_hairstyle_presets.load_catalog(DATA_DIR, legacy_male_raw)
    structures = [
        _build_male_hairstyle_structure_template(item)
        for item in raw_catalog["structures"]
    ]
    modifiers = [
        _build_male_hairstyle_modifier_template(item)
        for item in raw_catalog["modifiers"]
    ]
    techniques = [
        _build_male_hairstyle_technique_template(item)
        for item in raw_catalog["techniques"]
    ]
    presets = [
        _build_male_hairstyle_preset_template(item)
        for item in raw_catalog["presets"]
    ]
    return {
        "legacy_hairstyles": legacy_male_templates,
        "structures": structures,
        "modifiers": modifiers,
        "techniques": techniques,
        "presets": presets,
    }


@lru_cache(maxsize=1)
def _catalog() -> dict[str, list[dict]]:
    scenes = [_build_scene_template(item) for item in _load_json("scenes.json")]
    male_catalog = _male_hairstyle_catalog()
    female_hairstyles = [
        _build_hairstyle_template(item) for item in _load_json("hairstyles_female.json")
    ]
    stylings = [_build_styling_template(item) for item in _load_json("stylings.json")]
    scene_styling_rules = [
        _build_scene_styling_rule(item) for item in _load_json("scene_styling_rules.json")
    ]
    return {
        "scenes": scenes,
        "hairstyles": [*male_catalog["legacy_hairstyles"], *female_hairstyles],
        "male_hairstyle_structures": male_catalog["structures"],
        "male_hairstyle_modifiers": male_catalog["modifiers"],
        "male_hairstyle_techniques": male_catalog["techniques"],
        "male_hairstyle_presets": male_catalog["presets"],
        "stylings": stylings,
        "scene_styling_rules": scene_styling_rules,
    }


SCENES = _catalog()["scenes"]
HAIRSTYLES = _catalog()["hairstyles"]
MALE_HAIRSTYLE_STRUCTURES = _catalog()["male_hairstyle_structures"]
MALE_HAIRSTYLE_MODIFIERS = _catalog()["male_hairstyle_modifiers"]
MALE_HAIRSTYLE_TECHNIQUES = _catalog()["male_hairstyle_techniques"]
MALE_HAIRSTYLE_PRESETS = _catalog()["male_hairstyle_presets"]
STYLINGS = _catalog()["stylings"]
SCENE_STYLING_RULES = _catalog()["scene_styling_rules"]


def _find_template(items: Iterable[dict], template_id: str) -> dict | None:
    for item in items:
        if item["id"] == template_id:
            return item
    return None


def get_hairstyle(template_id: str) -> dict | None:
    resolved_id = _resolve_alias("hairstyle", template_id)
    return _find_template(HAIRSTYLES, resolved_id)


def get_male_hairstyle_preset(template_id: str) -> dict | None:
    return _find_template(MALE_HAIRSTYLE_PRESETS, template_id)


def get_male_hairstyle_presets() -> list[dict]:
    return [dict(item) for item in MALE_HAIRSTYLE_PRESETS]


def resolve_male_hairstyle_preset(template_id: str) -> dict | None:
    preset = get_male_hairstyle_preset(template_id)
    return dict(preset) if preset is not None else None


def get_scene(template_id: str) -> dict | None:
    resolved_id = _resolve_alias("scene", template_id)
    return _find_template(SCENES, resolved_id)


def get_hair_color_catalog() -> list[dict]:
    return [dict(item) for item in HAIR_COLOR_TONES]


def get_hair_color_technique_catalog() -> list[dict]:
    return [dict(item) for item in HAIR_COLOR_TECHNIQUES]


def get_professional_hair_color_catalog() -> list[dict]:
    return [dict(item) for item in PROFESSIONAL_HAIR_COLOR_OPTIONS]


def get_professional_hair_color_series_catalog() -> list[dict]:
    return [dict(item) for item in PROFESSIONAL_HAIR_COLOR_SERIES]


def get_styling(template_id: str) -> dict | None:
    return _find_template(STYLINGS, template_id)


def get_scene_styling_rule(scene_id: str) -> dict | None:
    return _find_template(SCENE_STYLING_RULES, scene_id)


def _normalize_rule_value_to_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [_normalize_sentence(raw)]
    if isinstance(raw, list):
        return [
            _normalize_sentence(item)
            for item in _dedupe_keep_order(str(item) for item in raw if str(item).strip())
        ]
    return []


def _resolve_rule_sentences(raw: object, preferred_gender: str | None) -> list[str]:
    if isinstance(raw, dict):
        resolved: list[str] = []
        ordered_keys: list[str] = []
        if preferred_gender:
            ordered_keys.append(preferred_gender)
        ordered_keys.extend(["default", "unisex"])
        for key in ordered_keys:
            resolved.extend(_normalize_rule_value_to_list(raw.get(key)))
        return _dedupe_keep_order(resolved)
    return _normalize_rule_value_to_list(raw)


def _resolve_rule_text(raw: object, preferred_gender: str | None) -> str:
    return "；".join(_resolve_rule_sentences(raw, preferred_gender))


def _scene_rule_styling_candidates(
    style_line: str,
    preferred_gender: str | None,
    seed_source: str,
    scene: dict | None,
    scene_rule: dict,
) -> dict | None:
    allowed_ids = {
        str(item).strip()
        for item in scene_rule.get("allowed_styling_ids", [])
        if str(item).strip()
    }
    forbidden_ids = {
        str(item).strip()
        for item in scene_rule.get("forbidden_styling_ids", [])
        if str(item).strip()
    }
    explicit_ids: list[str] = []
    gender_map = scene_rule.get("gender_styling_ids", {})
    if preferred_gender and isinstance(gender_map, dict):
        explicit_ids.append(str(gender_map.get(preferred_gender) or "").strip())
    explicit_ids.extend(
        [
            str(scene_rule.get("default_styling_id") or "").strip(),
            *[str(item).strip() for item in scene_rule.get("default_styling_ids", [])],
            *[str(item).strip() for item in scene_rule.get("fallback_styling_ids", [])],
        ]
    )

    for explicit_id in _dedupe_keep_order(explicit_ids):
        if not explicit_id or explicit_id in forbidden_ids:
            continue
        selected = get_styling(explicit_id)
        if (
            selected is not None
            and (not allowed_ids or selected["id"] in allowed_ids)
            and selected["style_line"] == style_line
            and _styling_scope_matches(selected, preferred_gender)
            and _styling_supports_scene(selected, scene)
        ):
            return selected

    candidates = _matching_stylings(style_line, preferred_gender, scene=scene)
    if forbidden_ids:
        candidates = [item for item in candidates if item["id"] not in forbidden_ids]
    if allowed_ids:
        filtered = [item for item in candidates if item["id"] in allowed_ids]
        if filtered:
            candidates = filtered

    if not candidates:
        return None

    selected_id = _select_one(
        [item["id"] for item in candidates],
        seed_source=seed_source,
        label=f"scene-rule-styling:{scene_rule['id']}:{preferred_gender or 'unisex'}",
    )
    return get_styling(selected_id)


def _build_hair_color_target_text(selection: dict[str, str]) -> str:
    return (
        "发色目标：发色调整为"
        f"{selection['tone_label']}，保持真实自然的人类染发质感与明暗层次。"
    )


def _build_hair_color_technique_text(selection: dict[str, str]) -> str:
    return (
        "染发工艺：采用"
        f"{selection['technique_label']}，{_normalize_sentence(selection['technique_description'])}。"
    )


def _build_hair_color_lock_text(selection: dict[str, str] | None) -> str:
    if selection is None:
        return (
            "发色锁定：保持参考图中静态完成的当前发色、明度层级与染发层次不变，"
            "不要二次改色，不要改变冷暖倾向、亮度层级、挑染位置和过渡关系。"
        )
    note = _normalize_sentence(str(selection.get("professional_note") or ""))
    suffix = f"同时保留当前{note}的专业色感表达。" if note else ""
    return (
        "发色锁定：保持参考图中静态完成的"
        f"{selection['tone_label']}发色和{selection['technique_label']}层次不变，"
        "不要二次改色，不要改变冷暖倾向、亮度层级、挑染位置和过渡关系。"
        f"{suffix}"
    )


def _preset_block(template: dict | None, key: str) -> dict:
    if template is None:
        return {}
    raw = template.get("preset_blocks") or {}
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def _format_items(items: Iterable[str]) -> str:
    return "；".join(_normalize_sentence(item) for item in _dedupe_keep_order(items) if item)


def _safe_value(raw: object) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    return _normalize_sentence(text) if text else ""


def _sanitize_scene_text_for_locked_hair(text: str) -> str:
    cleaned = _normalize_sentence(text)
    if not cleaned:
        return ""
    for source, target in LOCKED_HAIR_TEXT_REPLACEMENTS:
        cleaned = cleaned.replace(source, target)
    return cleaned


def _build_output_spec_text(aspect_ratio: str | None = None) -> str:
    ratio_text = aspect_ratio or DEFAULT_ASPECT_RATIO
    return (
        "输出规格：只输出 1 张完整成片，不要拼图，不要多宫格，"
        "不要在同一画面里同时展示多个动作版本或多个发型版本。"
        f"画幅使用 {ratio_text}。"
    )


def _build_edit_scope_text(mode: str) -> str:
    if mode == "hair_only":
        return (
            "编辑范围：本次以头发系统编辑为主，只调整主发型结构、刘海系统和发色系统；"
            "同时允许进行轻中度写真级肤质优化与肤色均匀化。"
            "不得改变脸型、五官比例、妆容风格、年龄感、背景、服饰、动作、构图和原有光线。"
        )
    if mode == "scene_only":
        return (
            "编辑范围：本次仅允许修改场景、妆造和人物表现；"
            "人物身份与当前头发系统必须保持不变，不要二次改发。"
        )
    return (
        "编辑范围：在严格锁定同一人物身份的前提下，"
        "可统一调整发型、刘海、发色、场景、妆造与人物表现。"
    )


def _tone_label_from_block(raw_tone: str) -> str:
    tone = get_hair_color_tone(raw_tone)
    return tone["label"] if tone else raw_tone


def _technique_label_from_block(raw_technique: str) -> str:
    technique = get_hair_color_technique(raw_technique)
    return technique["label"] if technique else raw_technique


def _build_hair_shape_text(hairstyle: dict) -> str:
    block = _preset_block(hairstyle, "hair_shape")
    if not block:
        return f"主发型结构：{_normalize_sentence(hairstyle['prompt_core'])}。"

    segments = [f"发型改为{hairstyle['name']}"]
    mapping = (
        ("hair_length", "发长"),
        ("hair_silhouette", "整体轮廓"),
        ("hair_texture", "发丝纹理"),
        ("hair_volume", "蓬松度"),
        ("hair_parting", "分线"),
        ("sideburn_nape", "鬓角与后颈区"),
        ("hair_tail_finish", "发尾处理"),
    )
    for field, label in mapping:
        value = _safe_value(block.get(field))
        if value:
            segments.append(f"{label}为{value}")
    return f"主发型结构：{'；'.join(segments)}。"


def _build_bangs_text(hairstyle: dict) -> str:
    block = _preset_block(hairstyle, "bangs")
    if not block:
        return "刘海系统：刘海与脸侧修饰需要和目标发型保持统一，自然贴合脸型。"

    segments: list[str] = []
    mapping = (
        ("bangs_type", "刘海类型"),
        ("bangs_density", "刘海厚薄"),
        ("bangs_length", "刘海长度"),
        ("bangs_split", "刘海开合"),
        ("bangs_face_framing", "脸侧修饰"),
    )
    for field, label in mapping:
        value = _safe_value(block.get(field))
        if value and value != "不适用":
            segments.append(f"{label}为{value}")
    if not segments:
        segments.append("保持无刘海或极轻刘海处理，不额外制造厚重遮挡")
    return f"刘海系统：{'；'.join(segments)}。"


def _build_hair_color_text(hairstyle: dict, selection: dict[str, str] | None) -> str:
    block = _preset_block(hairstyle, "recommended_hair_color")
    tone_label = selection["tone_label"] if selection else _tone_label_from_block(str(block.get("hair_color_tone") or ""))
    technique_label = selection["technique_label"] if selection else _technique_label_from_block(
        str(block.get("hair_color_technique") or "")
    )
    segments: list[str] = []
    if tone_label:
        segments.append(f"发色调整为{tone_label}")
    depth = _safe_value(block.get("hair_color_depth"))
    if depth:
        segments.append(f"明度层级为{depth}")
    temperature = _safe_value(block.get("hair_color_temperature"))
    if temperature:
        segments.append(f"冷暖倾向为{temperature}")
    if technique_label:
        segments.append(f"染发方式采用{technique_label}")
    distribution = _safe_value(block.get("hair_color_distribution"))
    if distribution:
        segments.append(f"色彩分布为{distribution}")
    professional_note = _normalize_sentence(str(selection.get("professional_note") or "")) if selection else ""
    if professional_note:
        segments.append(f"补充色感为{professional_note}")
    if not segments and selection:
        segments.append(f"发色调整为{selection['tone_label']}，染发方式采用{selection['technique_label']}")
    return f"发色系统：{'；'.join(segments)}。"


def _is_anti_confusion_constraint(text: str) -> bool:
    return any(keyword in text for keyword in ("不得变成", "不得偏成", "不要变成", "禁止变成"))


def _select_hair_constraints(constraints: list[str]) -> list[str]:
    anti_confusion = next((item for item in constraints if _is_anti_confusion_constraint(item)), "")
    selected = [item for item in constraints if item != anti_confusion][:3]
    if anti_confusion and anti_confusion not in selected:
        selected.append(anti_confusion)
    for item in constraints:
        if len(selected) >= 4:
            break
        if item not in selected:
            selected.append(item)
    return selected[:4]


def _build_hair_constraints_text(hairstyle: dict | None) -> str:
    if hairstyle is None:
        return ""
    constraints = [
        _normalize_sentence(str(item))
        for item in (hairstyle.get("constraints") or [])
        if str(item).strip()
    ]
    selected = _select_hair_constraints(constraints)
    if not selected:
        return ""
    return f"发型关键约束：{_format_items(selected)}。"


def _build_scene_text(scene: dict, scene_rule: dict | None = None) -> str:
    block = _preset_block(scene, "scene")
    shot = _sanitize_scene_text_for_locked_hair(_safe_value(block.get("shot") or scene.get("shot_advice")))
    environment = _sanitize_scene_text_for_locked_hair(
        _safe_value(block.get("scene_environment") or scene.get("environment"))
    )
    lighting = _sanitize_scene_text_for_locked_hair(
        _safe_value(block.get("scene_lighting") or _resolve_scene_lighting_text(scene, scene_rule))
    )
    mood = _sanitize_scene_text_for_locked_hair(
        _safe_value(block.get("scene_mood") or scene.get("style_mood"))
    )
    constraint_items = [
        _sanitize_scene_text_for_locked_hair(str(item))
        for item in (block.get("scene_constraints") or scene.get("constraints") or [])
    ]
    segments = []
    if shot:
        segments.append(f"构图：{shot}")
    if environment:
        segments.append(f"环境：{environment}")
    if lighting:
        segments.append(f"光线：{lighting}")
    if mood:
        segments.append(f"氛围：{mood}")
    constraint_text = _format_items(constraint_items)
    if constraint_text:
        segments.append(f"关键约束：{constraint_text}")
    return f"场景系统：{'。'.join(segments)}。"


def _build_styling_text(
    *,
    scene: dict,
    styling: dict,
    scene_rule: dict | None,
    preferred_gender: str | None,
    makeup_override: str | None = None,
    outfit_override: str | None = None,
) -> str:
    styling_block = _preset_block(styling, "styling")
    styling_values = _build_styling_prompt_values(
        scene=scene,
        styling=styling,
        scene_rule=scene_rule,
        preferred_gender=preferred_gender,
        makeup_override=makeup_override,
        outfit_override=outfit_override,
    )
    accessories = _format_items(styling_block.get("accessories") or [])
    constraints = _format_items(styling_block.get("styling_constraints") or [])
    if not constraints:
        constraints = _normalize_sentence(styling_values["styling_constraints"])
    segments = []
    if styling_values["makeup_text"]:
        segments.append(f"妆容：{styling_values['makeup_text']}")
    if styling_values["outfit_text"]:
        segments.append(f"服饰：{styling_values['outfit_text']}")
    if accessories:
        segments.append(f"配饰：{accessories}")
    if constraints:
        segments.append(f"妆造约束：{constraints}")
    return f"妆造系统：{'。'.join(segments)}。"


def _build_subject_performance_text(
    scene: dict,
    *,
    seed_source: str,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    allow_hair_touching_actions: bool = False,
) -> str:
    block = _preset_block(scene, "subject_performance")
    expressions = block.get("expression_options") or scene.get("expressions") or []
    actions = block.get("subject_action_options") or scene.get("actions") or []
    normalized_subject_action_override = (
        subject_action_override
        if allow_hair_touching_actions
        else _normalize_locked_hair_action_override(subject_action_override)
    )
    if not allow_hair_touching_actions and not normalized_subject_action_override:
        actions = _filter_scene_actions_for_locked_hairstyle(actions)
    expression = expression_override or _select_one(
        expressions or GENERIC_EXPRESSIONS,
        seed_source=seed_source,
        label=f"{scene['id']}:expression",
    )
    action = normalized_subject_action_override or _select_one(
        actions or GENERIC_SCENE_ACTIONS,
        seed_source=seed_source,
        label=f"{scene['id']}:subject-action",
    )
    gesture_constraints = _format_items(
        block.get("gesture_constraints")
        or [
            "后端每次只选 1 个主体动作，不再把多个动作选项同时写进同一条提示词",
            "单张图中只保留一种主体动作，不要把多个互斥手部动作同时放进同一画面",
        ]
    )
    return (
        "人物表现系统："
        f"人物表情固定为{expression or '自然看向镜头'}。"
        f"人物动作固定为{action or '自然站立或静止停顿'}。"
        f"手势约束：{gesture_constraints}。"
    )


def _build_hair_shape_lock_text(hairstyle: dict | None) -> str:
    if hairstyle is None:
        return (
            "发型锁定：保持参考图中已经生成完成的当前主发型结构不变；"
            "同时保持参考图中静态打理完成的当前主发型结构不变，"
            "不要改变发长、外轮廓、卷度、顶部体积、分线、鬓角与后颈区。"
        )
    block = _preset_block(hairstyle, "hair_shape")
    segments: list[str] = [
        "保持参考图中已经生成完成的当前主发型结构不变",
        "同时保持参考图中静态打理完成的当前主发型结构不变",
    ]
    mapping = (
        ("hair_length", "发长"),
        ("hair_silhouette", "轮廓"),
        ("hair_texture", "纹理"),
        ("hair_volume", "顶部与侧区体积"),
        ("hair_parting", "分线"),
        ("sideburn_nape", "鬓角与后颈区"),
    )
    for field, label in mapping:
        value = _safe_value(block.get(field))
        if value:
            segments.append(f"{label}保持为{value}")
    return f"发型锁定：{'；'.join(segments)}。"


def _build_bangs_lock_text(hairstyle: dict | None) -> str:
    if hairstyle is None:
        return (
            "刘海锁定：保持参考图中静态完成的当前刘海状态不变；"
            "如果当前为无刘海，额前不要新增刘海或大片落额发。"
        )
    block = _preset_block(hairstyle, "bangs")
    values = {
        "bangs_type": _safe_value(block.get("bangs_type")),
        "bangs_density": _safe_value(block.get("bangs_density")),
        "bangs_length": _safe_value(block.get("bangs_length")),
        "bangs_split": _safe_value(block.get("bangs_split")),
        "bangs_face_framing": _safe_value(block.get("bangs_face_framing")),
    }
    is_no_bangs = not any(value and value != "不适用" for value in values.values())
    if is_no_bangs:
        return "刘海锁定：保持参考图中静态完成的当前无刘海状态不变；额前不要生成新的刘海或大片落额发。"
    segments: list[str] = ["保持参考图中静态完成的当前刘海系统不变"]
    mapping = (
        ("bangs_type", "刘海类型"),
        ("bangs_density", "厚薄"),
        ("bangs_length", "长度"),
        ("bangs_split", "开合方式"),
        ("bangs_face_framing", "脸侧修饰"),
    )
    for field, label in mapping:
        value = _safe_value(block.get(field))
        if value and value != "不适用":
            segments.append(f"{label}保持为{value}")
    segments.append("不要新增第二套刘海分区或额前大面积垂落")
    return f"刘海锁定：{'；'.join(segments)}。"


def _build_hair_motion_constraint_text(hairstyle: dict | None) -> str:
    segments = [
        "如当前场景存在风力或空气流动，只允许少量边缘碎发与极少数表层发丝轻微摆动，用于体现环境气流",
        "禁止风力、动作或镜头变化改变主发型结构",
        "禁止把当前发型吹散、吹塌或改写成另一种结构性新发型",
    ]
    bangs_block = _preset_block(hairstyle, "bangs") if hairstyle is not None else {}
    bangs_type = _safe_value(bangs_block.get("bangs_type"))
    has_structured_bangs = bool(bangs_type and bangs_type != "不适用")
    if has_structured_bangs:
        segments.append("刘海只允许极轻微非结构性位移，不得改变厚薄、长度、开合方式和脸侧修饰")
    else:
        segments.append("保持当前无刘海状态，额前不生成新的刘海或大片落额发")
    return f"风感约束：{'；'.join(segments)}。"

def build_prompt_assembly(
    *,
    mode: str,
    hairstyle: dict | None = None,
    scene: dict | None = None,
    styling: dict | None = None,
    hair_color_selection: dict[str, str] | None = None,
    hair_color_tone_id: str | None = None,
    hair_color_technique_id: str | None = None,
    detected_hair_color_tone_id: str | None = None,
    preferred_gender: str | None = None,
    seed_source: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    outfit_override: str | None = None,
    aspect_ratio: str | None = None,
) -> PromptAssembly:
    normalized_mode = _normalize_prompt_mode(mode)

    if normalized_mode == "hair_only":
        if hairstyle is None:
            raise ValueError("hairstyle is required for hairstyle_only mode")
        selected_hair_color = hair_color_selection or normalize_hair_color_selection(
            tone_id=hair_color_tone_id,
            technique_id=hair_color_technique_id,
            hairstyle=hairstyle,
            detected_tone_id=detected_hair_color_tone_id,
        )
        return _assemble_prompt(
            normalized_mode,
            [
                _make_prompt_block("identity_lock", HAIRSTYLE_ONLY_IDENTITY_LOCK_SECTION),
                _make_prompt_block("output_spec", _build_output_spec_text(aspect_ratio)),
                _make_prompt_block("edit_scope", _build_edit_scope_text(normalized_mode)),
                _make_prompt_block("hair_shape", _build_hair_shape_text(hairstyle)),
                _make_prompt_block("bangs", _build_bangs_text(hairstyle)),
                _make_prompt_block("hair_color", _build_hair_color_text(hairstyle, selected_hair_color)),
                _make_prompt_block("hair_constraints", _build_hair_constraints_text(hairstyle)),
                *_build_quality_blocks(mode=normalized_mode),
                *_build_negative_blocks(),
            ],
        )

    if normalized_mode == "scene_only":
        if scene is None:
            raise ValueError("scene is required for scene_only mode")
        selected_hair_color = hair_color_selection
        if selected_hair_color is None and hairstyle is not None:
            selected_hair_color = normalize_hair_color_selection(hairstyle=hairstyle)
        selection_seed = seed_source or f"scene-only:{scene['id']}"
        scene_rule = get_scene_styling_rule(scene["id"])
        selected_styling = _resolve_styling(
            style_line=scene["style_line"],
            preferred_gender=preferred_gender,
            seed_source=selection_seed,
            scene=scene,
            styling=styling,
            scene_rule=scene_rule,
        )
        selected_expression = expression_override or _select_one(
            scene.get("expressions", []),
            seed_source=selection_seed,
            label=f"{scene['id']}:scene-only-expression",
        )
        normalized_subject_action_override = _normalize_locked_hair_action_override(subject_action_override)
        available_actions = (
            _filter_scene_actions_for_locked_hairstyle(scene.get("actions", []))
            if not normalized_subject_action_override
            else _dedupe_keep_order(scene.get("actions", []))
        )
        selected_subject_action = normalized_subject_action_override or _select_one(
            available_actions or GENERIC_SCENE_ACTIONS,
            seed_source=selection_seed,
            label=f"{scene['id']}:scene-only-subject-action",
        )
        makeup_override_text = _resolve_rule_text(
            scene_rule.get("makeup_override") if scene_rule else None,
            preferred_gender,
        )
        resolved_outfit_override = (
            outfit_override
            or _resolve_rule_text(
                scene_rule.get("outfit_override") if scene_rule else None,
                preferred_gender,
            )
        )
        styling_values = _build_styling_prompt_values(
            scene=scene,
            styling=selected_styling,
            scene_rule=scene_rule,
            preferred_gender=preferred_gender,
            makeup_override=makeup_override_text,
            outfit_override=resolved_outfit_override,
        )
        return _assemble_prompt(
            normalized_mode,
            [
                _make_prompt_block("identity_lock", SCENE_ONLY_IDENTITY_LOCK_SECTION),
                _make_prompt_block("output_spec", _build_output_spec_text(aspect_ratio)),
                _make_prompt_block("edit_scope", _build_edit_scope_text(normalized_mode)),
                _make_prompt_block("hair_shape_lock", _build_hair_shape_lock_text(hairstyle)),
                _make_prompt_block("bangs_lock", _build_bangs_lock_text(hairstyle)),
                _make_prompt_block("hair_color_lock", _build_hair_color_lock_text(selected_hair_color)),
                _make_prompt_block("hair_motion_constraint", _build_hair_motion_constraint_text(hairstyle)),
                _make_prompt_block("scene", _build_scene_text(scene, scene_rule)),
                _make_prompt_block(
                    "styling",
                    _build_styling_text(
                        scene=scene,
                        styling=selected_styling,
                        scene_rule=scene_rule,
                        preferred_gender=preferred_gender,
                        makeup_override=makeup_override_text,
                        outfit_override=resolved_outfit_override,
                    ),
                ),
                _make_prompt_block(
                    "subject_performance",
                    _build_subject_performance_text(
                        scene,
                        seed_source=selection_seed,
                        expression_override=selected_expression,
                        subject_action_override=selected_subject_action,
                    ),
                ),
                *_build_quality_blocks(mode=normalized_mode),
                *_build_negative_blocks(),
            ],
        )

    if hairstyle is None or scene is None:
        raise ValueError("hairstyle and scene are required for full_stylize mode")

    selection_seed = seed_source or f"{hairstyle['id']}:{scene['id']}"
    selected_hair_color = hair_color_selection or normalize_hair_color_selection(
        tone_id=hair_color_tone_id,
        technique_id=hair_color_technique_id,
        hairstyle=hairstyle,
        detected_tone_id=detected_hair_color_tone_id,
    )
    scene_rule = get_scene_styling_rule(scene["id"])
    selected_styling = _resolve_styling(
        style_line=scene["style_line"],
        preferred_gender=hairstyle.get("gender"),
        seed_source=selection_seed,
        scene=scene,
        styling=styling,
        scene_rule=scene_rule,
    )
    selected_details = _select_prompt_details(
        hairstyle,
        scene,
        seed_source=selection_seed,
    )
    expression_text = selected_details["expression"] or "自然看向镜头"
    scene_action_text = selected_details["subject_action"] or "自然站立或静止停顿"
    hairstyle_action_text = selected_details["hairstyle_action"]
    makeup_override_text = _resolve_rule_text(
        scene_rule.get("makeup_override") if scene_rule else None,
        hairstyle.get("gender"),
    )
    resolved_outfit_override = _resolve_rule_text(
        scene_rule.get("outfit_override") if scene_rule else None,
        hairstyle.get("gender"),
    )
    return _assemble_prompt(
        normalized_mode,
        [
            _make_prompt_block("identity_lock", IDENTITY_LOCK_SECTION),
            _make_prompt_block("output_spec", _build_output_spec_text(aspect_ratio)),
            _make_prompt_block("edit_scope", _build_edit_scope_text(normalized_mode)),
            _make_prompt_block("hair_shape", _build_hair_shape_text(hairstyle)),
            _make_prompt_block("bangs", _build_bangs_text(hairstyle)),
            _make_prompt_block("hair_color", _build_hair_color_text(hairstyle, selected_hair_color)),
            _make_prompt_block("hair_constraints", _build_hair_constraints_text(hairstyle)),
            _make_prompt_block("scene", _build_scene_text(scene, scene_rule)),
            _make_prompt_block(
                "styling",
                _build_styling_text(
                    scene=scene,
                    styling=selected_styling,
                    scene_rule=scene_rule,
                    preferred_gender=hairstyle.get("gender"),
                    makeup_override=makeup_override_text,
                    outfit_override=resolved_outfit_override,
                ),
            ),
            _make_prompt_block(
                "subject_performance",
                "人物表现系统："
                f"人物表情固定为{expression_text}。"
                f"人物动作固定为{scene_action_text}。"
                "后端每次只选 1 个主体动作，不再把多个动作选项同时写进同一条提示词。"
                + (
                    f"发型展示参考动作为{hairstyle_action_text}。发型展示动作不要与主体动作叠加成不合理肢体效果。"
                    if hairstyle_action_text
                    else "不额外叠加发型手部细节动作，避免与主体动作叠加成不合理肢体效果。"
                ),
            ),
            *_build_quality_blocks(mode=normalized_mode),
            *_build_negative_blocks(),
        ],
    )


def build_prompt(
    hairstyle: dict,
    scene: dict,
    *,
    styling: dict | None = None,
    hair_color_selection: dict[str, str] | None = None,
    hair_color_tone_id: str | None = None,
    hair_color_technique_id: str | None = None,
    detected_hair_color_tone_id: str | None = None,
    seed_source: str | None = None,
    aspect_ratio: str | None = None,
) -> str:
    return build_prompt_assembly(
        mode="full_stylize",
        hairstyle=hairstyle,
        scene=scene,
        styling=styling,
        hair_color_selection=hair_color_selection,
        hair_color_tone_id=hair_color_tone_id,
        hair_color_technique_id=hair_color_technique_id,
        detected_hair_color_tone_id=detected_hair_color_tone_id,
        seed_source=seed_source,
        aspect_ratio=aspect_ratio,
    ).render()


def build_hairstyle_only_prompt(
    hairstyle: dict,
    *,
    hair_color_selection: dict[str, str] | None = None,
    hair_color_tone_id: str | None = None,
    hair_color_technique_id: str | None = None,
    detected_hair_color_tone_id: str | None = None,
    aspect_ratio: str | None = None,
) -> str:
    return build_prompt_assembly(
        mode="hairstyle_only",
        hairstyle=hairstyle,
        hair_color_selection=hair_color_selection,
        hair_color_tone_id=hair_color_tone_id,
        hair_color_technique_id=hair_color_technique_id,
        detected_hair_color_tone_id=detected_hair_color_tone_id,
        aspect_ratio=aspect_ratio,
    ).render()


def build_scene_only_prompt(
    scene: dict,
    *,
    hairstyle: dict | None = None,
    styling: dict | None = None,
    hair_color_selection: dict[str, str] | None = None,
    preferred_gender: str | None = None,
    seed_source: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    outfit_override: str | None = None,
    aspect_ratio: str | None = None,
) -> str:
    return build_prompt_assembly(
        mode="scene_only",
        hairstyle=hairstyle,
        scene=scene,
        styling=styling,
        hair_color_selection=hair_color_selection,
        preferred_gender=preferred_gender,
        seed_source=seed_source,
        expression_override=expression_override,
        subject_action_override=subject_action_override,
        outfit_override=outfit_override,
        aspect_ratio=aspect_ratio,
    ).render()


def normalize_generation_options(
    *,
    generator_backend: str | None = None,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
) -> dict[str, str | None]:
    resolved_backend = _normalize_generator_backend(generator_backend)
    capability = GENERATOR_BACKEND_CAPABILITIES.get(resolved_backend)
    if capability is None:
        raise ValueError(f"Unsupported generator backend: {resolved_backend}")

    default_aspect_ratio = capability["default_aspect_ratio"] or DEFAULT_ASPECT_RATIO
    resolved_aspect_ratio = (aspect_ratio or default_aspect_ratio).strip()

    if resolved_aspect_ratio not in capability["aspect_ratios"]:
        raise ValueError(f"Unsupported aspect ratio: {resolved_aspect_ratio}")

    if capability["resolutions"]:
        default_resolution = capability["default_resolution"] or DEFAULT_RESOLUTION
        resolved_resolution = default_resolution
    else:
        resolved_resolution = None

    return {
        "generator_backend": resolved_backend,
        "aspect_ratio": resolved_aspect_ratio,
        "resolution": resolved_resolution,
    }


def _empty_template_selection() -> dict[str, object]:
    return {
        "source": "legacy_hairstyle",
        "preset_id": "",
        "preset_name": "",
        "resolved_hairstyle_id": "",
        "resolved_hairstyle_name": "",
        "display_group": "",
        "structure_id": "",
        "modifier_ids": [],
        "technique_ids": [],
    }


def build_job_prompt_payload(
    hairstyle: dict,
    scene: dict,
    *,
    generator_backend: str | None = None,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    hair_color_tone_id: str | None = None,
    hair_color_technique_id: str | None = None,
    hair_color_professional_id: str | None = None,
    detected_hair_color_tone_id: str | None = None,
    seed_source: str | None = None,
) -> str:
    generation_options = normalize_generation_options(
        generator_backend=generator_backend,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
    )
    selection_key = hairstyle.get("preset_id") or hairstyle["id"]
    selection_seed = seed_source or f"{selection_key}:{scene['id']}"
    selected_styling = _resolve_styling(
        style_line=scene["style_line"],
        preferred_gender=hairstyle.get("gender"),
        seed_source=selection_seed,
        scene=scene,
        scene_rule=get_scene_styling_rule(scene["id"]),
    )
    selected_hair_color = normalize_hair_color_selection(
        tone_id=hair_color_tone_id,
        technique_id=hair_color_technique_id,
        professional_id=hair_color_professional_id,
        hairstyle=hairstyle,
        detected_tone_id=detected_hair_color_tone_id,
    )
    payload = {
        "version": 5,
        "full_prompt": build_prompt(
            hairstyle,
            scene,
            styling=selected_styling,
            hair_color_selection=selected_hair_color,
            seed_source=selection_seed,
            aspect_ratio=generation_options["aspect_ratio"],
        ),
        "hairstyle_only_prompt": build_hairstyle_only_prompt(
            hairstyle,
            hair_color_selection=selected_hair_color,
            aspect_ratio=generation_options["aspect_ratio"],
        ),
        "scene_only_prompt": build_scene_only_prompt(
            scene,
            hairstyle=hairstyle,
            styling=selected_styling,
            hair_color_selection=selected_hair_color,
            preferred_gender=hairstyle.get("gender"),
            seed_source=f"scene-only:{selection_seed}",
            aspect_ratio=generation_options["aspect_ratio"],
        ),
        "styling_id": selected_styling["id"],
        "hair_color_selection": selected_hair_color,
        "template_selection": {
            "source": hairstyle.get("selection_source") or "legacy_hairstyle",
            "preset_id": hairstyle.get("preset_id") or "",
            "preset_name": hairstyle.get("preset_name") or "",
            "resolved_hairstyle_id": hairstyle.get("resolved_hairstyle_id") or hairstyle["id"],
            "resolved_hairstyle_name": hairstyle.get("resolved_hairstyle_name") or hairstyle["name"],
            "display_group": hairstyle.get("display_group") or hairstyle.get("category_label") or "",
            "structure_id": hairstyle.get("structure_id") or "",
            "modifier_ids": hairstyle.get("modifier_ids", []),
            "technique_ids": hairstyle.get("technique_ids", []),
        },
        "output_options": generation_options,
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_job_prompt_payload(raw_prompt: str) -> dict:
    normalized_options = normalize_generation_options()
    empty_hair_color_selection = _empty_hair_color_selection()
    empty_template_selection = _empty_template_selection()
    if not raw_prompt.strip():
        return {
            "version": 0,
            "full_prompt": "",
            "hairstyle_only_prompt": "",
            "scene_only_prompt": "",
            "styling_id": "",
            "hair_color_selection": empty_hair_color_selection,
            "template_selection": empty_template_selection,
            "output_options": normalized_options,
        }

    try:
        payload = json.loads(raw_prompt)
    except json.JSONDecodeError:
        return {
            "version": 0,
            "full_prompt": raw_prompt,
            "hairstyle_only_prompt": "",
            "scene_only_prompt": "",
            "styling_id": "",
            "hair_color_selection": empty_hair_color_selection,
            "template_selection": empty_template_selection,
            "output_options": normalized_options,
        }

    if not isinstance(payload, dict):
        return {
            "version": 0,
            "full_prompt": raw_prompt,
            "hairstyle_only_prompt": "",
            "scene_only_prompt": "",
            "styling_id": "",
            "hair_color_selection": empty_hair_color_selection,
            "template_selection": empty_template_selection,
            "output_options": normalized_options,
        }

    raw_output_options = payload.get("output_options") if isinstance(payload.get("output_options"), dict) else {}
    raw_generator_backend = raw_output_options.get("generator_backend")
    raw_aspect_ratio = raw_output_options.get("aspect_ratio")
    raw_resolution = raw_output_options.get("resolution")

    try:
        output_options = normalize_generation_options(
            generator_backend=raw_generator_backend,
            aspect_ratio=raw_aspect_ratio,
            resolution=raw_resolution,
        )
    except ValueError:
        resolved_backend = _normalize_generator_backend(raw_generator_backend)
        if resolved_backend not in GENERATOR_BACKEND_CAPABILITIES:
            resolved_backend = DEFAULT_GENERATOR_BACKEND
        capability = GENERATOR_BACKEND_CAPABILITIES[resolved_backend]
        output_options = {
            "generator_backend": resolved_backend,
            "aspect_ratio": (
                raw_aspect_ratio
                if isinstance(raw_aspect_ratio, str) and raw_aspect_ratio in SUPPORTED_ASPECT_RATIOS
                else capability["default_aspect_ratio"] or DEFAULT_ASPECT_RATIO
            ),
            "resolution": capability["default_resolution"] or DEFAULT_RESOLUTION,
        }
    raw_hair_color_selection = (
        payload.get("hair_color_selection")
        if isinstance(payload.get("hair_color_selection"), dict)
        else {}
    )
    if raw_hair_color_selection:
        hair_color_selection = normalize_hair_color_selection(
            tone_id=str(raw_hair_color_selection.get("tone_id") or "").strip() or None,
            technique_id=str(raw_hair_color_selection.get("technique_id") or "").strip() or None,
            professional_id=str(raw_hair_color_selection.get("professional_id") or "").strip() or None,
        )
    else:
        hair_color_selection = empty_hair_color_selection

    raw_template_selection = (
        payload.get("template_selection")
        if isinstance(payload.get("template_selection"), dict)
        else {}
    )
    template_selection = {
        "source": str(raw_template_selection.get("source") or "legacy_hairstyle").strip() or "legacy_hairstyle",
        "preset_id": str(raw_template_selection.get("preset_id") or "").strip(),
        "preset_name": str(raw_template_selection.get("preset_name") or "").strip(),
        "resolved_hairstyle_id": str(raw_template_selection.get("resolved_hairstyle_id") or "").strip(),
        "resolved_hairstyle_name": str(raw_template_selection.get("resolved_hairstyle_name") or "").strip(),
        "display_group": str(raw_template_selection.get("display_group") or "").strip(),
        "structure_id": str(raw_template_selection.get("structure_id") or "").strip(),
        "modifier_ids": [
            str(item).strip()
            for item in raw_template_selection.get("modifier_ids", [])
            if str(item).strip()
        ],
        "technique_ids": [
            str(item).strip()
            for item in raw_template_selection.get("technique_ids", [])
            if str(item).strip()
        ],
    }

    return {
        "version": int(payload.get("version") or 0),
        "full_prompt": str(payload.get("full_prompt") or ""),
        "hairstyle_only_prompt": str(payload.get("hairstyle_only_prompt") or ""),
        "scene_only_prompt": str(payload.get("scene_only_prompt") or ""),
        "styling_id": str(payload.get("styling_id") or ""),
        "hair_color_selection": hair_color_selection,
        "template_selection": template_selection,
        "output_options": output_options,
    }


def _template_keyword_blob(template: dict) -> str:
    return " ".join(
        [
            str(template.get("id", "")),
            str(template.get("name", "")),
            str(template.get("description", "")),
            " ".join(template.get("tags", [])),
        ]
    ).lower()


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _hairstyle_cover_variant(template: dict) -> str:
    blob = _template_keyword_blob(template)
    if _contains_any(blob, ("spike", "前刺", "firework", "刺状", "束感")):
        return "spiky"
    if _contains_any(blob, ("buzz", "圆寸", "平头", "flat", "栗子头", "铲青")):
        return "buzz"
    if _contains_any(blob, ("mullet", "wolf", "狼尾", "鲻", "tail")):
        return "mullet"
    if _contains_any(blob, ("bun", "samurai", "苹果头", "topknot")):
        return "bun"
    if _contains_any(
        blob,
        (
            "perm",
            "curl",
            "wave",
            "卷",
            "羊毛",
            "气垫",
            "云朵",
            "水波",
            "木马",
            "纹理烫",
            "锡纸",
            "羽毛",
        ),
    ):
        return "curls"
    if _contains_any(
        blob,
        (
            "part",
            "fringe",
            "comma",
            "slick",
            "pomade",
            "三七",
            "中分",
            "碎盖",
            "刘海",
            "摩根",
        ),
    ):
        return "parted"
    if _contains_any(
        blob,
        (
            "long",
            "mid",
            "straight",
            "锁骨",
            "中长",
            "长发",
            "直发",
            "waterfall",
            "hime",
            "xinzhilei",
        ),
    ):
        return "long"
    if _contains_any(blob, ("bob", "波波", "short", "短发", "超短", "boyish", "挂耳", "初恋")):
        return "bob"
    return "soft"


def _scene_cover_variant(template: dict) -> str:
    blob = _template_keyword_blob(template)
    if _contains_any(blob, ("bathroom", "浴室", "mirror-morning")):
        return "bathroom"
    if _contains_any(blob, ("study", "书房", "walnut")):
        return "study"
    if _contains_any(blob, ("cafe", "咖啡")):
        return "cafe"
    if _contains_any(blob, ("window", "窗", "雨天", "softlight")):
        return "window"
    if _contains_any(blob, ("hotel", "bedside", "床边", "home", "家居")):
        return "bedroom"
    if _contains_any(blob, ("hallway", "玄关", "楼道")):
        return "hallway"
    if _contains_any(blob, ("studio", "棚拍", "solid-backdrop")):
        return "studio"
    if _contains_any(blob, ("metal", "金属", "cold")):
        return "metal"
    if _contains_any(blob, ("cinema", "retro")):
        return "cinema"
    if _contains_any(blob, ("neon", "夜", "都市", "city")):
        return "neon"
    if _contains_any(blob, ("gallery", "white-cube", "展厅")):
        return "gallery"
    if _contains_any(blob, ("side-light", "dramatic")):
        return "side-light"
    if _contains_any(blob, ("lobby", "大堂", "luxury")):
        return "lobby"
    if _contains_any(blob, ("rooftop", "天台", "wind")):
        return "rooftop"
    if _contains_any(blob, ("bar", "吧台", "moody")):
        return "bar"
    if _contains_any(blob, ("vanity", "backstage", "化妆镜")):
        return "vanity"
    return "interior"


def _hairstyle_svg_shapes(variant: str) -> tuple[str, str]:
    fills = {
        "base": "#1c2433",
        "shadow": "#121824",
        "highlight": "#324156",
    }
    if variant == "spiky":
        return (
            (
                '<path d="M257 454 C272 354 332 308 360 304 C386 300 452 334 470 448 '
                'C448 418 430 400 410 382 C402 396 392 360 380 342 C365 360 356 324 344 342 '
                'C330 360 320 344 306 374 C292 396 276 416 257 454 Z" fill="{base}"/>'
            ).format(**fills),
            '<path d="M305 382 C330 350 366 328 404 338 C386 354 362 364 336 388 Z" fill="{highlight}" opacity="0.26"/>'.format(
                **fills
            ),
        )
    if variant == "buzz":
        return (
            '<path d="M266 446 C272 358 324 316 360 312 C396 308 446 350 454 446 C430 378 402 354 360 352 C318 350 288 376 266 446 Z" fill="{base}"/>'.format(
                **fills
            ),
            '<ellipse cx="360" cy="360" rx="82" ry="34" fill="{highlight}" opacity="0.18"/>'.format(
                **fills
            ),
        )
    if variant == "parted":
        return (
            (
                '<path d="M250 466 C254 354 328 292 364 294 C418 296 466 350 470 462 '
                'C442 422 428 394 420 350 C394 354 382 362 370 380 C360 400 348 410 332 432 '
                'C322 404 300 376 276 360 C270 390 262 424 250 466 Z" fill="{base}"/>'
            ).format(**fills),
            '<path d="M356 302 C386 312 402 330 412 356 C388 350 370 354 350 372 C352 344 352 324 356 302 Z" fill="{highlight}" opacity="0.24"/>'.format(
                **fills
            ),
        )
    if variant == "curls":
        circles = []
        coords = [
            (286, 384, 44),
            (332, 338, 54),
            (392, 336, 54),
            (438, 386, 46),
            (316, 424, 42),
            (404, 426, 44),
            (360, 308, 46),
        ]
        for cx, cy, r in coords:
            circles.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fills["base"]}"/>')
        highlight = '<circle cx="328" cy="342" r="18" fill="{0}" opacity="0.18"/><circle cx="404" cy="356" r="20" fill="{0}" opacity="0.16"/>'.format(
            fills["highlight"]
        )
        return ("".join(circles), highlight)
    if variant == "bob":
        return (
            (
                '<path d="M248 446 C260 344 320 300 360 298 C402 296 462 336 474 446 '
                'C454 460 438 474 420 500 C406 520 392 538 360 544 C328 538 314 520 300 500 '
                'C282 474 266 458 248 446 Z" fill="{base}"/>'
            ).format(**fills),
            '<path d="M294 368 C320 336 352 320 390 326 C366 348 342 372 318 412 Z" fill="{highlight}" opacity="0.24"/>'.format(
                **fills
            ),
        )
    if variant == "long":
        return (
            (
                '<path d="M242 454 C250 336 316 286 360 284 C406 282 470 336 478 454 '
                'C466 544 450 640 438 740 C418 794 390 830 360 838 C330 830 302 794 282 740 '
                'C270 640 254 544 242 454 Z" fill="{base}"/>'
            ).format(**fills),
            '<path d="M304 342 C332 308 380 302 418 324 C392 350 366 380 340 430 Z" fill="{highlight}" opacity="0.2"/>'.format(
                **fills
            ),
        )
    if variant == "bun":
        return (
            (
                '<circle cx="360" cy="266" r="44" fill="{base}"/>'
                '<path d="M250 456 C256 348 324 298 360 296 C396 294 462 342 470 456 '
                'C444 426 426 402 414 360 C390 360 376 372 360 392 C344 372 330 360 306 360 '
                'C294 402 276 426 250 456 Z" fill="{base}"/>'
            ).format(**fills),
            '<circle cx="348" cy="252" r="14" fill="{highlight}" opacity="0.22"/>'.format(**fills),
        )
    if variant == "mullet":
        return (
            (
                '<path d="M248 446 C254 344 322 296 360 294 C404 292 466 340 472 446 '
                'C456 430 442 414 428 396 C422 456 422 546 418 650 C392 714 376 754 360 786 '
                'C344 754 328 714 302 650 C298 546 298 458 292 400 C278 416 264 432 248 446 Z" fill="{base}"/>'
            ).format(**fills),
            '<path d="M320 334 C350 312 384 312 412 330 C388 350 364 360 336 386 Z" fill="{highlight}" opacity="0.22"/>'.format(
                **fills
            ),
        )
    return (
        '<path d="M252 454 C260 352 324 304 360 300 C398 296 460 346 468 454 C438 424 414 410 360 408 C306 410 282 424 252 454 Z" fill="{base}"/>'.format(
            **fills
        ),
        '<path d="M304 350 C330 324 364 320 398 334 C376 350 350 366 324 392 Z" fill="{highlight}" opacity="0.2"/>'.format(
            **fills
        ),
    )


def _portrait_svg(*, hair_variant: str, accent: str) -> str:
    hair_base, hair_highlight = _hairstyle_svg_shapes(hair_variant)
    return f"""
  <circle cx="360" cy="382" r="178" fill="{accent}" opacity="0.18" />
  <ellipse cx="360" cy="860" rx="232" ry="122" fill="#ffffff" opacity="0.30" />
  <path d="M170 960 C210 806 510 806 550 960 Z" fill="#fbfdff" />
  <path d="M240 960 C260 850 460 850 480 960 Z" fill="#d9e7f6" opacity="0.72" />
  <rect x="326" y="548" width="68" height="96" rx="32" fill="#efc9b4" />
  <ellipse cx="360" cy="462" rx="108" ry="132" fill="#f4d4c2" />
  <ellipse cx="360" cy="486" rx="92" ry="108" fill="#ffdcca" opacity="0.24" />
  {hair_base}
  {hair_highlight}
  <path d="M308 566 C324 612 344 632 360 636 C376 632 396 612 412 566" stroke="#d6a98f" stroke-width="8" stroke-linecap="round" opacity="0.34" />
"""


def _scene_subject_svg() -> str:
    return """
  <circle cx="520" cy="506" r="112" fill="#ffffff" opacity="0.12" />
  <path d="M442 884 C458 786 592 786 608 884 L608 960 L442 960 Z" fill="#f6f8fd" opacity="0.95" />
  <rect x="504" y="590" width="42" height="66" rx="18" fill="#efc9b4" />
  <ellipse cx="525" cy="514" rx="72" ry="90" fill="#f4d4c2" />
  <path d="M456 516 C462 444 506 404 528 404 C560 404 596 446 598 518 C582 566 562 594 526 602 C490 594 470 566 456 516 Z" fill="#202737" />
  <path d="M470 470 C490 438 530 426 562 446 C540 470 516 490 492 538 Z" fill="#41536a" opacity="0.22" />
"""


def _scene_background_svg(variant: str, color_a: str, color_b: str) -> str:
    if variant == "window":
        return f"""
  <rect x="92" y="92" width="536" height="620" rx="34" fill="#ffffff" opacity="0.10" />
  <rect x="132" y="130" width="456" height="470" rx="28" fill="#ffffff" opacity="0.18" />
  <path d="M132 130 C116 178 108 224 108 266 L108 628" stroke="#ffffff" stroke-width="26" stroke-linecap="round" opacity="0.20" />
  <path d="M588 130 C604 178 612 224 612 266 L612 628" stroke="#ffffff" stroke-width="26" stroke-linecap="round" opacity="0.20" />
  <path d="M360 130 L360 600" stroke="#ffffff" stroke-width="8" opacity="0.24" />
  <path d="M132 368 L588 368" stroke="#ffffff" stroke-width="8" opacity="0.24" />
  <rect x="174" y="704" width="276" height="54" rx="20" fill="#ffffff" opacity="0.16" />
  <rect x="204" y="666" width="66" height="32" rx="10" fill="#ffffff" opacity="0.18" />
  <rect x="280" y="678" width="84" height="20" rx="10" fill="#ffffff" opacity="0.16" />
  <rect x="384" y="664" width="24" height="42" rx="10" fill="#ffffff" opacity="0.18" />
  <ellipse cx="396" cy="662" rx="18" ry="10" fill="#ffffff" opacity="0.20" />
"""
    if variant == "study":
        return """
  <rect x="86" y="108" width="204" height="602" rx="28" fill="#4c382a" opacity="0.46" />
  <rect x="106" y="150" width="164" height="118" rx="18" fill="#ffffff" opacity="0.10" />
  <rect x="106" y="292" width="164" height="118" rx="18" fill="#ffffff" opacity="0.10" />
  <rect x="106" y="434" width="164" height="118" rx="18" fill="#ffffff" opacity="0.10" />
  <rect x="106" y="576" width="164" height="94" rx="18" fill="#ffffff" opacity="0.10" />
  <rect x="346" y="116" width="220" height="270" rx="24" fill="#ffffff" opacity="0.12" />
  <rect x="376" y="146" width="160" height="210" rx="18" fill="#19342a" opacity="0.42" />
  <path d="M564 680 C520 642 498 612 486 570 C528 596 560 618 602 672 Z" fill="#7ecb8c" opacity="0.26" />
  <rect x="318" y="714" width="250" height="40" rx="20" fill="#6e4d37" opacity="0.34" />
"""
    if variant == "cafe":
        return """
  <path d="M126 190 C126 112 188 92 256 92 L466 92 C548 92 604 140 604 224 L604 516 L126 516 Z" fill="#ffffff" opacity="0.14" />
  <circle cx="224" cy="222" r="28" fill="#ffffff" opacity="0.18" />
  <circle cx="508" cy="234" r="24" fill="#ffffff" opacity="0.14" />
  <rect x="174" y="648" width="280" height="34" rx="17" fill="#ffffff" opacity="0.18" />
  <rect x="444" y="618" width="24" height="62" rx="12" fill="#ffffff" opacity="0.18" />
  <ellipse cx="456" cy="614" rx="22" ry="10" fill="#ffffff" opacity="0.18" />
  <path d="M502 170 C502 150 514 134 532 126 C526 150 534 170 548 182" stroke="#ffffff" stroke-width="8" stroke-linecap="round" opacity="0.18" />
"""
    if variant == "bathroom":
        return """
  <rect x="118" y="116" width="484" height="580" rx="30" fill="#ffffff" opacity="0.12" />
  <rect x="150" y="150" width="420" height="516" rx="26" fill="#ffffff" opacity="0.08" />
  <ellipse cx="360" cy="340" rx="152" ry="188" fill="#ffffff" opacity="0.20" />
  <ellipse cx="360" cy="340" rx="132" ry="166" fill="#dbe7f3" opacity="0.18" />
  <rect x="246" y="610" width="228" height="44" rx="22" fill="#ffffff" opacity="0.18" />
  <rect x="328" y="574" width="64" height="24" rx="12" fill="#ffffff" opacity="0.18" />
  <path d="M168 224 L552 224 M168 322 L552 322 M168 420 L552 420 M168 518 L552 518" stroke="#ffffff" stroke-width="6" stroke-opacity="0.10" />
"""
    if variant == "bedroom":
        return """
  <rect x="120" y="292" width="482" height="212" rx="44" fill="#ffffff" opacity="0.14" />
  <rect x="156" y="256" width="410" height="84" rx="30" fill="#ffffff" opacity="0.12" />
  <rect x="184" y="372" width="140" height="70" rx="22" fill="#ffffff" opacity="0.16" />
  <rect x="338" y="372" width="140" height="70" rx="22" fill="#ffffff" opacity="0.14" />
  <rect x="508" y="322" width="38" height="142" rx="18" fill="#ffffff" opacity="0.10" />
  <circle cx="526" cy="292" r="26" fill="#ffffff" opacity="0.16" />
"""
    if variant == "hallway":
        return """
  <rect x="170" y="96" width="380" height="724" rx="26" fill="#ffffff" opacity="0.10" />
  <rect x="214" y="148" width="292" height="620" rx="22" fill="#ffffff" opacity="0.18" />
  <rect x="260" y="214" width="80" height="120" rx="12" fill="#ffffff" opacity="0.14" />
  <rect x="382" y="182" width="102" height="148" rx="12" fill="#ffffff" opacity="0.12" />
  <path d="M214 768 L506 768" stroke="#ffffff" stroke-width="8" opacity="0.18" />
"""
    if variant == "studio":
        return """
  <circle cx="360" cy="320" r="220" fill="#ffffff" opacity="0.10" />
  <circle cx="360" cy="320" r="150" fill="#ffffff" opacity="0.08" />
  <ellipse cx="360" cy="816" rx="240" ry="92" fill="#ffffff" opacity="0.12" />
  <path d="M92 816 C190 734 530 734 628 816" stroke="#ffffff" stroke-width="10" opacity="0.12" fill="none" />
"""
    if variant == "metal":
        return f"""
  <path d="M90 160 L356 98 L356 418 L90 480 Z" fill="{color_a}" opacity="0.34" />
  <path d="M364 98 L628 160 L628 480 L364 418 Z" fill="#ffffff" opacity="0.12" />
  <path d="M132 566 L588 470" stroke="#ffffff" stroke-width="8" opacity="0.14" />
  <path d="M132 676 L588 580" stroke="#ffffff" stroke-width="8" opacity="0.10" />
  <path d="M170 774 L552 692" stroke="#ffffff" stroke-width="8" opacity="0.08" />
"""
    if variant == "cinema":
        return """
  <path d="M92 90 C136 188 142 292 122 420 L92 716 Z" fill="#6f2035" opacity="0.48" />
  <path d="M628 90 C584 188 578 292 598 420 L628 716 Z" fill="#6f2035" opacity="0.48" />
  <rect x="154" y="124" width="412" height="502" rx="24" fill="#ffffff" opacity="0.10" />
  <circle cx="248" cy="718" r="48" fill="#ffffff" opacity="0.10" />
  <circle cx="360" cy="736" r="54" fill="#ffffff" opacity="0.12" />
  <circle cx="478" cy="718" r="48" fill="#ffffff" opacity="0.10" />
"""
    if variant == "neon":
        return f"""
  <rect width="720" height="960" fill="#141a28" opacity="0.52" />
  <rect x="108" y="176" width="104" height="284" rx="16" fill="#00d5ff" opacity="0.10" />
  <rect x="236" y="136" width="122" height="324" rx="18" fill="#ffffff" opacity="0.08" />
  <rect x="384" y="198" width="102" height="262" rx="16" fill="#ff6bcb" opacity="0.12" />
  <rect x="506" y="150" width="90" height="310" rx="16" fill="#00d5ff" opacity="0.10" />
  <path d="M126 564 C224 526 322 526 420 564" stroke="#48d8ff" stroke-width="10" stroke-linecap="round" opacity="0.34" />
  <path d="M294 632 C378 600 458 600 548 632" stroke="#ff74d7" stroke-width="10" stroke-linecap="round" opacity="0.30" />
"""
    if variant == "gallery":
        return """
  <rect x="106" y="126" width="224" height="356" rx="24" fill="#ffffff" opacity="0.10" />
  <rect x="390" y="170" width="192" height="264" rx="24" fill="#ffffff" opacity="0.08" />
  <rect x="314" y="622" width="92" height="156" rx="18" fill="#ffffff" opacity="0.14" />
  <ellipse cx="360" cy="616" rx="82" ry="28" fill="#ffffff" opacity="0.12" />
"""
    if variant == "side-light":
        return """
  <path d="M94 112 L316 112 L174 858 L94 858 Z" fill="#ffffff" opacity="0.16" />
  <path d="M322 96 L626 96 L626 864 L206 864 Z" fill="#0f172a" opacity="0.26" />
  <path d="M266 112 L422 112 L304 860 L150 860 Z" fill="#ffffff" opacity="0.08" />
"""
    if variant == "lobby":
        return """
  <rect x="138" y="112" width="58" height="620" rx="18" fill="#ffffff" opacity="0.12" />
  <rect x="524" y="112" width="58" height="620" rx="18" fill="#ffffff" opacity="0.12" />
  <rect x="214" y="124" width="292" height="100" rx="22" fill="#ffffff" opacity="0.08" />
  <circle cx="360" cy="226" r="34" fill="#ffffff" opacity="0.18" />
  <path d="M360 262 L360 324" stroke="#ffffff" stroke-width="8" opacity="0.18" />
  <rect x="184" y="736" width="352" height="54" rx="27" fill="#ffffff" opacity="0.10" />
"""
    if variant == "rooftop":
        return """
  <rect x="90" y="548" width="540" height="18" rx="9" fill="#ffffff" opacity="0.18" />
  <rect x="122" y="330" width="74" height="218" rx="14" fill="#ffffff" opacity="0.08" />
  <rect x="214" y="286" width="92" height="262" rx="14" fill="#ffffff" opacity="0.10" />
  <rect x="326" y="238" width="78" height="310" rx="14" fill="#ffffff" opacity="0.08" />
  <rect x="420" y="314" width="96" height="234" rx="14" fill="#ffffff" opacity="0.10" />
  <rect x="536" y="268" width="58" height="280" rx="14" fill="#ffffff" opacity="0.08" />
  <circle cx="564" cy="138" r="38" fill="#ffffff" opacity="0.14" />
"""
    if variant == "bar":
        return """
  <rect x="96" y="184" width="528" height="490" rx="28" fill="#ffffff" opacity="0.08" />
  <rect x="140" y="228" width="440" height="54" rx="18" fill="#ffffff" opacity="0.08" />
  <rect x="140" y="318" width="440" height="54" rx="18" fill="#ffffff" opacity="0.08" />
  <rect x="152" y="704" width="416" height="70" rx="22" fill="#ffffff" opacity="0.14" />
  <rect x="188" y="248" width="24" height="58" rx="10" fill="#ffffff" opacity="0.16" />
  <rect x="250" y="248" width="28" height="70" rx="10" fill="#ffffff" opacity="0.16" />
  <rect x="490" y="250" width="28" height="64" rx="10" fill="#ffffff" opacity="0.14" />
"""
    if variant == "vanity":
        bulbs = []
        for cx in (174, 240, 306, 372, 438, 504, 570):
            bulbs.append(
                f'<circle cx="{cx}" cy="186" r="14" fill="#ffffff" opacity="0.24" />'
                f'<circle cx="{cx}" cy="560" r="14" fill="#ffffff" opacity="0.20" />'
            )
        for cy in (248, 320, 392, 464):
            bulbs.append(
                f'<circle cx="142" cy="{cy}" r="14" fill="#ffffff" opacity="0.20" />'
                f'<circle cx="602" cy="{cy}" r="14" fill="#ffffff" opacity="0.20" />'
            )
        return """
  <rect x="162" y="204" width="398" height="338" rx="28" fill="#ffffff" opacity="0.10" />
""" + "".join(bulbs)
    return """
  <rect x="96" y="118" width="528" height="600" rx="34" fill="#ffffff" opacity="0.10" />
  <rect x="146" y="170" width="428" height="500" rx="30" fill="#ffffff" opacity="0.08" />
  <rect x="174" y="712" width="268" height="46" rx="18" fill="#ffffff" opacity="0.14" />
"""


def template_cover_svg(category: str, template: dict) -> str:
    color_a, color_b = template["palette"]
    if category in {"hairstyles", "male-hairstyle-presets"}:
        body = _portrait_svg(
            hair_variant=_hairstyle_cover_variant(template),
            accent=color_b,
        )
    else:
        body = _scene_background_svg(_scene_cover_variant(template), color_a, color_b) + _scene_subject_svg()

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="960" viewBox="0 0 720 960">
  <defs>
    <linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="{color_a}" />
      <stop offset="100%" stop-color="{color_b}" />
    </linearGradient>
    <linearGradient id="shine" x1="0%" x2="100%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.22" />
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
    </linearGradient>
    <linearGradient id="fadeBottom" x1="0%" x2="0%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0" />
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.18" />
    </linearGradient>
  </defs>
  <rect width="720" height="960" rx="40" fill="url(#bg)" />
  <rect width="720" height="960" rx="40" fill="#0f172a" opacity="0.08" />
  <circle cx="602" cy="154" r="128" fill="#ffffff" opacity="0.10" />
  <circle cx="124" cy="832" r="180" fill="#ffffff" opacity="0.06" />
  <path d="M0 724 C178 650 354 650 720 826 L720 960 L0 960 Z" fill="url(#fadeBottom)" />
  <path d="M88 72 C210 40 328 46 430 104 C374 120 308 160 262 212 C210 170 150 122 88 72 Z" fill="url(#shine)" />
  {body}
</svg>"""
