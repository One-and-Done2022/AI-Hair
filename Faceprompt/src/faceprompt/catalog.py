from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

BASE_IDENTITY_PROMPT = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真。"
    "第一优先级是严格保留参考人物的真实身份特征，保证一眼看出是同一个人。"
    "以上传照片中的人物为原型，不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质，"
    "不改变性别表达，不换脸，不生成第二个人。"
    "忽略原照片中的背景、原服饰、原发型和原有动作，仅保留参考人物本身，进行换发和换背景创作。"
    "主体必须始终是同一位单人肖像，仅对发型、场景、动作、表情和服装进行艺术化创作。"
)

HAIRSTYLE_ONLY_IDENTITY_PROMPT = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像图。"
    "第一优先级是严格保留参考人物的真实身份特征，保证一眼看出是同一个人。"
    "以上传照片中的人物为原型，不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质，"
    "不改变性别表达，不换脸，不生成第二个人。"
    "只更换图中人物的发型，除头发、刘海、鬓角、后颈发区和发际线相关区域外，"
    "尽量保持原图中的背景、服饰、姿态、表情、构图、镜头距离、光线和氛围不变。"
)

SCENE_ONLY_IDENTITY_PROMPT = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真。"
    "第一优先级是严格保留参考人物的真实身份特征，保证一眼看出是同一个人。"
    "以上传照片中的人物为原型，不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质和发型，"
    "不改变性别表达，不换脸，不生成第二个人。"
    "忽略原照片中的背景、原服饰、原有动作，仅保留参考人物本身，进行换背景创作。"
    "主体必须始终是同一位单人肖像，仅对场景、动作、表情和服装进行艺术化创作。"
)

OUTPUT_FORMAT_PROMPT = (
    "只输出 1 张完整成片，不要拼图，不要多宫格，不要在同一画面里同时展示多个动作版本或多个发型版本。"
)

QUALITY_SKIN_TEXTURE_PROMPT = (
    "皮肤质感真实自然，不过度磨皮，不过度妆感，保留真实面部纹理与发丝细节。"
)

QUALITY_IMAGE_FINISH_PROMPT = (
    "脸部清晰对焦，光影过渡自然，整体高级、自然、和谐。"
)

QUALITY_PROMPT = QUALITY_SKIN_TEXTURE_PROMPT + QUALITY_IMAGE_FINISH_PROMPT

HAIRSTYLE_ONLY_CONSTRAINTS_PROMPT = (
    "仅允许修改头发、刘海、鬓角、后颈发区和发际线相关视觉效果，不要改动背景、服饰、表情、动作和构图；"
    "发型必须贴合原人物头骨结构、头部朝向、耳位位置、肩颈遮挡关系与镜头透视；"
    "不能把新发型做成悬浮假发、错位发片或不贴合头皮的假发套效果。"
)

SCENE_ONLY_CONSTRAINTS_PROMPT = (
    "人物发型必须保持参考图中已经生成完成的现有发型，不要二次修改发型种类；"
    "不要改变发长、顶部体积、刘海、分线、鬓角、后颈发区、卷度、发色和整体轮廓；"
    "动作、表情、服装、场景和布光变化不能破坏既有发型结构、头皮贴合关系与发丝走向。"
)

NEGATIVE_IDENTITY_ARTIFACT_PROMPT = (
    "不要换脸、不要改变性别表达、不要生成第二个人、不要多人同框、不要双脸、不要身份漂移、"
    "不要整容感、AI 脸、过度磨皮、塑料皮肤、五官漂移、错位眼睛、"
    "手指异常、耳朵变形、发际线异常、假发感、不要背景杂乱、光影冲突、不要过强滤镜、过度锐化、不要文字水印。"
)

NEGATIVE_PHYSICAL_LOGIC_PROMPT = (
    "图片需要符合物理逻辑，不要在画面中多出不合逻辑的手和身体部位。"
    "不可以有不符合物理逻辑的身体部位（例如同时出现多于两只手的情况）。"
)

BASE_NEGATIVE_PROMPT = NEGATIVE_IDENTITY_ARTIFACT_PROMPT + NEGATIVE_PHYSICAL_LOGIC_PROMPT

VALID_STYLE_LINES = {"realistic_editorial", "fashion_editorial"}
VALID_CATEGORIES = {"scene", "hairstyle"}
VALID_GENDERS = {"male", "female", "unisex"}
VALID_FACE_SHAPES = {"oval", "round", "long", "square", "heart", "diamond"}
VALID_FOREHEAD_TYPES = {"narrow", "balanced", "broad"}
VALID_JAWLINES = {"soft", "defined", "angular"}
VALID_CHEEKBONES = {"soft", "balanced", "prominent"}
VALID_WIND_LEVELS = {"still", "low", "medium", "high"}
VALID_HUMIDITY_LOOKS = {"dry", "balanced", "humid", "wet"}
VALID_BACKGROUND_COMPLEXITIES = {"low", "medium", "high"}
VALID_LIGHTING_HARDNESSES = {"soft", "balanced", "hard"}
VALID_MIRROR_RISKS = {"none", "low", "medium", "high"}
PROMPT_MODE_ALIASES = {
    "hair_only": "hair_only",
    "hairstyle_only": "hair_only",
    "scene_only": "scene_only",
    "full_stylize": "full_stylize",
}
VALID_PROMPT_MODES = set(PROMPT_MODE_ALIASES)

FACE_SHAPE_LABELS = {
    "oval": "椭圆脸",
    "round": "圆脸",
    "long": "长脸",
    "square": "方脸",
    "heart": "心形脸",
    "diamond": "菱形脸",
}

FOREHEAD_LABELS = {
    "narrow": "额头偏窄",
    "balanced": "额头比例均衡",
    "broad": "额头偏宽",
}

JAWLINE_LABELS = {
    "soft": "下颌线柔和",
    "defined": "下颌线清晰",
    "angular": "下颌线偏棱角",
}

CHEEKBONE_LABELS = {
    "soft": "颧骨存在感低",
    "balanced": "颧骨比例均衡",
    "prominent": "颧骨较突出",
}

WIND_LEVEL_LABELS = {
    "still": "静止无风",
    "low": "轻微风感",
    "medium": "中等风感",
    "high": "明显风场",
}

HUMIDITY_LOOK_LABELS = {
    "dry": "干爽无湿发感",
    "balanced": "自然干发观感",
    "humid": "轻微潮润空气感",
    "wet": "明显湿发观感",
}

BACKGROUND_COMPLEXITY_LABELS = {
    "low": "低复杂度背景",
    "medium": "中等复杂度背景",
    "high": "高复杂度背景",
}

LIGHTING_HARDNESS_LABELS = {
    "soft": "柔光",
    "balanced": "中性清晰布光",
    "hard": "硬光高反差",
}

MIRROR_RISK_LABELS = {
    "none": "无镜面反射风险",
    "low": "低镜面反射风险",
    "medium": "中等镜面反射风险",
    "high": "高镜面反射风险",
}

COMPATIBILITY_TAG_LABELS = {
    "sharp_texture": "强纹理轮廓",
    "hard_light_ready": "硬光可读",
    "urban_night": "都市夜景",
    "soft_parting": "柔和分线",
    "face_framing": "包脸修饰",
    "fringe_correction": "刘海修正",
    "layered_face_framing": "层次包脸",
    "soft_motion": "轻动势轮廓",
    "soft_volume": "柔和蓬松",
    "head_wrapping": "头包脸轮廓",
    "fashion_minimal": "极简时装",
    "precise_outline": "精确切线",
    "lifestyle_softlight": "生活化软光",
    "urban_lifestyle": "都市生活感",
}

GENERIC_SCENE_BY_STYLE = {
    "realistic_editorial": (
        "室内生活感胶片人像写真，浅色墙面与木质家具形成安静背景，"
        "窗边自然光从侧前方进入，前景带少量浅色虚化遮挡，整体松弛克制。"
    ),
    "fashion_editorial": (
        "时尚大片风格人像，空间轮廓利落干净，布光有明确层次与反差，"
        "画面强调高级造型感与镜头张力。"
    ),
}

GENERIC_HAIRSTYLE_BY_STYLE = {
    "realistic_editorial": (
        "深棕至黑色自然层次发型，头顶保持轻盈蓬松，发丝走向自然，"
        "局部碎发轻扫脸侧，与真实写真氛围融洽。"
    ),
    "fashion_editorial": (
        "轮廓明确、层次清晰的高级造型发型，发丝纹理利落，"
        "重点区域有鲜明结构感，与时尚大片布光保持统一。"
    ),
}

GENERIC_EXPRESSIONS = [
    "自然看向镜头",
    "安静地垂眼停顿",
    "微微偏头、神情松弛",
]

GENERIC_SCENE_ACTIONS = [
    "自然站立或静止停顿",
    "平视镜头、肩颈轻微放松",
    "半侧身停在抓拍瞬间",
]

GENERIC_HAIRSTYLE_ACTIONS = [
    "看镜头微抬下巴",
    "半侧脸回望镜头",
]

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


@dataclass(frozen=True)
class SourceReference:
    id: str
    title: str
    url: str
    kind: str
    notes: str


@dataclass(frozen=True)
class CatalogRecord:
    id: str
    title: str
    categoryType: str
    gender: str
    styleLine: str
    summary: str
    promptCore: str
    detailTags: tuple[str, ...]
    constraints: tuple[str, ...]
    negativePrompt: str
    pairingAdvice: tuple[str, ...]
    shotAdvice: str
    expressionAction: tuple[str, ...]
    referenceNotes: str
    referenceSources: tuple[SourceReference, ...]
    exampleFinalPrompt: str
    environment: str = ""
    lighting: str = ""
    styleMood: str = ""
    expressions: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    outfitHints: tuple[str, ...] = ()
    hairstyleControl: HairstyleControlProfile | None = None
    sceneControl: SceneControlProfile | None = None
    presetBlocks: dict[str, Any] | None = None


