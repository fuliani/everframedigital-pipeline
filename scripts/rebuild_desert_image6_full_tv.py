"""Rebuild Desert-Southwest listing image 6 with a complete TV chassis.

The customer artwork is composited from the exact normalized delivery JPGs.
All marketing text and geometry are rendered deterministically with Pillow.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


REPO = Path(__file__).resolve().parents[1]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Desert-Southwest"
ART = PRODUCT / "customer-downloads" / "_work" / "normalized-jpg"
OUTPUT = PRODUCT / "cover-v2-review"
WORK = OUTPUT / "_work"
DESTINATION = OUTPUT / "06-quality-compatibility.jpg"
BACKUP = WORK / "06-quality-compatibility-before-full-tv.jpg"
REPORT = OUTPUT / "generation-report.txt"

W, H = 2600, 2000
IVORY = "#f7f2e9"
INK = "#252621"
SAGE = "#68735f"
GOLD = "#b69a63"
TAUPE = "#d8cbbb"
PANEL = "#eee7dc"
MUTED = "#62645e"

FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


def font(size: int, *, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    if serif:
        name = "georgiab.ttf" if bold else "georgia.ttf"
    else:
        name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def centered(draw: ImageDraw.ImageDraw, y: int, text: str, face, fill: str) -> None:
    box = draw.textbbox((0, 0), text, font=face)
    draw.text(((W - (box[2] - box[0])) / 2, y), text, font=face, fill=fill)


def load_art(number: int, size: tuple[int, int]) -> Image.Image:
    path = ART / f"Desert-Southwest-{number:03d}.jpg"
    if not path.is_file():
        raise RuntimeError(f"Missing exact customer artwork: {path.name}")
    with Image.open(path) as image:
        if image.size != (3840, 2160) or image.mode != "RGB":
            raise RuntimeError(f"Invalid normalized customer artwork: {path.name}")
        return ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS)


def shadow_layer(box: tuple[int, int, int, int], radius: int = 28) -> Image.Image:
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=8, fill=150)
    mask = mask.filter(ImageFilter.GaussianBlur(radius))
    layer = Image.new("RGBA", (W, H), (51, 42, 31, 0))
    layer.putalpha(mask)
    return layer


def draw_complete_tv(canvas: Image.Image, x: int, y: int) -> None:
    """Draw an unmistakable, fully visible television with an exact 16:9 screen."""
    # Exact 16:9 screen: 1408 x 792. Outer chassis leaves a 32 px bezel.
    screen_w, screen_h, bezel = 1408, 792, 32
    outer_w, outer_h = screen_w + bezel * 2, screen_h + bezel * 2
    canvas.paste(shadow_layer((x + 18, y + 25, x + outer_w + 18, y + outer_h + 25)), (0, 0),
                 shadow_layer((x + 18, y + 25, x + outer_w + 18, y + outer_h + 25)))
    draw = ImageDraw.Draw(canvas)
    # Full four-sided chassis, bevel highlights, and bottom sensor make the TV form explicit.
    draw.rounded_rectangle((x, y, x + outer_w, y + outer_h), radius=10, fill="#1e201e")
    draw.rounded_rectangle((x + 7, y + 7, x + outer_w - 7, y + outer_h - 7), radius=7,
                           outline="#50534d", width=3)
    draw.line((x + 18, y + 15, x + outer_w - 18, y + 15), fill="#777a73", width=2)
    draw.line((x + 16, y + 16, x + 16, y + outer_h - 16), fill="#444640", width=2)
    art = load_art(74, (screen_w, screen_h))
    canvas.paste(art, (x + bezel, y + bezel))
    # Inner lip on every side, not a cropped artwork border.
    draw.rectangle((x + bezel - 2, y + bezel - 2,
                    x + bezel + screen_w + 1, y + bezel + screen_h + 1),
                   outline="#080908", width=4)
    # Logo-free IR sensor and subtle feet, both fully inside the canvas.
    cx = x + outer_w // 2
    draw.rounded_rectangle((cx - 24, y + outer_h - 3, cx + 24, y + outer_h + 9),
                           radius=5, fill="#171817")
    draw.polygon([(x + 210, y + outer_h), (x + 270, y + outer_h),
                  (x + 250, y + outer_h + 22), (x + 225, y + outer_h + 22)], fill="#292b28")
    draw.polygon([(x + outer_w - 270, y + outer_h), (x + outer_w - 210, y + outer_h),
                  (x + outer_w - 225, y + outer_h + 22),
                  (x + outer_w - 250, y + outer_h + 22)], fill="#292b28")


def draw_thumbnail(canvas: Image.Image, number: int, x: int, y: int) -> None:
    art_w, art_h = 390, 219
    canvas.paste(shadow_layer((x + 8, y + 11, x + art_w + 28, y + art_h + 31), 14), (0, 0),
                 shadow_layer((x + 8, y + 11, x + art_w + 28, y + art_h + 31), 14))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y, x + art_w + 20, y + art_h + 20), fill=GOLD)
    draw.rectangle((x + 4, y + 4, x + art_w + 16, y + art_h + 16), fill="#ead9b5")
    canvas.paste(load_art(number, (art_w, art_h)), (x + 10, y + 10))


def build() -> Image.Image:
    top = Image.new("RGB", (W, H), IVORY)
    grain = ImageOps.colorize(Image.effect_noise((W, H), 9).convert("L"), "#ded4c5", "#fffdf9")
    canvas = Image.blend(top, grain, 0.08)
    draw = ImageDraw.Draw(canvas)

    draw.text((110, 58), "EVERFRAME DIGITAL", font=font(34, bold=True), fill=SAGE)
    draw.line((110, 112, 2490, 112), fill=GOLD, width=3)
    centered(draw, 137, "PREMIUM 4K QUALITY", font(72, serif=True, bold=True), INK)
    centered(draw, 232, "MADE FOR 16:9 DISPLAYS", font(31, bold=True), SAGE)

    draw_complete_tv(canvas, 100, 330)
    draw.text((100, 1233), "EXACT CUSTOMER ARTWORK • 16:9 LANDSCAPE", font=font(28, bold=True), fill=MUTED)

    draw.text((1660, 332), "A COLLECTION MADE\nFOR YOUR DISPLAY", font=font(43, serif=True, bold=True),
              fill=INK, spacing=8)
    for number, (x, y) in zip([18, 42, 66, 94],
                              [(1660, 485), (2100, 485), (1660, 770), (2100, 770)], strict=True):
        draw_thumbnail(canvas, number, x, y)

    # Bottom information panel.
    panel_box = (110, 1320, 2490, 1885)
    draw.rounded_rectangle(panel_box, radius=22, fill=PANEL, outline=GOLD, width=3)
    draw.line((1300, 1380, 1300, 1825), fill=TAUPE, width=3)
    draw.text((180, 1385), "DISPLAY COMPATIBILITY", font=font(39, serif=True, bold=True), fill=INK)
    items = ["FRAME TV ART MODE", "TELEVISIONS & MONITORS",
             "TABLETS & DIGITAL DISPLAYS", "SCREENSAVERS"]
    for index, item in enumerate(items):
        yy = 1470 + index * 78
        draw.ellipse((184, yy + 11, 202, yy + 29), fill=SAGE)
        draw.text((228, yy), item, font=font(31, bold=True), fill=MUTED)

    draw.text((1370, 1385), "READY FOR DISPLAY", font=font(39, serif=True, bold=True), fill=INK)
    right_lines = [
        "100 curated desert artworks",
        "3840 × 2160 JPG",
        "True 4K UHD • 16:9 landscape",
        "Instant digital download",
    ]
    for index, line in enumerate(right_lines):
        draw.text((1370, 1475 + index * 69), line, font=font(31, bold=index < 3), fill=MUTED)
    draw.text((1370, 1765), "Screen colors may vary by device and display settings.",
              font=font(24), fill=MUTED)
    return canvas


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists() and not BACKUP.exists():
        shutil.copy2(DESTINATION, BACKUP)

    image = build().convert("RGB")
    temp = DESTINATION.with_suffix(".tmp.jpg")
    image.save(temp, "JPEG", quality=95, optimize=True, subsampling=0)
    os.replace(temp, DESTINATION)
    with Image.open(DESTINATION) as check:
        if check.size != (W, H) or check.mode != "RGB" or check.format != "JPEG":
            raise RuntimeError("Rebuilt image 6 failed technical validation")

    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    revision = [
        "",
        "IMAGE 6 FULL-TV REVISION",
        f"Revised: {stamp}",
        "Status: PASS",
        "Reason: complete television chassis now visible on all four sides",
        "Exact customer artwork used: Desert-Southwest-074.jpg; previews 018, 042, 066, 094",
        "TV screen: exact 1408 × 792 (16:9); no artwork distortion",
        f"06-quality-compatibility.jpg: {DESTINATION.stat().st_size} bytes; SHA-256 {sha256(DESTINATION)}",
    ]
    existing = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    REPORT.write_text(existing.rstrip() + "\n" + "\n".join(revision) + "\n", encoding="utf-8")
    print(f"PASS: {DESTINATION}")


if __name__ == "__main__":
    main()
