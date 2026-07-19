"""
Build a dense mosaic-style cover (many small tiled thumbnails + a bold
central callout panel), modeled on real top-selling Frame TV Art bundle
covers, but with honest claims only (no "lifetime access").

Usage:
    python scripts/build_mosaic_cover.py --style everframe-100 --count 100 \
        --source /path/to/image/pool --out output/covers/everframe-100-frame-tv-art-collection-cover.jpg
"""

import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

CANVAS_SIZE = (3000, 2400)
BG_COLOR = (240, 237, 228)
TEXT_COLOR = (26, 26, 26)
KICKER_COLOR = (130, 148, 112)
PANEL_COLOR = (245, 242, 235)

FONT_DIR = Path("C:/Windows/Fonts")
F_BLACK = FONT_DIR / "arialbd.ttf"
F_REGULAR = FONT_DIR / "arial.ttf"


def font(path, size):
    return ImageFont.truetype(str(path), size)


def build_mosaic_background(image_paths, canvas_size, tile_cols=10, tile_rows=8, seed=42):
    rng = random.Random(seed)
    pool = list(image_paths)
    rng.shuffle(pool)
    tile_w = canvas_size[0] // tile_cols
    tile_h = canvas_size[1] // tile_rows
    canvas = Image.new("RGB", canvas_size, BG_COLOR)

    idx = 0
    for r in range(tile_rows):
        for c in range(tile_cols):
            if not pool:
                break
            img_path = pool[idx % len(pool)]
            idx += 1
            img = Image.open(img_path).convert("RGB")
            img_ratio = img.width / img.height
            box_ratio = tile_w / tile_h
            if img_ratio > box_ratio:
                new_h = tile_h
                new_w = int(tile_h * img_ratio)
            else:
                new_w = tile_w
                new_h = int(tile_w / img_ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - tile_w) // 2
            top = (new_h - tile_h) // 2
            img = img.crop((left, top, left + tile_w, top + tile_h))
            canvas.paste(img, (c * tile_w, r * tile_h))
    return canvas


