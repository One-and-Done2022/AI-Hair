from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.services import storage, templates

PAGE_SIZE = (1240, 1754)
PAGE_BACKGROUND = "#F7F4EE"
CARD_BACKGROUND = "#FFFFFF"
CARD_BORDER = "#DED7CB"
TEXT_PRIMARY = "#1F2933"
TEXT_SECONDARY = "#52606D"
ACCENT = "#8B6F47"
SWATCH_BORDER = "#E9E2D7"
ITEMS_PER_PAGE = 6
REFERENCE_PDF_FILENAME = "solugtor-hair-color-with-rgb-reference-latest.pdf"
STATIC_REFERENCE_SUBDIR = "reference_docs"
REPO_ROOT = Path(__file__).resolve().parents[3]
ASSET_REFERENCE_PDF_PATH = REPO_ROOT / "assets" / REFERENCE_PDF_FILENAME

SERIES_LABELS = {
    "base_color": "基色",
    "base_reference": "底色对照卡",
    "classic_cover": "经典盖白",
    "classic_green": "经典青系列",
    "classic_natural": "常规色系",
    "cool_mist": "烟熏冷雾系列",
    "icy_gloss": "冷雾莹彩系列",
    "is_multi_uniform": "IS多段统一",
    "mist_clear": "迷雾清透系列",
    "tool_color": "工具色系",
}

TEMPERATURE_LABELS = {
    "cool": "冷调",
    "neutral": "中性",
    "warm": "暖调",
}

DEPTH_LABELS = {
    "deep": "深色",
    "medium": "中明度",
    "light": "浅色",
}

FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/opentype/ipaexfont-mincho/ipaexm.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _safe_hex(value: str | None) -> str:
    raw = str(value or "").strip()
    if len(raw) == 7 and raw.startswith("#"):
        return raw
    return "#6B5C53"


@lru_cache(maxsize=1)
def _font_path() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return ""


@lru_cache(maxsize=8)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = _font_path()
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, font_size: int, fill: str) -> None:
    draw.text(xy, text, font=_font(font_size), fill=fill)


