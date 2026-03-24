from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from PIL import Image

from app.config import get_settings


SCENE_BLOCK_KEYS = (
    "shot",
    "scene_environment",
    "scene_lighting",
    "scene_mood",
    "expression",
    "subject_action",
    "outfit",
    "scene_constraints",
)


class ImageUnderstandingError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SceneUnderstandingResult:
    blocks: dict[str, str]
    raw_response: str
    model_name: str


@dataclass(frozen=True, slots=True)
class SceneDraftOptions:
    scene_id: str | None = None
    title: str | None = None
    style_line: str | None = None
    detail_tags: tuple[str, ...] = ()
    pairing_advice: tuple[str, ...] = ()
    reference_source_ids: tuple[str, ...] = ()
    reference_notes: str | None = None


def build_scene_understanding_prompt() -> str:
    return (
        "你是一个用于拆解图片提示词 block 的视觉分析助手。\n"
        "请只分析这张参考图里的场景相关信息，并输出严格 JSON。\n"
        "不要输出 markdown，不要输出解释，不要输出代码块。\n"
        "不要提取任何发型相关内容，不要输出 hair_target、hair_constraints、"
        "hairstyle_action、hair_lock 等发型字段。\n"
        "请仅返回以下 8 个字符串字段："
        "shot, scene_environment, scene_lighting, scene_mood, expression, "
        "subject_action, outfit, scene_constraints。\n"
        "要求：\n"
        "1. scene_only 视角，只保留场景、动作、表情、服饰、构图信息。\n"
        "2. 如果图片里有人物发型，请完全忽略，不要写入任何发型描述。\n"
        "3. 输出内容要适合直接拼装到中文提示词中，语气简洁、具体、可执行。\n"
        "4. 如果图片中某项不明显，也要给出最合理、最保守的概括。\n"
        "5. scene_constraints 只写场景与动作层面的关键约束，不写发型约束。\n"
        "输出示例格式："
        '{"shot":"...","scene_environment":"...","scene_lighting":"...",'
        '"scene_mood":"...","expression":"...","subject_action":"...",'
        '"outfit":"...","scene_constraints":"..."}'
    )


def _detect_mime_type(image_bytes: bytes) -> str:
    with Image.open(io.BytesIO(image_bytes)) as image:
        detected = (image.format or "").upper()
    if detected == "PNG":
        return "image/png"
    if detected in {"WEBP"}:
        return "image/webp"
    return "image/jpeg"


def _build_data_url(image_bytes: bytes) -> str:
    mime_type = _detect_mime_type(image_bytes)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _extract_json_object(text: str) -> dict[str, str]:
    stripped = text.strip()
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    candidate = match.group(0) if match else stripped

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ImageUnderstandingError("图片理解模型没有返回可解析的 JSON 结果。") from exc

    if not isinstance(payload, dict):
        raise ImageUnderstandingError("图片理解模型返回了非对象结构，无法继续解析。")

    blocks: dict[str, str] = {}
    for key in SCENE_BLOCK_KEYS:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ImageUnderstandingError(f"图片理解结果缺少必填字段：{key}")
        blocks[key] = value.strip()
    return blocks


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


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).rstrip("。；;，,")


def _split_list_field(text: str) -> list[str]:
    normalized = text.replace("\n", "；")
    items = [
        _normalize_phrase(item)
        for item in re.split(r"[；;]+", normalized)
    ]
    return _dedupe_keep_order([item for item in items if item])


def _infer_style_line(blocks: dict[str, str]) -> str:
    text = " ".join(blocks.values())
    if any(
        keyword in text
        for keyword in ("霓虹", "夜景", "冷调", "高反差", "戏剧化", "金属", "都市", "大片", "时装")
    ):
        return "fashion_editorial"
    return "realistic_editorial"


def _infer_detail_tags(blocks: dict[str, str], style_line: str) -> list[str]:
    text = " ".join(blocks.values())
    keyword_map = (
        ("室内", "室内"),
        ("户外", "户外"),
        ("窗", "窗边"),
        ("自然光", "自然光"),
        ("逆光", "逆光"),
        ("夕阳", "夕阳"),
        ("霓虹", "霓虹"),
        ("夜景", "夜景"),
        ("植物", "绿色植物"),
        ("树林", "树林"),
        ("咖啡", "咖啡馆"),
        ("客厅", "客厅"),
        ("卧室", "卧室"),
        ("留白", "留白"),
        ("胶片", "胶片感"),
        ("生活感", "生活感"),
        ("近景", "近景"),
        ("写真", "写真感"),
    )
    tags = [tag for keyword, tag in keyword_map if keyword in text]
    if not tags:
        tags = ["时尚感"] if style_line == "fashion_editorial" else ["生活感"]
    return _dedupe_keep_order(tags)[:6]


