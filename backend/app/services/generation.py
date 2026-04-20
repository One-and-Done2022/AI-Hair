from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable

import cv2
import httpx
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
from app.services.concurrency_limiter import concurrency_slot
from app.services.key_pool import ApiKeyLease
from app.services import provider_alerts, provider_routing


logger = logging.getLogger(__name__)
CANDIDATE_IMAGE_COUNT = 3
PRIMARY_PREVIEW_IMAGE_COUNT = 1
PreviewCallback = Callable[[bytes], None]
CandidateCallback = Callable[[bytes], None]
NANO_IMAGE_TIMEOUT_MAP = {"512px": 40, "1K": 60, "2K": 100, "4K": 120}
CHAT_COMPLETION_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
CHAT_COMPLETION_MAX_ATTEMPTS = 1
NANO_ROUTE2_TIMEOUT_SECONDS = 150
NANO_ROUTE2_FAST_RETRY_WINDOW_SECONDS = 10
NANO_ROUTE2_MAX_ATTEMPTS = 2
NANO_PROFILE_RETRY_BACKOFF_SECONDS = 180
SEEDREAM_REST_TIMEOUT_SECONDS = 180
_PROVIDER_BACKOFF_UNTIL: dict[str, float] = {}
_PROVIDER_BACKOFF_LOCK = Lock()
SCENE_ONLY_FROZEN_HAIR_GUARD = (
    "场景阶段执行优先级：直接沿用参考图中已经完成的当前头发成片，把整个头发区域视为冻结区域，"
    "不要重新生成、不要重新设计、不要重新定型；只允许修改场景、服装、妆容和人物微表情。"
)


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


