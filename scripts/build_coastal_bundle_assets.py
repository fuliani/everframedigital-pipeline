"""Build the Etsy delivery ZIPs and listing cover for the 20-piece coastal set."""

import csv
import io
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
CONFIG_PATH = ROOT / "config" / "styles.json"
ETSY_MAX_FILE_BYTES = 19 * 1024 * 1024


NAME = "everframe-coastal-collection-20"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_images(style_id: str, config: dict) -> list[dict]:
    style = next(item for item in config["styles"] if item["id"] == style_id)
    manifest = OUTPUT_DIR / "gemini" / style_id / "manifest.csv"
    rows = list(csv.DictReader(manifest.open("r", encoding="utf-8")))
    return [
        {"path": manifest.parent / row["filename"], "style_name": style["name"]}
        for row in rows
        if (manifest.parent / row["filename"]).exists()
    ]


def compressed_jpeg(path: Path) -> bytes:
    out = io.BytesIO()
    Image.open(path).convert("RGB").save(out, "JPEG", quality=78, optimize=True)
    return out.getvalue()


def build_zip_parts(images: list[dict], base: Path) -> list[Path]:
    parts: list[Path] = []
    current = None
    current_size = 0
    try:
        for item in images:
            data = compressed_jpeg(item["path"])
            if current is None or (current_size and current_size + len(data) > ETSY_MAX_FILE_BYTES):
                if current:
                    current.close()
                part = base.with_name(f"{base.stem}-part{len(parts) + 1}.zip")
                parts.append(part)
                current = zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED)
                current_size = 0
            current.writestr(item["path"].stem + ".jpg", data)
            current_size += len(data)
    finally:
        if current:
            current.close()
    return parts


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)


def crop_fill(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    src = image.convert("RGB")
    scale = max(size[0] / src.width, size[1] / src.height)
    resized = src.resize((round(src.width * scale), round(src.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def main() -> None:
    config = load_json(CONFIG_PATH)
    images = collect_images("coastal-landscape", config)
    if len(images) != 20:
        raise SystemExit(f"Expected 20 coastal images, found {len(images)}")

    parts = build_zip_parts(images, OUTPUT_DIR / "bundles" / f"{NAME}.zip")

    canvas = Image.new("RGB", (3000, 2400), "#eee7da")
    draw = ImageDraw.Draw(canvas)
    picks = [images[i]["path"] for i in (1, 4, 7, 13, 18)]
    panels = [
        (120, 900, 1800, 1012),
        (1990, 900, 890, 480),
        (1990, 1432, 890, 480),
        (120, 1964, 866, 316),
        (1053, 1964, 866, 316),
    ]
    for path, (x, y, w, h) in zip(picks, panels):
        art = crop_fill(Image.open(path), (w, h))
        art = ImageEnhance.Color(art).enhance(0.9)
        canvas.paste(art, (x, y))
        draw.rectangle((x, y, x + w, y + h), outline="#2b2925", width=16)

    draw.text((120, 95), "20", font=font(450, True), fill="#242522")
    draw.text((990, 150), "COASTAL", font=font(220, True), fill="#242522")
    draw.text((990, 390), "FRAME TV ART", font=font(190, True), fill="#242522")
    draw.rounded_rectangle((990, 660, 2660, 820), radius=55, fill="#7b8872")
    draw.text((1135, 690), "4K DIGITAL DOWNLOAD", font=font(92, True), fill="white")
    draw.text((120, 2315), "LANDSCAPES  •  LIGHTHOUSES  •  OCEAN VIEWS", font=font(48, True), fill="#56584f")

    cover = OUTPUT_DIR / "covers" / f"{NAME}-cover.jpg"
    cover.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(cover, quality=92, optimize=True)

    print(f"Cover: {cover}")
    for part in parts:
        print(f"ZIP: {part} ({part.stat().st_size / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
