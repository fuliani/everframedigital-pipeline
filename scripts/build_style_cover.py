"""
Build a cover image for a single-style bundle: one Fal.ai hero image with the
established EverframeDigital header/badge treatment (cream background, bold
headline, sage-green kicker, badge pills, bordered hero image).

Usage:
    python scripts/build_style_cover.py --style coastal-landscape --count 28
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "styles.json"
OUTPUT_DIR = ROOT / "output"
BUNDLES_DIR = OUTPUT_DIR / "bundles"

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


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_style(config, style_id):
    for s in config["styles"]:
        if s["id"] == style_id:
            return s
    raise SystemExit(f"Style '{style_id}' not found")


def paste_bordered(canvas, img_path, box):
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


def build_cover(style_id: str, count: int):
    config = load_config()
    style = get_style(config, style_id)

    hero_path = OUTPUT_DIR / "falai" / style_id
    hero_candidates = sorted(hero_path.glob("*.png")) + sorted(hero_path.glob("*.jpg"))
    if not hero_candidates:
        raise SystemExit(f"No Fal.ai images found for '{style_id}' at {hero_path}")
    hero_image = hero_candidates[0]

    canvas = Image.new("RGB", CANVAS_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    margin = 140
    kicker = f"{count} ACTUAL ARTWORKS • {style['name'].upper()}"
    title = f"{style['name']} Frame TV Art".upper()
    subtitle = "4K Digital Download for Samsung Frame TV"

    draw.text((margin, 90), kicker, font=font(F_BLACK, 40), fill=KICKER_COLOR)
    draw.text((margin, 160), title, font=font(F_BLACK, 100), fill=TEXT_COLOR)
    draw.text((margin, 300), subtitle, font=font(F_REGULAR, 46), fill=(80, 80, 80))

    draw_badge_row(
        draw,
        ["FRAME TV ART", "16:9 RATIO", "30-DAY MONEY BACK GUARANTEE", f"{count} UNIQUE DESIGNS"],
        margin, 400,
    )

    top = 520
    hero_h = CANVAS_SIZE[1] - top - margin
    paste_bordered(canvas, hero_image, (margin, top, CANVAS_SIZE[0] - margin, top + hero_h))

    out_dir = BUNDLES_DIR / style_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{style_id}-cover.jpg"
    canvas.save(out_path, quality=92)
    print(f"Cover saved: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", required=True)
    parser.add_argument("--count", type=int, required=True, help="Piece count to display in badges")
    args = parser.parse_args()
    build_cover(args.style, args.count)
