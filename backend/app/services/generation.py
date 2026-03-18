from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.config import get_settings


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


class BaseGenerator:
    model_name: str

    def generate(self, source_image_path: str, prompt: str, context: GenerationContext) -> bytes:
        raise NotImplementedError


class MockGenerator(BaseGenerator):
    model_name = "mock-image-generator"

    def generate(self, source_image_path: str, prompt: str, context: GenerationContext) -> bytes:
        with Image.open(source_image_path).convert("RGB") as source:
            target = Image.new("RGB", (1200, 1600), "#101820")
            background = ImageOps.fit(source, target.size).filter(ImageFilter.GaussianBlur(18))
            target.paste(background)

            portrait = ImageOps.fit(source, (860, 1120))
            portrait = portrait.filter(ImageFilter.SHARPEN)
            target.paste(portrait, (170, 160))

            overlay = Image.new("RGBA", target.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            draw.rounded_rectangle((120, 1040, 1080, 1460), radius=40, fill=(15, 23, 42, 185))
            draw.text((170, 1090), "AI Hair Remix Preview", fill=(255, 255, 255))
            draw.text((170, 1150), f"Hair: {context.hairstyle_name}", fill=(204, 251, 241))
            draw.text((170, 1200), f"Scene: {context.scene_name}", fill=(191, 219, 254))
            draw.text((170, 1260), "Switch USE_MOCK_GENERATOR=false to call Seedream.", fill=(226, 232, 240))
            draw.text((170, 1310), "This placeholder verifies the upload-task-result flow.", fill=(226, 232, 240))
            target = Image.alpha_composite(target.convert("RGBA"), overlay).convert("RGB")

            output = io.BytesIO()
            target.save(output, format="PNG", optimize=True)
            return output.getvalue()


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
        stream = self._client.images.generate(
            model=self.model_name,
            prompt=prompt,
            size="2K",
            response_format="b64_json",
            stream=True,
            extra_body={
                "image": image_data,
                "watermark": True,
            },
        )

        for event in stream:
            if event is None:
                continue
            event_type = _event_field(event, "type")
            if event_type == "image_generation.partial_succeeded":
                payload = _event_field(event, "b64_json")
                if payload:
                    return base64.b64decode(payload)

        raise ImageGenerationError("upstream_empty", "Seedream returned no image payload.")


def build_generator() -> BaseGenerator:
    settings = get_settings()
    if settings.use_mock_generator:
        return MockGenerator()
    return SeedreamGenerator()