def draw_pill(draw, x, y, text, text_font, fg=(255, 255, 255), bg=KICKER_COLOR, pad_x=26, pad_y=14):
    bbox = draw.textbbox((0, 0), text, font=text_font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pill_w, pill_h = w + pad_x * 2, h + pad_y * 2
    draw.rounded_rectangle((x, y, x + pill_w, y + pill_h), radius=pill_h // 2, fill=bg)
    draw.text((x + pad_x, y + pad_y - bbox[1]), text, font=text_font, fill=fg)
    return pill_w, pill_h


LABEL_COLORS = [
    (58, 74, 130),   # navy
    (30, 110, 100),  # teal
    (140, 55, 60),   # maroon
    (95, 105, 45),   # olive
    (95, 60, 120),   # purple
    (130, 80, 35),   # brown
]


def draw_sub_collection_grid(draw, panel_x, panel_w, top_y, sub_collections):
    """2 rows x 3 columns of sub-collection counts, centered inside the clean panel."""
    cols = 3
    col_w = panel_w // cols
    f_num = font(F_BLACK, 42)
    f_label = font(F_REGULAR, 22)
    row_h = 130
    for i, (count, label) in enumerate(sub_collections[:6]):
        r, c = divmod(i, cols)
        cx = panel_x + c * col_w + col_w // 2
        cy = top_y + r * row_h
        color = LABEL_COLORS[i % len(LABEL_COLORS)]

        num_text = str(count)
        num_bbox = draw.textbbox((0, 0), num_text, font=f_num)
        draw.text((cx - (num_bbox[2] - num_bbox[0]) // 2, cy), num_text, font=f_num, fill=color)
        ly = cy + (num_bbox[3] - num_bbox[1]) + 8

        for line in label.upper().split(" ", 1):
            line_bbox = draw.textbbox((0, 0), line, font=f_label)
            draw.text((cx - (line_bbox[2] - line_bbox[0]) // 2, ly), line, font=f_label, fill=(90, 90, 90))
            ly += (line_bbox[3] - line_bbox[1]) + 4


def build_cover(image_paths, big_number, subtitle_top, subtitle_bottom, brand_name, badges, out_path, sub_collections=None):
    canvas = build_mosaic_background(image_paths, CANVAS_SIZE)

    # Dim the mosaic slightly so the panel text stays legible everywhere
    overlay = Image.new("RGB", CANVAS_SIZE, (255, 255, 255))
    canvas = Image.blend(canvas, overlay, 0.12)

    draw = ImageDraw.Draw(canvas, "RGBA")

    # Central panel (taller when we have a sub-collection grid to fit at the bottom)
    panel_w, panel_h = 1500, (1050 if sub_collections else 1100)
    px = (CANVAS_SIZE[0] - panel_w) // 2
    py = (CANVAS_SIZE[1] - panel_h) // 2
    draw.rounded_rectangle((px, py, px + panel_w, py + panel_h), radius=28, fill=(245, 242, 235, 235))

    cy = py + 90
    f_kicker = font(F_BLACK, 40)
    kicker_bbox = draw.textbbox((0, 0), subtitle_top, font=f_kicker)
    draw.text((px + (panel_w - (kicker_bbox[2] - kicker_bbox[0])) // 2, cy), subtitle_top, font=f_kicker, fill=KICKER_COLOR)
    cy += 90

    f_big = font(F_BLACK, 220)
    big_bbox = draw.textbbox((0, 0), big_number, font=f_big)
    draw.text((px + (panel_w - (big_bbox[2] - big_bbox[0])) // 2, cy), big_number, font=f_big, fill=TEXT_COLOR)
    cy += (big_bbox[3] - big_bbox[1]) + 50

    f_sub = font(F_BLACK, 54)
    sub_bbox = draw.textbbox((0, 0), subtitle_bottom, font=f_sub)
    draw.text((px + (panel_w - (sub_bbox[2] - sub_bbox[0])) // 2, cy), subtitle_bottom, font=f_sub, fill=TEXT_COLOR)
    cy += 100

    # Badges, centered, wrapped into rows
    f_badge = font(F_BLACK, 30)
    row_gap = 18
    x_gap = 18
    row_widths = []
    current_row = []
    current_w = 0
    max_w = panel_w - 80
    for b in badges:
        bbox = draw.textbbox((0, 0), b, font=f_badge)
        w = (bbox[2] - bbox[0]) + 52
        if current_w + w > max_w and current_row:
            row_widths.append((current_row, current_w))
            current_row = []
            current_w = 0
        current_row.append(b)
        current_w += w + x_gap
    if current_row:
        row_widths.append((current_row, current_w))

    for row, row_w in row_widths:
        rx = px + (panel_w - (row_w - x_gap)) // 2
        for b in row:
            pw, ph = draw_pill(draw, rx, cy, b, f_badge)
            rx += pw + x_gap
        cy += ph + row_gap if row_widths else 0
        cy += 10

    cy += 20
    f_brand = font(F_REGULAR, 34)
    brand_bbox = draw.textbbox((0, 0), brand_name, font=f_brand)
    draw.text((px + (panel_w - (brand_bbox[2] - brand_bbox[0])) // 2, cy), brand_name, font=f_brand, fill=(100, 100, 100))
    cy += (brand_bbox[3] - brand_bbox[1]) + 50

    if sub_collections:
        draw.line((px + 60, cy, px + panel_w - 60, cy), fill=(210, 206, 195), width=2)
        cy += 40
        draw_sub_collection_grid(draw, px, panel_w, cy, sub_collections)

    canvas.save(out_path, quality=93)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Directory of images to tile (glob *.jpg/*.png)")
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--breakdown", nargs="+", default=None,
        help='Sub-collection labels as "COUNT:Label" pairs, e.g. 21:Coastal Landscape 22:Neutral Botanical',
    )
    parser.add_argument(
        "--kicker", default=None,
        help='Override the kicker line, e.g. "101 ACTUAL ARTWORKS • COASTAL LANDSCAPE". '
             'Defaults to "{count} ACTUAL ARTWORKS • 6 CURATED STYLES" if --breakdown is given.',
    )
    parser.add_argument("--title", default="Frame TV Art Collection", help="Subtitle under the big number")
    args = parser.parse_args()

    src = Path(args.source)
    images = sorted(src.glob("*.jpg")) + sorted(src.glob("*.png"))
    if not images:
        # search subfolders (per-style structure)
        images = sorted(src.glob("*/*.jpg")) + sorted(src.glob("*/*.png"))

    sub_collections = None
    if args.breakdown:
        sub_collections = []
        for item in args.breakdown:
            count_str, label = item.split(":", 1)
            sub_collections.append((int(count_str), label))

    default_kicker = f"{args.count} ACTUAL ARTWORKS • 6 CURATED STYLES" if args.breakdown else f"{args.count} ACTUAL ARTWORKS"
    build_cover(
        image_paths=images,
        big_number=str(args.count),
        subtitle_top=args.kicker or default_kicker,
        sub_collections=sub_collections,
        subtitle_bottom=args.title,
        brand_name="EverframeDigital",
        badges=["FRAME TV ART", "16:9 RATIO", "30-DAY MONEY BACK GUARANTEE"],
        out_path=args.out,
    )