def _ensure_provider_entry_enabled(provider_id: str, entry_id: str) -> None:
    try:
        provider_routing.ensure_entry_enabled(provider_id, entry_id)
    except provider_routing.ProviderRoutingError as exc:
        raise ImageGenerationError("provider_disabled", str(exc)) from exc


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

        if status_code == 429 and (
            normalized_provider_code == "setlimitexceeded"
            or "setlimitexceeded" in normalized_message
            or "set limit exceeded" in normalized_message
        ):
            return ImageGenerationError(
                "set_limit_exceeded",
                str(exc),
                retryable=True,
                retry_after_seconds=max(_extract_retry_after_seconds(exc) or 0, 3600),
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
    aspect_ratio: str = "3:4"
    resolution: str | None = "4K"
    image_count: int = CANDIDATE_IMAGE_COUNT
    full_prompt: str = ""
    hairstyle_only_prompt: str = ""
    scene_only_prompt: str = ""


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
    supports_key_pool: bool = False

    def generate(
        self,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        provider_key: ApiKeyLease | None = None,
        on_preview: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
    ) -> GenerationResult:
        raise NotImplementedError


def _normalize_prompt_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _is_scene_only_generation(prompt: str, context: GenerationContext | None) -> bool:
    scene_only_prompt = _normalize_prompt_text(getattr(context, "scene_only_prompt", ""))
    if not scene_only_prompt:
        return False
    current_prompt = _normalize_prompt_text(prompt)
    return (
        current_prompt == scene_only_prompt
        or current_prompt.endswith(scene_only_prompt)
        or scene_only_prompt in current_prompt
    )


def _build_generation_prompt(
    prompt: str,
    context: GenerationContext | None,
    *,
    candidate_index: int = 1,
) -> str:
    base_prompt = str(prompt or "")
    if _is_scene_only_generation(base_prompt, context):
        if SCENE_ONLY_FROZEN_HAIR_GUARD not in base_prompt:
            base_prompt = f"{SCENE_ONLY_FROZEN_HAIR_GUARD}\n{base_prompt}"
        if candidate_index > 1:
            return (
                f"{base_prompt}\n"
                f"候选图补充说明：这是第 {candidate_index} 张候选图，继续保持同一人物、同一头发成片和同一头部大轮廓；"
                "只允许表情、视线、手势和场景细节有轻微自然差异，"
                "不要改变头部朝向幅度，不要改变发型、刘海、分线、发色、发尾落点和头发遮挡关系。"
            )
        return base_prompt

    if candidate_index > 1:
        return (
            f"{base_prompt}\n"
            f"候选图补充说明：这是第 {candidate_index} 张候选图，保持同一人物与核心设定一致，"
            "允许表情、动作、头部角度和视线方向有自然差异。"
        )
    return base_prompt


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
    supports_key_pool = False

    def generate(
        self,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        provider_key: ApiKeyLease | None = None,
        on_preview: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
    ) -> GenerationResult:
        candidates: list[bytes] = []
        blur_levels = [10, 18, 26]
        portrait_offsets = [(160, 150), (170, 160), (185, 170)]
        preview_sent = False
        requested_count = max(1, int(context.image_count or CANDIDATE_IMAGE_COUNT))

        with Image.open(source_image_path).convert("RGB") as source:
            for idx in range(requested_count):
                target = Image.new("RGB", (1200, 1600), "#101820")
                background = ImageOps.fit(source, target.size).filter(
                    ImageFilter.GaussianBlur(blur_levels[idx % len(blur_levels)])
                )
                target.paste(background)

                portrait = ImageOps.fit(source, (860, 1120))
                portrait = portrait.filter(ImageFilter.SHARPEN)
                target.paste(portrait, portrait_offsets[idx % len(portrait_offsets)])

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
                if on_candidate is not None:
                    on_candidate(image_bytes)

        ordered_images = candidates if requested_count <= 2 else [
            candidate.image_bytes for candidate in _rank_candidates(candidates)
        ]
        return GenerationResult(
            primary_image_bytes=ordered_images[0],
            candidate_image_bytes=ordered_images,
        )


class SeedreamGenerator(BaseGenerator):
    supports_key_pool = True

    def __init__(self, model_name: str | None = None, entry_id: str | None = None) -> None:
        settings = get_settings()
        if not settings.ark_api_keys:
            raise ImageGenerationError(
                "missing_api_key", "At least one Ark API key must be configured when using Seedream."
            )

        self.entry_id = (
            str(entry_id or provider_routing.seedream_entry_id_for_model(model_name, settings) or "premium")
            .strip()
            .lower()
        )
        self.model_name = (
            model_name or provider_routing.seedream_model_name_for_entry(self.entry_id, settings)
        ).strip()
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

    def _uses_rest_generation_api(self) -> bool:
        return self.model_name.startswith("doubao-seedream-5-0")

    def _rest_generation_endpoint(self) -> str:
        return f"{self._base_url.rstrip('/')}/images/generations"

    def _rest_generation_size(self, resolution: str | None) -> str:
        normalized = (resolution or "").strip().upper()
        if normalized in {"1K", "2K"}:
            return normalized
        return "2K"

    def _download_generated_image(self, url: str) -> bytes:
        try:
            response = httpx.get(url, timeout=SEEDREAM_REST_TIMEOUT_SECONDS)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ImageGenerationError(
                "upstream_timeout",
                "Seedream generated image download timed out.",
                retryable=True,
                retry_after_seconds=30,
            ) from exc
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                "upstream_unreachable",
                str(exc),
                retryable=True,
                retry_after_seconds=30,
            ) from exc
        return response.content

    def _generate_single_rest_candidate(
        self,
        *,
        provider_key: ApiKeyLease,
        prompt: str,
        image_data: str,
        resolution: str | None,
    ) -> bytes:
        request_payload = {
            "model": self.model_name,
            "prompt": prompt,
            "image": image_data,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "size": self._rest_generation_size(resolution),
            "stream": False,
            "watermark": True,
        }

        try:
            response = httpx.post(
                self._rest_generation_endpoint(),
                headers={
                    "Authorization": f"Bearer {provider_key.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=SEEDREAM_REST_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise ImageGenerationError(
                "upstream_timeout",
                "Seedream request timed out.",
                retryable=True,
                retry_after_seconds=30,
            ) from exc
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                "upstream_unreachable",
                str(exc),
                retryable=True,
                retry_after_seconds=30,
            ) from exc

        if response.status_code >= 400:
            raise _map_seedream_http_error(response)

        payload = response.json()
        image_bytes = _extract_image_bytes_from_generation_payload(payload)
        if image_bytes:
            return image_bytes[0]

        image_urls = _extract_image_urls_from_generation_payload(payload)
        if image_urls:
            return self._download_generated_image(image_urls[0])

        raise ImageGenerationError(
            "upstream_empty",
            "Seedream returned no image payload.",
        )

    def _generate_via_rest_api(
        self,
        *,
        provider_key: ApiKeyLease,
        prompt: str,
        image_data: str,
        context: GenerationContext,
        on_preview: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
    ) -> GenerationResult:
        preview_sent = False
        candidates: list[bytes] = []
        requested_count = max(1, int(context.image_count or CANDIDATE_IMAGE_COUNT))

        for index in range(requested_count):
            candidate_prompt = _build_generation_prompt(
                prompt,
                context,
                candidate_index=index + 1,
            )
            candidate_bytes = self._generate_single_rest_candidate(
                provider_key=provider_key,
                prompt=candidate_prompt,
                image_data=image_data,
                resolution=context.resolution,
            )
            candidates.append(candidate_bytes)
            if not preview_sent and on_preview is not None:
                on_preview(candidate_bytes)
                preview_sent = True
            if on_candidate is not None:
                on_candidate(candidate_bytes)

        ordered_images = candidates if requested_count <= 2 else [
            candidate.image_bytes for candidate in _rank_candidates(candidates)
        ]
        return GenerationResult(
            primary_image_bytes=ordered_images[0],
            candidate_image_bytes=ordered_images,
        )

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
        on_candidate: CandidateCallback | None = None,
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
                if on_candidate is not None:
                    on_candidate(image_bytes)
        return candidates

    def _top_up_candidates(
        self,
        *,
        client: OpenAI,
        prompt: str,
        image_data: str,
        context: GenerationContext,
        existing_count: int,
        target_count: int,
        on_first_candidate: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
    ) -> list[bytes]:
        topped_up: list[bytes] = []
        for index in range(existing_count + 1, target_count + 1):
            variant_prompt = _build_generation_prompt(
                prompt,
                context,
                candidate_index=index,
            )
            extra_candidates = self._collect_stream_candidates(
                client=client,
                prompt=variant_prompt,
                image_data=image_data,
                max_images=1,
                on_first_candidate=on_first_candidate,
                on_candidate=on_candidate,
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
        on_candidate: CandidateCallback | None = None,
        enforce_enabled: bool = True,
    ) -> GenerationResult:
        if enforce_enabled:
            _ensure_provider_entry_enabled("seedream", self.entry_id)
        if provider_key is None:
            settings = get_settings()
            eligible_credentials = settings.ark_api_keys_for_model(self.model_name)
            if not eligible_credentials:
                raise ImageGenerationError(
                    "missing_api_key",
                    f"No Ark API key is allowed for Seedream model {self.model_name}.",
                )
            provider_key = ApiKeyLease(
                key_id=eligible_credentials[0].key_id,
                api_key=eligible_credentials[0].api_key,
            )
        context = context or GenerationContext(
            hairstyle_name="",
            scene_name="",
        )
        requested_count = max(1, int(context.image_count or CANDIDATE_IMAGE_COUNT))

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
        prepared_prompt = _build_generation_prompt(prompt, context, candidate_index=1)
        if self._uses_rest_generation_api():
            return self._generate_via_rest_api(
                provider_key=provider_key,
                prompt=prepared_prompt,
                image_data=image_data,
                context=context,
                on_preview=emit_preview,
                on_candidate=on_candidate,
            )

        client = self._client_for_key(provider_key)

        try:
            candidates = self._collect_stream_candidates(
                client=client,
                prompt=prepared_prompt,
                image_data=image_data,
                max_images=min(PRIMARY_PREVIEW_IMAGE_COUNT, requested_count),
                on_first_candidate=emit_preview,
                on_candidate=on_candidate,
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

        if len(candidates) < requested_count:
            logger.warning(
                "Seedream primary preview request returned %s candidate(s); topping up to %s.",
                len(candidates),
                requested_count,
            )
            try:
                candidates.extend(
                    self._top_up_candidates(
                        client=client,
                        prompt=prepared_prompt,
                        image_data=image_data,
                        context=context,
                        existing_count=len(candidates),
                        target_count=requested_count,
                        on_first_candidate=emit_preview,
                        on_candidate=on_candidate,
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

        ordered_images = candidates if requested_count <= 2 else [
            candidate.image_bytes for candidate in _rank_candidates(candidates)
        ]
        return GenerationResult(
            primary_image_bytes=ordered_images[0],
            candidate_image_bytes=ordered_images,
        )


def _guess_mime_type_from_path(source_image_path: str) -> str:
    suffix = Path(source_image_path).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def _extract_inline_image_bytes(payload) -> list[bytes]:
    images: list[bytes] = []

    def visit(value) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            inline = value.get("inlineData") or value.get("inline_data")
            if isinstance(inline, dict):
                data = inline.get("data")
                if isinstance(data, str) and data:
                    images.append(base64.b64decode(data))
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return images


def _extract_image_bytes_from_generation_payload(payload: dict) -> list[bytes]:
    images: list[bytes] = []
    data = payload.get("data")
    if not isinstance(data, list):
        return images

    for item in data:
        if not isinstance(item, dict):
            continue
        b64_json = item.get("b64_json")
        if isinstance(b64_json, str) and b64_json:
            images.append(base64.b64decode(b64_json))
    return images


def _extract_image_urls_from_generation_payload(payload: dict) -> list[str]:
    urls: list[str] = []
    data = payload.get("data")
    if not isinstance(data, list):
        return urls

    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            urls.append(url)
    return urls


def _extract_first_remote_image_url(payload: dict) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return None
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            match = re.search(r"https?://\S+", content)
            if match:
                return match.group(0).rstrip(")]}>\"'")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                image_url = item.get("image_url")
                if isinstance(image_url, dict):
                    url = image_url.get("url")
                    if isinstance(url, str) and url.startswith(("http://", "https://")):
                        return url
                text = item.get("text")
                if isinstance(text, str):
                    match = re.search(r"https?://\S+", text)
                    if match:
                        return match.group(0).rstrip(")]}>\"'")
    return None


def _extract_markdown_image_url(payload: dict) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return None
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        match = re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", content)
        if match:
            return match.group(1)
    return None


def _extract_nano_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
    return response.text or f"HTTP {response.status_code}"


def _is_no_available_channel_message(message: str) -> bool:
    normalized_message = str(message or "").strip().lower()
    if not normalized_message:
        return False
    return any(
        keyword in normalized_message
        for keyword in (
            "无可用渠道",
            "无可用通道",
            "no available channel",
            "no available channels",
            "no available provider",
            "no available providers",
        )
    )


def _map_nano_http_error(response: httpx.Response) -> ImageGenerationError:
    message = _extract_nano_error_message(response)
    normalized_message = message.lower()
    quota_keywords = (
        "quota",
        "insufficient",
        "balance",
        "credit",
        "额度",
        "余额",
        "用完",
        "耗尽",
        "exhausted",
    )
    if response.status_code == 402 or any(keyword in normalized_message for keyword in quota_keywords):
        return ImageGenerationError(
            "quota_exhausted",
            message,
            retryable=True,
            retry_after_seconds=3600,
        )
    if response.status_code in {401, 403}:
        return ImageGenerationError("authentication_failed", message)
    if response.status_code == 400:
        return ImageGenerationError("bad_request", message)
    if response.status_code in {500, 503} and _is_no_available_channel_message(message):
        return ImageGenerationError(
            "provider_unavailable",
            "当前换发线路暂无可用渠道，请稍后再试。",
            retryable=True,
            retry_after_seconds=300,
        )
    if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
        return ImageGenerationError(
            f"upstream_status_{response.status_code}",
            message,
            retryable=True,
            retry_after_seconds=30,
        )
    return ImageGenerationError(
        f"upstream_status_{response.status_code}",
        message,
    )


def _map_seedream_http_error(response: httpx.Response) -> ImageGenerationError:
    message = _extract_nano_error_message(response)
    normalized_message = message.lower()
    if response.status_code in {401, 403}:
        return ImageGenerationError(
            "authentication_failed",
            message,
            retryable=True,
            retry_after_seconds=600,
            disable_key=True,
        )
    if response.status_code == 400:
        return ImageGenerationError("bad_request", message)
    if response.status_code == 429 and (
        "setlimitexceeded" in normalized_message
        or "set inference limit" in normalized_message
        or "safe experience mode" in normalized_message
    ):
        return ImageGenerationError(
            "set_limit_exceeded",
            message,
            retryable=True,
            retry_after_seconds=3600,
            disable_key=True,
        )
    if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
        return ImageGenerationError(
            f"upstream_status_{response.status_code}",
            message,
            retryable=True,
            retry_after_seconds=30,
        )
    return ImageGenerationError(
        f"upstream_status_{response.status_code}",
        message,
    )


class ApiYiImageGenerator(BaseGenerator):
    supports_key_pool = False

    @dataclass(frozen=True, slots=True)
    class ProviderProfile:
        profile_id: str
        profile_label: str
        api_key: str
        base_url: str
        limiter_name: str
        protocol: str
        model_name: str

    def __init__(
        self,
        *,
        profiles: tuple[tuple[str, str, str, str, str, str], ...],
        model_name: str,
        provider_name: str,
        api_key_env_name: str,
        max_concurrency: int,
        routing_provider_id: str | None = None,
    ) -> None:
        if not profiles:
            raise ImageGenerationError(
                "missing_api_key",
                f"{api_key_env_name} must be configured when using {provider_name}.",
            )
        self.model_name = model_name
        self.provider_name = provider_name
        self._routing_provider_id = (routing_provider_id or "").strip() or None
        self._max_concurrency = max(1, int(max_concurrency))
        self._profiles = tuple(
            self.ProviderProfile(
                profile_id=profile_id,
                profile_label=profile_label,
                api_key=api_key,
                base_url=base_url.rstrip("/"),
                limiter_name=(
                    f"{provider_name}:"
                    f"{hashlib.sha1(f'{profile_id}|{base_url}|{api_key}|{protocol}|{profile_model_name}'.encode('utf-8')).hexdigest()[:12]}"
                ),
                protocol=protocol,
                model_name=profile_model_name.strip() or model_name,
            )
            for profile_id, profile_label, base_url, api_key, protocol, profile_model_name in profiles
            if base_url.strip() and api_key.strip()
        )
        if not self._profiles:
            raise ImageGenerationError(
                "missing_api_key",
                f"{api_key_env_name} must be configured when using {provider_name}.",
            )

    def _endpoint(self, profile: ProviderProfile) -> str:
        if profile.protocol == "openai_chat_markdown":
            if profile.base_url.endswith("/chat/completions"):
                return profile.base_url
            return f"{profile.base_url}/chat/completions"
        return f"{profile.base_url}/v1beta/models/{profile.model_name}:generateContent"

    def _runtime_profiles(self) -> tuple[ProviderProfile, ...]:
        if self._routing_provider_id:
            return provider_routing.apply_provider_entry_routing(
                self._routing_provider_id,
                self._profiles,
            )
        return self._profiles

    def _should_try_next_profile(
        self,
        profile: ProviderProfile,
        exc: ImageGenerationError,
    ) -> bool:
        if exc.code == "authentication_failed" or exc.retryable:
            return True

        return self._is_profile_compatibility_error(profile, exc)

    def _is_profile_compatibility_error(
        self,
        profile: ProviderProfile,
        exc: ImageGenerationError,
    ) -> bool:
        normalized_message = str(exc).strip().lower()
        return (
            self.provider_name == "nano-banana-pro"
            and exc.code == "bad_request"
            and "valid role" in normalized_message
            and profile.profile_id in {"route1", "route2"}
        )

    def _profile_backoff_key(self, profile: ProviderProfile) -> str:
        return f"{self.provider_name}:{profile.profile_id}"

    def _is_profile_backed_off(self, profile: ProviderProfile) -> bool:
        key = self._profile_backoff_key(profile)
        with _PROVIDER_BACKOFF_LOCK:
            until = _PROVIDER_BACKOFF_UNTIL.get(key)
            if until is None:
                return False
            if until <= time.time():
                _PROVIDER_BACKOFF_UNTIL.pop(key, None)
                return False
            return True

    def _set_profile_backoff(self, profile: ProviderProfile, seconds: int) -> None:
        key = self._profile_backoff_key(profile)
        with _PROVIDER_BACKOFF_LOCK:
            _PROVIDER_BACKOFF_UNTIL[key] = time.time() + max(1, seconds)

    def _clear_profile_backoff(self, profile: ProviderProfile) -> None:
        key = self._profile_backoff_key(profile)
        with _PROVIDER_BACKOFF_LOCK:
            _PROVIDER_BACKOFF_UNTIL.pop(key, None)

    def _profile_backoff_seconds(
        self,
        profile: ProviderProfile,
        exc: ImageGenerationError,
    ) -> int | None:
        if exc.code == "quota_exhausted":
            return exc.retry_after_seconds or 3600
        if exc.code == "provider_unavailable":
            return exc.retry_after_seconds or 300
        if exc.code == "authentication_failed":
            return exc.retry_after_seconds or 600
        if self._is_profile_compatibility_error(profile, exc):
            return exc.retry_after_seconds or NANO_PROFILE_RETRY_BACKOFF_SECONDS
        if exc.retryable:
            return exc.retry_after_seconds or NANO_PROFILE_RETRY_BACKOFF_SECONDS
        return None

    def _provider_alert_id(self, profile: ProviderProfile, alert_type: str) -> str:
        return f"{self.provider_name}:{profile.profile_id}:{alert_type}"

    def _notify_profile_quota_exhausted(self, profile: ProviderProfile) -> None:
        if self.provider_name != "nano-banana-pro":
            return
        if profile.profile_id not in {"route1", "route2"}:
            return
        provider_alerts.upsert_alert(
            alert_id=self._provider_alert_id(profile, "quota"),
            message=f"Nano Banana Pro {profile.profile_label}额度可能已用完，系统已自动切换到下一条线路。",
        )

    def _notify_profile_unavailable(self, profile: ProviderProfile) -> None:
        if self.provider_name != "nano-banana-pro":
            return
        if profile.profile_id in {"route1", "route2"}:
            message = (
                f"Nano Banana Pro {profile.profile_label}当前无可用渠道，系统已自动切换到下一条线路。"
            )
        else:
            message = "Nano Banana Pro 主线路当前无可用渠道，暂时无法生成，请稍后再试。"
        provider_alerts.upsert_alert(
            alert_id=self._provider_alert_id(profile, "availability"),
            message=message,
        )

    def _clear_profile_alerts(self, profile: ProviderProfile) -> None:
        provider_alerts.clear_alert(self._provider_alert_id(profile, "quota"))
        provider_alerts.clear_alert(self._provider_alert_id(profile, "availability"))

    @staticmethod
    def _prompt_with_ratio(prompt: str, aspect_ratio: str) -> str:
        ratio_tag = f"〖{aspect_ratio}〗"
        if ratio_tag in prompt:
            return prompt
        return f"{ratio_tag}\n{prompt}"

    def _request_timeout_seconds(
        self,
        profile: ProviderProfile,
        context: GenerationContext,
    ) -> int:
        timeout_seconds = NANO_IMAGE_TIMEOUT_MAP.get(context.resolution, 300)
        if (
            self.provider_name == "nano-banana-pro"
            and profile.profile_id == "route2"
            and profile.protocol == "openai_chat_markdown"
        ):
            return NANO_ROUTE2_TIMEOUT_SECONDS
        return timeout_seconds

    def _is_route2_chat_profile(self, profile: ProviderProfile) -> bool:
        return (
            self.provider_name == "nano-banana-pro"
            and profile.profile_id == "route2"
            and profile.protocol == "openai_chat_markdown"
        )

    def _chat_max_attempts(self, profile: ProviderProfile) -> int:
        if self._is_route2_chat_profile(profile):
            return NANO_ROUTE2_MAX_ATTEMPTS
        return CHAT_COMPLETION_MAX_ATTEMPTS

    def _should_retry_chat_request(
        self,
        *,
        profile: ProviderProfile,
        attempt: int,
        max_attempts: int,
        elapsed_seconds: float,
        status_code: int | None = None,
    ) -> bool:
        if attempt + 1 >= max_attempts:
            return False
        if not self._is_route2_chat_profile(profile):
            return False
        if elapsed_seconds > NANO_ROUTE2_FAST_RETRY_WINDOW_SECONDS:
            return False
        if status_code is None:
            return True
        return status_code in CHAT_COMPLETION_RETRYABLE_STATUS_CODES

    def _generate_via_chat_markdown(
        self,
        *,
        profile: ProviderProfile,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        on_preview: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
    ) -> GenerationResult:
        with open(source_image_path, "rb") as handle:
            image_bytes = handle.read()

        mime_type = _guess_mime_type_from_path(source_image_path)
        data_url = (
            f"data:{mime_type};base64,"
            f"{base64.b64encode(image_bytes).decode('utf-8')}"
        )
        request_payload = {
            "model": profile.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self._prompt_with_ratio(prompt, context.aspect_ratio),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
        }

        timeout_seconds = self._request_timeout_seconds(profile, context)
        max_attempts = self._chat_max_attempts(profile)
        response = None
        for attempt in range(max_attempts):
            attempt_started = time.perf_counter()
            try:
                with concurrency_slot(profile.limiter_name, self._max_concurrency):
                    response = httpx.post(
                        self._endpoint(profile),
                        headers={
                            "Authorization": f"Bearer {profile.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request_payload,
                        timeout=timeout_seconds,
                    )
            except httpx.TimeoutException as exc:
                elapsed_seconds = time.perf_counter() - attempt_started
                if self._should_retry_chat_request(
                    profile=profile,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    elapsed_seconds=elapsed_seconds,
                ):
                    logger.warning(
                        "%s chat route %s timed out in %.2fs; retrying once.",
                        self.provider_name,
                        profile.profile_id,
                        elapsed_seconds,
                    )
                    continue
                raise ImageGenerationError(
                    "upstream_timeout",
                    f"{self.provider_name} request timed out.",
                    retryable=True,
                    retry_after_seconds=30,
                ) from exc
            except httpx.HTTPError as exc:
                elapsed_seconds = time.perf_counter() - attempt_started
                if self._should_retry_chat_request(
                    profile=profile,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    elapsed_seconds=elapsed_seconds,
                ):
                    logger.warning(
                        "%s chat route %s hit transport error in %.2fs; retrying once: %s",
                        self.provider_name,
                        profile.profile_id,
                        elapsed_seconds,
                        exc,
                    )
                    continue
                raise ImageGenerationError(
                    "upstream_unreachable",
                    str(exc),
                    retryable=True,
                    retry_after_seconds=30,
                ) from exc

            if response.status_code < 400:
                break

            mapped_error = _map_nano_http_error(response)
            elapsed_seconds = time.perf_counter() - attempt_started
            if self._should_retry_chat_request(
                profile=profile,
                attempt=attempt,
                max_attempts=max_attempts,
                elapsed_seconds=elapsed_seconds,
                status_code=response.status_code,
            ):
                logger.warning(
                    "%s chat route %s returned %s in %.2fs; retrying once.",
                    self.provider_name,
                    profile.profile_id,
                    response.status_code,
                    elapsed_seconds,
                )
                continue
            raise mapped_error

        if response is None:
            raise ImageGenerationError(
                "upstream_unreachable",
                f"{self.provider_name} returned no response.",
                retryable=True,
                retry_after_seconds=30,
            )

        payload = response.json()
        remote_url = _extract_first_remote_image_url(payload)
        if not remote_url:
            remote_url = _extract_markdown_image_url(payload)
        if not remote_url:
            raise ImageGenerationError(
                "upstream_empty",
                f"{self.provider_name} returned no downloadable image url.",
            )

        try:
            image_response = httpx.get(remote_url, timeout=120)
            image_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                "upstream_unreachable",
                str(exc),
                retryable=True,
                retry_after_seconds=30,
            ) from exc

        primary_image = image_response.content
        if on_preview is not None:
            on_preview(primary_image)
        if on_candidate is not None:
            on_candidate(primary_image)
        return GenerationResult(
            primary_image_bytes=primary_image,
            candidate_image_bytes=[primary_image],
        )

    def _generate_once(
        self,
        *,
        profile: ProviderProfile,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        on_preview: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
    ) -> GenerationResult:
        if profile.protocol == "openai_chat_markdown":
            return self._generate_via_chat_markdown(
                profile=profile,
                source_image_path=source_image_path,
                prompt=prompt,
                context=context,
                on_preview=on_preview,
                on_candidate=on_candidate,
            )
        with open(source_image_path, "rb") as handle:
            image_bytes = handle.read()

        request_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": _guess_mime_type_from_path(source_image_path),
                                "data": base64.b64encode(image_bytes).decode("utf-8"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": context.aspect_ratio,
                    "imageSize": context.resolution,
                },
            },
        }

        timeout_seconds = NANO_IMAGE_TIMEOUT_MAP.get(context.resolution, 300)
        try:
            with concurrency_slot(profile.limiter_name, self._max_concurrency):
                response = httpx.post(
                    self._endpoint(profile),
                    headers={
                        "Authorization": f"Bearer {profile.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                    timeout=timeout_seconds,
                )
        except httpx.TimeoutException as exc:
            raise ImageGenerationError(
                "upstream_timeout",
                f"{self.provider_name} request timed out.",
                retryable=True,
                retry_after_seconds=30,
            ) from exc
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                "upstream_unreachable",
                str(exc),
                retryable=True,
                retry_after_seconds=30,
            ) from exc

        if response.status_code >= 400:
            raise _map_nano_http_error(response)

        images = _extract_inline_image_bytes(response.json())
        if not images:
            raise ImageGenerationError(
                "upstream_empty",
                f"{self.provider_name} returned no image payload.",
            )

        primary_image = images[0]
        if on_preview is not None:
            on_preview(primary_image)
        if on_candidate is not None:
            on_candidate(primary_image)

        return GenerationResult(
            primary_image_bytes=primary_image,
            candidate_image_bytes=[primary_image],
        )

    def generate(
        self,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        provider_key: ApiKeyLease | None = None,
        on_preview: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
    ) -> GenerationResult:
        runtime_profiles = self._runtime_profiles()
        if not runtime_profiles:
            raise ImageGenerationError(
                "provider_disabled",
                f"No enabled provider profiles are configured for {self.provider_name}.",
            )
        available_profiles = [
            profile for profile in runtime_profiles if not self._is_profile_backed_off(profile)
        ]
        if not available_profiles:
            available_profiles = list(runtime_profiles)

        last_error: ImageGenerationError | None = None

        for index, profile in enumerate(available_profiles):
            try:
                result = self._generate_once(
                    profile=profile,
                    source_image_path=source_image_path,
                    prompt=prompt,
                    context=context,
                    on_preview=on_preview,
                    on_candidate=on_candidate,
                )
                self._clear_profile_backoff(profile)
                self._clear_profile_alerts(profile)
                return result
            except ImageGenerationError as exc:
                last_error = exc
                backoff_seconds = self._profile_backoff_seconds(profile, exc)
                if backoff_seconds is not None:
                    self._set_profile_backoff(profile, backoff_seconds)
                if exc.code == "quota_exhausted":
                    self._notify_profile_quota_exhausted(profile)
                elif exc.code == "provider_unavailable":
                    self._notify_profile_unavailable(profile)
                has_next_profile = index < len(available_profiles) - 1
                if not has_next_profile or not self._should_try_next_profile(profile, exc):
                    raise
                logger.warning(
                    "%s failed on provider profile %s/%s (%s); falling back to next profile.",
                    self.provider_name,
                    index + 1,
                    len(available_profiles),
                    exc.code,
                )

        if last_error is not None:
            raise last_error
        raise ImageGenerationError(
            "missing_api_key",
            f"No usable provider profiles are configured for {self.provider_name}.",
        )


class NanoBananaProGenerator(ApiYiImageGenerator):
    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            profiles=settings.nano_banana_pro_profiles(),
            model_name=settings.nano_banana_pro_model,
            provider_name="nano-banana-pro",
            api_key_env_name="NANO_BANANA_PRO_PRIMARY_API_KEY",
            max_concurrency=settings.nano_banana_pro_max_concurrency,
            routing_provider_id="nano_banana_pro",
        )