def _infer_pairing_advice(style_line: str, detail_tags: list[str]) -> list[str]:
    if style_line == "fashion_editorial":
        return ["利落短层次", "高层次中短发", "精致轮廓短发"]
    if "绿色植物" in detail_tags or "户外" in detail_tags:
        return ["法式慵懒卷", "空气感锁骨发", "轻盈波波头"]
    return ["自然层次中长发", "法式慵懒卷", "蓬松锁骨发"]


def _infer_scene_title(blocks: dict[str, str], style_line: str) -> str:
    text = " ".join(blocks.values())
    if "咖啡" in text:
        return "咖啡馆松弛人像"
    if "窗" in text:
        return "窗边自然光人像"
    if "植物" in text or "树林" in text:
        return "绿意清新人像"
    if "夜景" in text or "霓虹" in text:
        return "都市夜景人像"
    if "客厅" in text or "卧室" in text or "家居" in text:
        return "家居松弛人像"
    if style_line == "fashion_editorial":
        return "时尚氛围人像"
    return "生活感人像"


def _infer_scene_prefix(blocks: dict[str, str], style_line: str) -> str:
    text = " ".join(blocks.values())
    if "咖啡" in text:
        return "cafe-lifestyle"
    if "窗" in text:
        return "window-softlight"
    if "植物" in text or "树林" in text:
        return "green-outdoor"
    if "夜景" in text or "霓虹" in text:
        return "city-night"
    if "客厅" in text or "卧室" in text or "家居" in text:
        return "home-lifestyle"
    if style_line == "fashion_editorial":
        return "fashion-scene"
    return "scene"


def _infer_scene_id(blocks: dict[str, str], title: str, style_line: str) -> str:
    prefix = _infer_scene_prefix(blocks, style_line)
    seed = f"{title}|{blocks['scene_environment']}|{blocks['scene_lighting']}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def _infer_summary(blocks: dict[str, str]) -> str:
    environment = _normalize_phrase(blocks["scene_environment"])
    lighting = _normalize_phrase(blocks["scene_lighting"])
    return f"{environment}，{lighting}，构成稳定可复用的场景化人像环境。"


def _infer_control_profile(blocks: dict[str, str], style_line: str) -> dict[str, object]:
    text = " ".join(blocks.values())

    if any(keyword in text for keyword in ("强风", "大风", "明显风感")):
        wind_level = "medium"
    elif any(keyword in text for keyword in ("微风", "吹拂", "风感")):
        wind_level = "low"
    else:
        wind_level = "still"

    if any(keyword in text for keyword in ("湿发", "淋雨", "潮湿", "雨后")):
        humidity_look = "humid"
    else:
        humidity_look = "balanced"

    if any(keyword in text for keyword in ("留白", "简洁", "干净")):
        background_complexity = "low"
    elif any(keyword in text for keyword in ("人群", "复杂", "密集")):
        background_complexity = "high"
    else:
        background_complexity = "medium"

    if any(keyword in text for keyword in ("硬光", "直射", "高反差")):
        lighting_hardness = "hard"
    elif any(keyword in text for keyword in ("柔光", "柔和", "通透", "自然光")):
        lighting_hardness = "soft"
    else:
        lighting_hardness = "balanced"

    if any(keyword in text for keyword in ("镜子", "镜前")):
        mirror_risk = "high"
    elif any(keyword in text for keyword in ("玻璃", "反射")):
        mirror_risk = "medium"
    else:
        mirror_risk = "none"

    compatible_tags: list[str]
    if style_line == "fashion_editorial":
        compatible_tags = ["fashion_minimal"]
        if "夜景" in text or "霓虹" in text:
            compatible_tags.extend(["urban_night", "hard_light_ready", "sharp_texture"])
        else:
            compatible_tags.append("precise_outline")
    else:
        compatible_tags = ["lifestyle_softlight"]
        if wind_level != "still":
            compatible_tags.append("soft_motion")
        if any(keyword in text for keyword in ("窗", "近景", "包脸", "柔和")):
            compatible_tags.append("layered_face_framing")

    return {
        "windLevel": wind_level,
        "humidityLook": humidity_look,
        "backgroundComplexity": background_complexity,
        "lightingHardness": lighting_hardness,
        "mirrorRisk": mirror_risk,
        "compatibleHairstyleTags": _dedupe_keep_order(compatible_tags),
    }


