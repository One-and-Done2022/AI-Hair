from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path

import cv2  # type: ignore
import numpy as np  # type: ignore
from PIL import Image

from app.services import storage, templates


class RecommendationError(Exception):
    pass


@dataclass(slots=True)
class PortraitAnalysis:
    face_shape_id: str
    face_shape_label: str
    feature_tags: list[str]
    style_bias: str
    measurements: dict[str, float]
    summary: str


FACE_SHAPE_LABELS = {
    "oval": "椭圆脸",
    "round": "圆脸",
    "square": "方脸",
    "long": "长脸",
    "heart": "心形脸",
    "diamond": "菱形脸",
}


HAIRSTYLE_RULES = {
    "round": {
        "positive": ["前刺", "铲青", "高层次", "蓬松", "渐变", "露耳", "侧分", "中分", "顶部卷度"],
        "negative": ["服帖", "重量线", "一刀切", "极短刘海"],
        "style_line": "fashion_editorial",
        "reasons": ["适合拉长面部纵向比例", "适合增强头顶层次和利落感"],
    },
    "long": {
        "positive": ["刘海", "挂耳", "波波头", "卷度", "中长发", "栗子头", "服帖"],
        "negative": ["前刺", "极短", "圆寸", "高层次", "铲青"],
        "style_line": "realistic_editorial",
        "reasons": ["适合平衡脸部长宽比例", "适合增加横向展开感"],
    },
    "square": {
        "positive": ["碎感", "卷度", "法式", "蓬松", "层次", "中长发"],
        "negative": ["圆寸", "极短", "一刀切"],
        "style_line": "fashion_editorial",
        "reasons": ["适合柔化下颌线条", "适合增加发丝纹理与层次"],
    },
    "heart": {
        "positive": ["刘海", "中长发", "层次", "挂耳", "法式", "自然"],
        "negative": ["露额", "前刺", "极短"],
        "style_line": "realistic_editorial",
        "reasons": ["适合平衡额头与下颌视觉重心", "适合保留柔和轮廓感"],
    },
    "diamond": {
        "positive": ["中分", "侧分", "层次", "蓬松", "卷度", "自然"],
        "negative": ["极短", "圆寸"],
        "style_line": "fashion_editorial",
        "reasons": ["适合平衡颧骨宽度", "适合增强整体线条协调感"],
    },
    "oval": {
        "positive": ["自然", "层次", "蓬松", "法式", "侧分", "中分"],
        "negative": [],
        "style_line": "realistic_editorial",
        "reasons": ["脸型整体均衡，可尝试更多风格", "适合优先选择贴近气质的款式"],
    },
}


SCENE_RULES = {
    "soft": {
        "positive": ["窗边", "自然光", "生活感", "胶片感", "木质", "暖调", "软光", "书房", "咖啡馆"],
        "style_line": "realistic_editorial",
        "reasons": ["更适合柔和自然的生活感场景", "能强化松弛与亲和气质"],
    },
    "sharp": {
        "positive": ["极简", "都市", "冷调", "霓虹", "金属", "高反差", "戏剧化", "夜色"],
        "style_line": "fashion_editorial",
        "reasons": ["更适合利落明确的场景线条", "能强化轮廓和时尚感"],
    },
    "balanced": {
        "positive": ["近景", "克制", "自然光", "室内", "纯色", "棚拍"],
        "style_line": "realistic_editorial",
        "reasons": ["适合优先突出人物本身", "适合稳定、干净的背景表达"],
    },
}


def _decode_image(image_bytes: bytes) -> tuple[np.ndarray, int, int]:
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded is None:
        raise RecommendationError("无法解析上传图片，暂时不能完成智能推荐。")
    return decoded, width, height


def _detect_eyes(face_roi: np.ndarray) -> list[tuple[int, int, int, int]]:
    grayscale = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    detected = eye_cascade.detectMultiScale(
        grayscale,
        scaleFactor=1.05,
        minNeighbors=4,
        minSize=(18, 18),
    )
    eyes = []
    upper_bound = int(face_roi.shape[0] * 0.62)
    for x, y, w, h in detected:
        if y + h > upper_bound:
            continue
        eyes.append((int(x), int(y), int(w), int(h)))
    eyes.sort(key=lambda item: item[2] * item[3], reverse=True)
    return eyes[:4]