@dataclass(frozen=True)
class FaceProfile:
    faceShape: str | None = None
    forehead: str | None = None
    jawline: str | None = None
    cheekbone: str | None = None


@dataclass(frozen=True)
class HairstyleControlProfile:
    faceShapeFitBest: tuple[str, ...] = ()
    faceShapeFitOk: tuple[str, ...] = ()
    faceShapeFitAvoid: tuple[str, ...] = ()
    recommendedForeheads: tuple[str, ...] = ()
    recommendedJawlines: tuple[str, ...] = ()
    recommendedCheekbones: tuple[str, ...] = ()
    foreheadStrategy: str = ""
    templeCoverage: str = ""
    cheekSoftening: str = ""
    jawlineExposure: str = ""
    crownVolume: str = ""
    sideVolume: str = ""
    partingOptions: tuple[str, ...] = ()
    fringeType: str = ""
    lengthZone: str = ""
    curlScale: str = ""
    compatibilityTags: tuple[str, ...] = ()
    recommendedSceneIds: tuple[str, ...] = ()


@dataclass(frozen=True)
class SceneControlProfile:
    windLevel: str = ""
    humidityLook: str = ""
    backgroundComplexity: str = ""
    lightingHardness: str = ""
    mirrorRisk: str = ""
    compatibleHairstyleTags: tuple[str, ...] = ()
    recommendedHairstyleIds: tuple[str, ...] = ()


@dataclass(frozen=True)
class PairingRecommendation:
    hairstyleId: str
    hairstyleTitle: str
    sceneId: str
    sceneTitle: str
    totalScore: int
    reasons: tuple[str, ...]
    exampleCommand: str


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
        "hair_lock": "发型锁定",
        "shot": "场景系统",
        "scene_environment": "场景系统",
        "scene_lighting": "场景系统",
        "scene_mood": "场景系统",
        "expression": "人物表现系统",
        "subject_action": "人物表现系统",
        "outfit": "妆造系统",
        "quality_skin_texture": "质量控制",
        "quality_image_finish": "质量控制",
        "negative_identity_artifact": "负面约束",
        "negative_physical_logic": "负面约束",
    }


def _data_file(name: str):
    return files("faceprompt.data").joinpath(name)


