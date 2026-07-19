"""Build the 100-piece mixed Frame TV art bundle and Etsy cover."""

import csv
import io
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
NAME = "everframe-100-frame-tv-art-collection"
MAX_PART = 19 * 1024 * 1024
STYLE_IDS = [
    "coastal-landscape",
    "neutral-botanical",
    "modern-abstract-neutral",
    "minimalist-line-art",
    "vintage-botanical",
    "seasonal-neutral",
]


def collect() -> list[Path]:
    result = []
    for style_id in STYLE_IDS:
        folder = OUTPUT / "gemini" / style_id
        with (folder / "manifest.csv").open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                path = folder / row["filename"]
                if path.exists():
                    result.append(path)
    result.extend(sorted((OUTPUT / "generated" / "everframe-100-additions").glob("*.png")))
    return result


def delivery_bytes(path: Path) -> bytes:
    with Image.open(path) as source:
        image = source.convert("RGB").resize((3840, 2160), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=76, optimize=True)
        return buffer.getvalue()


def build_parts(images: list[Path]) -> list[Path]:
    parts = []
    archive = None
    size = 0
    try:
        for index, path in enumerate(images, 1):
            data = delivery_bytes(path)
            if archive is None or (size and size + len(data) > MAX_PART):
                if archive:
                    archive.close()
                part = OUTPUT / "bundles" / f"{NAME}-part{len(parts) + 1}.zip"
                parts.append(part)
                archive = zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED)
                size = 0
            archive.writestr(f"everframe-{index:03d}-{path.stem}.jpg", data)
            size += len(data)
    finally:
        if archive:
            archive.close()
    if len(parts) > 5:
        raise SystemExit(f"Etsy allows 5 files; bundle produced {len(parts)}")
    return parts


def fill(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert("RGB")
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x = (image.width - size[0]) // 2
    y = (image.height - size[1]) // 2
    return ImageEnhance.Color(image.crop((x, y, x + size[0], y + size[1]))).enhance(0.9)


def font(size: int, bold: bool = False):
    filename = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(f"C:/Windows/Fonts/{filename}", size)


def build_cover(images: list[Path]) -> Path:
    canvas = Image.new("RGB", (3000, 2400), "#eee8dc")
    draw = ImageDraw.Draw(canvas)

    draw.text((120, 45), "100", font=font(500, True), fill="#242522")
    draw.text((1120, 120), "FRAME TV", font=font(210, True), fill="#242522")
    draw.text((1120, 355), "ART COLLECTION", font=font(165, True), fill="#242522")
    draw.rounded_rectangle((1120, 620, 2750, 785), radius=50, fill="#7b8872")
    draw.text((1325, 650), "4K DIGITAL DOWNLOAD", font=font(85, True), fill="white")

    picks = [images[1], images[22], images[43], images[58], images[97], images[88]]
    boxes = [
        (120, 940, 1760, 950),
        (1960, 940, 920, 445),
        (1960, 1445, 920, 445),
        (120, 1970, 850, 310),
        (1075, 1970, 850, 310),
        (2030, 1970, 850, 310),
    ]
    for path, (x, y, width, height) in zip(picks, boxes):
        canvas.paste(fill(path, (width, height)), (x, y))
        draw.rectangle((x, y, x + width, y + height), outline="#292824", width=14)

    draw.text((410, 2305), "6 CURATED STYLES • 100 ACTUAL ARTWORKS", font=font(58, True), fill="#56584f")

    path = OUTPUT / "covers" / f"{NAME}-cover.jpg"
    canvas.save(path, "JPEG", quality=92, optimize=True)
    return path


def main() -> None:
    images = collect()
    if len(images) != 100:
        raise SystemExit(f"Expected exactly 100 images, found {len(images)}")
    parts = build_parts(images)
    cover = build_cover(images)
    print(f"Cover: {cover}")
    for part in parts:
        print(f"ZIP: {part.name} ({part.stat().st_size / 1048576:.2f} MB)")


if __name__ == "__main__":
    main()
