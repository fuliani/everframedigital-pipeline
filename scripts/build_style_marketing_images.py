"""
Build the full consistent marketing photo set (cover + alternate cover +
2 gallery previews + what-you-receive + how-to-display) for a single-style
bundle, matching the combined bundles' visual treatment.

Usage:
    python scripts/build_style_marketing_images.py --style coastal-landscape --count 29
"""

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_marketing_images import (
    new_canvas, draw_header, draw_badge_row, paste_bordered, CANVAS_SIZE,
    font, F_BLACK, F_REGULAR, KICKER_COLOR, TEXT_COLOR,
)
from PIL import ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FALAI_DIR = ROOT / "output" / "falai"


def find_images(style_id, n=None):
    files = sorted((FALAI_DIR / style_id).glob("*.png")) + sorted((FALAI_DIR / style_id).glob("*.jpg"))
    return files[:n] if n else files


def out_dir(style_id):
    d = ROOT / "output" / "bundles" / style_id / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def style_display_name(style_id):
    return style_id.replace("-", " ").title()


def build_alternate_cover(style_id, count):
    images = find_images(style_id)
    name = style_display_name(style_id)
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, f"SAMSUNG FRAME TV ART • {name.upper()}", f"{count}-PIECE ART LIBRARY",
                "Instant Digital Download • 4K UHD")
    draw_badge_row(draw, ["FRAME TV ART", "16:9 RATIO", "30-DAY MONEY BACK GUARANTEE", f"{count} UNIQUE DESIGNS"], 140, 400)

    margin = 140
    top = 560
    cols = 4
    gap = 30
    cell_w = (CANVAS_SIZE[0] - margin * 2 - gap * (cols - 1)) // cols
    cell_h = 720
    sample = images[:8] if len(images) >= 8 else (images * 8)[:8]
    for i, img in enumerate(sample):
        r, c = divmod(i, cols)
        x0 = margin + c * (cell_w + gap)
        y0 = top + r * (cell_h + gap)
        paste_bordered(canvas, img, (x0, y0, x0 + cell_w, y0 + cell_h))

    canvas.save(out_dir(style_id) / "01-alternate-cover.jpg", quality=92)
    print(f"[{style_id}] alternate cover done")


def build_gallery_preview(style_id, count, part_num, image_slice, subtitle):
    images = find_images(style_id)[image_slice]
    name = style_display_name(style_id)
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, f"{count} INCLUDED ARTWORKS", f"{name.upper()} GALLERY {part_num}", subtitle)

    margin = 140
    top = 460
    big_w, big_h = 1780, 1000
    if not images:
        images = find_images(style_id)[:6]
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

    canvas.save(out_dir(style_id) / f"0{1 + part_num}-gallery-preview-{part_num}.jpg", quality=92)
    print(f"[{style_id}] gallery preview {part_num} done")


def build_what_you_receive(style_id, count):
    images = find_images(style_id)
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "EVERFRAME DIGITAL", "WHAT YOU RECEIVE", "A complete, ready-to-display Frame TV collection")

    margin = 140
    bullets = [
        f"{count} HIGH-RESOLUTION JPG FILES",
        "3840 x 2160 PIXELS • 4K UHD",
        "16:9 LANDSCAPE FORMAT",
        "1-2 ORGANIZED ZIP DOWNLOADS",
        "ONE COHESIVE ART STYLE",
        "DIGITAL PRODUCT • NO SHIPPING",
    ]
    y = 620
    for b in bullets:
        draw.ellipse((margin, y + 14, margin + 34, y + 48), fill=KICKER_COLOR)
        draw.text((margin + 70, y), b, font=font(F_BLACK, 44), fill=TEXT_COLOR)
        y += 130

    img_x = 1560
    img_w = CANVAS_SIZE[0] - margin - img_x
    idx = min(8, len(images) - 1)
    paste_bordered(canvas, images[idx], (img_x, 620, img_x + img_w, 620 + 800))
    sub_w = (img_w - 30) // 2
    sub_y = 620 + 800 + 30
    idx2 = min(9, len(images) - 1)
    idx3 = min(10, len(images) - 1)
    paste_bordered(canvas, images[idx2], (img_x, sub_y, img_x + sub_w, sub_y + 480))
    paste_bordered(canvas, images[idx3], (img_x + sub_w + 30, sub_y, img_x + img_w, sub_y + 480))

    draw.text(
        (margin, sub_y + 480 + 60),
        f"Download all ZIP file(s) to receive the complete {count}-piece set.",
        font=font(F_REGULAR, 42),
        fill=(80, 80, 80),
    )

    canvas.save(out_dir(style_id) / "04-what-you-receive.jpg", quality=92)
    print(f"[{style_id}] what-you-receive done")


def build_how_to_display(style_id):
    images = find_images(style_id)
    canvas = new_canvas()
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "EVERFRAME DIGITAL", "HOW TO DISPLAY", "From download to Art Mode in four steps")

    steps = [
        ("1", "DOWNLOAD", "Save the ZIP file(s) from your Etsy purchases page."),
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
        draw.multiline_text(
            (x, y + 210), "\n".join(textwrap.wrap(desc, 22)), font=font(F_REGULAR, 34), fill=(80, 80, 80), spacing=10
        )

    idx = min(11, len(images) - 1)
    paste_bordered(canvas, images[idx], (margin, 1300, CANVAS_SIZE[0] - margin, 1300 + 900))

    canvas.save(out_dir(style_id) / "05-how-to-display.jpg", quality=92)
    print(f"[{style_id}] how-to-display done")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", required=True)
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args()

    build_alternate_cover(args.style, args.count)
    build_gallery_preview(args.style, args.count, 1, slice(8, 15), "More pieces from this collection")
    build_gallery_preview(args.style, args.count, 2, slice(15, 22), "Even more variety included")
    build_what_you_receive(args.style, args.count)
    build_how_to_display(args.style)
    print(f"\n[{args.style}] all photos in: {out_dir(args.style)}")


if __name__ == "__main__":
    main()
