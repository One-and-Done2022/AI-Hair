from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

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
BASIC_PLAN_RESOLUTIONS = ("2K",)
PREMIUM_PLAN_RESOLUTIONS = ("1K", "2K")
DEFAULT_GENERATOR_BACKEND = "basic"
DEFAULT_ASPECT_RATIO = "3:4"
DEFAULT_RESOLUTION = "2K"

GENERATOR_BACKEND_CAPABILITIES = {
    "basic": {
        "label": "基础版",
        "description": "先用 Nano Banana 2 生成仅换发图，再用 Seedream 4.5 生成 2 张场景成片。支持常用画幅，清晰度固定 2K。",
        "supports_reference_image": True,
        "aspect_ratios": PLAN_SAFE_ASPECT_RATIOS,
        "resolutions": BASIC_PLAN_RESOLUTIONS,
        "default_aspect_ratio": "3:4",
        "default_resolution": "2K",
        "hair_backend": "nano_banana_2",
        "scene_backend": "seedream",
        "scene_model_tier": "basic",
        "badge": "Nano Banana 2 + Seedream 4.5",
    },
    "premium": {
        "label": "高级版",
        "description": "先用 Nano Banana Pro 生成仅换发图，再用 Seedream 4.5 生成 2 张场景成片。支持常用画幅，清晰度可选 1K / 2K。",
        "supports_reference_image": True,
        "aspect_ratios": PLAN_SAFE_ASPECT_RATIOS,
        "resolutions": PREMIUM_PLAN_RESOLUTIONS,
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
        "generator_backend": "basic",
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
        "generator_backend": "basic",
        "aspect_ratio": "3:4",
        "resolution": "2K",
    },
    {
        "id": "showcase-film-parted",
        "title": "室内生活感三七分",
        "summary": "韩系三七分适合自然生活流场景，完成度更稳定。",
        "hairstyle_id": "male-korean-37-part",
        "scene_id": "indoor-film-lifestyle",
        "generator_backend": "basic",
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
    "nano_banana_2": "basic",
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
VALID_PROMPT_MODES = {"full_stylize", "hairstyle_only", "scene_only"}
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
    "只更换图中人物的发型，除头发、刘海、鬓角、后颈发区和发际线相关区域外，"
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
    "皮肤质感真实自然，不过度磨皮，不过度妆感，保留真实面部纹理与发丝细节。"
)

QUALITY_IMAGE_FINISH_SECTION = (
    "脸部清晰对焦，光影过渡自然，整体高级、自然、和谐。"
)

QUALITY_SECTION = QUALITY_SKIN_TEXTURE_SECTION + QUALITY_IMAGE_FINISH_SECTION

HAIRSTYLE_ONLY_CONSTRAINTS_SECTION = (
    "仅允许修改头发、刘海、鬓角、后颈发区和发际线相关视觉效果，不要改动背景、服饰、表情、动作和构图；"
    "发型必须贴合原人物头骨结构、头部朝向、耳位位置、肩颈遮挡关系与镜头透视；"
    "不能把新发型做成悬浮假发、错位发片或不贴合头皮的假发套效果。"
)

SCENE_ONLY_CONSTRAINTS_SECTION = (
    "人物发型必须保持参考图中已经生成完成的现有发型，不要二次修改发型种类；"
    "不要改变发长、顶部体积、刘海、分线、鬓角、后颈发区、卷度、发色和整体轮廓；"
    "动作、表情、服装、场景和布光变化不能破坏既有发型结构、头皮贴合关系与发丝走向。"
)

NEGATIVE_IDENTITY_ARTIFACT_SECTION = (
    "不要换脸、不要改变性别表达、不要生成第二个人、不要多人同框、不要双脸、不要身份漂移、"
    "不要整容感、AI 脸、过度磨皮、塑料皮肤、五官漂移、错位眼睛、手指异常、耳朵变形、"
    "发际线异常、假发感、不要背景杂乱、光影冲突、不要过强滤镜、过度锐化、不要文字水印、不要拼图排版。"
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
        "output_format": "输出形式",
        "face_strategy": "脸型修饰",
        "shot": "构图景别",
        "scene_environment": "场景环境",
        "scene_lighting": "场景光线",
        "scene_mood": "场景氛围",
        "scene_control": "场景控制",
        "expression": "人物表情",
        "subject_action": "主体动作",
        "hairstyle_action": "发型展示动作",
        "makeup": "人物妆容",
        "outfit": "人物服饰",
        "edit_scope": "编辑目标",
        "hair_target": "目标发型",
        "hair_lock": "发型锁定",
        "styling_constraints": "妆造约束",
        "scene_constraints": "场景约束",
        "hair_constraints": "发型约束",
        "hair_edit_scope_constraints": "换发范围约束",
        "hair_preservation_constraints": "发型保持约束",
        "hair_shape_constraints": "发型落地约束",
        "motion_safety_constraints": "动作安全约束",
        "quality_skin_texture": "肤质细节",
        "quality_image_finish": "成片质量",
        "negative_identity_artifact": "身份伪影负面约束",
        "negative_physical_logic": "物理逻辑负面约束",
    }


def _normalize_generator_backend(backend_id: str | None) -> str:
    raw = (backend_id or DEFAULT_GENERATOR_BACKEND).strip().lower()
    return LEGACY_GENERATOR_BACKEND_ALIASES.get(raw, raw)


def get_generation_plan(backend_id: str | None) -> dict | None:
    resolved_backend = _normalize_generator_backend(backend_id)
    capability = GENERATOR_BACKEND_CAPABILITIES.get(resolved_backend)
    if capability is None:
        return None
    settings = get_settings()
    scene_model_name = (
        settings.seedream_basic_model
        if capability["scene_model_tier"] == "basic"
        else settings.seedream_premium_model
    )
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
        return bool(settings.nano_banana_pro_api_key)
    if plan["hair_backend"] == "nano_banana_2":
        return bool(settings.nano_banana_2_api_key)
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
    if mode not in VALID_PROMPT_MODES:
        raise ValueError(f"Unsupported prompt mode: {mode}")
    assembly = PromptAssembly(
        mode=mode,
        blocks=tuple(block for block in blocks if block is not None),
    )
    _validate_prompt_assembly(assembly)
    return assembly


def _build_quality_blocks() -> list[PromptBlock | None]:
    return [
        _make_prompt_block("quality_skin_texture", QUALITY_SKIN_TEXTURE_SECTION),
        _make_prompt_block("quality_image_finish", QUALITY_IMAGE_FINISH_SECTION),
    ]


def _build_negative_blocks() -> list[PromptBlock | None]:
    return [
        _make_prompt_block("negative_identity_artifact", f"负面约束：{NEGATIVE_IDENTITY_ARTIFACT_SECTION}"),
        _make_prompt_block("negative_physical_logic", NEGATIVE_PHYSICAL_LOGIC_SECTION),
    ]


def get_prompt_rule_table() -> dict[str, PromptRule]:
    return {
        "full_stylize": PromptRule(
            mode="full_stylize",
            required_blocks=(
                "identity_lock",
                "output_format",
                "shot",
                "scene_environment",
                "scene_lighting",
                "scene_mood",
                "expression",
                "subject_action",
                "makeup",
                "outfit",
                "hair_target",
                "styling_constraints",
                "scene_constraints",
                "hair_constraints",
                "motion_safety_constraints",
                "quality_skin_texture",
                "quality_image_finish",
                "negative_identity_artifact",
                "negative_physical_logic",
            ),
            optional_blocks=("hairstyle_action",),
            forbidden_blocks=(
                "edit_scope",
                "hair_lock",
                "hair_preservation_constraints",
                "hair_edit_scope_constraints",
                "hair_shape_constraints",
            ),
            description="完整换发型与换场景创作模式。",
        ),
        "hairstyle_only": PromptRule(
            mode="hairstyle_only",
            required_blocks=(
                "identity_lock",
                "output_format",
                "edit_scope",
                "hair_target",
                "hair_edit_scope_constraints",
                "hair_shape_constraints",
                "quality_skin_texture",
                "quality_image_finish",
                "negative_identity_artifact",
                "negative_physical_logic",
            ),
            forbidden_blocks=(
                "face_strategy",
                "scene_control",
                "shot",
                "scene_environment",
                "scene_lighting",
                "scene_mood",
                "expression",
                "subject_action",
                "hairstyle_action",
                "makeup",
                "outfit",
                "hair_lock",
                "hair_preservation_constraints",
                "styling_constraints",
                "scene_constraints",
                "hair_constraints",
                "motion_safety_constraints",
            ),
            description="只改发型，不改背景服饰动作构图。",
        ),
        "scene_only": PromptRule(
            mode="scene_only",
            required_blocks=(
                "identity_lock",
                "output_format",
                "shot",
                "scene_environment",
                "scene_lighting",
                "scene_mood",
                "expression",
                "subject_action",
                "makeup",
                "outfit",
                "hair_lock",
                "hair_preservation_constraints",
                "styling_constraints",
                "scene_constraints",
                "motion_safety_constraints",
                "quality_skin_texture",
                "quality_image_finish",
                "negative_identity_artifact",
                "negative_physical_logic",
            ),
            forbidden_blocks=(
                "hairstyle_action",
                "hair_target",
                "hair_edit_scope_constraints",
                "hair_shape_constraints",
                "hair_constraints",
            ),
            description="锁定现有发型和人脸，只扩展场景动作服饰。",
        ),
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


def _filter_scene_actions_for_locked_hairstyle(actions: Iterable[str]) -> list[str]:
    candidates = _dedupe_keep_order(actions)
    filtered = [
        action
        for action in candidates
        if not any(keyword in action for keyword in HAIR_TOUCH_ACTION_KEYWORDS)
    ]
    return filtered or candidates


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


@lru_cache(maxsize=1)
def _catalog() -> dict[str, list[dict]]:
    scenes = [_build_scene_template(item) for item in _load_json("scenes.json")]
    male_hairstyles = [
        _build_hairstyle_template(item) for item in _load_json("hairstyles_male.json")
    ]
    female_hairstyles = [
        _build_hairstyle_template(item) for item in _load_json("hairstyles_female.json")
    ]
    stylings = [_build_styling_template(item) for item in _load_json("stylings.json")]
    scene_styling_rules = [
        _build_scene_styling_rule(item) for item in _load_json("scene_styling_rules.json")
    ]
    return {
        "scenes": scenes,
        "hairstyles": [*male_hairstyles, *female_hairstyles],
        "stylings": stylings,
        "scene_styling_rules": scene_styling_rules,
    }


SCENES = _catalog()["scenes"]
HAIRSTYLES = _catalog()["hairstyles"]
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


def get_scene(template_id: str) -> dict | None:
    resolved_id = _resolve_alias("scene", template_id)
    return _find_template(SCENES, resolved_id)


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


def build_prompt_assembly(
    *,
    mode: str,
    hairstyle: dict | None = None,
    scene: dict | None = None,
    styling: dict | None = None,
    preferred_gender: str | None = None,
    seed_source: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    outfit_override: str | None = None,
) -> PromptAssembly:
    if mode not in VALID_PROMPT_MODES:
        raise ValueError(f"Unsupported prompt mode: {mode}")

    if mode == "hairstyle_only":
        if hairstyle is None:
            raise ValueError("hairstyle is required for hairstyle_only mode")
        constraint_items = [
            _normalize_sentence(item)
            for item in _dedupe_keep_order(
                [
                    HAIRSTYLE_ONLY_CONSTRAINTS_SECTION,
                    *hairstyle.get("constraints", []),
                ]
            )
        ]
        edit_scope_constraint_text = _normalize_sentence(HAIRSTYLE_ONLY_CONSTRAINTS_SECTION)
        shape_constraint_text = "；".join(
            item for item in constraint_items if item != edit_scope_constraint_text
        )
        return _assemble_prompt(
            "hairstyle_only",
            [
                _make_prompt_block("identity_lock", HAIRSTYLE_ONLY_IDENTITY_LOCK_SECTION),
                _make_prompt_block("output_format", OUTPUT_FORMAT_SECTION),
                _make_prompt_block("edit_scope", f"换发目标：只更换图中人物的发型为：{hairstyle['name']}。"),
                _make_prompt_block("hair_target", f"人物发型：{_normalize_sentence(hairstyle['prompt_core'])}。"),
                _make_prompt_block("hair_edit_scope_constraints", f"编辑范围约束：{edit_scope_constraint_text}。"),
                _make_prompt_block("hair_shape_constraints", f"发型落地约束：{shape_constraint_text}。"),
                *_build_quality_blocks(),
                *_build_negative_blocks(),
            ],
        )

    if mode == "scene_only":
        if scene is None:
            raise ValueError("scene is required for scene_only mode")
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
        available_actions = (
            _filter_scene_actions_for_locked_hairstyle(scene.get("actions", []))
            if not subject_action_override
            else _dedupe_keep_order(scene.get("actions", []))
        )
        selected_subject_action = subject_action_override or _select_one(
            available_actions,
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
        scene_constraint_text = "；".join(
            _normalize_sentence(item) for item in _dedupe_keep_order(scene.get("constraints", []))
        )
        hair_preservation_text = _normalize_sentence(SCENE_ONLY_CONSTRAINTS_SECTION)
        motion_safety_text = "；".join(
            [
                "后端每次只选 1 个主体动作，不再把多个动作选项同时写进同一条提示词",
                "单张图中只保留一种主体动作，不要把多个互斥手部动作同时放进同一画面",
                "如果主体动作已经占用手部，不要再追加抓头发、拨头发、整理发丝等额外发型细节动作",
                "不要因为动作、风感或镜头变化把当前发型改成另一种发型",
            ]
        )
        return _assemble_prompt(
            "scene_only",
            [
                _make_prompt_block("identity_lock", SCENE_ONLY_IDENTITY_LOCK_SECTION),
                _make_prompt_block("output_format", OUTPUT_FORMAT_SECTION),
                _make_prompt_block("shot", f"构图：{_normalize_sentence(scene['shot_advice'])}。"),
                _make_prompt_block("scene_environment", f"场景：{_normalize_sentence(scene['environment'])}。"),
                _make_prompt_block(
                    "scene_lighting",
                    f"光线：{_resolve_scene_lighting_text(scene, scene_rule)}。",
                ),
                _make_prompt_block("scene_mood", f"风格氛围：{_normalize_sentence(scene['style_mood'])}。"),
                _make_prompt_block(
                    "expression",
                    f"人物表情：本张图只选择 1 种主表情，固定为：{selected_expression or '自然看向镜头'}。",
                ),
                _make_prompt_block(
                    "subject_action",
                    f"人物动作：单张图中只选择 1 种主体动作，本张图固定为：{selected_subject_action or '自然站立或静止停顿'}。",
                ),
                _make_prompt_block(
                    "makeup",
                    f"妆容：{styling_values['makeup_text'] or '妆面保持轻透真实、干净克制，不要出现夸张浓妆'}。",
                ),
                _make_prompt_block(
                    "outfit",
                    f"服饰：{styling_values['outfit_text'] or '米白色针织、浅卡其衬衫或裸色背心'}。",
                ),
                _make_prompt_block(
                    "hair_lock",
                    "人物发型：保持参考图中已经生成完成的发型不变，不要二次改发，不改变发长、顶部体积、刘海、分线、鬓角、后颈发区、卷度、发色和整体轮廓。",
                ),
                _make_prompt_block("hair_preservation_constraints", f"发型保持约束：{hair_preservation_text}。"),
                _make_prompt_block(
                    "styling_constraints",
                    f"妆造约束：{styling_values['styling_constraints'] or '妆容与服饰需服从当前场景光线和氛围，不要出现与环境冲突的夸张造型'}。",
                ),
                _make_prompt_block("scene_constraints", f"场景关键约束：{scene_constraint_text}。"),
                _make_prompt_block("motion_safety_constraints", f"动作安全约束：{motion_safety_text}。"),
                *_build_quality_blocks(),
                *_build_negative_blocks(),
            ],
        )

    if hairstyle is None or scene is None:
        raise ValueError("hairstyle and scene are required for full_stylize mode")

    selection_seed = seed_source or f"{hairstyle['id']}:{scene['id']}"
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
    styling_values = _build_styling_prompt_values(
        scene=scene,
        styling=selected_styling,
        scene_rule=scene_rule,
        preferred_gender=hairstyle.get("gender"),
        makeup_override=makeup_override_text,
        outfit_override=resolved_outfit_override,
    )
    scene_constraint_text = "；".join(
        _normalize_sentence(item) for item in _dedupe_keep_order(scene.get("constraints", []))
    )
    hair_constraint_text = "；".join(
        _normalize_sentence(item) for item in _dedupe_keep_order(hairstyle.get("constraints", []))
    )
    motion_safety_text = "；".join(
        [
            "后端每次只选 1 个主体动作，不再把多个动作选项同时写进同一条提示词",
            "单张图中只保留一种主体动作，不要把多个互斥手部动作同时放进同一画面",
            "如果主体动作已经占用手部，不要再叠加抓头发、拨头发、握杯等额外手部细节动作",
            "发型细节动作不要与主体动作叠加成不合理肢体效果",
        ]
    )
    return _assemble_prompt(
        "full_stylize",
        [
            _make_prompt_block("identity_lock", IDENTITY_LOCK_SECTION),
            _make_prompt_block("output_format", OUTPUT_FORMAT_SECTION),
            _make_prompt_block("shot", f"构图：{_normalize_sentence(scene['shot_advice'])}。"),
            _make_prompt_block("scene_environment", f"场景：{_normalize_sentence(scene['environment'])}。"),
            _make_prompt_block(
                "scene_lighting",
                f"光线：{_resolve_scene_lighting_text(scene, scene_rule)}。",
            ),
            _make_prompt_block("scene_mood", f"风格氛围：{_normalize_sentence(scene['style_mood'])}。"),
            _make_prompt_block(
                "expression",
                f"人物表情：本张图只选择 1 种主表情，固定为：{expression_text}。",
            ),
            _make_prompt_block(
                "subject_action",
                f"人物动作：单张图中只选择 1 种主体动作，本张图固定为：{scene_action_text}。",
            ),
            _make_prompt_block(
                "hairstyle_action",
                (
                    "发型展示动作参考：如需突出发型，本张图最多只允许额外参考 1 种细节动作，"
                    f"固定为：{hairstyle_action_text}。"
                    if hairstyle_action_text
                    else "发型展示动作参考：本张图不额外叠加发型手部细节动作，以免与主体动作产生手部冲突。"
                ),
            ),
            _make_prompt_block(
                "makeup",
                f"妆容：{styling_values['makeup_text'] or '妆面保持轻透真实、干净克制，不要出现夸张浓妆'}。",
            ),
            _make_prompt_block(
                "outfit",
                f"服饰：{styling_values['outfit_text'] or '白色宽松衬衫，内搭浅色背心或吊带'}。",
            ),
            _make_prompt_block("hair_target", f"人物发型：{_normalize_sentence(hairstyle['prompt_core'])}。"),
            _make_prompt_block(
                "styling_constraints",
                f"妆造约束：{styling_values['styling_constraints'] or '妆容与服饰需与发型、布光和场景基调统一，不要出现不合时宜的强妆或夸张服装'}。",
            ),
            _make_prompt_block("scene_constraints", f"场景关键约束：{scene_constraint_text}。"),
            _make_prompt_block("hair_constraints", f"发型关键约束：{hair_constraint_text}。"),
            _make_prompt_block("motion_safety_constraints", f"动作安全约束：{motion_safety_text}。"),
            *_build_quality_blocks(),
            *_build_negative_blocks(),
        ],
    )


def build_prompt(
    hairstyle: dict,
    scene: dict,
    *,
    styling: dict | None = None,
    seed_source: str | None = None,
) -> str:
    return build_prompt_assembly(
        mode="full_stylize",
        hairstyle=hairstyle,
        scene=scene,
        styling=styling,
        seed_source=seed_source,
    ).render()


def build_hairstyle_only_prompt(hairstyle: dict) -> str:
    return build_prompt_assembly(
        mode="hairstyle_only",
        hairstyle=hairstyle,
    ).render()


def build_scene_only_prompt(
    scene: dict,
    *,
    styling: dict | None = None,
    preferred_gender: str | None = None,
    seed_source: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    outfit_override: str | None = None,
) -> str:
    return build_prompt_assembly(
        mode="scene_only",
        scene=scene,
        styling=styling,
        preferred_gender=preferred_gender,
        seed_source=seed_source,
        expression_override=expression_override,
        subject_action_override=subject_action_override,
        outfit_override=outfit_override,
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
    raw_resolution = (resolution or DEFAULT_RESOLUTION).strip()
    resolved_resolution = "512px" if raw_resolution.lower() == "512px" else raw_resolution.upper()

    if resolved_aspect_ratio not in capability["aspect_ratios"]:
        raise ValueError(f"Unsupported aspect ratio: {resolved_aspect_ratio}")

    if capability["resolutions"]:
        default_resolution = capability["default_resolution"] or DEFAULT_RESOLUTION
        if not resolution:
            resolved_resolution = default_resolution
        if resolved_resolution not in capability["resolutions"]:
            raise ValueError(f"Unsupported resolution: {resolved_resolution}")
    else:
        resolved_resolution = None

    return {
        "generator_backend": resolved_backend,
        "aspect_ratio": resolved_aspect_ratio,
        "resolution": resolved_resolution,
    }


def build_job_prompt_payload(
    hairstyle: dict,
    scene: dict,
    *,
    generator_backend: str | None = None,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    seed_source: str | None = None,
) -> str:
    generation_options = normalize_generation_options(
        generator_backend=generator_backend,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
    )
    selection_seed = seed_source or f"{hairstyle['id']}:{scene['id']}"
    selected_styling = _resolve_styling(
        style_line=scene["style_line"],
        preferred_gender=hairstyle.get("gender"),
        seed_source=selection_seed,
        scene=scene,
        scene_rule=get_scene_styling_rule(scene["id"]),
    )
    payload = {
        "version": 2,
        "full_prompt": build_prompt(
            hairstyle,
            scene,
            styling=selected_styling,
            seed_source=selection_seed,
        ),
        "hairstyle_only_prompt": build_hairstyle_only_prompt(hairstyle),
        "scene_only_prompt": build_scene_only_prompt(
            scene,
            styling=selected_styling,
            preferred_gender=hairstyle.get("gender"),
            seed_source=f"scene-only:{selection_seed}",
        ),
        "styling_id": selected_styling["id"],
        "output_options": generation_options,
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_job_prompt_payload(raw_prompt: str) -> dict:
    normalized_options = normalize_generation_options()
    if not raw_prompt.strip():
        return {
            "version": 0,
            "full_prompt": "",
            "hairstyle_only_prompt": "",
            "scene_only_prompt": "",
            "styling_id": "",
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
            "output_options": normalized_options,
        }

    if not isinstance(payload, dict):
        return {
            "version": 0,
            "full_prompt": raw_prompt,
            "hairstyle_only_prompt": "",
            "scene_only_prompt": "",
            "styling_id": "",
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
        normalized_resolution = (
            "512px" if isinstance(raw_resolution, str) and raw_resolution.lower() == "512px"
            else str(raw_resolution).upper() if raw_resolution is not None else None
        )
        output_options = {
            "generator_backend": resolved_backend,
            "aspect_ratio": (
                raw_aspect_ratio
                if isinstance(raw_aspect_ratio, str) and raw_aspect_ratio in SUPPORTED_ASPECT_RATIOS
                else capability["default_aspect_ratio"] or DEFAULT_ASPECT_RATIO
            ),
            "resolution": (
                normalized_resolution
                if isinstance(normalized_resolution, str) and normalized_resolution in SUPPORTED_RESOLUTIONS
                else (capability["default_resolution"] or DEFAULT_RESOLUTION)
            ),
        }
    return {
        "version": payload.get("version", 1),
        "full_prompt": str(payload.get("full_prompt") or ""),
        "hairstyle_only_prompt": str(payload.get("hairstyle_only_prompt") or ""),
        "scene_only_prompt": str(payload.get("scene_only_prompt") or ""),
        "styling_id": str(payload.get("styling_id") or ""),
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
    if category == "hairstyles":
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
