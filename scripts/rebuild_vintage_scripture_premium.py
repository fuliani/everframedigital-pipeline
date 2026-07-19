from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "Vintage-scripture-paintings"
MAPPING = PRODUCT / "listing" / "filename-mapping.csv"
VERSES = ROOT / "config" / "bible_verses_vintage.json"
SOURCE_V2 = PRODUCT / "source-art-v2"
OUT = PRODUCT / "customer-downloads-v3" / "_work" / "normalized-jpg"
PREVIEW = PRODUCT / "listing" / "premium-prototypes-v2"

W, H = 3840, 2160
SERIF = Path(r"C:\Windows\Fonts\BASKVILL.TTF")
SERIF_BOLD = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
SANS = Path(r"C:\Windows\Fonts\arial.ttf")
SANS_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")

IVORY = (246, 239, 221)
INK = (48, 39, 31)
GOLD = (161, 125, 68)
CHARCOAL = (42, 38, 34)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def load_rows() -> list[dict[str, str]]:
    with MAPPING.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_verses() -> dict[str, str]:
    payload = json.loads(VERSES.read_text(encoding="utf-8"))
    items = payload["verses"]
    return {item["ref"].replace("–", "-"): item["text"].strip() for item in items}


def region_score(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    region = image.crop(box).resize((320, 180), Image.Resampling.BILINEAR).convert("L")
    edges = region.filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edges).mean[0]
    variance = ImageStat.Stat(region).var[0]
    return edge_mean * 2.2 + math.sqrt(variance)


def choose_side(image: Image.Image) -> str:
    left = region_score(image, (120, 130, 1810, 2030))
    right = region_score(image, (2030, 130, 3720, 2030))
    return "left" if left <= right else "right"


def wrap_for_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        if draw.textlength(trial, font=fnt) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_verse(draw: ImageDraw.ImageDraw, text: str, width: int, height: int):
    for size in range(116, 68, -2):
        fnt = font(SERIF, size)
        lines = wrap_for_width(draw, text, fnt, width)
        leading = int(size * 1.30)
        if len(lines) <= 8 and len(lines) * leading <= height:
            return fnt, lines, leading
    fnt = font(SERIF, 68)
    return fnt, wrap_for_width(draw, text, fnt, width), 88


def rounded_panel(base: Image.Image, box: tuple[int, int, int, int], light: bool) -> None:
    x1, y1, x2, y2 = box
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x1 + 18, y1 + 24, x2 + 18, y2 + 24), 34, fill=(24, 18, 14, 86))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    base.alpha_composite(shadow)

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    fill = (*IVORY, 224) if light else (*CHARCOAL, 220)
    stroke = (*GOLD, 178)
    ld.rounded_rectangle(box, 34, fill=fill, outline=stroke, width=4)
    ld.rounded_rectangle((x1 + 18, y1 + 18, x2 - 18, y2 - 18), 25, outline=(*GOLD, 86), width=2)
    base.alpha_composite(layer)


def render_one(source: Path, verse: str, reference: str, destination: Path) -> dict:
    image = Image.open(source).convert("RGB")
    if image.size != (W, H):
        image = ImageOps.fit(image, (W, H), method=Image.Resampling.LANCZOS)
    side = choose_side(image)
    panel_w = 1580
    margin = 150
    panel = (margin, 160, margin + panel_w, H - 160) if side == "left" else (W - margin - panel_w, 160, W - margin, H - 160)

    # Use a light parchment panel unless the underlying area is very dark.
    underlying = image.crop(panel).resize((100, 100), Image.Resampling.BILINEAR).convert("L")
    light_panel = ImageStat.Stat(underlying).mean[0] >= 72
    base = image.convert("RGBA")
    rounded_panel(base, panel, light_panel)
    draw = ImageDraw.Draw(base)
    x1, y1, x2, y2 = panel
    fg = INK if light_panel else (248, 241, 225)
    muted = (102, 82, 57) if light_panel else (218, 194, 148)

    quote = "“"
    draw.text((x1 + 105, y1 + 60), quote, font=font(SERIF, 210), fill=GOLD)

    text_x = x1 + 145
    text_y = y1 + 300
    text_w = panel_w - 290
    text_h = 1050
    body_font, lines, leading = fit_verse(draw, verse, text_w, text_h)
    for line in lines:
        draw.text((text_x, text_y), line, font=body_font, fill=fg)
        text_y += leading

    divider_y = max(y1 + 1510, text_y + 80)
    divider_y = min(divider_y, y2 - 265)
    draw.line((text_x, divider_y, text_x + 230, divider_y), fill=GOLD, width=5)
    draw.ellipse((text_x + 250, divider_y - 8, text_x + 266, divider_y + 8), fill=GOLD)
    draw.line((text_x + 286, divider_y, text_x + 516, divider_y), fill=GOLD, width=5)

    ref_y = divider_y + 54
    ref_text = reference.replace("-", "–").upper()
    draw.text((text_x, ref_y), ref_text, font=font(SERIF_BOLD, 60), fill=fg)
    draw.text((text_x, ref_y + 93), "KING JAMES VERSION", font=font(SANS_BOLD, 32), fill=muted)

    final = base.convert("RGB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Etsy permits five downloadable files with a 20 MB limit each. Quality 75
    # with 4:4:4 chroma preserves fine typography and painterly texture while
    # keeping the complete 100-image set safely packageable in five archives.
    final.save(destination, "JPEG", quality=75, subsampling=0, optimize=True, dpi=(300, 300))
    return {
        "side": side,
        "light_panel": light_panel,
        "lines": len(lines),
        "font_size": body_font.size,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "bytes": destination.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--indices", default="all", help="Comma-separated 1-based indices or all")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    rows = load_rows()
    verses = load_verses()
    indices = range(1, len(rows) + 1) if args.indices == "all" else [int(x) for x in args.indices.split(",")]
    target_root = PREVIEW if args.preview else OUT
    records = []
    for idx in indices:
        row = rows[idx - 1]
        reference = row["verse_ref"].replace("–", "-")
        verse = verses[reference]
        source = SOURCE_V2 / f"Vintage-Scripture-Base-{idx:03d}.png"
        if not source.is_file():
            raise RuntimeError(f"Missing replacement source artwork: {source.name}")
        destination = target_root / row["filename"]
        result = render_one(source, verse, reference, destination)
        records.append({"index": idx, "source": source.name, "destination": destination.name, **result})
        print(f"{idx:03d}: {destination.name} side={result['side']} size={result['font_size']} lines={result['lines']}")
    report = target_root / "render-report.json"
    report.write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
