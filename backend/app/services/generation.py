from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.config import get_settings


logger = logging.getLogger(__name__)
CANDIDATE_IMAGE_COUNT = 3


class ImageGenerationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _event_field(event, name: str):
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


@dataclass(slots=True)
class GenerationContext:
    hairstyle_name: str
    scene_name: str


@dataclass(slots=True)
class CandidateScore:
    index: int
    score: float
    summary: str
    image_bytes: bytes


class BaseGenerator:
    model_name: str

    def generate(self, source_image_path: str, prompt: str, context: GenerationContext) -> bytes:
        raise NotImplementedError


def _decode_image(image_bytes: bytes) -> np.ndarray:
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded is None:
        raise ImageGenerationError("invalid_image", "Failed to decode generated image.")
    return decoded


def _score_portrait_candidate(index: int, image_bytes: bytes) -> CandidateScore:
    image = _decode_image(image_bytes)
    height, width = image.shape[:2]
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    score = 0.0
    notes: list[str] = []

    face_detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_detector.detectMultiScale(grayscale, scaleFactor=1.1, minNeighbors=5)
    face_count = len(faces)
    if face_count == 1:
        x, y, w, h = faces[0]
        face_ratio = (w * h) / float(width * height)
        center_x = x + w / 2
        center_y = y + h / 2
        center_offset = abs(center_x - width / 2) / width + abs(center_y - height / 2) / height
        score += 50
        score += max(0, 12 - abs(face_ratio - 0.18) * 90)
        score += max(0, 8 - center_offset * 22)
        notes.append("single-face")
    elif face_count == 0:
        score -= 35
        notes.append("no-face")
    else:
        score -= 60
        notes.append("multi-face")

    sharpness = cv2.Laplacian(grayscale, cv2.CV_64F).var()
    score += min(sharpness / 120, 18)
    notes.append(f"sharp={sharpness:.0f}")

    luminance_mean = float(np.mean(grayscale))
    exposure_score = max(0.0, 16 - abs(luminance_mean - 138) / 4.5)
    score += exposure_score
    notes.append(f"light={luminance_mean:.0f}")

    contrast = float(np.std(grayscale))
    score += min(contrast / 5, 10)
    notes.append(f"contrast={contrast:.0f}")

    saturation_mean = float(np.mean(hsv[:, :, 1]))
    saturation_penalty = abs(saturation_mean - 78) / 7
    score += max(0.0, 8 - saturation_penalty)
    notes.append(f"sat={saturation_mean:.0f}")

    highlight_ratio = float(np.mean(grayscale > 242))
    shadow_ratio = float(np.mean(grayscale < 18))
    score += max(0.0, 6 - (highlight_ratio * 26 + shadow_ratio * 18))
    notes.append(f"clip={highlight_ratio:.2f}/{shadow_ratio:.2f}")

    return CandidateScore(
        index=index,
        score=score,
        summary=", ".join(notes),
        image_bytes=image_bytes,
    )


def _select_best_candidate(candidates: list[bytes]) -> bytes:
    if not candidates:
        raise ImageGenerationError("upstream_empty", "Seedream returned no image payload.")

    scored_candidates = [
        _score_portrait_candidate(index=index + 1, image_bytes=image_bytes)
        for index, image_bytes in enumerate(candidates)
    ]
    scored_candidates.sort(key=lambda item: item.score, reverse=True)
    for candidate in scored_candidates:
        logger.info(
            "Seedream candidate %s scored %.2f (%s)",
            candidate.index,
            candidate.score,
            candidate.summary,
        )
    best = scored_candidates[0]
    logger.info("Selected Seedream candidate %s as final output", best.index)
    return best.image_bytes


class MockGenerator(BaseGenerator):
    model_name = "mock-image-generator"

    def generate(self, source_image_path: str, prompt: str, context: GenerationContext) -> bytes:
        candidates: list[bytes] = []
        blur_levels = [10, 18, 26]
        portrait_offsets = [(160, 150), (170, 160), (185, 170)]

        with Image.open(source_image_path).convert("RGB") as source:
            for idx in range(CANDIDATE_IMAGE_COUNT):
                target = Image.new("RGB", (1200, 1600), "#101820")
                background = ImageOps.fit(source, target.size).filter(
                    ImageFilter.GaussianBlur(blur_levels[idx])
                )
                target.paste(background)

                portrait = ImageOps.fit(source, (860, 1120))
                portrait = portrait.filter(ImageFilter.SHARPEN)
                target.paste(portrait, portrait_offsets[idx])

                overlay = Image.new("RGBA", target.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                draw.rounded_rectangle((120, 1040, 1080, 1460), radius=40, fill=(15, 23, 42, 185))
                draw.text((170, 1090), f"AI Hair Remix Preview #{idx + 1}", fill=(255, 255, 255))
                draw.text((170, 1150), f"Hair: {context.hairstyle_name}", fill=(204, 251, 241))
                draw.text((170, 1200), f"Scene: {context.scene_name}", fill=(191, 219, 254))
                draw.text((170, 1260), "Mock flow now creates 3 candidates.", fill=(226, 232, 240))
                draw.text((170, 1310), "The backend auto-selects the best portrait.", fill=(226, 232, 240))
                target = Image.alpha_composite(target.convert("RGBA"), overlay).convert("RGB")

                output = io.BytesIO()
                target.save(output, format="PNG", optimize=True)
                candidates.append(output.getvalue())

        return _select_best_candidate(candidates)


class SeedreamGenerator(BaseGenerator):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.ark_api_key:
            raise ImageGenerationError(
                "missing_api_key", "ARK_API_KEY must be configured when using Seedream."
            )

        self.model_name = settings.ark_image_model
        self._client = OpenAI(
            base_url=settings.ark_base_url,
            api_key=settings.ark_api_key,
        )

    def generate(self, source_image_path: str, prompt: str, context: GenerationContext) -> bytes:
        with open(source_image_path, "rb") as handle:
            image_bytes = handle.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        suffix = Path(source_image_path).suffix.lower()
        mime_type = "image/png" if suffix == ".png" else "image/jpeg"
        image_data = f"data:{mime_type};base64,{image_base64}"
        candidates: list[bytes] = []
        stream = self._client.images.generate(
            model=self.model_name,
            prompt=prompt,
            size="2K",
            response_format="b64_json",
            stream=True,
            extra_body={
                "image": image_data,
                "watermark": True,
                "sequential_image_generation": "auto",
                "sequential_image_generation_options": {
                    "max_images": CANDIDATE_IMAGE_COUNT,
                },
            },
        )

        for event in stream:
            if event is None:
                continue
            event_type = _event_field(event, "type")
            if event_type == "image_generation.partial_succeeded":
                payload = _event_field(event, "b64_json")
                if payload:
                    candidates.append(base64.b64decode(payload))

        return _select_best_candidate(candidates)


def build_generator() -> BaseGenerator:
    settings = get_settings()
    if settings.use_mock_generator:
        return MockGenerator()
    return SeedreamGenerator()
