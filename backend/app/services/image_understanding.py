from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass

from PIL import Image

from app.config import get_settings


SCENE_BLOCK_KEYS = (
    "shot",
    "scene_environment",
    "scene_lighting",
    "scene_mood",
    "expression",
    "subject_action",
    "makeup",
    "outfit",
    "styling_constraints",
    "scene_constraints",
)


class ImageUnderstandingError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SceneUnderstandingResult:
    blocks: dict[str, str]
    raw_response: str
    model_name: str
    subject_gender: str = "unknown"


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
        "请额外判断参考图中主要人物的性别表达，并返回 subject_gender。\n"
        "subject_gender 只能是 male、female、unknown 三个值之一。\n"
        "请返回以下字段："
        "subject_gender, "
        "shot, scene_environment, scene_lighting, scene_mood, expression, "
        "subject_action, makeup, outfit, styling_constraints, scene_constraints。\n"
        "要求：\n"
        "1. scene_only 视角，只保留场景、动作、表情、服饰、构图信息。\n"
        "2. 如果图片里有人物发型，请完全忽略，不要写入任何发型描述。\n"
        "3. 输出内容要适合直接拼装到中文提示词中，语气简洁、具体、可执行。\n"
        "4. 如果图片中某项不明显，也要给出最合理、最保守的概括。\n"
        "5. scene_constraints 只写场景与动作层面的关键约束，不写发型约束。\n"
        "6. makeup 只写适合当前场景的人物妆造方向，不要写发型。\n"
        "7. styling_constraints 只写妆造和服饰禁忌，不要写镜头或发型禁忌。\n"
        "8. 如果人物性别表达不明确，或者图片里没有明确单人主体，subject_gender 返回 unknown。\n"
        "输出示例格式："
        '{"subject_gender":"female","shot":"...","scene_environment":"...","scene_lighting":"...",'
        '"scene_mood":"...","expression":"...","subject_action":"...",'
        '"makeup":"...","outfit":"...","styling_constraints":"...","scene_constraints":"..."}'
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


def _prepare_understanding_image(image_bytes: bytes, *, max_side: int = 1280) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as image:
        working = image.convert("RGB")
        if max(working.width, working.height) <= max_side:
            buffer = io.BytesIO()
            working.save(buffer, format="JPEG", quality=88)
            return buffer.getvalue()

        working.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        working.save(buffer, format="JPEG", quality=88)
        return buffer.getvalue()


def _extract_json_object(text: str) -> tuple[dict[str, str], str]:
    stripped = text.strip()
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    candidate = match.group(0) if match else stripped

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ImageUnderstandingError("图片理解模型没有返回可解析的 JSON 结果。") from exc

    if not isinstance(payload, dict):
        raise ImageUnderstandingError("图片理解模型返回了非对象结构，无法继续解析。")

    raw_subject_gender = str(payload.get("subject_gender") or "unknown").strip().lower()
    if raw_subject_gender not in {"male", "female", "unknown"}:
        raw_subject_gender = "unknown"

    blocks: dict[str, str] = {}
    for key in SCENE_BLOCK_KEYS:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ImageUnderstandingError(f"图片理解结果缺少必填字段：{key}")
        blocks[key] = value.strip()
    return blocks, raw_subject_gender


def _extract_message_content(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts)
    return ""


