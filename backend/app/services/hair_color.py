from __future__ import annotations

import colorsys
import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True, slots=True)
class HairColorEstimate:
    tone_id: str
    confidence: float
    sample_hex: str


DEFAULT_HAIR_COLOR_TONE = "natural_black"


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    red, green, blue = rgb
    return f"#{red:02X}{green:02X}{blue:02X}"


def _average_rgb(pixels: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    if not pixels:
        return (31, 26, 24)
    count = len(pixels)
    return (
        round(sum(pixel[0] for pixel in pixels) / count),
        round(sum(pixel[1] for pixel in pixels) / count),
        round(sum(pixel[2] for pixel in pixels) / count),
    )


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _pick_hair_like_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    left = max(0, int(width * 0.18))
    right = min(width, int(width * 0.82))
    top = max(0, int(height * 0.04))
    bottom = min(height, int(height * 0.42))
    crop = rgb_image.crop((left, top, right, bottom)).resize((120, 120))
    pixels = list(crop.getdata())
    usable = [
        pixel
        for pixel in pixels
        if max(pixel) < 245 and min(pixel) < 235
    ]
    if not usable:
        usable = pixels
    darkest = sorted(usable, key=_relative_luminance)
    keep_count = max(400, int(len(darkest) * 0.38))
    return darkest[:keep_count]


def _classify_tone(avg_rgb: tuple[int, int, int]) -> str:
    red, green, blue = avg_rgb
    hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    hue_degrees = hue * 360
    value_score = value * 255

    if value_score < 42 and saturation < 0.22:
        return "natural_black"
    if 190 <= hue_degrees <= 260 and value_score < 92:
        return "blue_black"
    if 18 <= hue_degrees <= 46 and value_score >= 150:
        return "linen_blonde" if saturation >= 0.3 else "honey_brown"
    if 15 <= hue_degrees <= 38 and saturation >= 0.32 and value_score >= 95:
        return "chestnut_brown"
    if saturation < 0.18 and value_score >= 72:
        return "ash_brown"
    if 18 <= hue_degrees <= 42 and value_score >= 82:
        return "mocha_brown"
    if 12 <= hue_degrees <= 45 and value_score >= 64:
        return "dark_brown"
    if value_score >= 120:
        return "honey_brown"
    return DEFAULT_HAIR_COLOR_TONE


def estimate_hair_color(image_bytes: bytes) -> HairColorEstimate | None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            pixels = _pick_hair_like_pixels(image)
    except (UnidentifiedImageError, OSError):
        return None

    if not pixels:
        return None

    avg_rgb = _average_rgb(pixels)
    tone_id = _classify_tone(avg_rgb)
    luminance = _relative_luminance(avg_rgb)
    confidence = 0.62
    if luminance < 48 or luminance > 150:
        confidence += 0.1
    if max(avg_rgb) - min(avg_rgb) > 18:
        confidence += 0.08
    if len(pixels) > 1200:
        confidence += 0.05

    return HairColorEstimate(
        tone_id=tone_id,
        confidence=round(min(confidence, 0.95), 2),
        sample_hex=_rgb_to_hex(avg_rgb),
    )
