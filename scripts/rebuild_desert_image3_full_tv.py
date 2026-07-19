"""Rebuild Desert-Southwest listing image 3 with a complete television."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


REPO = Path(__file__).resolve().parents[1]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Desert-Southwest"
ART_DIR = PRODUCT / "customer-downloads" / "_work" / "normalized-jpg"
OUTPUT = PRODUCT / "cover-v2-review"
WORK = OUTPUT / "_work"
DESTINATION = OUTPUT / "03-frame-tv-preview.jpg"
BACKUP = WORK / "03-frame-tv-preview-before-full-tv.jpg"
REPORT = OUTPUT / "generation-report.txt"

W, H = 2600, 2000
IVORY = "#f7f2e9"
TAUPE = "#c8bbaa"
INK = "#242520"
SAGE = "#66715f"
GOLD = "#b79a61"
FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
PREVIEWS = [5, 12, 20, 28, 36, 44, 60, 68, 76, 84, 92, 100]


def font(size: int, *, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = ("georgiab.ttf" if bold else "georgia.ttf") if serif else (
        "arialbd.ttf" if bold else "arial.ttf"
    )
    return ImageFont.truetype(str(FONT_DIR / name), size)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_art(number: int, size: tuple[int, int]) -> Image.Image:
    path = ART_DIR / f"Desert-Southwest-{number:03d}.jpg"
    if not path.is_file():
        raise RuntimeError(f"Missing exact customer artwork: {path.name}")
    with Image.open(path) as image:
        if image.size != (3840, 2160) or image.mode != "RGB":
            raise RuntimeError(f"Invalid normalized customer artwork: {path.name}")
        return ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS)


def add_shadow(canvas: Image.Image, box: tuple[int, int, int, int], blur: int = 24) -> None:
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=10, fill=145)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    layer = Image.new("RGBA", (W, H), (48, 39, 29, 0))
    layer.putalpha(mask)
    canvas.paste(layer, (0, 0), layer)


def draw_tv(canvas: Image.Image) -> None:
    # Exact 16:9 screen and a complete chassis with at least 60 px of background.
    x, y = 468, 250
    screen_w, screen_h, bezel = 1600, 900, 32
    outer_w, outer_h = screen_w + bezel * 2, screen_h + bezel * 2
    add_shadow(canvas, (x + 18, y + 25, x + outer_w + 18, y + outer_h + 25), 30)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((x, y, x + outer_w, y + outer_h), radius=11, fill="#1d1f1d")
    draw.rounded_rectangle((x + 7, y + 7, x + outer_w - 7, y + outer_h - 7),
                           radius=8, outline="#555850", width=3)
    draw.line((x + 18, y + 15, x + outer_w - 18, y + 15), fill="#7c7f77", width=2)
    draw.line((x + 16, y + 17, x + 16, y + outer_h - 17), fill="#454741", width=2)
    canvas.paste(load_art(52, (screen_w, screen_h)), (x + bezel, y + bezel))
    draw.rectangle((x + bezel - 2, y + bezel - 2,
                    x + bezel + screen_w + 1, y + bezel + screen_h + 1),
                   outline="#070807", width=4)
    center = x + outer_w // 2
    draw.rounded_rectangle((center - 23, y + outer_h - 3, center + 23, y + outer_h + 9),
                           radius=5, fill="#171817")
    draw.polygon([(x + 235, y + outer_h), (x + 300, y + outer_h),
                  (x + 280, y + outer_h + 22), (x + 250, y + outer_h + 22)], fill="#292b28")
    draw.polygon([(x + outer_w - 300, y + outer_h), (x + outer_w - 235, y + outer_h),
                  (x + outer_w - 250, y + outer_h + 22),
                  (x + outer_w - 280, y + outer_h + 22)], fill="#292b28")


def draw_preview(canvas: Image.Image, number: int, x: int, y: int) -> None:
    art_w, art_h = 360, 203
    add_shadow(canvas, (x + 6, y + 8, x + 380, y + 231), 10)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y, x + 380, y + 223), fill=GOLD)
    draw.rectangle((x + 3, y + 3, x + 377, y + 220), fill="#ead8b3")
    canvas.paste(load_art(number, (art_w, art_h)), (x + 10, y + 10))


def build() -> Image.Image:
    base = Image.new("RGB", (W, H), IVORY)
    paper = ImageOps.colorize(Image.effect_noise((W, H), 8).convert("L"), "#e0d7ca", "#fffdf8")
    canvas = Image.blend(base, paper, 0.07)
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle((110, 65, 2490, 190), radius=18, fill="#fbf8f1", outline=GOLD, width=3)
    heading = "EVERFRAME DIGITAL   •   FRAME TV ART PREVIEW   •   100 CURATED 4K ARTWORKS"
    box = draw.textbbox((0, 0), heading, font=font(31, bold=True))
    draw.text(((W - (box[2] - box[0])) / 2, 109), heading, font=font(31, bold=True), fill=INK)

    draw_tv(canvas)
    draw.rectangle((0, 1320, W, H), fill=TAUPE)
    draw.text((110, 1340), "EXPLORE MORE ARTWORKS INCLUDED IN THE COLLECTION",
              font=font(27, bold=True), fill=INK)
    positions = []
    for row_y in (1400, 1670):
        for col in range(6):
            positions.append((110 + col * 400, row_y))
    for number, (x, y) in zip(PREVIEWS, positions, strict=True):
        draw_preview(canvas, number, x, y)
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
            raise RuntimeError("Rebuilt image 3 failed technical validation")

    revision = [
        "",
        "IMAGE 3 FULL-TV REVISION",
        f"Revised: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "Status: PASS",
        "Reason: complete television chassis visible on all four sides at full and thumbnail size",
        "Exact featured customer artwork: Desert-Southwest-052.jpg",
        "Exact additional artworks: " + ", ".join(f"Desert-Southwest-{n:03d}.jpg" for n in PREVIEWS),
        "TV screen: exact 1600 × 900 (16:9); no artwork distortion",
        f"03-frame-tv-preview.jpg: {DESTINATION.stat().st_size} bytes; SHA-256 {sha256(DESTINATION)}",
    ]
    existing = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    REPORT.write_text(existing.rstrip() + "\n" + "\n".join(revision) + "\n", encoding="utf-8")
    print(f"PASS: {DESTINATION}")


if __name__ == "__main__":
    main()