def _run_chat_completion_via_curl(
    *,
    base_url: str,
    api_key: str,
    model_name: str,
    prompt_text: str,
    data_url: str,
    timeout_seconds: int,
) -> dict:
    request_payload = {
        "model": model_name,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "你只负责把参考图拆成 scene_only 所需的结构化 block。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_text,
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            },
        ],
    }

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=True) as handle:
        json.dump(request_payload, handle, ensure_ascii=False)
        handle.flush()
        command = [
            "curl",
            "--max-time",
            str(timeout_seconds),
            "-sS",
            f"{base_url}/chat/completions",
            "-H",
            "Content-Type: application/json",
            "-H",
            f"Authorization: Bearer {api_key}",
            "--data-binary",
            f"@{handle.name}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

    if completed.returncode != 0:
        error_text = (completed.stderr or completed.stdout or "").strip()
        if "Operation timed out" in error_text or "timed out" in error_text.lower():
            raise ImageUnderstandingError("图片理解服务超时，请稍后重试。")
        raise ImageUnderstandingError(
            f"图片理解服务调用失败：{error_text or f'curl exit {completed.returncode}'}"
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ImageUnderstandingError("图片理解服务返回了无法解析的 JSON。") from exc

    if not isinstance(payload, dict):
        raise ImageUnderstandingError("图片理解服务返回了非对象结构。")
    return payload


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


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _infer_lighting_profile(blocks: dict[str, str], style_line: str) -> dict[str, object]:
    text = " ".join(blocks.values())

    if _contains_any(text, ("逆光", "侧后方", "背后", "夕阳")):
        light_direction = "back"
    elif _contains_any(text, ("侧光", "侧面", "窗边", "侧前方")):
        light_direction = "side"
    elif _contains_any(text, ("顶部", "镜前灯", "顶灯", "下落光")):
        light_direction = "top"
    elif _contains_any(text, ("混合光", "霓虹", "冷暖", "多方向", "环境光")):
        light_direction = "mixed"
    else:
        light_direction = "front" if style_line == "fashion_editorial" else "side"

    if _contains_any(text, ("硬光", "强侧光", "戏剧化", "高反差", "金属")):
        light_quality = "hard"
    elif _contains_any(text, ("柔和", "柔光", "通透", "自然光", "软光")):
        light_quality = "soft"
    else:
        light_quality = "medium"

    if _contains_any(text, ("冷暖混合", "混合光", "霓虹", "冷暖对比")):
        color_temperature = "mixed"
    elif _contains_any(text, ("冷调", "阴天", "雨天", "金属", "夜色")):
        color_temperature = "cool"
    elif _contains_any(text, ("暖调", "夕阳", "暖白", "木色", "酒吧", "酒店")):
        color_temperature = "warm"
    else:
        color_temperature = "neutral"

    if _contains_any(text, ("高反差", "戏剧化", "霓虹", "冷感大片")):
        contrast_level = "high"
    elif _contains_any(text, ("低反差", "清晨", "柔和", "留白", "松弛")):
        contrast_level = "low"
    else:
        contrast_level = "medium"

    if contrast_level == "high":
        shadow_density = "deep"
    elif contrast_level == "low":
        shadow_density = "light"
    else:
        shadow_density = "balanced"

    if _contains_any(text, ("镜前", "金属", "霓虹", "反射")):
        hair_highlight_mode = "controlled_specular"
    elif _contains_any(text, ("轮廓光", "边缘光", "逆光")):
        hair_highlight_mode = "clean_rim"
    elif _contains_any(text, ("阴天", "散射", "柔雾")):
        hair_highlight_mode = "none"
    else:
        hair_highlight_mode = "soft_edge"

    if style_line == "fashion_editorial" or _contains_any(text, ("骨相", "结构", "利落")):
        skin_rendering = "structured_texture"
    elif _contains_any(text, ("清透", "通透", "干净")):
        skin_rendering = "clean_texture"
    else:
        skin_rendering = "soft_texture"

    if _contains_any(text, ("略微欠曝", "低照度", "暗调", "夜色", "雨天", "傍晚")):
        exposure_bias = "slightly_under"
    elif _contains_any(text, ("明亮", "高键", "白盒子", "通透")):
        exposure_bias = "slightly_over"
    else:
        exposure_bias = "neutral"

    practical_lights_allowed = _contains_any(
        text,
        ("镜前", "酒吧", "酒店", "后台", "咖啡馆", "霓虹", "灯带", "室内暖光"),
    )

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


def _infer_outfit_palette(blocks: dict[str, str], style_line: str) -> list[str]:
    text = blocks["outfit"]
    palette_map = (
        ("白", "白色"),
        ("米白", "米白"),
        ("奶油", "奶油白"),
        ("浅灰", "浅灰"),
        ("灰", "深灰"),
        ("卡其", "浅卡其"),
        ("黑", "黑色"),
        ("酒红", "酒红"),
        ("银", "银灰"),
        ("裸", "裸色中性调"),
        ("绿", "低饱和绿"),
    )
    palette = [tag for keyword, tag in palette_map if keyword in text]
    if palette:
        return _dedupe_keep_order(palette)[:4]
    if style_line == "fashion_editorial":
        return ["黑色", "冷灰", "白色"]
    return ["白色", "浅灰", "米白"]


def _infer_outfit_materials(blocks: dict[str, str], style_line: str) -> list[str]:
    text = blocks["outfit"]
    material_map = (
        ("针织", "柔软针织"),
        ("衬衫", "衬衫棉布"),
        ("棉", "轻薄棉质"),
        ("吊带", "轻薄贴肤面料"),
        ("背心", "轻薄背心面料"),
        ("风衣", "风衣面料"),
        ("皮", "皮质"),
        ("西装", "挺括西装面料"),
        ("缎", "缎面"),
    )
    materials = [tag for keyword, tag in material_map if keyword in text]
    if materials:
        return _dedupe_keep_order(materials)[:4]
    if style_line == "fashion_editorial":
        return ["挺括西装面料", "结构化织物"]
    return ["柔软针织", "轻薄棉质"]


def _infer_outfit_shapes(blocks: dict[str, str], style_line: str) -> list[str]:
    text = blocks["outfit"]
    shape_map = (
        ("宽松衬衫", "宽松衬衫"),
        ("衬衫", "简洁衬衫"),
        ("背心", "简洁背心"),
        ("吊带", "轻薄吊带"),
        ("开衫", "针织开衫"),
        ("高领", "高领上衣"),
        ("西装", "结构西装"),
        ("风衣", "利落外套"),
    )
    shapes = [tag for keyword, tag in shape_map if keyword in text]
    if shapes:
        return _dedupe_keep_order(shapes)[:4]
    if style_line == "fashion_editorial":
        return ["结构西装", "利落上衣"]
    return ["宽松衬衫", "松弛上衣"]


def _infer_outfit_avoids(blocks: dict[str, str], style_line: str) -> list[str]:
    text = " ".join(blocks.values())
    avoids: list[str] = []
    if style_line == "fashion_editorial":
        avoids.extend(["家居感软塌单品", "高饱和甜美元素", "复杂大面积图案"])
    else:
        avoids.extend(["强结构礼服感", "高饱和撞色", "复杂夸张配饰"])
    if _contains_any(text, ("镜前", "镜子", "浴室")):
        avoids.append("过度性感化处理")
    if _contains_any(text, ("雨天", "清晨", "窗边")):
        avoids.append("厚重浓妆感")
    return _dedupe_keep_order(avoids)


def _infer_sample_image_ids(blocks: dict[str, str], style_line: str) -> dict[str, list[str]]:
    text = " ".join(blocks.values())
    if _contains_any(text, ("户外", "树林", "植物", "风场", "天台")):
        return {"female": ["female1"], "male": ["male3"]}
    if style_line == "fashion_editorial" or _contains_any(
        text,
        ("夜色", "霓虹", "金属", "酒吧", "后台", "镜前", "大堂", "棚拍", "白盒子"),
    ):
        return {"female": ["female2"], "male": ["male1"]}
    return {"female": ["female3"], "male": ["male2"]}


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
        "lightingProfile": _infer_lighting_profile(blocks, style_line),
        "styleMood": _normalize_phrase(blocks["scene_mood"]),
        "detailTags": detail_tags,
        "expressions": _split_list_field(blocks["expression"]),
        "actions": _split_list_field(blocks["subject_action"]),
        "outfitHints": _split_list_field(blocks["outfit"]),
        "outfitPalette": _infer_outfit_palette(blocks, style_line),
        "outfitMaterials": _infer_outfit_materials(blocks, style_line),
        "outfitShapes": _infer_outfit_shapes(blocks, style_line),
        "outfitAvoids": _infer_outfit_avoids(blocks, style_line),
        "pairingAdvice": pairing_advice,
        "shotAdvice": _normalize_phrase(blocks["shot"]),
        "constraints": _split_list_field(blocks["scene_constraints"]),
        "controlProfile": _infer_control_profile(blocks, style_line),
        "sampleImageIds": _infer_sample_image_ids(blocks, style_line),
        "referenceNotes": reference_notes,
        "referenceSourceIds": reference_source_ids,
    }


class ImageUnderstandingService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.image_understanding_api_key:
            raise ImageUnderstandingError("尚未配置图片理解 API Key。")

        self.model_name = settings.image_understanding_model
        self._api_key = settings.image_understanding_api_key
        self._base_url = settings.image_understanding_base_url.rstrip("/")
        self._timeout_seconds = settings.image_understanding_timeout_seconds

    def extract_scene_blocks(self, image_bytes: bytes) -> SceneUnderstandingResult:
        optimized_bytes = _prepare_understanding_image(image_bytes)
        data_url = _build_data_url(optimized_bytes)
        payload = _run_chat_completion_via_curl(
            base_url=self._base_url,
            api_key=self._api_key,
            model_name=self.model_name,
            prompt_text=build_scene_understanding_prompt(),
            data_url=data_url,
            timeout_seconds=self._timeout_seconds,
        )

        raw_content = _extract_message_content(payload)
        if not raw_content.strip():
            if isinstance(payload, dict):
                raw_content = json.dumps(payload, ensure_ascii=False)

        if not raw_content.strip():
            raise ImageUnderstandingError("图片理解模型没有返回有效内容。")

        blocks, subject_gender = _extract_json_object(raw_content)
        return SceneUnderstandingResult(
            blocks=blocks,
            raw_response=raw_content,
            model_name=self.model_name,
            subject_gender=subject_gender,
        )