def build_scene_draft(
    blocks: dict[str, str],
    options: SceneDraftOptions | None = None,
) -> dict[str, object]:
    options = options or SceneDraftOptions()
    style_line = options.style_line or _infer_style_line(blocks)
    if style_line not in {"realistic_editorial", "fashion_editorial"}:
        raise ImageUnderstandingError("scene draft 的 style_line 非法。")

    title = _normalize_phrase(options.title or _infer_scene_title(blocks, style_line))
    scene_id = _normalize_phrase(options.scene_id or _infer_scene_id(blocks, title, style_line))
    detail_tags = _dedupe_keep_order(
        list(options.detail_tags) or _infer_detail_tags(blocks, style_line)
    )
    pairing_advice = _dedupe_keep_order(
        list(options.pairing_advice) or _infer_pairing_advice(style_line, detail_tags)
    )
    reference_source_ids = _dedupe_keep_order(
        list(options.reference_source_ids) or ["scene-understanding-api"]
    )
    reference_notes = _normalize_phrase(
        options.reference_notes
        or "该场景草案由参考图自动拆解生成，建议人工复核标题、标签和搭配建议后再写入 scenes.json"
    )

    return {
        "id": scene_id,
        "title": title,
        "styleLine": style_line,
        "summary": _infer_summary(blocks),
        "environment": _normalize_phrase(blocks["scene_environment"]),
        "lighting": _normalize_phrase(blocks["scene_lighting"]),
        "styleMood": _normalize_phrase(blocks["scene_mood"]),
        "detailTags": detail_tags,
        "expressions": _split_list_field(blocks["expression"]),
        "actions": _split_list_field(blocks["subject_action"]),
        "outfitHints": _split_list_field(blocks["outfit"]),
        "pairingAdvice": pairing_advice,
        "shotAdvice": _normalize_phrase(blocks["shot"]),
        "constraints": _split_list_field(blocks["scene_constraints"]),
        "controlProfile": _infer_control_profile(blocks, style_line),
        "referenceNotes": reference_notes,
        "referenceSourceIds": reference_source_ids,
    }


class ImageUnderstandingService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.image_understanding_api_key:
            raise ImageUnderstandingError("尚未配置图片理解 API Key。")

        self.model_name = settings.image_understanding_model
        self._client = OpenAI(
            api_key=settings.image_understanding_api_key,
            base_url=settings.image_understanding_base_url,
            timeout=settings.image_understanding_timeout_seconds,
        )

    def extract_scene_blocks(self, image_bytes: bytes) -> SceneUnderstandingResult:
        data_url = _build_data_url(image_bytes)

        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": "你只负责把参考图拆成 scene_only 所需的结构化 block。",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": build_scene_understanding_prompt(),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                        ],
                    },
                ],
            )
        except AuthenticationError as exc:
            raise ImageUnderstandingError("图片理解 API Key 无效或权限不足。") from exc
        except RateLimitError as exc:
            raise ImageUnderstandingError("图片理解模型当前触发限流，请稍后重试。") from exc
        except APIConnectionError as exc:
            raise ImageUnderstandingError("图片理解服务连接失败，请检查网络或服务状态。") from exc
        except APIStatusError as exc:
            raise ImageUnderstandingError(
                f"图片理解服务返回异常状态：{exc.status_code}"
            ) from exc
        except APIError as exc:
            raise ImageUnderstandingError(f"图片理解服务调用失败：{exc}") from exc

        message = response.choices[0].message if response.choices else None
        raw_content = ""
        if message is not None and isinstance(message.content, str):
            raw_content = message.content

        if not raw_content.strip():
            raise ImageUnderstandingError("图片理解模型没有返回有效内容。")

        return SceneUnderstandingResult(
            blocks=_extract_json_object(raw_content),
            raw_response=raw_content,
            model_name=self.model_name,
        )
