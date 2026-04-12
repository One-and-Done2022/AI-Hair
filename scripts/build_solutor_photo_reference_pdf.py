from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
OUTPUT_FILENAME = "solutor-hair-color-reference.pdf"
PHOTO_PATTERN = "微信图片_202604032252*.jpg"
PAGE_SIZE = (3000, 2200)
PAGE_BACKGROUND = "#F7F4EE"
CARD_BACKGROUND = "#FFFCF8"
CARD_BORDER = "#E6DED1"
TEXT_PRIMARY = "#1F2933"
TEXT_SECONDARY = "#5D6670"
ACCENT = "#8B6F47"
PHOTO_CROP_BOX = (40, 40, 4220, 3140)
PHOTO_ORDER = [
    "微信图片_20260403225240_283_89.jpg",
    "微信图片_20260403225237_282_89.jpg",
    "微信图片_20260403225234_281_89.jpg",
    "微信图片_20260403225232_280_89.jpg",
    "微信图片_20260403225229_279_89.jpg",
]
FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/opentype/ipaexfont-mincho/ipaexm.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _font_path() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return ""


def _font(size: int):
    path = _font_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, font_size: int, fill: str) -> None:
    draw.text(xy, text, font=_font(font_size), fill=fill)


def _cover_page(page_count: int) -> Image.Image:
    page = Image.new("RGB", PAGE_SIZE, PAGE_BACKGROUND)
    draw = ImageDraw.Draw(page)
    draw.rounded_rectangle((140, 120, PAGE_SIZE[0] - 140, PAGE_SIZE[1] - 120), radius=44, fill=CARD_BACKGROUND, outline=CARD_BORDER, width=4)
    _draw_text(draw, (220, 220), "SOLUTOR 色卡实拍整理版", font_size=72, fill=TEXT_PRIMARY)
    _draw_text(draw, (220, 320), "基于 5 张实拍原图重新整理，优先保留二维码区域与色束细节。", font_size=34, fill=TEXT_SECONDARY)
    _draw_text(draw, (220, 372), "适合在手机或平板上放大查看，也适合作为人工扫码参考。", font_size=34, fill=TEXT_SECONDARY)

    items = [
        "保留原始系列排布，不重新拆散二维码与色束位置关系",
        "裁掉拍照底部水印区域，让有效内容尽量铺满页面",
        "对实拍图做轻度自动对比度与锐度增强，提升可读性",
        f"正文共 {page_count} 页，每页对应 1 张实拍整理图",
    ]
    top = 580
    for index, item in enumerate(items, start=1):
        draw.rounded_rectangle((220, top + (index - 1) * 160, PAGE_SIZE[0] - 220, top + (index - 1) * 160 + 108), radius=28, fill="#FFFFFF", outline=CARD_BORDER, width=2)
        _draw_text(draw, (258, top + (index - 1) * 160 + 30), f"0{index}", font_size=34, fill=ACCENT)
        _draw_text(draw, (360, top + (index - 1) * 160 + 30), item, font_size=30, fill=TEXT_PRIMARY)

    footer_y = PAGE_SIZE[1] - 250
    _draw_text(draw, (220, footer_y), "说明：二维码来自原始实拍图，本版不重新生成二维码内容。", font_size=28, fill=TEXT_SECONDARY)
    _draw_text(draw, (220, footer_y + 44), "如果后续替换同名 PDF 文件，固定静态链接地址可以保持不变。", font_size=28, fill=TEXT_SECONDARY)
    return page


def _prepare_photo(photo: Image.Image) -> Image.Image:
    crop = photo.crop(PHOTO_CROP_BOX)
    crop = ImageOps.autocontrast(crop, cutoff=1)
    crop = ImageEnhance.Contrast(crop).enhance(1.05)
    crop = ImageEnhance.Sharpness(crop).enhance(1.18)
    crop = ImageEnhance.Color(crop).enhance(1.03)
    return crop


def _photo_page(image_path: Path, index: int, total: int) -> Image.Image:
    source = Image.open(image_path).convert("RGB")
    prepared = _prepare_photo(source)

    page = Image.new("RGB", PAGE_SIZE, PAGE_BACKGROUND)
    draw = ImageDraw.Draw(page)
    draw.rounded_rectangle((80, 70, PAGE_SIZE[0] - 80, PAGE_SIZE[1] - 70), radius=40, fill=CARD_BACKGROUND, outline=CARD_BORDER, width=4)
    _draw_text(draw, (150, 126), f"实拍整理页 {index}", font_size=54, fill=TEXT_PRIMARY)
    _draw_text(draw, (150, 196), "已尽量保留二维码区域，建议放大后查看或扫码。", font_size=28, fill=TEXT_SECONDARY)
    _draw_text(draw, (PAGE_SIZE[0] - 260, 134), f"{index}/{total}", font_size=28, fill=TEXT_SECONDARY)

    frame_left = 120
    frame_top = 270
    frame_right = PAGE_SIZE[0] - 120
    frame_bottom = PAGE_SIZE[1] - 130
    frame_width = frame_right - frame_left
    frame_height = frame_bottom - frame_top
    draw.rounded_rectangle((frame_left, frame_top, frame_right, frame_bottom), radius=32, fill="#FFFFFF", outline=CARD_BORDER, width=3)

    ratio = min((frame_width - 40) / prepared.width, (frame_height - 40) / prepared.height)
    resized = prepared.resize((int(prepared.width * ratio), int(prepared.height * ratio)), Image.Resampling.LANCZOS)
    paste_x = frame_left + (frame_width - resized.width) // 2
    paste_y = frame_top + (frame_height - resized.height) // 2
    page.paste(resized, (paste_x, paste_y))

    return page


def build_pdf(output_path: Path) -> Path:
    ordered_paths = []
    for name in PHOTO_ORDER:
        path = ASSETS_DIR / name
        if path.exists():
            ordered_paths.append(path)
    if not ordered_paths:
        ordered_paths = sorted(ASSETS_DIR.glob(PHOTO_PATTERN), reverse=True)
    if not ordered_paths:
        raise FileNotFoundError("No source photos found for SOLUTOR PDF build.")

    pages = [_cover_page(len(ordered_paths))]
    for index, path in enumerate(ordered_paths, start=1):
        pages.append(_photo_page(path, index, len(ordered_paths)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = pages
    first.save(output_path, format="PDF", resolution=220.0, save_all=True, append_images=rest)
    return output_path


def main() -> None:
    outputs = [
        ASSETS_DIR / OUTPUT_FILENAME,
        ROOT / "storage" / "public" / "reference_docs" / OUTPUT_FILENAME,
        ROOT / "storage" / "reference_docs" / OUTPUT_FILENAME,
        ROOT / "storage" / "exports" / OUTPUT_FILENAME,
    ]
    primary = None
    for output in outputs:
        built = build_pdf(output)
        if primary is None:
            primary = built
        print(f"built: {built}")
    if primary is not None:
        print(f"done: {primary}")


if __name__ == "__main__":
    main()