def _measure_text(draw: ImageDraw.ImageDraw, text: str, *, font_size: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=_font(font_size))
    return bbox[2] - bbox[0]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, *, font_size: int, max_width: int, max_lines: int) -> list[str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return []
    lines: list[str] = []
    current = ""
    for char in cleaned:
        probe = f"{current}{char}"
        if current and _measure_text(draw, probe, font_size=font_size) > max_width:
            lines.append(current)
            current = char
            if len(lines) >= max_lines - 1:
                break
        else:
            current = probe
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len("".join(lines)) < len(cleaned):
        tail = lines[-1]
        if len(tail) > 1:
            lines[-1] = f"{tail[:-1]}…"
        else:
            lines[-1] = "…"
    return lines


def _cover_page() -> Image.Image:
    page = Image.new("RGB", PAGE_SIZE, PAGE_BACKGROUND)
    draw = ImageDraw.Draw(page)
    draw.rounded_rectangle((88, 110, PAGE_SIZE[0] - 88, PAGE_SIZE[1] - 110), radius=42, fill="#FFFDFC", outline="#E9E2D7", width=3)
    _draw_text(draw, (132, 164), "SOLUTOR 专业色号参考", font_size=48, fill=TEXT_PRIMARY)
    _draw_text(draw, (132, 236), "用于小程序专业色号检索与人工参考", font_size=26, fill=TEXT_SECONDARY)
    _draw_text(draw, (132, 286), "本 PDF 基于当前内置色号目录自动生成。", font_size=24, fill=TEXT_SECONDARY)
    _draw_text(draw, (132, 322), "选择时仍以小程序内可生成色号为准。", font_size=24, fill=TEXT_SECONDARY)
    
    legend_top = 430
    legend_items = [
        ("色号检索", "支持 5/72、572、5-72、冷雾、奶茶等搜索方式"),
        ("可生成色号", "小程序中可直接选择并参与生图"),
        ("参考色", "仅展示供比对，不一定开放生成"),
    ]
    for index, (title, body) in enumerate(legend_items):
        top = legend_top + index * 164
        draw.rounded_rectangle((132, top, PAGE_SIZE[0] - 132, top + 124), radius=26, fill="#FFFFFF", outline=CARD_BORDER, width=2)
        _draw_text(draw, (164, top + 22), title, font_size=30, fill=ACCENT)
        _draw_text(draw, (164, top + 66), body, font_size=23, fill=TEXT_SECONDARY)

    footer = PAGE_SIZE[1] - 180
    _draw_text(draw, (132, footer), "字段说明", font_size=28, fill=TEXT_PRIMARY)
    _draw_text(draw, (132, footer + 44), "Code: 品牌色号", font_size=22, fill=TEXT_SECONDARY)
    _draw_text(draw, (132, footer + 78), "Series: 系列", font_size=22, fill=TEXT_SECONDARY)
    _draw_text(draw, (132, footer + 112), "Tone / Temp / Depth: 映射发色、冷暖调、深浅度", font_size=22, fill=TEXT_SECONDARY)
    return page


def _color_page(items: list[dict], page_index: int, total_pages: int) -> Image.Image:
    page = Image.new("RGB", PAGE_SIZE, PAGE_BACKGROUND)
    draw = ImageDraw.Draw(page)
    _draw_text(draw, (92, 74), "SOLUTOR 专业色号参考", font_size=34, fill=TEXT_PRIMARY)
    _draw_text(draw, (PAGE_SIZE[0] - 240, 82), f"{page_index}/{total_pages}", font_size=22, fill=TEXT_SECONDARY)

    card_width = PAGE_SIZE[0] - 184
    card_height = 228
    left = 92
    top = 142
    for index, item in enumerate(items):
        y = top + index * (card_height + 28)
        draw.rounded_rectangle((left, y, left + card_width, y + card_height), radius=28, fill=CARD_BACKGROUND, outline=CARD_BORDER, width=2)

        swatch_left = left + 28
        swatch_top = y + 28
        draw.rounded_rectangle((swatch_left, swatch_top, swatch_left + 136, swatch_top + 136), radius=28, fill=_safe_hex(item.get("hex_estimate")), outline=SWATCH_BORDER, width=3)

        code_left = swatch_left + 168
        code_top = y + 26
        code = str(item.get("code") or "-")
        series = SERIES_LABELS.get(item.get("series_type"), str(item.get("series_name") or "未分类"))
        note = str(item.get("visual_note") or "").strip()
        prompt_alias = str(item.get("prompt_alias") or "").strip()
        tone = str(item.get("mapped_tone_label") or "-")
        temp = TEMPERATURE_LABELS.get(item.get("mapped_temperature"), str(item.get("mapped_temperature") or "-"))
        depth = DEPTH_LABELS.get(item.get("mapped_depth_bucket"), str(item.get("mapped_depth_bucket") or "-"))
        recommended = "可生成" if item.get("is_recommended_for_generation") else "参考色"

        _draw_text(draw, (code_left, code_top), f"Code  {code}", font_size=36, fill=TEXT_PRIMARY)
        badge_text = recommended
        badge_width = _measure_text(draw, badge_text, font_size=20) + 34
        badge_left = left + card_width - badge_width - 28
        draw.rounded_rectangle((badge_left, y + 30, badge_left + badge_width, y + 68), radius=18, fill="#F0ECE4", outline="#DED7CB", width=1)
        _draw_text(draw, (badge_left + 17, y + 38), badge_text, font_size=20, fill=ACCENT)

        _draw_text(draw, (code_left, code_top + 48), f"Series  {series}", font_size=22, fill=TEXT_SECONDARY)
        _draw_text(draw, (code_left, code_top + 84), f"Tone  {tone}    Temp  {temp}    Depth  {depth}", font_size=21, fill=TEXT_SECONDARY)
        if prompt_alias:
            _draw_text(draw, (code_left, code_top + 118), f"Alias  {prompt_alias}", font_size=20, fill=TEXT_SECONDARY)

        note_lines = _wrap_text(draw, f"视觉描述  {note}", font_size=21, max_width=card_width - 220, max_lines=2)
        for line_index, line in enumerate(note_lines):
            _draw_text(draw, (code_left, code_top + 154 + line_index * 28), line, font_size=21, fill=TEXT_SECONDARY)

    return page


def build_professional_hair_color_reference_pdf() -> bytes:
    items = templates.get_professional_hair_color_catalog()
    pages: list[Image.Image] = [_cover_page()]
    chunked = [items[index:index + ITEMS_PER_PAGE] for index in range(0, len(items), ITEMS_PER_PAGE)]
    total_pages = len(chunked)
    for index, chunk in enumerate(chunked, start=1):
        pages.append(_color_page(chunk, index, total_pages))

    output = io.BytesIO()
    first_page, *rest_pages = pages
    first_page.save(output, format="PDF", resolution=150.0, save_all=True, append_images=rest_pages)
    return output.getvalue()



def _load_reference_pdf_source_bytes() -> bytes:
    if ASSET_REFERENCE_PDF_PATH.exists():
        return ASSET_REFERENCE_PDF_PATH.read_bytes()
    return build_professional_hair_color_reference_pdf()



def professional_hair_color_reference_object_key() -> str:
    return storage.reference_document_object_key(REFERENCE_PDF_FILENAME)



def professional_hair_color_reference_static_relative_path() -> str:
    return f"{STATIC_REFERENCE_SUBDIR}/{REFERENCE_PDF_FILENAME}"



def professional_hair_color_reference_static_file_path() -> Path:
    settings = get_settings()
    public_dir = settings.storage_dir / "public" / STATIC_REFERENCE_SUBDIR
    public_dir.mkdir(parents=True, exist_ok=True)
    return public_dir / REFERENCE_PDF_FILENAME



def ensure_professional_hair_color_reference_static_file(*, force_refresh: bool = False) -> Path:
    destination = professional_hair_color_reference_static_file_path()
    pdf_bytes = _load_reference_pdf_source_bytes()
    if not force_refresh and destination.exists():
        try:
            if destination.read_bytes() == pdf_bytes:
                return destination
        except Exception:
            pass
    destination.write_bytes(pdf_bytes)
    return destination



def ensure_professional_hair_color_reference_pdf_cached(*, force_refresh: bool = False) -> str:
    object_key = professional_hair_color_reference_object_key()
    pdf_bytes = _load_reference_pdf_source_bytes()
    if not force_refresh:
        try:
            if storage.read_file_bytes(object_key) == pdf_bytes:
                ensure_professional_hair_color_reference_static_file()
                return object_key
        except Exception:
            pass
    ensure_professional_hair_color_reference_static_file(force_refresh=True)
    return storage.save_reference_document(REFERENCE_PDF_FILENAME, pdf_bytes)



def get_professional_hair_color_reference_url(*, base_url: str | None = None) -> str | None:
    object_key = ensure_professional_hair_color_reference_pdf_cached()
    return storage.media_url(object_key, base_url=base_url)



def get_professional_hair_color_reference_static_url(*, base_url: str) -> str:
    ensure_professional_hair_color_reference_static_file()
    return f"{base_url.rstrip('/')}/static/{professional_hair_color_reference_static_relative_path()}"
