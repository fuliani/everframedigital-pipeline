from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "Vintage-scripture-paintings"
SOURCE = PRODUCT / "source-art-v2"
ART = PRODUCT / "customer-downloads-v3" / "_work" / "normalized-jpg"
DOWNLOADS = PRODUCT / "customer-downloads-v3"
LISTING = PRODUCT / "cover-premium-v2-review"
QC = LISTING / "_work" / "qc"
FONT = Path(r"C:\Windows\Fonts\arialbd.ttf")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ahash(path: Path) -> int:
    with Image.open(path) as image:
        pixels = list(ImageOps.grayscale(image).resize((16, 16), Image.Resampling.LANCZOS).getdata())
    mean = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= mean)
    return value


def contact(paths: list[Path], target: Path, columns: int, cell: tuple[int, int]) -> None:
    cw, ch = cell
    rows = (len(paths) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * cw, rows * ch), "#e9e2d5")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(FONT), max(18, ch // 14))
    for index, path in enumerate(paths):
        x = (index % columns) * cw
        y = (index // columns) * ch
        with Image.open(path) as image:
            preview = ImageOps.fit(image.convert("RGB"), (cw - 8, ch - 8), Image.Resampling.LANCZOS)
        canvas.paste(preview, (x + 4, y + 4))
        label = path.stem.split("-")[-1]
        draw.rounded_rectangle((x + 10, y + 10, x + 78, y + 44), 6, fill=(20, 17, 14))
        draw.text((x + 44, y + 27), label, font=font, fill="white", anchor="mm")
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, "JPEG", quality=92, optimize=True)


def main() -> None:
    source = [SOURCE / f"Vintage-Scripture-Base-{i:03d}.png" for i in range(1, 101)]
    art = [ART / f"Vintage-Scripture-Paintings-{i:03d}.jpg" for i in range(1, 101)]
    listing = [LISTING / name for name in [
        "01-main-cover.jpg", "02-product-details.jpg", "03-collection-specs.jpg", "04-how-to-download.jpg",
        "05-compatibility.jpg", "06-premium-quality.jpg", "07-framed-gallery-one.jpg",
        "08-framed-gallery-two.jpg", "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg",
    ]]
    if not all(path.is_file() for path in source + art + listing):
        raise RuntimeError("A required source, delivery, or listing image is missing")

    for path in art:
        with Image.open(path) as image:
            image.load()
            if image.size != (3840, 2160) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid delivery image: {path.name}")
    for path in listing:
        with Image.open(path) as image:
            image.load()
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid listing image: {path.name}")

    exact = [digest(path) for path in art]
    if len(set(exact)) != 100:
        raise RuntimeError("Exact duplicate delivery artwork found")
    hashes = [ahash(path) for path in source]
    near = []
    for left in range(100):
        for right in range(left + 1, 100):
            distance = (hashes[left] ^ hashes[right]).bit_count()
            if distance <= 18:
                near.append({"left": left + 1, "right": right + 1, "distance": distance})

    zips = sorted(DOWNLOADS.glob("Vintage-Scripture-Paintings-100-Images-Part*of5.zip"))
    if len(zips) != 5:
        raise RuntimeError("Expected exactly five ZIP archives")
    members: list[str] = []
    zip_rows = []
    for path in zips:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"CRC failure: {path.name}")
            names = archive.namelist()
        members.extend(names)
        zip_rows.append({"name": path.name, "bytes": path.stat().st_size, "members": len(names)})
        if path.stat().st_size > 19_500_000:
            raise RuntimeError(f"ZIP exceeds conservative Etsy target: {path.name}")
    expected = [path.name for path in art]
    if sorted(members) != sorted(expected) or len(set(members)) != 100:
        raise RuntimeError("ZIP membership does not match the 100 delivery artworks")

    contact(art, QC / "customer-art-contact-sheet.jpg", 5, (500, 281))
    contact(listing, QC / "listing-contact-sheet.jpg", 2, (650, 500))
    report = {
        "status": "PASS",
        "source_images": 100,
        "delivery_images": 100,
        "listing_images": 10,
        "exact_duplicates": 0,
        "perceptual_pairs_requiring_visual_review": near,
        "zip_archives": zip_rows,
        "customer_contact_sheet": str(QC / "customer-art-contact-sheet.jpg"),
        "listing_contact_sheet": str(QC / "listing-contact-sheet.jpg"),
    }
    (QC / "qc-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