def _edge_width(signal: np.ndarray, *, fallback: float) -> float:
    active = np.where(signal > 0)[0]
    if len(active) < 2:
        return fallback
    return float(active[-1] - active[0])


def _estimate_outline_widths(face_roi: np.ndarray) -> dict[str, float]:
    grayscale = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    grayscale = cv2.equalizeHist(grayscale)
    blurred = cv2.GaussianBlur(grayscale, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 110)

    height, width = edges.shape[:2]
    fallback_forehead = width * 0.72
    fallback_cheek = width * 0.82
    fallback_jaw = width * 0.7
    fallback_chin = width * 0.48

    def row_band(sample_ratio: float) -> np.ndarray:
        row = max(0, min(height - 1, int(height * sample_ratio)))
        band = edges[max(0, row - 2):min(height, row + 3), :]
        return band.max(axis=0)

    return {
        "forehead_width": _edge_width(row_band(0.2), fallback=fallback_forehead),
        "cheek_width": _edge_width(row_band(0.46), fallback=fallback_cheek),
        "jaw_width": _edge_width(row_band(0.76), fallback=fallback_jaw),
        "chin_width": _edge_width(row_band(0.9), fallback=fallback_chin),
    }


def _classify_face_shape(
    *,
    face_width: float,
    face_height: float,
    outline_widths: dict[str, float],
) -> str:
    aspect_ratio = face_height / max(face_width, 1.0)
    forehead = outline_widths["forehead_width"] / max(face_width, 1.0)
    cheek = outline_widths["cheek_width"] / max(face_width, 1.0)
    jaw = outline_widths["jaw_width"] / max(face_width, 1.0)
    chin = outline_widths["chin_width"] / max(face_width, 1.0)

    if aspect_ratio >= 1.52:
        return "long"
    if cheek > max(forehead, jaw) * 1.08 and jaw < cheek * 0.92 and forehead < cheek * 0.94:
        return "diamond"
    if forehead > jaw * 1.1 and chin < jaw * 0.88:
        return "heart"
    if aspect_ratio < 1.26 and jaw >= cheek * 0.9:
        return "square"
    if aspect_ratio < 1.24:
        return "round"
    return "oval"


def analyze_upload_image(image_bytes: bytes) -> PortraitAnalysis:
    decoded, width, height = _decode_image(image_bytes)
    faces = storage._detect_faces(image_bytes)
    if faces is None:
        raise RecommendationError("当前环境缺少人脸分析能力，暂时不能完成智能推荐。")
    faces = storage._normalize_detected_faces(faces, width, height)
    if len(faces) == 0:
        raise RecommendationError("未识别到清晰人脸，暂时无法给出可靠推荐。")

    x, y, face_width, face_height = max(faces, key=lambda item: item[2] * item[3])
    face_roi = decoded[y:y + face_height, x:x + face_width]
    if face_roi.size == 0:
        raise RecommendationError("无法截取有效人脸区域，暂时不能完成智能推荐。")

    outline_widths = _estimate_outline_widths(face_roi)
    face_shape_id = _classify_face_shape(
        face_width=float(face_width),
        face_height=float(face_height),
        outline_widths=outline_widths,
    )
    face_shape_label = FACE_SHAPE_LABELS[face_shape_id]

    feature_tags = [face_shape_label]
    style_bias = "balanced"
    if face_shape_id in {"round", "heart"}:
        style_bias = "soft"
    elif face_shape_id in {"square", "diamond"}:
        style_bias = "sharp"

    face_area_ratio = (face_width * face_height) / float(width * height)
    feature_tags.append("轮廓偏长" if (face_height / max(face_width, 1.0)) >= 1.45 else "比例均衡")
    feature_tags.append("轮廓分明" if face_shape_id in {"square", "diamond"} else "轮廓柔和")

    eyes = _detect_eyes(face_roi)
    eye_distance_ratio = 0.0
    if len(eyes) >= 2:
        eyes = sorted(eyes[:2], key=lambda item: item[0])
        left_center = eyes[0][0] + eyes[0][2] / 2
        right_center = eyes[1][0] + eyes[1][2] / 2
        eye_distance_ratio = (right_center - left_center) / max(face_width, 1.0)
        if eye_distance_ratio <= 0.34:
            feature_tags.append("五官集中")
        elif eye_distance_ratio >= 0.42:
            feature_tags.append("五官舒展")

    if face_area_ratio <= 0.12:
        feature_tags.append("适合近景构图")

    summary = f"识别为{face_shape_label}，推荐优先选择更能平衡面部比例的发型和场景。"
    measurements = {
        "face_aspect_ratio": round(face_height / max(face_width, 1.0), 3),
        "face_area_ratio": round(face_area_ratio, 3),
        "eye_distance_ratio": round(eye_distance_ratio, 3),
        "forehead_width_ratio": round(outline_widths["forehead_width"] / max(face_width, 1.0), 3),
        "cheek_width_ratio": round(outline_widths["cheek_width"] / max(face_width, 1.0), 3),
        "jaw_width_ratio": round(outline_widths["jaw_width"] / max(face_width, 1.0), 3),
    }
    return PortraitAnalysis(
        face_shape_id=face_shape_id,
        face_shape_label=face_shape_label,
        feature_tags=list(dict.fromkeys(feature_tags)),
        style_bias=style_bias,
        measurements=measurements,
        summary=summary,
    )