class NanoBanana2Generator(ApiYiImageGenerator):
    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            profiles=(
                (
                    "primary",
                    "主线路",
                    settings.nano_banana_2_base_url,
                    settings.nano_banana_2_api_key,
                    "gemini_v1beta",
                    settings.nano_banana_2_model,
                ),
            ),
            model_name=settings.nano_banana_2_model,
            provider_name="nano-banana-2",
            api_key_env_name="NANO_BANANA_2_API_KEY",
            max_concurrency=settings.nano_banana_2_max_concurrency,
            routing_provider_id="nano_banana_2",
        )


class SoraImageGenerator(BaseGenerator):
    supports_key_pool = False

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.sora_image_api_key:
            raise ImageGenerationError(
                "missing_api_key",
                "SORA_IMAGE_API_KEY must be configured when using sora-image.",
            )
        self._entry_id = "primary"
        self._api_key = settings.sora_image_api_key
        self._base_url = settings.sora_image_base_url
        self.model_name = settings.sora_image_model

    def _endpoint(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _prompt_with_ratio(self, prompt: str, aspect_ratio: str) -> str:
        ratio_tag = f"〖{aspect_ratio}〗"
        if ratio_tag in prompt:
            return prompt
        return f"{ratio_tag}\n{prompt}"

    def generate(
        self,
        source_image_path: str,
        prompt: str,
        context: GenerationContext,
        provider_key: ApiKeyLease | None = None,
        on_preview: PreviewCallback | None = None,
        on_candidate: CandidateCallback | None = None,
        enforce_enabled: bool = True,
    ) -> GenerationResult:
        if enforce_enabled:
            _ensure_provider_entry_enabled("sora_image", self._entry_id)
        with open(source_image_path, "rb") as handle:
            image_bytes = handle.read()

        mime_type = _guess_mime_type_from_path(source_image_path)
        data_url = (
            f"data:{mime_type};base64,"
            f"{base64.b64encode(image_bytes).decode('utf-8')}"
        )
        request_payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self._prompt_with_ratio(prompt, context.aspect_ratio),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
        }

        try:
            response = httpx.post(
                self._endpoint(),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=180,
            )
        except httpx.TimeoutException as exc:
            raise ImageGenerationError(
                "upstream_timeout",
                "sora-image request timed out.",
                retryable=True,
                retry_after_seconds=30,
            ) from exc
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                "upstream_unreachable",
                str(exc),
                retryable=True,
                retry_after_seconds=30,
            ) from exc

        if response.status_code >= 400:
            raise _map_nano_http_error(response)

        remote_url = _extract_first_remote_image_url(response.json())
        if not remote_url:
            raise ImageGenerationError(
                "upstream_empty",
                "sora-image returned no downloadable image url.",
            )

        try:
            image_response = httpx.get(remote_url, timeout=120)
            image_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ImageGenerationError(
                "upstream_unreachable",
                str(exc),
                retryable=True,
                retry_after_seconds=30,
            ) from exc

        primary_image = image_response.content
        if on_preview is not None:
            on_preview(primary_image)
        if on_candidate is not None:
            on_candidate(primary_image)

        return GenerationResult(
            primary_image_bytes=primary_image,
            candidate_image_bytes=[primary_image],
        )


def build_generator(backend: str | None = None) -> BaseGenerator:
    settings = get_settings()
    if settings.use_mock_generator:
        return MockGenerator()
    resolved_backend = (backend or settings.image_generator_backend).strip().lower()
    if resolved_backend == "seedream_basic":
        return SeedreamGenerator(model_name=settings.seedream_basic_model, entry_id="basic")
    if resolved_backend == "seedream_premium":
        return SeedreamGenerator(model_name=settings.seedream_premium_model, entry_id="premium")
    if resolved_backend == "seedream":
        entry_id = provider_routing.first_enabled_entry_id("seedream") or "premium"
        return SeedreamGenerator(entry_id=entry_id)
    if resolved_backend == "nano_banana_pro":
        return NanoBananaProGenerator()
    if resolved_backend == "nano_banana_2":
        return NanoBanana2Generator()
    if resolved_backend == "sora_image":
        return SoraImageGenerator()
    raise ValueError(f"Unsupported generator backend: {resolved_backend}")
