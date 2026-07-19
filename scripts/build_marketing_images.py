"""
Build cover + preview marketing images for a bundle listing, matching the
established EverframeDigital visual style (cream background, bold black
headline, sage-green kicker label, black-bordered image frames).

Usage:
    python scripts/build_marketing_images.py
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = Path("C:/Users/ulian/AppData/Local/Temp/check100")  # extracted 100-piece image pool
OUT_DIR = ROOT / "output" / "covers" / "everframe-100-frame-tv-art-collection"

CANVAS_SIZE = (3000, 2400)
BG_COLOR = (240, 237, 228)
TEXT_COLOR = (26, 26, 26)
KICKER_COLOR = (130, 148, 112)
BORDER_COLOR = (26, 26, 26)
BORDER_WIDTH = 8

FONT_DIR = Path("C:/Windows/Fonts")
F_BLACK = FONT_DIR / "arialbd.ttf"
F_REGULAR = FONT_DIR / "arial.ttf"


def font(path, size):
    return ImageFont.truetype(str(path), size)


def find_images(style_prefix: str, n: int) -> list[Path]:
    all_files = sorted(SOURCE_DIR.glob(f"*-{style_prefix}-*"))
    return all_files[:n]


def paste_bordered(canvas: Image.Image, img_path: Path, box: tuple) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    img = Image.open(img_path).convert("RGB")
    img_ratio = img.width / img.height
    box_ratio = w / h
    if img_ratio > box_ratio:
        new_h = h
        new_w = int(h * img_ratio)
    else:
        new_w = w
        new_h = int(w / img_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    img = img.crop((left, top, left + w, top + h))
    canvas.paste(img, (x0, y0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(box, outline=BORDER_COLOR, width=BORDER_WIDTH)


def new_canvas():
    return Image.new("RGB", CANVAS_SIZE, BG_COLOR)


def draw_header(draw, kicker, title, subtitle, margin=140, y=90):
    draw.text((margin, y), kicker, font=font(F_BLACK, 44), fill=KICKER_COLOR)
    draw.text((margin, y + 70), title, font=font(F_BLACK, 130), fill=TEXT_COLOR)
    if subtitle:
        draw.text((margin, y + 220), subtitle, font=font(F_REGULAR, 46), fill=(80, 80, 80))


def draw_pill(draw, x, y, text, text_font, fg=(255, 255, 255), bg=KICKER_COLOR, pad_x=28, pad_y=16):
    bbox = draw.textbbox((0, 0), text, font=text_font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pill_w, pill_h = w + pad_x * 2, h + pad_y * 2
    draw.rounded_rectangle((x, y, x + pill_w, y + pill_h), radius=pill_h // 2, fill=bg)
    draw.text((x + pad_x, y + pad_y - bbox[1]), text, font=text_font, fill=fg)
    return pill_w


def draw_badge_row(draw, badges, margin, y):
    f = font(F_BLACK, 32)
    x = margin
    gap = 24
    for text in badges:
        w = draw_pill(draw, x, y, text, f)
        x += w + gap


def build_main_cover():
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "100 ACTUAL ARTWORKS • 6 CURATED STYLES", "100 FRAME TV ART COLLECTION",
                "4K Digital Download for Samsung Frame TV")
    draw_badge_row(
        draw,
        ["FRAME TV ART", "16:9 RATIO", "30-DAY MONEY BACK GUARANTEE", "100 UNIQUE DESIGNS"],
        140, 400,
    )

    margin = 140
    top = 520
    big_w, big_h = 1780, 1000
    paste_bordered(canvas, find_images("coastal-landscape", 1)[0], (margin, top, margin + big_w, top + big_h))

    small_w = CANVAS_SIZE[0] - margin - (margin + big_w) - 40
    sx = margin + big_w + 40
    sy = top
    small_h = (big_h - 40) // 2
    samples = find_images("neutral-botanical", 1) + find_images("vintage-botanical", 1)
    for i, img in enumerate(samples):
        paste_bordered(canvas, img, (sx, sy + i * (small_h + 40), sx + small_w, sy + i * (small_h + 40) + small_h))

    bottom_y = top + big_h + 40
    bottom_h = 560
    bottom_w = (CANVAS_SIZE[0] - margin * 2 - 40 * 2) // 3
    bottom_samples = (
        find_images("modern-abstract-neutral", 1)
        + find_images("minimalist-line-art", 1)
        + find_images("seasonal-neutral", 1)
    )
    for i, img in enumerate(bottom_samples):
        bx = margin + i * (bottom_w + 40)
        paste_bordered(canvas, img, (bx, bottom_y, bx + bottom_w, bottom_y + bottom_h))

    canvas.save(OUT_DIR.parent / "everframe-100-frame-tv-art-collection-cover.jpg", quality=92)
    print("cover done")


def build_alternate_cover():
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "SAMSUNG FRAME TV ART", "100-PIECE ART LIBRARY", "Instant Digital Download • 4K UHD")

    margin = 140
    top = 460
    cols, rows = 4, 2
    gap = 30
    cell_w = (CANVAS_SIZE[0] - margin * 2 - gap * (cols - 1)) // cols
    cell_h = 780
    styles_cycle = [
        "coastal-landscape", "neutral-botanical", "modern-abstract-neutral", "minimalist-line-art",
        "vintage-botanical", "seasonal-neutral", "coastal-landscape", "neutral-botanical",
    ]
    used = {}
    for i, style_id in enumerate(styles_cycle):
        idx = used.get(style_id, 0)
        img = find_images(style_id, idx + 2)[idx + 1]
        used[style_id] = idx + 1
        r, c = divmod(i, cols)
        x0 = margin + c * (cell_w + gap)
        y0 = top + r * (cell_h + gap)
        paste_bordered(canvas, img, (x0, y0, x0 + cell_w, y0 + cell_h))

    canvas.save(OUT_DIR / "01-everframe-100-alternate-cover.jpg", quality=92)
    print("alternate cover done")


def build_style_preview(filename, kicker_count, title, style_prefixes, n_each, sample_counts):
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, f"{kicker_count} INCLUDED ARTWORKS", title, "Representative images from the actual download")

    images = []
    for prefix, count in zip(style_prefixes, sample_counts):
        images.extend(find_images(prefix, count))

    margin = 140
    top = 460
    big_w, big_h = 1780, 1000
    paste_bordered(canvas, images[0], (margin, top, margin + big_w, top + big_h))
    if len(images) > 1:
        sx = margin + big_w + 40
        sw = CANVAS_SIZE[0] - margin - sx
        paste_bordered(canvas, images[1], (sx, top, sx + sw, top + big_h))

    remaining = images[2:6]
    if remaining:
        row_y = top + big_h + 40
        row_h = 560
        cols = len(remaining)
        gap = 30
        cell_w = (CANVAS_SIZE[0] - margin * 2 - gap * (cols - 1)) // cols
        for i, img in enumerate(remaining):
            x0 = margin + i * (cell_w + gap)
            paste_bordered(canvas, img, (x0, row_y, x0 + cell_w, row_y + row_h))

    canvas.save(OUT_DIR / filename, quality=92)
    print(f"{filename} done")


def build_what_you_receive():
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "EVERFRAME DIGITAL", "WHAT YOU RECEIVE", "A complete, ready-to-display Frame TV collection")

    margin = 140
    bullets = [
        "100 HIGH-RESOLUTION JPG FILES",
        "3840 × 2160 PIXELS • 4K UHD",
        "16:9 LANDSCAPE FORMAT",
        "5 ORGANIZED ZIP DOWNLOADS",
        "6 COORDINATED ART STYLES",
        "DIGITAL PRODUCT • NO SHIPPING",
    ]
    y = 620
    for b in bullets:
        draw.ellipse((margin, y + 14, margin + 34, y + 48), fill=KICKER_COLOR)
        draw.text((margin + 70, y), b, font=font(F_BLACK, 44), fill=TEXT_COLOR)
        y += 130

    img_x = 1560
    img_w = CANVAS_SIZE[0] - margin - img_x
    paste_bordered(canvas, find_images("coastal-landscape", 6)[5], (img_x, 620, img_x + img_w, 620 + 800))
    sub_w = (img_w - 30) // 2
    sub_y = 620 + 800 + 30
    paste_bordered(canvas, find_images("vintage-botanical", 6)[5], (img_x, sub_y, img_x + sub_w, sub_y + 480))
    paste_bordered(
        canvas, find_images("seasonal-neutral", 6)[5], (img_x + sub_w + 30, sub_y, img_x + img_w, sub_y + 480)
    )

    draw.text(
        (margin, sub_y + 480 + 60),
        "Download all five ZIP files to receive the complete 100-piece set.",
        font=font(F_REGULAR, 42),
        fill=(80, 80, 80),
    )

    canvas.save(OUT_DIR / "06-what-you-receive.jpg", quality=92)
    print("what-you-receive done")


def build_how_to_display():
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "EVERFRAME DIGITAL", "HOW TO DISPLAY", "From download to Art Mode in four steps")

    steps = [
        ("1", "DOWNLOAD", "Save all 5 ZIP files from your Etsy purchases page."),
        ("2", "UNZIP", "Extract the JPG files on your computer or phone."),
        ("3", "TRANSFER", "Use a USB drive or the Samsung SmartThings app to move files to your TV."),
        ("4", "DISPLAY", "Open Art Mode, select your artwork, and enjoy."),
    ]
    margin = 140
    col_w = (CANVAS_SIZE[0] - margin * 2 - 30 * 3) // 4
    y = 620
    for i, (num, label, desc) in enumerate(steps):
        x = margin + i * (col_w + 30)
        draw.ellipse((x, y, x + 100, y + 100), outline=KICKER_COLOR, width=6)
        draw.text((x + 32, y + 18), num, font=font(F_BLACK, 56), fill=KICKER_COLOR)
        draw.text((x, y + 140), label, font=font(F_BLACK, 40), fill=TEXT_COLOR)
        draw.multiline_text((x, y + 210), wrap_text(desc, 22), font=font(F_REGULAR, 34), fill=(80, 80, 80), spacing=10)

    img = find_images("neutral-botanical", 8)[7]
    paste_bordered(canvas, img, (margin, 1300, CANVAS_SIZE[0] - margin, 1300 + 900))

    canvas.save(OUT_DIR / "07-how-to-display.jpg", quality=92)
    print("how-to-display done")


def wrap_text(text, width):
    import textwrap

    return "\n".join(textwrap.wrap(text, width))


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_main_cover()
    build_alternate_cover()
    build_style_preview(
        "02-coastal-nature-preview.jpg", 21, "COASTAL & NATURE",
        ["coastal-landscape"], 1, [6],
    )
    build_style_preview(
        "03-neutral-botanical-preview.jpg", 22, "NEUTRAL BOTANICAL",
        ["neutral-botanical"], 1, [6],
    )
    build_style_preview(
        "04-abstract-minimal-vintage-preview.jpg", 42, "ABSTRACT, MINIMALIST & VINTAGE",
        ["modern-abstract-neutral", "minimalist-line-art", "vintage-botanical"], 1, [2, 2, 2],
    )
    build_style_preview(
        "05-seasonal-nature-preview.jpg", 15, "SEASONAL NATURE",
        ["seasonal-neutral"], 1, [6],
    )
    build_what_you_receive()
    build_how_to_display()
    print("\nAll marketing images built in:", OUT_DIR)
