"""
Composite a Bible verse (text overlay, not AI-rendered) onto a text-free
background image. Uses precise PIL typography instead of relying on the
image model to render text, since AI models routinely garble/misspell text.

Usage:
    python scripts/overlay_verse.py --image path/to/bg.png --text "For God so loved..." \
        --ref "John 3:16" --out output/bundles/vintage-scripture-paintings/final/001.jpg
"""

import argparse
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = Path("C:/Windows/Fonts")
F_VERSE = FONT_DIR / "cambriai.ttf"  # italic serif, classic scripture feel
F_REF = FONT_DIR / "cambriab.ttf"

TEXT_COLOR = (255, 255, 255)
SHADOW_COLOR = (0, 0, 0)


def font(path, size):
    return ImageFont.truetype(str(path), size)


def fit_text_size(draw, text, max_width, max_height, font_path, start_size=90, min_size=36):
    size = start_size
    while size > min_size:
        f = font(font_path, size)
        avg_char_w = draw.textlength("M", font=f)
        chars_per_line = max(1, int(max_width / (avg_char_w * 0.55)))
        wrapped = textwrap.wrap(text, chars_per_line)
        line_h = f.getbbox("Ag")[3] + 14
        total_h = line_h * len(wrapped)
        if total_h <= max_height:
            return f, wrapped, line_h
        size -= 4
    f = font(font_path, min_size)
    wrapped = textwrap.wrap(text, max(1, int(max_width / (draw.textlength("M", font=f) * 0.55))))
    return f, wrapped, f.getbbox("Ag")[3] + 14


def overlay_verse(image_path: Path, verse_text: str, ref: str, out_path: Path):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    # Darken the lower-center area slightly so white text stays legible on any background
    overlay = Image.new("L", (w, h), 0)
    odraw = ImageDraw.Draw(overlay)
    band_top = int(h * 0.30)
    band_bottom = int(h * 0.78)
    for y in range(band_top, band_bottom):
        fade = min((y - band_top) / (h * 0.12), (band_bottom - y) / (h * 0.12), 1.0)
        odraw.line((0, y, w, y), fill=int(90 * max(0, fade)))
    dark = Image.new("RGB", (w, h), (10, 10, 10))
    img = Image.composite(dark, img, overlay)

    draw = ImageDraw.Draw(img)
    max_text_w = int(w * 0.62)
    max_text_h = int(h * 0.32)
    f_verse, lines, line_h = fit_text_size(draw, verse_text, max_text_w, max_text_h, F_VERSE)

    total_h = line_h * len(lines)
    start_y = (h - total_h) // 2 - int(h * 0.02)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=f_verse)
        line_w = bbox[2] - bbox[0]
        x = (w - line_w) // 2
        y = start_y + i * line_h
        draw.text((x + 2, y + 2), line, font=f_verse, fill=SHADOW_COLOR)
        draw.text((x, y), line, font=f_verse, fill=TEXT_COLOR)

    f_ref = font(F_REF, 34)
    ref_text = f"— {ref}"
    ref_bbox = draw.textbbox((0, 0), ref_text, font=f_ref)
    ref_w = ref_bbox[2] - ref_bbox[0]
    ref_x = (w - ref_w) // 2
    ref_y = start_y + total_h + 30
    draw.text((ref_x + 2, ref_y + 2), ref_text, font=f_ref, fill=SHADOW_COLOR)
    draw.text((ref_x, ref_y), ref_text, font=f_ref, fill=(230, 220, 190))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    overlay_verse(Path(args.image), args.text, args.ref, Path(args.out))
    print(f"Saved: {args.out}")
