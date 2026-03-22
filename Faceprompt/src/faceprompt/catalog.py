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

OUTPUT_FORMAT_PROMPT = (
    "只输出 1 张完整成片，不要拼图，不要多宫格，不要在同一画面里同时展示多个动作版本或多个发型版本。"
)

QUALITY_PROMPT = (
    "皮肤质感真实自然，不过度磨皮，不过度妆感，保留真实面部纹理与发丝细节，"
    "脸部清晰对焦，光影过渡自然，整体高级、自然、和谐。"
)

BASE_NEGATIVE_PROMPT = (
    "不要换脸、不要改变性别表达、不要生成第二个人、不要多人同框、不要双脸、不要身份漂移、"
    "不要整容感、AI 脸、过度磨皮、塑料皮肤、五官漂移、错位眼睛、"
    "手指异常、耳朵变形、发际线异常、假发感、不要背景杂乱、光影冲突、不要过强滤镜、过度锐化、不要文字水印。"
    "图片需要符合物理逻辑，不要在画面中多出不合逻辑的手和身体部位。"
    "不可以有不符合物理逻辑的身体部位（例如同时出现多于两只手的情况）。"
)

VALID_STYLE_LINES = {"realistic_editorial", "fashion_editorial"}
VALID_CATEGORIES = {"scene", "hairstyle"}
VALID_GENDERS = {"male", "female", "unisex"}

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


def _ensure_text(raw: Any, field_name: str, record_id: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{record_id}: field '{field_name}' must be a non-empty string")
    return raw.strip()


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


def _build_runtime_prompt(
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
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    hairstyle_action_override: str | None = None,
    outfit_override: str | None = None,
) -> str:
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
    constraint_text = _build_constraint_text(scene_constraints, hairstyle_constraints)
    scene_sections = [f"场景：{_normalize_sentence(scene_prompt)}。"]
    if scene_lighting.strip():
        scene_sections.append(f"光线：{_normalize_sentence(scene_lighting)}。")
    if scene_mood.strip():
        scene_sections.append(f"风格氛围：{_normalize_sentence(scene_mood)}。")

    sections = [
        BASE_IDENTITY_PROMPT,
        OUTPUT_FORMAT_PROMPT,
        f"构图：{_normalize_sentence(shot_advice)}。",
        " ".join(scene_sections),
        f"人物表情：本张图只选择 1 种主表情，固定为：{selected_expression or '自然看向镜头'}。",
        f"人物动作：单张图中只选择 1 种主体动作，本张图固定为：{selected_subject_action or '自然站立或静止停顿'}。",
        (
            "发型展示动作参考：如需突出发型，本张图最多只允许额外参考 1 种细节动作，"
            f"固定为：{selected_hairstyle_action}。"
            if selected_hairstyle_action
            else "发型展示动作参考：本张图不额外叠加发型手部细节动作，以免与主体动作产生手部冲突。"
        ),
        f"服饰：{outfit_text or '白色宽松衬衫，内搭浅色背心或吊带'}。",
        f"人物发型：{_normalize_sentence(hairstyle_prompt)}。",
        f"关键约束：{constraint_text}。",
        QUALITY_PROMPT,
        f"负面约束：{BASE_NEGATIVE_PROMPT}",
    ]
    return "\n".join(sections)


def _resolve_sources(source_ids: list[str], record_id: str) -> tuple[SourceReference, ...]:
    references = load_reference_sources()
    resolved: list[SourceReference] = []
    for source_id in source_ids:
        if source_id not in references:
            raise ValueError(f"{record_id}: unknown reference source '{source_id}'")
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
    hairstyle_actions = hairstyle_actions or GENERIC_HAIRSTYLE_ACTIONS
    scene_constraints = scene_constraints or []
    hairstyle_constraints = hairstyle_constraints or []

    return _build_runtime_prompt(
        scene_prompt=scene_prompt,
        scene_lighting=scene_lighting,
        scene_mood=scene_mood,
        shot_advice=scene_shot,
        scene_constraints=scene_constraints,
        scene_expressions=expressions,
        scene_actions=actions,
        outfit_hints=outfit_hints,
        hairstyle_prompt=hairstyle_prompt,
        hairstyle_constraints=hairstyle_constraints,
        hairstyle_actions=hairstyle_actions,
        seed_source=seed_source,
    )


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
    }


def render_prompt(
    scene_id: str,
    hairstyle_id: str,
    *,
    outfit_override: str | None = None,
    expression_override: str | None = None,
    subject_action_override: str | None = None,
    hairstyle_action_override: str | None = None,
    seed_source: str | None = None,
) -> str:
    scene = get_record(scene_id)
    hairstyle = get_record(hairstyle_id)
    if scene.categoryType != "scene":
        raise ValueError(f"{scene_id} is not a scene record")
    if hairstyle.categoryType != "hairstyle":
        raise ValueError(f"{hairstyle_id} is not a hairstyle record")

    scene_expressions = list(scene.expressions) or list(GENERIC_EXPRESSIONS)
    scene_actions = list(scene.actions) or list(GENERIC_SCENE_ACTIONS)

    return _build_runtime_prompt(
        scene_prompt=scene.environment or scene.promptCore,
        scene_lighting=scene.lighting,
        scene_mood=scene.styleMood,
        shot_advice=scene.shotAdvice,
        scene_constraints=list(scene.constraints),
        scene_expressions=scene_expressions,
        scene_actions=scene_actions,
        outfit_hints=list(scene.outfitHints) or ["白色宽松衬衫，内搭浅色背心或吊带"],
        hairstyle_prompt=hairstyle.promptCore,
        hairstyle_constraints=list(hairstyle.constraints),
        hairstyle_actions=list(hairstyle.expressionAction),
        seed_source=seed_source or f"{scene_id}:{hairstyle_id}",
        expression_override=expression_override,
        subject_action_override=subject_action_override,
        hairstyle_action_override=hairstyle_action_override,
        outfit_override=outfit_override,
    )


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

    summary = catalog_summary()
    if summary["scene_count"] != 20:
        errors.append(f"Expected 20 scenes, found {summary['scene_count']}")
    if summary["hairstyle_count"] != 40:
        errors.append(f"Expected 40 hairstyles, found {summary['hairstyle_count']}")
    if summary["male_hairstyles"] != 20:
        errors.append(f"Expected 20 male hairstyles, found {summary['male_hairstyles']}")
    if summary["female_hairstyles"] != 20:
        errors.append(f"Expected 20 female hairstyles, found {summary['female_hairstyles']}")

    return errors