@lru_cache(maxsize=None)
def _load_json(name: str) -> Any:
    return json.loads(_data_file(name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_reference_sources() -> dict[str, SourceReference]:
    return {
        item["id"]: SourceReference(**item)
        for item in _load_json("reference_sources.json")
    }


def _ensure_non_empty_list(raw: Any, field_name: str, record_id: str) -> list[str]:
    if not isinstance(raw, list) or not raw or any(not isinstance(item, str) or not item.strip() for item in raw):
        raise ValueError(f"{record_id}: field '{field_name}' must be a non-empty list of strings")
    return [item.strip() for item in raw]


def _ensure_optional_non_empty_list(raw: Any, field_name: str, record_id: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item.strip() for item in raw):
        raise ValueError(f"{record_id}: field '{field_name}' must be a list of non-empty strings")
    return [item.strip() for item in raw]


def _ensure_text(raw: Any, field_name: str, record_id: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{record_id}: field '{field_name}' must be a non-empty string")
    return raw.strip()


def _ensure_optional_text(raw: Any, field_name: str, record_id: str) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{record_id}: field '{field_name}' must be a non-empty string")
    return raw.strip()


def _ensure_optional_choice_list(
    raw: Any, field_name: str, record_id: str, valid_values: set[str]
) -> list[str]:
    items = _ensure_optional_non_empty_list(raw, field_name, record_id)
    invalid = [item for item in items if item not in valid_values]
    if invalid:
        raise ValueError(f"{record_id}: field '{field_name}' contains invalid values {invalid}")
    return items


def _ensure_optional_choice_text(
    raw: Any, field_name: str, record_id: str, valid_values: set[str]
) -> str:
    value = _ensure_optional_text(raw, field_name, record_id)
    if value and value not in valid_values:
        raise ValueError(f"{record_id}: field '{field_name}' has invalid value '{value}'")
    return value


def _ensure_mapping(raw: Any, field_name: str, record_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{record_id}: field '{field_name}' must be an object")
    return raw


def _join_segments(items: list[str] | tuple[str, ...], separator: str = "；") -> str:
    return separator.join(item for item in items if item)


def _normalize_sentence(text: str) -> str:
    return text.strip().rstrip("。；,.，")


def _dedupe_keep_order(items: list[str] | tuple[str, ...]) -> list[str]:
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


def _normalize_prompt_mode(mode: str) -> str:
    normalized = PROMPT_MODE_ALIASES.get(mode.strip().lower())
    if normalized is None:
        raise ValueError(f"Unsupported prompt mode: {mode}")
    return normalized


def _assemble_prompt(mode: str, blocks: list[PromptBlock | None]) -> PromptAssembly:
    normalized_mode = _normalize_prompt_mode(mode)
    assembly = PromptAssembly(
        mode=normalized_mode,
        blocks=tuple(block for block in blocks if block is not None),
    )
    _validate_prompt_assembly(assembly)
    return assembly


def _build_quality_blocks() -> list[PromptBlock | None]:
    return [
        _make_prompt_block(
            "quality_control",
            "质量控制："
            f"{QUALITY_SKIN_TEXTURE_PROMPT}"
            f"{QUALITY_IMAGE_FINISH_PROMPT}"
            "同时保持发丝清晰自然、边缘贴合头皮、光影过渡真实。",
        ),
    ]


def _build_negative_blocks() -> list[PromptBlock | None]:
    return [
        _make_prompt_block(
            "negative_constraints",
            f"负面约束：{NEGATIVE_IDENTITY_ARTIFACT_PROMPT}{NEGATIVE_PHYSICAL_LOGIC_PROMPT}",
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
        description="只改头发系统。",
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
        description="锁定头发系统，只改场景、妆造和人物表现。",
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
        description="完整换发型与换场景创作模式。",
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


def _label_list(items: list[str] | tuple[str, ...], labels: dict[str, str]) -> str:
    return "、".join(labels[item] for item in items if item in labels)


def _action_uses_hands(action: str) -> bool:
    cleaned = action.strip()
    if not cleaned:
        return False
    return cleaned.startswith("手") or any(keyword in cleaned for keyword in HAND_ACTION_KEYWORDS)


def _select_one(items: list[str] | tuple[str, ...], *, seed_source: str, label: str) -> str:
    choices = _dedupe_keep_order(items)
    if not choices:
        return ""
    if len(choices) == 1:
        return choices[0]
    digest = hashlib.sha256(f"{seed_source}:{label}".encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(choices)
    return choices[index]


def _filter_compatible_hairstyle_actions(
    subject_action: str, hairstyle_actions: list[str] | tuple[str, ...]
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


def _filter_scene_actions_for_locked_hairstyle(
    actions: list[str] | tuple[str, ...]
) -> list[str]:
    candidates = _dedupe_keep_order(actions)
    filtered = [action for action in candidates if not _is_locked_hair_conflicting_action(action)]
    return filtered


def _build_face_profile(
    *,
    face_shape: str | None = None,
    forehead: str | None = None,
    jawline: str | None = None,
    cheekbone: str | None = None,
) -> FaceProfile:
    if face_shape and face_shape not in VALID_FACE_SHAPES:
        raise ValueError(f"Unsupported face shape: {face_shape}")
    if forehead and forehead not in VALID_FOREHEAD_TYPES:
        raise ValueError(f"Unsupported forehead type: {forehead}")
    if jawline and jawline not in VALID_JAWLINES:
        raise ValueError(f"Unsupported jawline type: {jawline}")
    if cheekbone and cheekbone not in VALID_CHEEKBONES:
        raise ValueError(f"Unsupported cheekbone type: {cheekbone}")
    return FaceProfile(
        faceShape=face_shape,
        forehead=forehead,
        jawline=jawline,
        cheekbone=cheekbone,
    )


def _parse_hairstyle_control_profile(raw: Any, record_id: str) -> HairstyleControlProfile | None:
    if raw is None:
        return None

    profile = _ensure_mapping(raw, "controlProfile", record_id)
    face_shape_fit = _ensure_mapping(profile.get("faceShapeFit"), "controlProfile.faceShapeFit", record_id)
    best = _ensure_optional_choice_list(
        face_shape_fit.get("best"),
        "controlProfile.faceShapeFit.best",
        record_id,
        VALID_FACE_SHAPES,
    )
    ok = _ensure_optional_choice_list(
        face_shape_fit.get("ok"),
        "controlProfile.faceShapeFit.ok",
        record_id,
        VALID_FACE_SHAPES,
    )
    avoid = _ensure_optional_choice_list(
        face_shape_fit.get("avoid"),
        "controlProfile.faceShapeFit.avoid",
        record_id,
        VALID_FACE_SHAPES,
    )
    if not best and not ok and not avoid:
        raise ValueError(f"{record_id}: controlProfile.faceShapeFit must define at least one face-shape bucket")

    overlap = (set(best) & set(ok)) | (set(best) & set(avoid)) | (set(ok) & set(avoid))
    if overlap:
        raise ValueError(f"{record_id}: controlProfile.faceShapeFit contains overlapping values {sorted(overlap)}")

    return HairstyleControlProfile(
        faceShapeFitBest=tuple(best),
        faceShapeFitOk=tuple(ok),
        faceShapeFitAvoid=tuple(avoid),
        recommendedForeheads=tuple(
            _ensure_optional_choice_list(
                profile.get("recommendedForeheads"),
                "controlProfile.recommendedForeheads",
                record_id,
                VALID_FOREHEAD_TYPES,
            )
        ),
        recommendedJawlines=tuple(
            _ensure_optional_choice_list(
                profile.get("recommendedJawlines"),
                "controlProfile.recommendedJawlines",
                record_id,
                VALID_JAWLINES,
            )
        ),
        recommendedCheekbones=tuple(
            _ensure_optional_choice_list(
                profile.get("recommendedCheekbones"),
                "controlProfile.recommendedCheekbones",
                record_id,
                VALID_CHEEKBONES,
            )
        ),
        foreheadStrategy=_ensure_optional_text(profile.get("foreheadStrategy"), "controlProfile.foreheadStrategy", record_id),
        templeCoverage=_ensure_optional_text(profile.get("templeCoverage"), "controlProfile.templeCoverage", record_id),
        cheekSoftening=_ensure_optional_text(profile.get("cheekSoftening"), "controlProfile.cheekSoftening", record_id),
        jawlineExposure=_ensure_optional_text(profile.get("jawlineExposure"), "controlProfile.jawlineExposure", record_id),
        crownVolume=_ensure_optional_text(profile.get("crownVolume"), "controlProfile.crownVolume", record_id),
        sideVolume=_ensure_optional_text(profile.get("sideVolume"), "controlProfile.sideVolume", record_id),
        partingOptions=tuple(
            _ensure_optional_non_empty_list(profile.get("partingOptions"), "controlProfile.partingOptions", record_id)
        ),
        fringeType=_ensure_optional_text(profile.get("fringeType"), "controlProfile.fringeType", record_id),
        lengthZone=_ensure_optional_text(profile.get("lengthZone"), "controlProfile.lengthZone", record_id),
        curlScale=_ensure_optional_text(profile.get("curlScale"), "controlProfile.curlScale", record_id),
        compatibilityTags=tuple(
            _ensure_optional_non_empty_list(profile.get("compatibilityTags"), "controlProfile.compatibilityTags", record_id)
        ),
        recommendedSceneIds=tuple(
            _ensure_optional_non_empty_list(profile.get("recommendedSceneIds"), "controlProfile.recommendedSceneIds", record_id)
        ),
    )


def _parse_scene_control_profile(raw: Any, record_id: str) -> SceneControlProfile | None:
    if raw is None:
        return None

    profile = _ensure_mapping(raw, "controlProfile", record_id)
    wind_level = _ensure_optional_choice_text(
        profile.get("windLevel"),
        "controlProfile.windLevel",
        record_id,
        VALID_WIND_LEVELS,
    )
    humidity_look = _ensure_optional_choice_text(
        profile.get("humidityLook"),
        "controlProfile.humidityLook",
        record_id,
        VALID_HUMIDITY_LOOKS,
    )
    background_complexity = _ensure_optional_choice_text(
        profile.get("backgroundComplexity"),
        "controlProfile.backgroundComplexity",
        record_id,
        VALID_BACKGROUND_COMPLEXITIES,
    )
    lighting_hardness = _ensure_optional_choice_text(
        profile.get("lightingHardness"),
        "controlProfile.lightingHardness",
        record_id,
        VALID_LIGHTING_HARDNESSES,
    )
    mirror_risk = _ensure_optional_choice_text(
        profile.get("mirrorRisk"),
        "controlProfile.mirrorRisk",
        record_id,
        VALID_MIRROR_RISKS,
    )

    required_values = {
        "windLevel": wind_level,
        "humidityLook": humidity_look,
        "backgroundComplexity": background_complexity,
        "lightingHardness": lighting_hardness,
        "mirrorRisk": mirror_risk,
    }
    missing = [key for key, value in required_values.items() if not value]
    if missing:
        raise ValueError(f"{record_id}: controlProfile missing required fields {missing}")

    return SceneControlProfile(
        windLevel=wind_level,
        humidityLook=humidity_look,
        backgroundComplexity=background_complexity,
        lightingHardness=lighting_hardness,
        mirrorRisk=mirror_risk,
        compatibleHairstyleTags=tuple(
            _ensure_optional_non_empty_list(
                profile.get("compatibleHairstyleTags"),
                "controlProfile.compatibleHairstyleTags",
                record_id,
            )
        ),
        recommendedHairstyleIds=tuple(
            _ensure_optional_non_empty_list(
                profile.get("recommendedHairstyleIds"),
                "controlProfile.recommendedHairstyleIds",
                record_id,
            )
        ),
    )


def _build_constraint_text(
    scene_constraints: list[str] | tuple[str, ...],
    hairstyle_constraints: list[str] | tuple[str, ...],
) -> str:
    return _join_segments(
        _dedupe_keep_order(
            [
                *scene_constraints,
                *hairstyle_constraints,
                "后端每次只选 1 个主体动作，不再把多个动作选项同时写进同一条提示词",
                "单张图中只保留一种主体动作，不要把多个互斥手部动作同时放进同一画面",
                "如果主体动作已经占用手部，不要再叠加抓头发、拨头发、握杯等额外手部细节动作",
                "发型细节动作不要与主体动作叠加成不合理肢体效果",
            ]
        )
    )


def _score_hairstyle_for_face(
    hairstyle: CatalogRecord, face_profile: FaceProfile
) -> tuple[int, tuple[str, ...]]:
    control = hairstyle.hairstyleControl
    if control is None:
        return 0, ("该发型暂无结构化脸型策略，当前仅使用基础提示词控制",)

    score = 0
    reasons: list[str] = []

    if face_profile.faceShape:
        face_label = FACE_SHAPE_LABELS[face_profile.faceShape]
        if face_profile.faceShape in control.faceShapeFitBest:
            score += 42
            reasons.append(f"脸型匹配高：{face_label}属于该发型优先适配脸型")
        elif face_profile.faceShape in control.faceShapeFitOk:
            score += 24
            reasons.append(f"脸型可兼容：{face_label}可通过分线和体积控制稳定落地")
        elif face_profile.faceShape in control.faceShapeFitAvoid:
            score -= 24
            reasons.append(f"脸型需谨慎：{face_label}不属于该发型优先适配范围")
        else:
            reasons.append(f"脸型未进入试点档位：{face_label}需要依赖默认修饰策略")

    if face_profile.forehead and control.recommendedForeheads:
        forehead_label = FOREHEAD_LABELS[face_profile.forehead]
        if face_profile.forehead in control.recommendedForeheads:
            score += 12
            reasons.append(f"额头匹配：{forehead_label}与该发型额前策略一致")
        else:
            score -= 5
            reasons.append(f"额头需人工复核：{forehead_label}不在该发型优选范围")

    if face_profile.jawline and control.recommendedJawlines:
        jawline_label = JAWLINE_LABELS[face_profile.jawline]
        if face_profile.jawline in control.recommendedJawlines:
            score += 10
            reasons.append(f"下颌线匹配：{jawline_label}与当前露出策略兼容")
        else:
            score -= 4
            reasons.append(f"下颌线需谨慎：{jawline_label}不在该发型优选范围")

    if face_profile.cheekbone and control.recommendedCheekbones:
        cheekbone_label = CHEEKBONE_LABELS[face_profile.cheekbone]
        if face_profile.cheekbone in control.recommendedCheekbones:
            score += 10
            reasons.append(f"颧骨匹配：{cheekbone_label}与脸侧层次策略兼容")
        else:
            score -= 4
            reasons.append(f"颧骨需谨慎：{cheekbone_label}不在该发型优选范围")

    if not reasons:
        reasons.append("使用试点发型的默认脸型修饰策略")

    return score, tuple(reasons)


def _score_scene_for_pair(scene: CatalogRecord, hairstyle: CatalogRecord) -> tuple[int, tuple[str, ...]]:
    hairstyle_control = hairstyle.hairstyleControl
    scene_control = scene.sceneControl

    score = 0
    reasons: list[str] = []

    if hairstyle_control and scene.id in hairstyle_control.recommendedSceneIds:
        score += 26
        reasons.append(f"发型侧直接推荐该场景：{scene.title}")

    if scene_control and hairstyle.id in scene_control.recommendedHairstyleIds:
        score += 20
        reasons.append(f"场景侧直接推荐该发型：{hairstyle.title}")

    if hairstyle_control and scene_control:
        tag_overlap = [
            COMPATIBILITY_TAG_LABELS.get(tag, tag)
            for tag in scene_control.compatibleHairstyleTags
            if tag in hairstyle_control.compatibilityTags
        ]
        if tag_overlap:
            score += 6 * len(tag_overlap)
            reasons.append(f"兼容标签重合：{'、'.join(tag_overlap[:3])}")

        if scene_control.windLevel in {"medium", "high"}:
            if "soft_motion" in hairstyle_control.compatibilityTags:
                score += 4
                reasons.append("场景风感与发型动态兼容")
            elif "precise_outline" in hairstyle_control.compatibilityTags:
                score -= 4
                reasons.append("场景风感偏强，可能破坏精确切线")

        if scene_control.lightingHardness == "hard":
            if {
                "hard_light_ready",
                "sharp_texture",
                "precise_outline",
            } & set(hairstyle_control.compatibilityTags):
                score += 4
                reasons.append("硬光有利于读清发型边界和纹理")
            elif "soft_volume" in hairstyle_control.compatibilityTags:
                score -= 2
                reasons.append("硬光会压缩柔和蓬松层次，需要谨慎控光")

    if not reasons:
        reasons.append("当前搭配以基础场景和发型骨架直接拼装")

    return score, tuple(reasons)


def _pairing_priority_label(score: int) -> str:
    if score >= 40:
        return "高"
    if score >= 20:
        return "中"
    return "谨慎"


def _build_face_strategy_text(
    face_profile: FaceProfile,
    hairstyle_control: HairstyleControlProfile | None,
) -> str:
    if hairstyle_control is None and not any(
        [face_profile.faceShape, face_profile.forehead, face_profile.jawline, face_profile.cheekbone]
    ):
        return ""

    parts = [
        "保持参考人物原始骨相不变，不改变下颌宽度、颧骨位置、额头真实高度和五官比例",
        "仅通过刘海覆盖比例、分线位置、顶部体积、耳侧露出程度和脸侧层次做视觉修饰",
    ]

    profile_parts: list[str] = []
    if face_profile.faceShape:
        profile_parts.append(FACE_SHAPE_LABELS[face_profile.faceShape])
    if face_profile.forehead:
        profile_parts.append(FOREHEAD_LABELS[face_profile.forehead])
    if face_profile.jawline:
        profile_parts.append(JAWLINE_LABELS[face_profile.jawline])
    if face_profile.cheekbone:
        profile_parts.append(CHEEKBONE_LABELS[face_profile.cheekbone])
    if profile_parts:
        parts.append(f"参考人物特征：{'，'.join(profile_parts)}")

    if hairstyle_control:
        if face_profile.faceShape:
            if face_profile.faceShape in hairstyle_control.faceShapeFitBest:
                parts.append(f"适配判断：当前发型优先用于{FACE_SHAPE_LABELS[face_profile.faceShape]}")
            elif face_profile.faceShape in hairstyle_control.faceShapeFitOk:
                parts.append(f"适配判断：当前发型可兼容{FACE_SHAPE_LABELS[face_profile.faceShape]}")
            elif face_profile.faceShape in hairstyle_control.faceShapeFitAvoid:
                parts.append(
                    f"适配判断：当前发型不优先用于{FACE_SHAPE_LABELS[face_profile.faceShape]}，必须严格控制横向体积与露额比例"
                )

        if hairstyle_control.foreheadStrategy:
            parts.append(f"额头处理：{hairstyle_control.foreheadStrategy}")
        if hairstyle_control.templeCoverage:
            parts.append(f"太阳穴处理：{hairstyle_control.templeCoverage}")
        if hairstyle_control.cheekSoftening:
            parts.append(f"颧骨处理：{hairstyle_control.cheekSoftening}")
        if hairstyle_control.jawlineExposure:
            parts.append(f"下颌处理：{hairstyle_control.jawlineExposure}")
        if hairstyle_control.crownVolume:
            parts.append(f"顶部体积：{hairstyle_control.crownVolume}")
        if hairstyle_control.sideVolume:
            parts.append(f"侧区体积：{hairstyle_control.sideVolume}")
        if hairstyle_control.partingOptions:
            parts.append(f"建议分线：{_join_segments(hairstyle_control.partingOptions, '、')}")
        if hairstyle_control.fringeType:
            parts.append(f"刘海类型：{hairstyle_control.fringeType}")
        if hairstyle_control.lengthZone:
            parts.append(f"长度区间：{hairstyle_control.lengthZone}")
        if hairstyle_control.curlScale:
            parts.append(f"卷度级别：{hairstyle_control.curlScale}")

    return f"脸型修饰策略：{_join_segments(parts)}。"


def _build_scene_control_text(scene: CatalogRecord, hairstyle: CatalogRecord) -> str:
    scene_control = scene.sceneControl
    hairstyle_control = hairstyle.hairstyleControl
    if scene_control is None and hairstyle_control is None:
        return ""

    parts: list[str] = []
    if scene_control:
        parts.extend(
            [
                f"风力：{WIND_LEVEL_LABELS[scene_control.windLevel]}",
                f"湿发观感：{HUMIDITY_LOOK_LABELS[scene_control.humidityLook]}",
                f"背景复杂度：{BACKGROUND_COMPLEXITY_LABELS[scene_control.backgroundComplexity]}",
                f"布光硬度：{LIGHTING_HARDNESS_LABELS[scene_control.lightingHardness]}",
                f"镜面风险：{MIRROR_RISK_LABELS[scene_control.mirrorRisk]}",
            ]
        )

    pairing_score, pairing_reasons = _score_scene_for_pair(scene, hairstyle)
    parts.append(f"搭配优先级：{_pairing_priority_label(pairing_score)}")
    if pairing_reasons:
        parts.append(f"搭配依据：{_join_segments(pairing_reasons[:2])}")

    return f"场景控制：{_join_segments(parts)}。"


def _build_runtime_prompt_assembly(
    *,
    scene_prompt: str,
    scene_lighting: str,
    scene_mood: str,
    shot_advice: str,
    scene_constraints: list[str] | tuple[str, ...],
    scene_expressions: list[str] | tuple[str, ...],
    scene_actions: list[str] | tuple[str, ...],
    outfit_hints: list[str] | tuple[str, ...],
    hairstyle_prompt: str,
    hairstyle_constraints: list[str] | tuple[str, ...],
    hairstyle_actions: list[str] | tuple[str, ...],
    seed_source: str,
    scene_record: CatalogRecord | None = None,
    hairstyle_record: CatalogRecord | None = None,
    face_profile: FaceProfile | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    hairstyle_action_override: str | None = None,
    outfit_override: str | None = None,
) -> PromptAssembly:
    face_profile = face_profile or FaceProfile()
    selected_expression = expression_override or _select_one(
        scene_expressions or tuple(GENERIC_EXPRESSIONS),
        seed_source=seed_source,
        label="expression",
    )
    selected_subject_action = subject_action_override or _select_one(
        scene_actions or tuple(GENERIC_SCENE_ACTIONS),
        seed_source=seed_source,
        label="subject-action",
    )
    compatible_hairstyle_actions = _filter_compatible_hairstyle_actions(
        selected_subject_action,
        hairstyle_actions or tuple(GENERIC_HAIRSTYLE_ACTIONS),
    )
    selected_hairstyle_action = hairstyle_action_override or _select_one(
        compatible_hairstyle_actions,
        seed_source=seed_source,
        label="hairstyle-action",
    )
    outfit_text = outfit_override or "；".join(_dedupe_keep_order(outfit_hints)[:2])
    scene_constraint_text = _join_segments(
        [_normalize_sentence(item) for item in _dedupe_keep_order(scene_constraints)]
    )
    hair_constraint_text = _join_segments(
        [_normalize_sentence(item) for item in _dedupe_keep_order(hairstyle_constraints)]
    )
    motion_safety_text = _join_segments(
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
            _make_prompt_block("identity_lock", BASE_IDENTITY_PROMPT),
            _make_prompt_block("output_format", OUTPUT_FORMAT_PROMPT),
            _make_prompt_block(
                "face_strategy",
                _build_face_strategy_text(
                    face_profile,
                    hairstyle_record.hairstyleControl if hairstyle_record else None,
                ),
            ),
            _make_prompt_block("shot", f"构图：{_sanitize_scene_text_for_locked_hair(_normalize_sentence(shot_advice))}。"),
            _make_prompt_block("scene_environment", f"场景：{_sanitize_scene_text_for_locked_hair(_normalize_sentence(scene_prompt))}。"),
            _make_prompt_block(
                "scene_lighting",
                f"光线：{_sanitize_scene_text_for_locked_hair(_normalize_sentence(scene_lighting))}。" if scene_lighting.strip() else "",
            ),
            _make_prompt_block(
                "scene_mood",
                f"风格氛围：{_sanitize_scene_text_for_locked_hair(_normalize_sentence(scene_mood))}。" if scene_mood.strip() else "",
            ),
            _make_prompt_block(
                "scene_control",
                _build_scene_control_text(scene_record, hairstyle_record)
                if scene_record and hairstyle_record
                else "",
            ),
            _make_prompt_block(
                "expression",
                f"人物表情：本张图只选择 1 种主表情，固定为：{selected_expression or '自然看向镜头'}。",
            ),
            _make_prompt_block(
                "subject_action",
                f"人物动作：单张图中只选择 1 种主体动作，本张图固定为：{selected_subject_action or '自然站立或静止停顿'}。",
            ),
            _make_prompt_block(
                "hairstyle_action",
                (
                    "发型展示动作参考：如需突出发型，本张图最多只允许额外参考 1 种细节动作，"
                    f"固定为：{selected_hairstyle_action}。"
                    if selected_hairstyle_action
                    else "发型展示动作参考：本张图不额外叠加发型手部细节动作，以免与主体动作产生手部冲突。"
                ),
            ),
            _make_prompt_block(
                "outfit",
                f"服饰：{outfit_text or '白色宽松衬衫，内搭浅色背心或吊带'}。",
            ),
            _make_prompt_block("hair_target", f"人物发型：{_normalize_sentence(hairstyle_prompt)}。"),
            _make_prompt_block("scene_constraints", f"场景关键约束：{scene_constraint_text}。"),
            _make_prompt_block("hair_constraints", f"发型关键约束：{hair_constraint_text}。"),
            _make_prompt_block("motion_safety_constraints", f"动作安全约束：{motion_safety_text}。"),
            *_build_quality_blocks(),
            *_build_negative_blocks(),
        ],
    )


def _build_runtime_prompt(
    **kwargs: Any,
) -> str:
    return _build_runtime_prompt_assembly(**kwargs).render()


def _build_hairstyle_only_runtime_prompt_assembly(
    *,
    hairstyle_prompt: str,
    hairstyle_title: str,
    hairstyle_constraints: list[str] | tuple[str, ...],
) -> PromptAssembly:
    constraint_items = [
        _normalize_sentence(item)
        for item in _dedupe_keep_order(
            [
                HAIRSTYLE_ONLY_CONSTRAINTS_PROMPT,
                *hairstyle_constraints,
            ]
        )
    ]
    edit_scope_constraint_text = _normalize_sentence(HAIRSTYLE_ONLY_CONSTRAINTS_PROMPT)
    shape_constraint_text = _join_segments(
        [
            item
            for item in constraint_items
            if item != edit_scope_constraint_text
        ]
    )
    return _assemble_prompt(
        "hairstyle_only",
        [
            _make_prompt_block("identity_lock", HAIRSTYLE_ONLY_IDENTITY_PROMPT),
            _make_prompt_block("output_format", OUTPUT_FORMAT_PROMPT),
            _make_prompt_block("edit_scope", f"换发目标：只更换图中人物的发型为：{hairstyle_title}。"),
            _make_prompt_block("hair_target", f"人物发型：{_normalize_sentence(hairstyle_prompt)}。"),
            _make_prompt_block("hair_edit_scope_constraints", f"编辑范围约束：{edit_scope_constraint_text}。"),
            _make_prompt_block("hair_shape_constraints", f"发型落地约束：{shape_constraint_text}。"),
            *_build_quality_blocks(),
            *_build_negative_blocks(),
        ],
    )


def _build_hairstyle_only_runtime_prompt(
    **kwargs: Any,
) -> str:
    return _build_hairstyle_only_runtime_prompt_assembly(**kwargs).render()


def _build_scene_only_runtime_prompt_assembly(
    *,
    scene_prompt: str,
    scene_lighting: str,
    scene_mood: str,
    shot_advice: str,
    scene_constraints: list[str] | tuple[str, ...],
    scene_expressions: list[str] | tuple[str, ...],
    scene_actions: list[str] | tuple[str, ...],
    outfit_hints: list[str] | tuple[str, ...],
    seed_source: str,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    outfit_override: str | None = None,
) -> PromptAssembly:
    selected_expression = expression_override or _select_one(
        scene_expressions or tuple(GENERIC_EXPRESSIONS),
        seed_source=seed_source,
        label="scene-only-expression",
    )
    normalized_subject_action_override = _normalize_locked_hair_action_override(subject_action_override)
    available_actions = (
        _filter_scene_actions_for_locked_hairstyle(scene_actions)
        if not normalized_subject_action_override
        else _dedupe_keep_order(scene_actions)
    )
    selected_subject_action = normalized_subject_action_override or _select_one(
        available_actions or tuple(GENERIC_SCENE_ACTIONS),
        seed_source=seed_source,
        label="scene-only-subject-action",
    )
    outfit_text = outfit_override or "；".join(_dedupe_keep_order(outfit_hints)[:2])
    scene_constraint_text = _join_segments(
        [_sanitize_scene_text_for_locked_hair(_normalize_sentence(item)) for item in _dedupe_keep_order(scene_constraints)]
    )
    hair_preservation_text = _join_segments(
        [
            _normalize_sentence(item)
            for item in _dedupe_keep_order([SCENE_ONLY_CONSTRAINTS_PROMPT])
        ]
    )
    motion_safety_text = _join_segments(
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
            _make_prompt_block("identity_lock", SCENE_ONLY_IDENTITY_PROMPT),
            _make_prompt_block("output_format", OUTPUT_FORMAT_PROMPT),
            _make_prompt_block("shot", f"构图：{_normalize_sentence(shot_advice)}。"),
            _make_prompt_block("scene_environment", f"场景：{_normalize_sentence(scene_prompt)}。"),
            _make_prompt_block(
                "scene_lighting",
                f"光线：{_normalize_sentence(scene_lighting)}。" if scene_lighting.strip() else "",
            ),
            _make_prompt_block(
                "scene_mood",
                f"风格氛围：{_normalize_sentence(scene_mood)}。" if scene_mood.strip() else "",
            ),
            _make_prompt_block(
                "expression",
                f"人物表情：本张图只选择 1 种主表情，固定为：{selected_expression or '自然看向镜头'}。",
            ),
            _make_prompt_block(
                "subject_action",
                f"人物动作：单张图中只选择 1 种主体动作，本张图固定为：{selected_subject_action or '自然站立或静止停顿'}。",
            ),
            _make_prompt_block(
                "outfit",
                f"服饰：{outfit_text or '米白色针织、浅卡其衬衫或裸色背心'}。",
            ),
            _make_prompt_block(
                "hair_lock",
                "人物发型：保持参考图中已经生成完成的发型不变，不要二次改发，不改变发长、顶部体积、刘海、分线、鬓角、后颈发区、卷度、发色和整体轮廓。",
            ),
            _make_prompt_block("hair_preservation_constraints", f"发型保持约束：{hair_preservation_text}。"),
            _make_prompt_block("scene_constraints", f"场景关键约束：{scene_constraint_text}。"),
            _make_prompt_block("motion_safety_constraints", f"动作安全约束：{motion_safety_text}。"),
            *_build_quality_blocks(),
            *_build_negative_blocks(),
        ],
    )


def _build_scene_only_runtime_prompt(
    **kwargs: Any,
) -> str:
    return _build_scene_only_runtime_prompt_assembly(**kwargs).render()


def _resolve_sources(source_ids: list[str], record_id: str) -> tuple[SourceReference, ...]:
    references = load_reference_sources()
    resolved: list[SourceReference] = []
    for source_id in source_ids:
        if source_id not in references:
            resolved.append(
                SourceReference(
                    id=source_id,
                    title=f"内部参考：{source_id}",
                    url=f"internal://{source_id}",
                    kind="internal",
                    notes="自动保留的内部来源占位，避免场景草案来源在 catalog 校验阶段报错。",
                )
            )
            continue
        resolved.append(references[source_id])
    return tuple(resolved)


def _build_example_prompt(
    *,
    style_line: str,
    scene_prompt: str | None = None,
    scene_lighting: str | None = None,
    scene_mood: str | None = None,
    scene_shot: str | None = None,
    expressions: list[str] | None = None,
    actions: list[str] | None = None,
    outfit_hints: list[str] | None = None,
    hairstyle_prompt: str | None = None,
    hairstyle_actions: list[str] | None = None,
    scene_constraints: list[str] | None = None,
    hairstyle_constraints: list[str] | None = None,
    scene_record: CatalogRecord | None = None,
    hairstyle_record: CatalogRecord | None = None,
    face_profile: FaceProfile | None = None,
    seed_source: str = "example",
) -> str:
    expressions = expressions or GENERIC_EXPRESSIONS
    actions = actions or GENERIC_SCENE_ACTIONS
    outfit_hints = outfit_hints or ["白色宽松衬衫，内搭浅色背心"]
    scene_prompt = scene_prompt or GENERIC_SCENE_BY_STYLE[style_line]
    scene_lighting = scene_lighting or "光线层次清楚，亮部柔和，阴影干净。"
    scene_mood = scene_mood or "整体高级、克制、画面气质统一。"
    scene_shot = scene_shot or "3:4 竖构图，胸口以上近景。"
    hairstyle_prompt = hairstyle_prompt or GENERIC_HAIRSTYLE_BY_STYLE[style_line]
    scene_constraints = scene_constraints or []
    hairstyle_constraints = hairstyle_constraints or []

    parts = [
        BASE_IDENTITY_PROMPT,
        OUTPUT_FORMAT_PROMPT,
        f"构图：{_normalize_sentence(scene_shot)}。",
        f"场景：{_normalize_sentence(scene_prompt)}。",
        f"光线：{_normalize_sentence(scene_lighting)}。",
        f"风格氛围：{_normalize_sentence(scene_mood)}。",
        f"人物表情：本张图只选择 1 种主表情，固定为：{expressions[0]}。",
        f"人物动作：单张图中只选择 1 种主体动作，本张图固定为：{actions[0]}。",
        f"服饰：{_normalize_sentence(outfit_hints[0])}。",
        f"人物发型：{_normalize_sentence(hairstyle_prompt)}。",
    ]
    if scene_constraints:
        parts.append(f"场景关键约束：{_join_segments(scene_constraints)}。")
    if hairstyle_constraints:
        parts.append(f"发型关键约束：{_join_segments(hairstyle_constraints)}。")
    parts.extend(
        [
            QUALITY_PROMPT,
            f"负面约束：{BASE_NEGATIVE_PROMPT}",
        ]
    )
    return "\n".join(part for part in parts if part)


def _scene_to_record(raw: dict[str, Any]) -> CatalogRecord:
    record_id = _ensure_text(raw.get("id"), "id", "scene")
    style_line = _ensure_text(raw.get("styleLine"), "styleLine", record_id)
    if style_line not in VALID_STYLE_LINES:
        raise ValueError(f"{record_id}: invalid style line '{style_line}'")

    expressions = _ensure_non_empty_list(raw.get("expressions"), "expressions", record_id)
    actions = _ensure_non_empty_list(raw.get("actions"), "actions", record_id)
    outfit_hints = _ensure_non_empty_list(raw.get("outfitHints"), "outfitHints", record_id)
    constraints = _ensure_non_empty_list(raw.get("constraints"), "constraints", record_id)
    detail_tags = _ensure_non_empty_list(raw.get("detailTags"), "detailTags", record_id)
    pairing_advice = _ensure_non_empty_list(raw.get("pairingAdvice"), "pairingAdvice", record_id)
    source_ids = _ensure_non_empty_list(raw.get("referenceSourceIds"), "referenceSourceIds", record_id)

    environment = _ensure_text(raw.get("environment"), "environment", record_id)
    lighting = _ensure_text(raw.get("lighting"), "lighting", record_id)
    style_mood = _ensure_text(raw.get("styleMood"), "styleMood", record_id)
    shot_advice = _ensure_text(raw.get("shotAdvice"), "shotAdvice", record_id)
    scene_control = _parse_scene_control_profile(raw.get("controlProfile"), record_id)

    prompt_core = f"{environment} 光线：{lighting} 风格：{style_mood}"
    example_final_prompt = _build_example_prompt(
        style_line=style_line,
        scene_prompt=environment,
        scene_lighting=lighting,
        scene_mood=style_mood,
        scene_shot=shot_advice,
        expressions=expressions,
        actions=actions,
        outfit_hints=outfit_hints,
        scene_constraints=constraints,
        seed_source=record_id,
    )

    return CatalogRecord(
        id=record_id,
        title=_ensure_text(raw.get("title"), "title", record_id),
        categoryType="scene",
        gender="unisex",
        styleLine=style_line,
        summary=_ensure_text(raw.get("summary"), "summary", record_id),
        promptCore=prompt_core,
        detailTags=tuple(detail_tags),
        constraints=tuple(constraints),
        negativePrompt=BASE_NEGATIVE_PROMPT,
        pairingAdvice=tuple(pairing_advice),
        shotAdvice=shot_advice,
        expressionAction=tuple([*expressions, *actions]),
        referenceNotes=_ensure_text(raw.get("referenceNotes"), "referenceNotes", record_id),
        referenceSources=_resolve_sources(source_ids, record_id),
        exampleFinalPrompt=example_final_prompt,
        environment=environment,
        lighting=lighting,
        styleMood=style_mood,
        expressions=tuple(expressions),
        actions=tuple(actions),
        outfitHints=tuple(outfit_hints),
        sceneControl=scene_control,
        presetBlocks=raw.get("presetBlocks") or {},
    )


def _hairstyle_to_record(raw: dict[str, Any]) -> CatalogRecord:
    record_id = _ensure_text(raw.get("id"), "id", "hairstyle")
    style_line = _ensure_text(raw.get("styleLine"), "styleLine", record_id)
    if style_line not in VALID_STYLE_LINES:
        raise ValueError(f"{record_id}: invalid style line '{style_line}'")

    gender = _ensure_text(raw.get("gender"), "gender", record_id)
    if gender not in {"male", "female"}:
        raise ValueError(f"{record_id}: hairstyle gender must be male or female")

    constraints = _ensure_non_empty_list(raw.get("constraints"), "constraints", record_id)
    detail_tags = _ensure_non_empty_list(raw.get("detailTags"), "detailTags", record_id)
    pairing_advice = _ensure_non_empty_list(raw.get("pairingAdvice"), "pairingAdvice", record_id)
    expression_action = _ensure_non_empty_list(raw.get("expressionAction"), "expressionAction", record_id)
    source_ids = _ensure_non_empty_list(raw.get("referenceSourceIds"), "referenceSourceIds", record_id)
    hairstyle_control = _parse_hairstyle_control_profile(raw.get("controlProfile"), record_id)

    prompt_core = _ensure_text(raw.get("promptCore"), "promptCore", record_id)
    example_final_prompt = _build_example_prompt(
        style_line=style_line,
        hairstyle_prompt=prompt_core,
        expressions=expression_action,
        hairstyle_actions=expression_action,
        hairstyle_constraints=constraints,
        seed_source=record_id,
    )

    return CatalogRecord(
        id=record_id,
        title=_ensure_text(raw.get("title"), "title", record_id),
        categoryType="hairstyle",
        gender=gender,
        styleLine=style_line,
        summary=_ensure_text(raw.get("summary"), "summary", record_id),
        promptCore=prompt_core,
        detailTags=tuple(detail_tags),
        constraints=tuple(constraints),
        negativePrompt=BASE_NEGATIVE_PROMPT,
        pairingAdvice=tuple(pairing_advice),
        shotAdvice=_ensure_text(raw.get("shotAdvice"), "shotAdvice", record_id),
        expressionAction=tuple(expression_action),
        referenceNotes=_ensure_text(raw.get("referenceNotes"), "referenceNotes", record_id),
        referenceSources=_resolve_sources(source_ids, record_id),
        exampleFinalPrompt=example_final_prompt,
        hairstyleControl=hairstyle_control,
        presetBlocks=raw.get("presetBlocks") or {},
    )


@lru_cache(maxsize=1)
def _catalog() -> dict[str, CatalogRecord]:
    catalog: dict[str, CatalogRecord] = {}
    for raw_scene in _load_json("scenes.json"):
        record = _scene_to_record(raw_scene)
        catalog[record.id] = record
    for data_file in ("hairstyles_male.json", "hairstyles_female.json"):
        for raw_hairstyle in _load_json(data_file):
            record = _hairstyle_to_record(raw_hairstyle)
            catalog[record.id] = record
    return catalog


def list_records(
    *,
    category: str | None = None,
    gender: str | None = None,
    style_line: str | None = None,
) -> list[CatalogRecord]:
    if category and category not in VALID_CATEGORIES:
        raise ValueError(f"Unsupported category: {category}")
    if gender and gender not in VALID_GENDERS:
        raise ValueError(f"Unsupported gender: {gender}")
    if style_line and style_line not in VALID_STYLE_LINES:
        raise ValueError(f"Unsupported style line: {style_line}")

    records = list(_catalog().values())
    if category:
        records = [record for record in records if record.categoryType == category]
    if gender:
        records = [record for record in records if record.gender == gender]
    if style_line:
        records = [record for record in records if record.styleLine == style_line]
    return records


def get_record(record_id: str) -> CatalogRecord:
    try:
        return _catalog()[record_id]
    except KeyError as exc:
        raise KeyError(f"Unknown catalog record: {record_id}") from exc


def catalog_summary() -> dict[str, int]:
    records = list(_catalog().values())
    hairstyles = [record for record in records if record.categoryType == "hairstyle"]
    scenes = [record for record in records if record.categoryType == "scene"]
    return {
        "total_records": len(records),
        "scene_count": len(scenes),
        "hairstyle_count": len(hairstyles),
        "male_hairstyles": len([record for record in hairstyles if record.gender == "male"]),
        "female_hairstyles": len([record for record in hairstyles if record.gender == "female"]),
        "realistic_records": len(
            [record for record in records if record.styleLine == "realistic_editorial"]
        ),
        "fashion_records": len(
            [record for record in records if record.styleLine == "fashion_editorial"]
        ),
        "structured_hairstyle_controls": len(
            [record for record in hairstyles if record.hairstyleControl is not None]
        ),
        "structured_scene_controls": len(
            [record for record in scenes if record.sceneControl is not None]
        ),
    }


@lru_cache(maxsize=1)
def _load_stylings() -> list[dict[str, Any]]:
    return _load_json("stylings.json")


@lru_cache(maxsize=1)
def _load_hair_color_maps() -> dict[str, dict[str, str]]:
    tone_labels = {
        str(item["id"]).strip(): str(item["label"]).strip()
        for item in _load_json("hair_colors.json")
    }
    technique_labels = {
        str(item["id"]).strip(): str(item["label"]).strip()
        for item in _load_json("hair_color_techniques.json")
    }
    return {
        "tones": tone_labels,
        "techniques": technique_labels,
    }


def _preset_block_from_record(record: CatalogRecord, key: str) -> dict[str, Any]:
    raw = (record.presetBlocks or {}).get(key)
    return raw if isinstance(raw, dict) else {}


def _safe_text(raw: Any) -> str:
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


def _format_prompt_items(items: list[str] | tuple[str, ...]) -> str:
    return "；".join(_normalize_sentence(item) for item in _dedupe_keep_order(items) if item)


def _pick_default_styling(style_line: str, preferred_gender: str | None) -> dict[str, Any] | None:
    stylings = [item for item in _load_stylings() if item.get("styleLine") == style_line]
    if preferred_gender:
        for scope in (preferred_gender, "unisex"):
            for styling in stylings:
                gender_scope = str(styling.get("genderScope") or styling.get("gender") or "").strip()
                if gender_scope == scope:
                    return styling
    return stylings[0] if stylings else None


def _build_output_spec_text() -> str:
    return (
        "输出规格：只输出 1 张完整成片，不要拼图，不要多宫格，"
        "不要在同一画面里同时展示多个动作版本或多个发型版本。"
    )


def _build_edit_scope_text(mode: str) -> str:
    if mode == "hair_only":
        return (
            "编辑范围：本次仅允许修改头发系统，只调整主发型结构、刘海系统和发色系统；"
            "背景、服饰、表情、动作、构图和光线保持不变。"
        )
    if mode == "scene_only":
        return (
            "编辑范围：本次仅允许修改场景、妆造和人物表现；"
            "人物身份与当前头发系统必须保持不变。"
        )
    return (
        "编辑范围：在锁定同一人物身份的前提下，可统一调整发型、刘海、发色、场景、妆造与人物表现。"
    )


def _build_hair_shape_block(record: CatalogRecord) -> str:
    block = _preset_block_from_record(record, "hair_shape")
    if not block:
        return f"主发型结构：{_normalize_sentence(record.promptCore)}。"
    segments = [f"发型改为{record.title}"]
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
        value = _safe_text(block.get(field))
        if value:
            segments.append(f"{label}为{value}")
    return f"主发型结构：{'；'.join(segments)}。"


def _build_bangs_block(record: CatalogRecord) -> str:
    block = _preset_block_from_record(record, "bangs")
    if not block:
        return "刘海系统：刘海与脸侧修饰需要和目标发型统一，自然贴合脸型。"
    segments: list[str] = []
    mapping = (
        ("bangs_type", "刘海类型"),
        ("bangs_density", "刘海厚薄"),
        ("bangs_length", "刘海长度"),
        ("bangs_split", "刘海开合"),
        ("bangs_face_framing", "脸侧修饰"),
    )
    for field, label in mapping:
        value = _safe_text(block.get(field))
        if value and value != "不适用":
            segments.append(f"{label}为{value}")
    if not segments:
        segments.append("保持无刘海或极轻刘海处理，不额外制造厚重遮挡")
    return f"刘海系统：{'；'.join(segments)}。"


def _build_hair_color_block(record: CatalogRecord) -> str:
    block = _preset_block_from_record(record, "recommended_hair_color")
    labels = _load_hair_color_maps()
    tone = labels["tones"].get(str(block.get("hair_color_tone") or "").strip(), _safe_text(block.get("hair_color_tone")))
    technique = labels["techniques"].get(
        str(block.get("hair_color_technique") or "").strip(),
        _safe_text(block.get("hair_color_technique")),
    )
    segments: list[str] = []
    if tone:
        segments.append(f"发色调整为{tone}")
    for field, label in (
        ("hair_color_depth", "明度层级"),
        ("hair_color_temperature", "冷暖倾向"),
        ("hair_color_distribution", "色彩分布"),
    ):
        value = _safe_text(block.get(field))
        if value:
            segments.append(f"{label}为{value}")
    if technique:
        segments.append(f"染发方式采用{technique}")
    return f"发色系统：{'；'.join(segment for segment in segments if segment)}。"


def _build_scene_block(record: CatalogRecord) -> str:
    block = _preset_block_from_record(record, "scene")
    shot = _sanitize_scene_text_for_locked_hair(_safe_text(block.get("shot") or record.shotAdvice))
    environment = _sanitize_scene_text_for_locked_hair(
        _safe_text(block.get("scene_environment") or record.environment)
    )
    lighting = _sanitize_scene_text_for_locked_hair(_safe_text(block.get("scene_lighting") or record.lighting))
    mood = _sanitize_scene_text_for_locked_hair(_safe_text(block.get("scene_mood") or record.styleMood))
    constraints = _format_prompt_items(
        tuple(
            _sanitize_scene_text_for_locked_hair(str(item))
            for item in (block.get("scene_constraints") or record.constraints)
        )
    )
    segments = []
    if shot:
        segments.append(f"构图：{shot}")
    if environment:
        segments.append(f"环境：{environment}")
    if lighting:
        segments.append(f"光线：{lighting}")
    if mood:
        segments.append(f"氛围：{mood}")
    if constraints:
        segments.append(f"关键约束：{constraints}")
    return f"场景系统：{'。'.join(segments)}。"


def _build_styling_block(style_line: str, preferred_gender: str | None) -> str:
    styling = _pick_default_styling(style_line, preferred_gender)
    if not styling:
        return "妆造系统：妆容与服饰需服从当前场景氛围，保持自然、协调、不过度。"
    block = styling.get("presetBlocks", {}).get("styling", {})
    makeup = _safe_text(block.get("makeup") or styling.get("makeupPrompt"))
    outfit = _safe_text(block.get("outfit") or styling.get("outfitPrompt"))
    accessories = _format_prompt_items(tuple(block.get("accessories") or ()))
    constraints = _format_prompt_items(tuple(block.get("styling_constraints") or styling.get("constraints") or ()))
    segments = []
    if makeup:
        segments.append(f"妆容：{makeup}")
    if outfit:
        segments.append(f"服饰：{outfit}")
    if accessories:
        segments.append(f"配饰：{accessories}")
    if constraints:
        segments.append(f"妆造约束：{constraints}")
    return f"妆造系统：{'。'.join(segments)}。"


def _build_subject_performance_block(
    scene: CatalogRecord,
    *,
    seed_source: str,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    allow_hair_touching_actions: bool = False,
) -> str:
    block = _preset_block_from_record(scene, "subject_performance")
    expressions = tuple(block.get("expression_options") or scene.expressions or GENERIC_EXPRESSIONS)
    actions = tuple(block.get("subject_action_options") or scene.actions or GENERIC_SCENE_ACTIONS)
    normalized_subject_action_override = (
        subject_action_override
        if allow_hair_touching_actions
        else _normalize_locked_hair_action_override(subject_action_override)
    )
    if not allow_hair_touching_actions and not normalized_subject_action_override:
        actions = tuple(_filter_scene_actions_for_locked_hairstyle(actions))
    expression = expression_override or _select_one(expressions, seed_source=seed_source, label="expression")
    action = normalized_subject_action_override or _select_one(actions, seed_source=seed_source, label="subject-action")
    gesture_constraints = _format_prompt_items(
        tuple(
            block.get("gesture_constraints")
            or (
                "主体动作优先，不要叠加互斥手部动作",
                "手部必须符合真实解剖结构，十指分明",
            )
        )
    )
    return (
        "人物表现系统："
        f"人物表情固定为{expression or '自然看向镜头'}。"
        f"人物动作固定为{action or '自然站立或静止停顿'}。"
        f"手势约束：{gesture_constraints}。"
    )


def _build_hair_shape_lock_block(hairstyle: CatalogRecord | None) -> str:
    if hairstyle is None:
        return "发型锁定：保持参考图中静态打理完成的当前主发型结构不变，不要改变发长、轮廓、卷度、体积、分线和鬓角后颈区。"
    block = _preset_block_from_record(hairstyle, "hair_shape")
    segments = ["保持参考图中静态打理完成的当前主发型结构不变"]
    for field, label in (
        ("hair_length", "发长"),
        ("hair_silhouette", "轮廓"),
        ("hair_texture", "纹理"),
        ("hair_volume", "体积"),
        ("hair_parting", "分线"),
        ("sideburn_nape", "鬓角与后颈区"),
    ):
        value = _safe_text(block.get(field))
        if value:
            segments.append(f"{label}保持为{value}")
    return f"发型锁定：{'；'.join(segments)}。"


def _build_bangs_lock_block(hairstyle: CatalogRecord | None) -> str:
    if hairstyle is None:
        return "刘海锁定：保持参考图中静态完成的当前刘海状态不变；如果当前为无刘海，额前不要新增刘海或大片落额发。"
    block = _preset_block_from_record(hairstyle, "bangs")
    values = {
        "bangs_type": _safe_text(block.get("bangs_type")),
        "bangs_density": _safe_text(block.get("bangs_density")),
        "bangs_length": _safe_text(block.get("bangs_length")),
        "bangs_split": _safe_text(block.get("bangs_split")),
        "bangs_face_framing": _safe_text(block.get("bangs_face_framing")),
    }
    is_no_bangs = not any(value and value != "不适用" for value in values.values())
    if is_no_bangs:
        return "刘海锁定：保持参考图中静态完成的当前无刘海状态不变；额前不要生成新的刘海或大片落额发。"
    segments = ["保持参考图中静态完成的当前刘海系统不变"]
    for field, label in (
        ("bangs_type", "刘海类型"),
        ("bangs_density", "厚薄"),
        ("bangs_length", "长度"),
        ("bangs_split", "开合方式"),
        ("bangs_face_framing", "脸侧修饰"),
    ):
        value = _safe_text(block.get(field))
        if value and value != "不适用":
            segments.append(f"{label}保持为{value}")
    segments.append("不要新增第二套刘海分区或额前大面积垂落")
    return f"刘海锁定：{'；'.join(segments)}。"


def _build_hair_color_lock_block(hairstyle: CatalogRecord | None) -> str:
    if hairstyle is None:
        return (
            "发色锁定：保持参考图中静态完成的当前发色、明度层级与染发层次不变，"
            "不要二次改色，不要改变冷暖倾向、亮度层级、挑染位置和过渡关系。"
        )
    labels = _load_hair_color_maps()
    block = _preset_block_from_record(hairstyle, "recommended_hair_color")
    tone_id = str(block.get("hair_color_tone") or "").strip()
    tone_label = labels["tones"].get(tone_id, tone_id)
    return (
        "发色锁定：保持参考图中静态完成的"
        f"{tone_label or '当前'}发色和现有染发层次不变，"
        "不要二次改色，不要改变冷暖倾向、亮度层级、挑染位置和过渡关系。"
    )


def _build_hair_motion_constraint_block(hairstyle: CatalogRecord | None) -> str:
    segments = [
        "如当前场景存在风力或空气流动，只允许少量边缘碎发与极少数表层发丝轻微摆动，用于体现环境气流",
        "禁止风力、动作或镜头变化改变主发型结构",
        "禁止把当前发型吹散、吹塌或改写成另一种结构性新发型",
    ]
    bangs_block = _preset_block_from_record(hairstyle, "bangs") if hairstyle is not None else {}
    bangs_type = _safe_text(bangs_block.get("bangs_type"))
    has_structured_bangs = bool(bangs_type and bangs_type != "不适用")
    if has_structured_bangs:
        segments.append("刘海只允许极轻微非结构性位移，不得改变厚薄、长度、开合方式和脸侧修饰")
    else:
        segments.append("保持当前无刘海状态，额前不生成新的刘海或大片落额发")
    return f"风感约束：{'；'.join(segments)}。"


def render_prompt(
    scene_id: str,
    hairstyle_id: str,
    *,
    outfit_override: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    hairstyle_action_override: str | None = None,
    face_shape: str | None = None,
    forehead: str | None = None,
    jawline: str | None = None,
    cheekbone: str | None = None,
    seed_source: str | None = None,
) -> str:
    return build_prompt_assembly(
        mode="full_stylize",
        scene_id=scene_id,
        hairstyle_id=hairstyle_id,
        outfit_override=outfit_override,
        expression_override=expression_override,
        subject_action_override=subject_action_override,
        hairstyle_action_override=hairstyle_action_override,
        face_shape=face_shape,
        forehead=forehead,
        jawline=jawline,
        cheekbone=cheekbone,
        seed_source=seed_source,
    ).render()


def build_prompt_assembly(
    *,
    mode: str,
    scene_id: str | None = None,
    hairstyle_id: str | None = None,
    outfit_override: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    hairstyle_action_override: str | None = None,
    face_shape: str | None = None,
    forehead: str | None = None,
    jawline: str | None = None,
    cheekbone: str | None = None,
    seed_source: str | None = None,
) -> PromptAssembly:
    normalized_mode = _normalize_prompt_mode(mode)

    if normalized_mode == "hair_only":
        if not hairstyle_id:
            raise ValueError("hairstyle_id is required for hairstyle_only mode")
        hairstyle = get_record(hairstyle_id)
        if hairstyle.categoryType != "hairstyle":
            raise ValueError(f"{hairstyle_id} is not a hairstyle record")
        return _assemble_prompt(
            normalized_mode,
            [
                _make_prompt_block("identity_lock", HAIRSTYLE_ONLY_IDENTITY_PROMPT),
                _make_prompt_block("output_spec", _build_output_spec_text()),
                _make_prompt_block("edit_scope", _build_edit_scope_text(normalized_mode)),
                _make_prompt_block("hair_shape", _build_hair_shape_block(hairstyle)),
                _make_prompt_block("bangs", _build_bangs_block(hairstyle)),
                _make_prompt_block("hair_color", _build_hair_color_block(hairstyle)),
                *_build_quality_blocks(),
                *_build_negative_blocks(),
            ],
        )

    if normalized_mode == "scene_only":
        if not scene_id:
            raise ValueError("scene_id is required for scene_only mode")
        scene = get_record(scene_id)
        if scene.categoryType != "scene":
            raise ValueError(f"{scene_id} is not a scene record")
        return _assemble_prompt(
            normalized_mode,
            [
                _make_prompt_block("identity_lock", SCENE_ONLY_IDENTITY_PROMPT),
                _make_prompt_block("output_spec", _build_output_spec_text()),
                _make_prompt_block("edit_scope", _build_edit_scope_text(normalized_mode)),
                _make_prompt_block("hair_shape_lock", _build_hair_shape_lock_block(None)),
                _make_prompt_block("bangs_lock", _build_bangs_lock_block(None)),
                _make_prompt_block("hair_color_lock", _build_hair_color_lock_block(None)),
                _make_prompt_block("hair_motion_constraint", _build_hair_motion_constraint_block(None)),
                _make_prompt_block("scene", _build_scene_block(scene)),
                _make_prompt_block("styling", _build_styling_block(scene.styleLine, None)),
                _make_prompt_block(
                    "subject_performance",
                    _build_subject_performance_block(
                        scene,
                        seed_source=seed_source or f"scene-only:{scene_id}",
                        expression_override=expression_override,
                        subject_action_override=subject_action_override,
                    ),
                ),
                *_build_quality_blocks(),
                *_build_negative_blocks(),
            ],
        )

    if not scene_id or not hairstyle_id:
        raise ValueError("scene_id and hairstyle_id are required for full_stylize mode")

    scene = get_record(scene_id)
    hairstyle = get_record(hairstyle_id)
    if scene.categoryType != "scene":
        raise ValueError(f"{scene_id} is not a scene record")
    if hairstyle.categoryType != "hairstyle":
        raise ValueError(f"{hairstyle_id} is not a hairstyle record")

    return _assemble_prompt(
        normalized_mode,
        [
            _make_prompt_block("identity_lock", BASE_IDENTITY_PROMPT),
            _make_prompt_block("output_spec", _build_output_spec_text()),
            _make_prompt_block("edit_scope", _build_edit_scope_text(normalized_mode)),
            _make_prompt_block("hair_shape", _build_hair_shape_block(hairstyle)),
            _make_prompt_block("bangs", _build_bangs_block(hairstyle)),
            _make_prompt_block("hair_color", _build_hair_color_block(hairstyle)),
            _make_prompt_block("scene", _build_scene_block(scene)),
            _make_prompt_block("styling", _build_styling_block(scene.styleLine, hairstyle.gender)),
            _make_prompt_block(
                "subject_performance",
                _build_subject_performance_block(
                    scene,
                    seed_source=seed_source or f"{scene_id}:{hairstyle_id}",
                    expression_override=expression_override,
                    subject_action_override=subject_action_override,
                    allow_hair_touching_actions=True,
                ),
            ),
            *_build_quality_blocks(),
            *_build_negative_blocks(),
        ],
    )


def render_hairstyle_only_prompt(hairstyle_id: str) -> str:
    return build_prompt_assembly(
        mode="hairstyle_only",
        hairstyle_id=hairstyle_id,
    ).render()


def render_scene_only_prompt(
    scene_id: str,
    *,
    outfit_override: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    seed_source: str | None = None,
) -> str:
    return build_prompt_assembly(
        mode="scene_only",
        scene_id=scene_id,
        outfit_override=outfit_override,
        expression_override=expression_override,
        subject_action_override=subject_action_override,
        seed_source=seed_source,
    ).render()


def recommend_pairings(
    *,
    gender: str,
    face_shape: str,
    forehead: str | None = None,
    jawline: str | None = None,
    cheekbone: str | None = None,
    style_line: str | None = None,
    limit: int = 5,
) -> list[PairingRecommendation]:
    if gender not in {"male", "female"}:
        raise ValueError(f"Unsupported hairstyle gender: {gender}")
    if style_line and style_line not in VALID_STYLE_LINES:
        raise ValueError(f"Unsupported style line: {style_line}")
    if limit < 1:
        raise ValueError("limit must be greater than 0")

    face_profile = _build_face_profile(
        face_shape=face_shape,
        forehead=forehead,
        jawline=jawline,
        cheekbone=cheekbone,
    )

    hairstyles = list_records(category="hairstyle", gender=gender, style_line=style_line)
    structured_hairstyles = [record for record in hairstyles if record.hairstyleControl is not None]
    if structured_hairstyles:
        hairstyles = structured_hairstyles

    scenes = list_records(category="scene", style_line=style_line)
    if not hairstyles or not scenes:
        return []

    recommendations: list[PairingRecommendation] = []
    for hairstyle in hairstyles:
        hairstyle_score, hairstyle_reasons = _score_hairstyle_for_face(hairstyle, face_profile)
        candidate_scenes = [scene for scene in scenes if scene.styleLine == hairstyle.styleLine]
        for scene in candidate_scenes:
            scene_score, scene_reasons = _score_scene_for_pair(scene, hairstyle)
            command_parts = [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "faceprompt.cli",
                "render",
                "--scene",
                scene.id,
                "--hairstyle",
                hairstyle.id,
                "--face-shape",
                face_shape,
            ]
            if forehead:
                command_parts.extend(["--forehead", forehead])
            if jawline:
                command_parts.extend(["--jawline", jawline])
            if cheekbone:
                command_parts.extend(["--cheekbone", cheekbone])

            recommendations.append(
                PairingRecommendation(
                    hairstyleId=hairstyle.id,
                    hairstyleTitle=hairstyle.title,
                    sceneId=scene.id,
                    sceneTitle=scene.title,
                    totalScore=hairstyle_score + scene_score,
                    reasons=tuple([*hairstyle_reasons, *scene_reasons]),
                    exampleCommand=" ".join(command_parts),
                )
            )

    recommendations.sort(
        key=lambda item: (
            -item.totalScore,
            item.hairstyleTitle,
            item.sceneTitle,
        )
    )
    return recommendations[:limit]


def validate_catalog() -> list[str]:
    errors: list[str] = []

    try:
        records = list(_catalog().values())
    except ValueError as exc:
        return [str(exc)]

    seen_ids: set[str] = set()
    for record in records:
        if record.id in seen_ids:
            errors.append(f"Duplicate record id: {record.id}")
        seen_ids.add(record.id)
        if not record.exampleFinalPrompt.startswith("请基于上传参考图中的同一人物生成 1 张高相似度"):
            errors.append(f"{record.id}: exampleFinalPrompt must start with runtime prompt prefix")
        if not record.referenceSources:
            errors.append(f"{record.id}: missing reference sources")
        if record.hairstyleControl:
            for scene_id in record.hairstyleControl.recommendedSceneIds:
                try:
                    linked_record = get_record(scene_id)
                except KeyError:
                    errors.append(f"{record.id}: unknown recommended scene '{scene_id}'")
                    continue
                if linked_record.categoryType != "scene":
                    errors.append(f"{record.id}: recommended scene id '{scene_id}' is not a scene record")
        if record.sceneControl:
            for hairstyle_id in record.sceneControl.recommendedHairstyleIds:
                try:
                    linked_record = get_record(hairstyle_id)
                except KeyError:
                    errors.append(f"{record.id}: unknown recommended hairstyle '{hairstyle_id}'")
                    continue
                if linked_record.categoryType != "hairstyle":
                    errors.append(f"{record.id}: recommended hairstyle id '{hairstyle_id}' is not a hairstyle record")

    summary = catalog_summary()
    if summary["scene_count"] != 22:
        errors.append(f"Expected 22 scenes, found {summary['scene_count']}")
    if summary["hairstyle_count"] != 56:
        errors.append(f"Expected 56 hairstyles, found {summary['hairstyle_count']}")
    if summary["male_hairstyles"] != 23:
        errors.append(f"Expected 23 male hairstyles, found {summary['male_hairstyles']}")
    if summary["female_hairstyles"] != 33:
        errors.append(f"Expected 33 female hairstyles, found {summary['female_hairstyles']}")
    if summary["structured_hairstyle_controls"] < 5:
        errors.append(
            "Expected at least 5 structured hairstyle control profiles for the pilot"
        )
    if summary["structured_scene_controls"] < 6:
        errors.append(
            "Expected at least 6 structured scene control profiles for the pilot"
        )

    return errors