def _score_keywords(text: str, positive_keywords: list[str], negative_keywords: list[str]) -> int:
    score = 0
    for keyword in positive_keywords:
        if keyword and keyword in text:
            score += 2
    for keyword in negative_keywords:
        if keyword and keyword in text:
            score -= 2
    return score


def _hairstyle_text(template: dict) -> str:
    return " ".join(
        [
            template.get("name", ""),
            template.get("description", ""),
            " ".join(template.get("tags", [])),
            " ".join(template.get("pairing_advice", [])),
            template.get("prompt_core", ""),
        ]
    )


def _scene_text(template: dict) -> str:
    return " ".join(
        [
            template.get("name", ""),
            template.get("description", ""),
            " ".join(template.get("tags", [])),
            " ".join(template.get("pairing_advice", [])),
            template.get("environment", ""),
            template.get("lighting", ""),
            template.get("style_mood", ""),
        ]
    )


def recommend_hairstyles(
    analysis: PortraitAnalysis,
    *,
    gender: str,
    limit: int = 3,
) -> list[dict]:
    rules = HAIRSTYLE_RULES.get(analysis.face_shape_id, HAIRSTYLE_RULES["oval"])
    candidates: list[dict] = []

    for template in templates.HAIRSTYLES:
        if template.get("gender") != gender:
            continue
        text = _hairstyle_text(template)
        score = _score_keywords(text, rules["positive"], rules["negative"])
        if template.get("style_line") == rules["style_line"]:
            score += 1
        if "五官集中" in analysis.feature_tags and any(keyword in text for keyword in ["极简", "利落", "清爽", "服帖"]):
            score += 1
        if "五官舒展" in analysis.feature_tags and any(keyword in text for keyword in ["层次", "卷度", "蓬松"]):
            score += 1
        reasons = rules["reasons"][:]
        candidates.append(
            {
                "id": template["id"],
                "name": template["name"],
                "score": score,
                "reasons": reasons[:2],
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["name"]))
    return candidates[:limit]


def recommend_scenes(
    analysis: PortraitAnalysis,
    *,
    limit: int = 3,
) -> list[dict]:
    scene_rule = SCENE_RULES.get(analysis.style_bias, SCENE_RULES["balanced"])
    candidates: list[dict] = []

    for template in templates.SCENES:
        text = _scene_text(template)
        score = _score_keywords(text, scene_rule["positive"], [])
        if template.get("style_line") == scene_rule["style_line"]:
            score += 1
        if "适合近景构图" in analysis.feature_tags and "近景" in text:
            score += 1
        candidates.append(
            {
                "id": template["id"],
                "name": template["name"],
                "score": score,
                "reasons": scene_rule["reasons"][:2],
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["name"]))
    return candidates[:limit]


def build_recommendation_payload(upload: dict) -> dict:
    image_bytes = storage.read_file_bytes(upload["stored_path"])
    analysis = analyze_upload_image(image_bytes)
    return {
        "face_shape": {
            "id": analysis.face_shape_id,
            "label": analysis.face_shape_label,
        },
        "feature_tags": analysis.feature_tags,
        "summary": analysis.summary,
        "measurements": analysis.measurements,
        "recommended_hairstyles": {
            "male": recommend_hairstyles(analysis, gender="male"),
            "female": recommend_hairstyles(analysis, gender="female"),
        },
        "recommended_scenes": recommend_scenes(analysis),
    }
