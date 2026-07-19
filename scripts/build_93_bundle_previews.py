"""Create an alternate cover and Etsy preview slides for the 93-piece bundle."""

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
DEST = OUTPUT / "covers" / "everframe-93-previews"
SIZE = (3000, 2400)
STYLES = [
    ("coastal-landscape", "COASTAL & NATURE", 20),
    ("neutral-botanical", "NEUTRAL BOTANICAL", 21),
    ("modern-abstract-neutral", "MODERN ABSTRACT", 13),
    ("minimalist-line-art", "MINIMAL LINE ART", 13),
    ("vintage-botanical", "VINTAGE BOTANICAL", 13),
    ("seasonal-neutral", "SEASONAL NATURE", 13),
]


def font(size: int, bold: bool = False):
    filename = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(f"C:/Windows/Fonts/{filename}", size)


def load_style(style_id: str) -> list[Path]:
    folder = OUTPUT / "gemini" / style_id
    with (folder / "manifest.csv").open(encoding="utf-8") as file:
        return [folder / row["filename"] for row in csv.DictReader(file) if (folder / row["filename"]).exists()]


def crop_fill(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert("RGB")
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x = (image.width - size[0]) // 2
    y = (image.height - size[1]) // 2
    return ImageEnhance.Color(image.crop((x, y, x + size[0], y + size[1]))).enhance(0.94)


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGB", SIZE, "#eee8dc")
    return canvas, ImageDraw.Draw(canvas)


def save(canvas: Image.Image, name: str) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    canvas.save(DEST / name, "JPEG", quality=93, optimize=True)


def framed(canvas: Image.Image, draw: ImageDraw.ImageDraw, path: Path, box: tuple[int, int, int, int]) -> None:
    x, y, width, height = box
    canvas.paste(crop_fill(path, (width, height)), (x, y))
    draw.rectangle((x, y, x + width, y + height), outline="#292824", width=14)


def heading(draw: ImageDraw.ImageDraw, eyebrow: str, title: str, subtitle: str = "") -> None:
    draw.text((140, 90), eyebrow, font=font(64, True), fill="#7b8872")
    draw.text((140, 180), title, font=font(170, True), fill="#242522")
    if subtitle:
        draw.text((145, 390), subtitle, font=font(62), fill="#55564f")


def alternate_cover(styles: dict[str, list[Path]]) -> None:
    canvas, draw = base()
    draw.text((120, 45), "93", font=font(500, True), fill="#242522")
    draw.text((1120, 120), "FRAME TV", font=font(210, True), fill="#242522")
    draw.text((1120, 355), "ART COLLECTION", font=font(165, True), fill="#242522")
    draw.rounded_rectangle((1120, 620, 2750, 785), radius=50, fill="#7b8872")
    draw.text((1325, 650), "4K DIGITAL DOWNLOAD", font=font(85, True), fill="white")
    picks = [
        styles["coastal-landscape"][4], styles["neutral-botanical"][1],
        styles["modern-abstract-neutral"][6], styles["minimalist-line-art"][0],
        styles["vintage-botanical"][0], styles["seasonal-neutral"][8],
    ]
    boxes = [(120, 940, 1760, 950), (1960, 940, 920, 445), (1960, 1445, 920, 445),
             (120, 1970, 850, 310), (1075, 1970, 850, 310), (2030, 1970, 850, 310)]
    for art, box in zip(picks, boxes):
        framed(canvas, draw, art, box)
    draw.text((410, 2305), "6 CURATED STYLES • 93 ACTUAL ARTWORKS", font=font(58, True), fill="#56584f")
    save(canvas, "01-everframe-93-alternate-cover.jpg")


def category_grid(styles: dict[str, list[Path]], style_id: str, title: str, count: int, name: str) -> None:
    canvas, draw = base()
    heading(draw, f"{count} INCLUDED ARTWORKS", title, "Representative images from the actual download")
    items = styles[style_id]
    picks = [items[i] for i in (0, len(items)//5, 2*len(items)//5, 3*len(items)//5, 4*len(items)//5, len(items)-1)]
    boxes = [(140, 590, 1320, 740), (1540, 590, 1320, 740),
             (140, 1410, 850, 560), (1075, 1410, 850, 560), (2010, 1410, 850, 560),
             (1075, 2045, 850, 260)]
    for art, box in zip(picks, boxes):
        framed(canvas, draw, art, box)
    save(canvas, name)


def mixed_grid(styles: dict[str, list[Path]]) -> None:
    canvas, draw = base()
    heading(draw, "40 INCLUDED ARTWORKS", "THREE DISTINCT STYLES", "Modern abstract • minimal line art • vintage botanical")
    groups = [
        ("modern-abstract-neutral", "13 MODERN ABSTRACT"),
        ("minimalist-line-art", "13 MINIMAL LINE ART"),
        ("vintage-botanical", "13 VINTAGE BOTANICAL"),
    ]
    for column, (style_id, label) in enumerate(groups):
        x = 120 + column * 960
        draw.text((x, 570), label, font=font(48, True), fill="#56584f")
        for row, index in enumerate((0, 5, 10)):
            framed(canvas, draw, styles[style_id][index], (x, 660 + row * 540, 850, 470))
    save(canvas, "04-abstract-minimal-vintage-preview.jpg")


def included_slide(styles: dict[str, list[Path]]) -> None:
    canvas, draw = base()
    heading(draw, "EVERFRAME DIGITAL", "WHAT YOU RECEIVE", "A complete, ready-to-display Frame TV collection")
    framed(canvas, draw, styles["coastal-landscape"][7], (1550, 640, 1320, 750))
    lines = [
        "93 HIGH-RESOLUTION JPG FILES",
        "3840 × 2160 PIXELS • 4K UHD",
        "16:9 LANDSCAPE FORMAT",
        "5 ORGANIZED ZIP DOWNLOADS",
        "6 COORDINATED ART STYLES",
        "DIGITAL PRODUCT • NO SHIPPING",
    ]
    for i, line in enumerate(lines):
        y = 650 + i * 190
        draw.ellipse((150, y + 10, 205, y + 65), fill="#7b8872")
        draw.text((250, y), line, font=font(55, True), fill="#30302d")
    framed(canvas, draw, styles["neutral-botanical"][8], (1550, 1470, 630, 570))
    framed(canvas, draw, styles["seasonal-neutral"][3], (2240, 1470, 630, 570))
    draw.text((1550, 2120), "Download all five ZIP files to receive the full set.", font=font(48), fill="#56584f")
    save(canvas, "06-what-you-receive.jpg")


def how_to_slide(styles: dict[str, list[Path]]) -> None:
    canvas, draw = base()
    heading(draw, "INSTANT DIGITAL DOWNLOAD", "DISPLAY IN FOUR STEPS", "Simple setup with the Samsung SmartThings app")
    framed(canvas, draw, styles["coastal-landscape"][2], (1540, 620, 1320, 745))
    steps = [
        ("1", "DOWNLOAD", "Download all five ZIP files from Etsy."),
        ("2", "UNZIP", "Extract the JPG artworks on your device."),
        ("3", "UPLOAD", "Add a favorite through SmartThings."),
        ("4", "ENJOY", "Select it in Art Mode and adjust the mat."),
    ]
    for i, (number, title, body) in enumerate(steps):
        y = 650 + i * 360
        draw.ellipse((150, y, 330, y + 180), fill="#7b8872")
        draw.text((211, y + 25), number, font=font(95, True), fill="white")
        draw.text((390, y), title, font=font(65, True), fill="#292925")
        draw.text((390, y + 90), body, font=font(43), fill="#56584f")
    framed(canvas, draw, styles["modern-abstract-neutral"][2], (1540, 1450, 630, 570))
    framed(canvas, draw, styles["minimalist-line-art"][7], (2230, 1450, 630, 570))
    draw.text((1540, 2110), "Personal-use digital files • No physical product", font=font(48, True), fill="#56584f")
    save(canvas, "07-how-to-display.jpg")


def main() -> None:
    styles = {style_id: load_style(style_id) for style_id, _, _ in STYLES}
    if sum(len(items) for items in styles.values()) != 93:
        raise SystemExit(f"Expected 93 source artworks, found {sum(len(items) for items in styles.values())}")
    alternate_cover(styles)
    category_grid(styles, "coastal-landscape", "COASTAL & NATURE", 20, "02-coastal-nature-preview.jpg")
    category_grid(styles, "neutral-botanical", "NEUTRAL BOTANICAL", 21, "03-neutral-botanical-preview.jpg")
    mixed_grid(styles)
    category_grid(styles, "seasonal-neutral", "SEASONAL NATURE", 13, "05-seasonal-nature-preview.jpg")
    included_slide(styles)
    how_to_slide(styles)
    print(f"Created 7 Etsy images in {DEST}")


if __name__ == "__main__":
    main()
