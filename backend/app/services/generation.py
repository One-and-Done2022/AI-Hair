from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable

import cv2
import numpy as np
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.config import get_settings
from app.services.key_pool import ApiKeyLease


logger = logging.getLogger(__name__)
CANDIDATE_IMAGE_COUNT = 3
PRIMARY_PREVIEW_IMAGE_COUNT = 1
PreviewCallback = Callable[[bytes], None]


class ImageGenerationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
        disable_key: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.disable_key = disable_key


def _event_field(event, name: str):
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _extract_b64_payloads(event) -> list[str]:
    payloads: list[str] = []

    def visit(value) -> None:
        if value is None:
            return
        if isinstance(value, str):
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "b64_json" and isinstance(item, str) and item:
                    payloads.append(item)
                    continue
                visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
            return

        nested_payload = getattr(value, "b64_json", None)
        if isinstance(nested_payload, str) and nested_payload:
            payloads.append(nested_payload)
            return

        if hasattr(value, "__dict__"):
            visit(vars(value))

    visit(event)
    return payloads


def _extract_retry_after_seconds(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if not retry_after:
        return None
    try:
        return max(1, int(float(retry_after)))
    except (TypeError, ValueError):
        return None


def _extract_status_error_details(exc: APIStatusError) -> tuple[str | None, str | None]:
    response = getattr(exc, "response", None)
    if response is None:
        return None, None

    try:
        payload = response.json()
    except Exception:
        return None, None

    if not isinstance(payload, dict):
        return None, None

    error = payload.get("error")
    if not isinstance(error, dict):
        return None, None

    code = error.get("code")
    message = error.get("message")
    return (
        str(code).strip() if code is not None else None,
        str(message).strip() if message is not None else None,
    )


def _map_openai_error(exc: Exception) -> ImageGenerationError:
    if isinstance(exc, RateLimitError):
        return ImageGenerationError(
            "rate_limited",
            str(exc),
            retryable=True,
            retry_after_seconds=_extract_retry_after_seconds(exc),
        )

    if isinstance(exc, AuthenticationError):
        return ImageGenerationError(
            "authentication_failed",
            str(exc),
            retryable=True,
            retry_after_seconds=600,
            disable_key=True,
        )

    if isinstance(exc, BadRequestError):
        return ImageGenerationError("bad_request", str(exc))

    if isinstance(exc, APIConnectionError):
        return ImageGenerationError(
            "upstream_unreachable",
            str(exc),
            retryable=True,
            retry_after_seconds=30,
        )

    if isinstance(exc, InternalServerError):
        return ImageGenerationError(
            "upstream_internal_error",
            str(exc),
            retryable=True,
            retry_after_seconds=30,
        )

    if isinstance(exc, APIStatusError):
        status_code = exc.status_code
        provider_code, provider_message = _extract_status_error_details(exc)
        normalized_provider_code = (provider_code or "").strip().lower()
        normalized_message = f"{provider_message or ''} {exc}".lower()

        if status_code in {401, 403}:
            return ImageGenerationError(
                "permission_denied" if status_code == 403 else "authentication_failed",
                str(exc),
                retryable=True,
                retry_after_seconds=600,
                disable_key=True,
            )

        if status_code == 404 and (
            normalized_provider_code == "modelnotopen"
            or "has not activated the model" in normalized_message
            or "activate the model service" in normalized_message
        ):
            return ImageGenerationError(
                "model_not_open",
                str(exc),
                retryable=True,
                disable_key=True,
            )

        retryable = status_code in {408, 409, 429, 500, 502, 503, 504}
        return ImageGenerationError(
            f"upstream_status_{status_code}",
            str(exc),
            retryable=retryable,
            retry_after_seconds=_extract_retry_after_seconds(exc),
        )

    if isinstance(exc, APIError):
        return ImageGenerationError(
            "upstream_api_error",
            str(exc),
            retryable=True,
            retry_after_seconds=30,
        )

    return ImageGenerationError("internal_error", str(exc))


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


@dataclass(slots=True)
class GenerationResult:
    primary_image_bytes: bytes
    candidate_image_bytes: list[bytes]


class BaseGenerator:
    model_name: str

    def generate(
        self,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        provider_key: ApiKeyLease | None = None,
        on_preview: PreviewCallback | None = None,
    ) -> GenerationResult:
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


def _rank_candidates(candidates: list[bytes]) -> list[CandidateScore]:
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
    logger.info("Selected Seedream candidate %s as final output", scored_candidates[0].index)
    return scored_candidates


class MockGenerator(BaseGenerator):
    model_name = "mock-image-generator"

    def generate(
        self,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        provider_key: ApiKeyLease | None = None,
        on_preview: PreviewCallback | None = None,
    ) -> GenerationResult:
        candidates: list[bytes] = []
        blur_levels = [10, 18, 26]
        portrait_offsets = [(160, 150), (170, 160), (185, 170)]
        preview_sent = False

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
                image_bytes = output.getvalue()
                candidates.append(image_bytes)
                if not preview_sent and on_preview is not None:
                    on_preview(image_bytes)
                    preview_sent = True

        ranked_candidates = _rank_candidates(candidates)
        ordered_images = [candidate.image_bytes for candidate in ranked_candidates]
        return GenerationResult(
            primary_image_bytes=ordered_images[0],
            candidate_image_bytes=ordered_images,
        )


class SeedreamGenerator(BaseGenerator):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.ark_api_keys:
            raise ImageGenerationError(
                "missing_api_key", "At least one Ark API key must be configured when using Seedream."
            )

        self.model_name = settings.ark_image_model
        self._base_url = settings.ark_base_url
        self._clients: dict[str, OpenAI] = {}
        self._client_lock = Lock()

    def _client_for_key(self, provider_key: ApiKeyLease) -> OpenAI:
        with self._client_lock:
            client = self._clients.get(provider_key.key_id)
            if client is not None:
                return client
            client = OpenAI(
                base_url=self._base_url,
                api_key=provider_key.api_key,
            )
            self._clients[provider_key.key_id] = client
            return client

    def _build_stream(
        self,
        *,
        client: OpenAI,
        prompt: str,
        image_data: str,
        max_images: int,
    ):
        return client.images.generate(
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
                    "max_images": max_images,
                },
            },
        )

    def _collect_stream_candidates(
        self,
        *,
        client: OpenAI,
        prompt: str,
        image_data: str,
        max_images: int,
        on_first_candidate: PreviewCallback | None = None,
    ) -> list[bytes]:
        candidates: list[bytes] = []
        seen_payloads: set[str] = set()
        stream = self._build_stream(
            client=client,
            prompt=prompt,
            image_data=image_data,
            max_images=max_images,
        )
        preview_sent = False

        for event in stream:
            if event is None:
                continue
            for payload in _extract_b64_payloads(event):
                if payload in seen_payloads:
                    continue
                seen_payloads.add(payload)
                image_bytes = base64.b64decode(payload)
                candidates.append(image_bytes)
                if not preview_sent and on_first_candidate is not None:
                    on_first_candidate(image_bytes)
                    preview_sent = True
        return candidates

    def _top_up_candidates(
        self,
        *,
        client: OpenAI,
        prompt: str,
        image_data: str,
        existing_count: int,
        on_first_candidate: PreviewCallback | None = None,
    ) -> list[bytes]:
        topped_up: list[bytes] = []
        for index in range(existing_count + 1, CANDIDATE_IMAGE_COUNT + 1):
            variant_prompt = (
                f"{prompt}\n"
                f"候选图补充说明：这是第 {index} 张候选图，保持同一人物与核心设定一致，"
                "允许表情、动作、头部角度和视线方向有自然差异。"
            )
            extra_candidates = self._collect_stream_candidates(
                client=client,
                prompt=variant_prompt,
                image_data=image_data,
                max_images=1,
                on_first_candidate=on_first_candidate,
            )
            if not extra_candidates:
                logger.warning("Seedream top-up request %s returned no candidate.", index)
                continue
            topped_up.append(extra_candidates[0])
        return topped_up

    def generate(
        self,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        provider_key: ApiKeyLease | None = None,
        on_preview: PreviewCallback | None = None,
    ) -> GenerationResult:
        if provider_key is None:
            settings = get_settings()
            if not settings.ark_api_keys:
                raise ImageGenerationError(
                    "missing_api_key",
                    "At least one Ark API key must be configured when using Seedream.",
                )
            provider_key = ApiKeyLease(
                key_id=settings.ark_api_keys[0].key_id,
                api_key=settings.ark_api_keys[0].api_key,
            )

        with open(source_image_path, "rb") as handle:
            image_bytes = handle.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        preview_sent = False

        def emit_preview(candidate_bytes: bytes) -> None:
            nonlocal preview_sent
            if preview_sent or on_preview is None:
                return
            on_preview(candidate_bytes)
            preview_sent = True

        suffix = Path(source_image_path).suffix.lower()
        mime_type = "image/png" if suffix == ".png" else "image/jpeg"
        image_data = f"data:{mime_type};base64,{image_base64}"
        client = self._client_for_key(provider_key)

        try:
            candidates = self._collect_stream_candidates(
                client=client,
                prompt=prompt,
                image_data=image_data,
                max_images=PRIMARY_PREVIEW_IMAGE_COUNT,
                on_first_candidate=emit_preview,
            )
        except (
            RateLimitError,
            AuthenticationError,
            BadRequestError,
            APIConnectionError,
            InternalServerError,
            APIStatusError,
            APIError,
        ) as exc:
            raise _map_openai_error(exc) from exc

        if len(candidates) < CANDIDATE_IMAGE_COUNT:
            logger.warning(
                "Seedream primary preview request returned %s candidate(s); topping up to %s.",
                len(candidates),
                CANDIDATE_IMAGE_COUNT,
            )
            try:
                candidates.extend(
                    self._top_up_candidates(
                        client=client,
                        prompt=prompt,
                        image_data=image_data,
                        existing_count=len(candidates),
                        on_first_candidate=emit_preview,
                    )
                )
            except (
                RateLimitError,
                AuthenticationError,
                BadRequestError,
                APIConnectionError,
                InternalServerError,
                APIStatusError,
                APIError,
            ) as exc:
                raise _map_openai_error(exc) from exc

        ranked_candidates = _rank_candidates(candidates)
        ordered_images = [candidate.image_bytes for candidate in ranked_candidates]
        return GenerationResult(
            primary_image_bytes=ordered_images[0],
            candidate_image_bytes=ordered_images,
        )


def build_generator() -> BaseGenerator:
    settings = get_settings()
    if settings.use_mock_generator:
        return MockGenerator()
    return SeedreamGenerator()
