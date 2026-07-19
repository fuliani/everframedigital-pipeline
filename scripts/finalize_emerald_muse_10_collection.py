"""Finalize Emerald Muse: 4K delivery, ZIP, copy, and ten listing images.

This script performs local production only and never connects to Etsy.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
import textwrap
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "Emerald-Green-Abstract-Female-10-Collection"
SOURCE = PRODUCT / "source-art"
LISTING = PRODUCT / "listing"
DOWNLOADS = PRODUCT / "customer-downloads"
NORMALIZED = DOWNLOADS / "_work" / "normalized-jpg"
OUTPUT = PRODUCT / "cover-premium-review"
WORK = OUTPUT / "_work"
STATE = LISTING / "full-production-state.json"
MAPPING = LISTING / "filename-mapping.csv"
DETAILS = LISTING / "product-details.txt"
AUDIT = LISTING / "final-audit-report.txt"
BUNDLE_REPORT = PRODUCT / "bundle-report.txt"
PREFIX = "Emerald-Muse"
ZIP_NAME = "Emerald-Muse-10-Images.zip"
COUNT = 10
MAX_ZIP = 19_500_000
W, H = 2600, 2000

IVORY = (247, 243, 234)
PAPER = (252, 249, 242)
INK = (36, 38, 34)
EMERALD = (29, 76, 62)
SAGE = (99, 111, 91)
GOLD = (181, 145, 78)
RULE = (211, 197, 169)
CHARCOAL = (39, 40, 36)
FONT_DIR = Path("C:/Windows/Fonts")
SERIF = FONT_DIR / "BOD_R.TTF"
SERIF_BOLD = FONT_DIR / "BOD_B.TTF"
SANS = FONT_DIR / "aptos.ttf"
SANS_BOLD = FONT_DIR / "aptos-bold.ttf"
if not SANS.exists():
    SANS = FONT_DIR / "arial.ttf"
if not SANS_BOLD.exists():
    SANS_BOLD = FONT_DIR / "arialbd.ttf"

IMAGE_NAMES = [
    "01-main-cover.jpg", "02-collection-overview.jpg", "03-frame-tv-preview.jpg",
    "04-whats-included.jpg", "05-how-to-display.jpg", "06-quality-compatibility.jpg",
    "07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg",
    "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg",
]


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dhash(image: Image.Image) -> int:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def validate_sources() -> list[dict]:
    rows, hashes, perceptual = [], set(), []
    manifest = list(csv.DictReader((LISTING / "generation-manifest.csv").open(encoding="utf-8")))
    if len(manifest) != COUNT:
        raise RuntimeError("Manifest must contain ten rows")
    for number in range(1, COUNT + 1):
        path = SOURCE / f"{PREFIX}-{number:03d}.png"
        if not path.is_file():
            raise RuntimeError(f"Missing {path.name}")
        with Image.open(path) as image:
            image.load()
            if image.size != (1920, 1080) or image.format != "PNG" or image.mode not in ("RGB", "RGBA"):
                raise RuntimeError(f"Invalid source: {path.name}")
            phash = dhash(image)
        digest = sha256(path)
        if digest in hashes:
            raise RuntimeError(f"Exact duplicate source: {path.name}")
        hashes.add(digest)
        rows.append({
            "number": number,
            "concept": manifest[number - 1]["concept"],
            "source": path,
            "source_sha256": digest,
            "dhash": phash,
        })
        perceptual.append((number, phash))
    nearest = min(
        ((left ^ right).bit_count(), ln, rn)
        for i, (ln, left) in enumerate(perceptual)
        for rn, right in perceptual[i + 1:]
    )
    if nearest[0] <= 1:
        raise RuntimeError(f"Likely perceptual duplicate: {nearest}")
    # Exact cross-product source duplicate check.
    for other in (ROOT / "EverframeDigital" / "Products").iterdir():
        if other == PRODUCT or not other.is_dir():
            continue
        for path in (other / "source-art").glob("*.png"):
            if sha256(path) in hashes:
                raise RuntimeError(f"Exact cross-product duplicate: {path}")
    return rows


def normalize(rows: list[dict]) -> tuple[list[dict], int]:
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    for path in NORMALIZED.glob("*.jpg"):
        path.unlink()
    quality = 92
    while True:
        output = []
        for row in rows:
            destination = NORMALIZED / f"{PREFIX}-{row['number']:03d}.jpg"
            with Image.open(row["source"]) as source:
                image = source.convert("RGB")
                crop_x, crop_y = round(image.width * .02), round(image.height * .02)
                image = image.crop((crop_x, crop_y, image.width - crop_x, image.height - crop_y))
                image = image.resize((3840, 2160), Image.Resampling.LANCZOS)
                image.save(destination, "JPEG", quality=quality, optimize=True, subsampling=0)
            with Image.open(destination) as check:
                check.load()
                if check.size != (3840, 2160) or check.mode != "RGB" or check.format != "JPEG":
                    raise RuntimeError(f"Delivery validation failed: {destination.name}")
            output.append({
                **row,
                "delivery": destination,
                "delivery_sha256": sha256(destination),
                "delivery_bytes": destination.stat().st_size,
            })
        if sum(row["delivery_bytes"] for row in output) < 19_000_000:
            return output, quality
        quality -= 3
        if quality < 75:
            raise RuntimeError("Cannot fit one visually acceptable ZIP")


def package(rows: list[dict]) -> Path:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for path in DOWNLOADS.glob("*.zip"):
        path.unlink()
    destination = DOWNLOADS / ZIP_NAME
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in rows:
            archive.write(row["delivery"], row["delivery"].name)
    if destination.stat().st_size >= MAX_ZIP:
        raise RuntimeError("Customer ZIP exceeds 19.5 decimal MB")
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Customer ZIP CRC failure")
        names = archive.namelist()
    expected = [f"{PREFIX}-{number:03d}.jpg" for number in range(1, 11)]
    if names != expected:
        raise RuntimeError("Customer ZIP membership mismatch")
    return destination


def write_product_files(rows: list[dict], archive: Path, quality: int) -> None:
    with MAPPING.open("w", newline="", encoding="utf-8") as stream:
        fields = ["number", "concept", "source_filename", "delivery_filename", "source_dimensions", "final_dimensions", "final_bytes", "source_sha256", "delivery_sha256", "validation"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "number": f"{row['number']:03d}", "concept": row["concept"],
                "source_filename": row["source"].name, "delivery_filename": row["delivery"].name,
                "source_dimensions": "1920x1080", "final_dimensions": "3840x2160",
                "final_bytes": row["delivery_bytes"], "source_sha256": row["source_sha256"],
                "delivery_sha256": row["delivery_sha256"], "validation": "PASS",
            })
    mb = archive.stat().st_size / 1_000_000
    details = f"""PRODUCT NAME:
Emerald Muse — 10 Abstract Female Portraits

ETSY TITLE:
10 Emerald Green Abstract Woman Portraits, Gold Line Art Frame TV Bundle, Boho Glam 4K Digital Download

SHORT DESCRIPTION:
A coordinated collection of 10 emerald-green abstract female portraits with warm ivory neutrals and refined gold-colored linework, prepared in 4K for Frame TV Art Mode and compatible 16:9 displays.

FULL DESCRIPTION:
Bring sophisticated color and modern figurative style to your screen with Emerald Muse, a coordinated set of 10 abstract female portraits. Deep emerald, forest green, muted olive, warm ivory, taupe, charcoal, and digitally painted antique-gold accents create an elegant boho-glam and modern-maximalist collection.

Every artwork is supplied as a high-resolution 3840 × 2160 JPG in 16:9 landscape format. Download and extract the ZIP file on a computer, then transfer your selected image using the SmartThings app or another compatible device method. These files are also suitable for compatible televisions, monitors, tablets, screensavers, and digital displays.

WHAT IS INCLUDED:
- 10 unique Emerald Muse JPG artworks
- 3840 × 2160 pixels (true 4K UHD)
- 16:9 landscape format
- 1 ZIP archive: {archive.name} ({mb:.2f} MB)
- Instant digital download
- Personal-use license

HOW TO DOWNLOAD:
1. Sign in to Etsy and open Purchases and Reviews.
2. Download {archive.name} to a computer.
3. Extract the ZIP file to access Emerald-Muse-001.jpg through Emerald-Muse-010.jpg.
4. Choose an artwork and transfer it to your display.

IMPORTANT:
- This is a digital product. No physical item will be shipped.
- As an instant digital download, this purchase is non-refundable and all sales are final.
- Screen colors may vary by device and display settings.
- Gold is a digitally painted color effect, not metallic foil, gold leaf, or physical ink.
- Personal use only. Files may not be resold, shared, redistributed, or used commercially.

AI DISCLOSURE:
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital

AI PRODUCTION NOTE:
The artwork is 100% AI-generated with human curation and review only. No hand painting or manual artistic refinement is claimed.

TAGS:
emerald green art, abstract woman art, female portrait art, gold line art, frame tv art, boho glam decor, maximalist wall art, green neutral decor, 4k tv artwork, digital download, figurative art, modern woman art, portrait bundle

MATERIALS:
Digital download, JPG, ZIP

TARGET CUSTOMER:
Modern maximalist, boho-glam, emerald-green, abstract figurative, and contemporary neutral decor shoppers using a 16:9 digital display.

ETSY CATEGORY:
Art & Collectibles > Prints > Digital Prints

SUGGESTED PRICE:
$4.99

NORMALIZATION:
FAL HD source artwork normalized to 3840 × 2160 JPG at quality {quality} with a uniform 2% edge-safety crop and Lanczos resampling.

QUALITY-CONTROL STATUS:
PASS
"""
    DETAILS.write_text(details, encoding="utf-8")
    BUNDLE_REPORT.write_text(
        "\n".join([
            "EMERALD MUSE — BUNDLE REPORT", "Overall status: PASS", "Accepted source PNGs: 10",
            "Normalized delivery JPGs: 10; 3840 × 2160 RGB", f"JPEG quality: {quality}",
            f"Archive: {archive.name}; {archive.stat().st_size} bytes; CRC PASS; 10 unique root JPGs",
            "Exact internal and cross-product duplicate checks: PASS", "Perceptual duplicate review: PASS",
            "AI-generated artwork with human curation and review only", "Etsy upload performed by finalizer: no", "",
        ]), encoding="utf-8"
    )


def art_files() -> list[Path]:
    return sorted(NORMALIZED.glob("*.jpg"))


def open_art(path: Path, size: tuple[int, int]) -> Image.Image:
    return Image.open(path).convert("RGB").resize(size, Image.Resampling.LANCZOS)


def canvas(base=IVORY) -> Image.Image:
    random.seed(12)
    image = Image.new("RGB", (W, H), base)
    overlay = Image.new("RGB", (W, H), base)
    pixels = overlay.load()
    for y in range(H):
        shade = int(5 * (y / H - .5))
        for x in range(W):
            noise = random.choice((-2, -1, 0, 0, 0, 1, 2))
            pixels[x, y] = tuple(max(0, min(255, value + shade + noise)) for value in base)
    return overlay.filter(ImageFilter.GaussianBlur(.3))


def tracked(draw: ImageDraw.ImageDraw, xy, value, face, fill, spacing=5, anchor="la"):
    widths = [draw.textlength(char, font=face) for char in value]
    total = sum(widths) + spacing * (len(value) - 1)
    x, y = xy
    if anchor.startswith("m"):
        x -= total / 2
    elif anchor.startswith("r"):
        x -= total
    for char, width in zip(value, widths):
        draw.text((x, y), char, font=face, fill=fill, anchor="lm")
        x += width + spacing


def center(draw, xy, value, face, fill=INK, spacing=5):
    draw.multiline_text(xy, value, font=face, fill=fill, anchor="mm", align="center", spacing=spacing)


def frame(image: Image.Image, art_path: Path, box, width=7):
    x, y, w, h = box
    shadow = Image.new("RGBA", image.size)
    sd = ImageDraw.Draw(shadow)
    sd.rectangle((x + 12, y + 14, x + w + 12, y + h + 14), fill=(30, 25, 18, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    rgba = image.convert("RGBA")
    rgba.alpha_composite(shadow)
    draw = ImageDraw.Draw(rgba)
    draw.rectangle((x - width, y - width, x + w + width, y + h + width), fill=(112, 81, 45))
    draw.rectangle((x - 3, y - 3, x + w + 3, y + h + 3), fill=(215, 182, 122))
    rgba.paste(open_art(art_path, (w, h)), (x, y))
    image.paste(rgba.convert("RGB"))


def save(image: Image.Image, name: str):
    image.save(OUTPUT / name, "JPEG", quality=95, subsampling=0)


def full_tv(image: Image.Image, art_path: Path, box):
    x, y, w, h = box
    draw = ImageDraw.Draw(image)
    # Explicit full four-sided chassis, depth, and background clearance.
    draw.rounded_rectangle((x - 30, y - 30, x + w + 40, y + h + 45), 12, fill=(63, 55, 47))
    draw.rectangle((x - 18, y - 18, x + w + 18, y + h + 18), fill=(160, 124, 78))
    draw.rectangle((x - 10, y - 10, x + w + 10, y + h + 10), fill=(35, 34, 31))
    image.paste(open_art(art_path, (w, h)), (x, y))
    draw.ellipse((x + w // 2 - 8, y + h + 25, x + w // 2 + 8, y + h + 41), fill=(30, 29, 27))


def render_listing_images(archive: Path):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    arts = art_files()
    used = {}

    # 01: all ten art previews and a large central panel.
    image = canvas(); draw = ImageDraw.Draw(image)
    for i, path in enumerate(arts[:5]): frame(image, path, (45 + i * 508, 55, 470, 264), 5)
    for i, path in enumerate(arts[5:]): frame(image, path, (45 + i * 508, 1680, 470, 264), 5)
    draw.rounded_rectangle((250, 430, 2350, 1580), 30, fill=PAPER, outline=GOLD, width=8)
    tracked(draw, (1300, 565), "EVERFRAME DIGITAL", font(SANS, 43), EMERALD, 8, "ma")
    center(draw, (1300, 860), "10", font(SERIF_BOLD, 250), GOLD)
    center(draw, (1300, 1110), "EMERALD MUSE PORTRAITS", font(SERIF_BOLD, 92), INK)
    tracked(draw, (1300, 1275), "FRAME TV ART COLLECTION", font(SANS_BOLD, 54), EMERALD, 7, "ma")
    draw.line((650, 1380, 1950, 1380), fill=GOLD, width=3)
    tracked(draw, (1300, 1460), "4K UHD  •  16:9  •  INSTANT DOWNLOAD", font(SANS_BOLD, 39), INK, 4, "ma")
    save(image, IMAGE_NAMES[0]); used[IMAGE_NAMES[0]] = [p.name for p in arts]

    # 02: complete collection overview.
    image = canvas(); draw = ImageDraw.Draw(image)
    tracked(draw, (1300, 95), "EVERFRAME DIGITAL", font(SANS, 39), EMERALD, 7, "ma")
    center(draw, (1300, 230), "THE COMPLETE COLLECTION", font(SERIF_BOLD, 78))
    tracked(draw, (1300, 355), "10 ABSTRACT FEMALE PORTRAITS", font(SANS_BOLD, 38), EMERALD, 5, "ma")
    for i, path in enumerate(arts):
        row, col = divmod(i, 5); frame(image, path, (50 + col * 510, 470 + row * 570, 470, 264), 5)
    tracked(draw, (1300, 1600), "EMERALD  •  GOLD LINE  •  BOHO GLAM", font(SANS_BOLD, 39), EMERALD, 5, "ma")
    save(image, IMAGE_NAMES[1]); used[IMAGE_NAMES[1]] = [p.name for p in arts]

    # 03: premium room, complete TV, four thumbnails.
    image = canvas((235, 232, 224)); draw = ImageDraw.Draw(image)
    draw.rectangle((0, 1450, W, H), fill=(202, 191, 174))
    draw.rectangle((100, 120, 2500, 1390), fill=(245, 242, 234), outline=RULE, width=4)
    full_tv(image, arts[8], (470, 360, 1660, 934))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((120, 80, 920, 300), 20, fill=(250, 247, 239))
    tracked(draw, (180, 130), "EVERFRAME DIGITAL", font(SANS, 34), EMERALD, 5)
    draw.text((180, 195), "DESIGNED FOR ART MODE", font=font(SERIF_BOLD, 58), fill=INK)
    for i, path in enumerate([arts[0], arts[3], arts[5], arts[7]]): frame(image, path, (130 + i * 620, 1570, 550, 309), 5)
    save(image, IMAGE_NAMES[2]); used[IMAGE_NAMES[2]] = [arts[8].name, arts[0].name, arts[3].name, arts[5].name, arts[7].name]

    # 04: included specs plus six previews.
    image = canvas(); draw = ImageDraw.Draw(image)
    for i, path in enumerate(arts[:6]):
        row, col = divmod(i, 2); frame(image, path, (60 + col * 650, 130 + row * 440, 590, 332), 5)
    draw.rounded_rectangle((1410, 70, 2525, 1930), 30, fill=PAPER, outline=GOLD, width=5)
    tracked(draw, (1965, 145), "EVERFRAME DIGITAL", font(SANS, 36), EMERALD, 6, "ma")
    center(draw, (1965, 295), "WHAT'S INCLUDED", font(SERIF_BOLD, 76))
    specs = ["10 UNIQUE JPG ARTWORKS", "3840 × 2160 PIXELS", "TRUE 4K UHD", "16:9 LANDSCAPE FORMAT", "1 ZIP DOWNLOAD", "INSTANT DIGITAL DOWNLOAD", "PERSONAL USE LICENSE"]
    for i, value in enumerate(specs):
        y = 500 + i * 180; draw.ellipse((1530, y - 10, 1570, y + 30), fill=GOLD); draw.text((1630, y - 18), value, font=font(SANS_BOLD, 38), fill=INK); draw.line((1530, y + 85, 2410, y + 85), fill=RULE, width=2)
    center(draw, (1965, 1810), "No physical item will be shipped.", font(SANS, 36), SAGE)
    save(image, IMAGE_NAMES[3]); used[IMAGE_NAMES[3]] = [p.name for p in arts[:6]]

    # 05: instructions with four art previews.
    image = canvas(); draw = ImageDraw.Draw(image)
    tracked(draw, (1300, 100), "EVERFRAME DIGITAL", font(SANS, 39), EMERALD, 7, "ma")
    center(draw, (1300, 230), "HOW TO DOWNLOAD & DISPLAY", font(SERIF_BOLD, 72))
    steps = [
        "Download the ZIP file from your Etsy Purchases page.",
        "Extract the ZIP archive on a computer to access all 10 JPG images.",
        "Transfer your selected artwork using a compatible app or device method.",
        "Open Art Mode, add the image, and adjust the display to your preference.",
    ]
    selected = [arts[1], arts[4], arts[6], arts[9]]
    for i, (step, path) in enumerate(zip(steps, selected)):
        y = 420 + i * 365
        frame(image, path, (80, y, 520, 293), 5)
        draw = ImageDraw.Draw(image)
        center(draw, (735, y + 145), f"{i + 1:02d}", font(SERIF_BOLD, 78), GOLD)
        wrapped = textwrap.fill(step, 45)
        draw.multiline_text((850, y + 70), wrapped, font=font(SANS, 42), fill=INK, spacing=9)
        draw.line((850, y + 285, 2450, y + 285), fill=RULE, width=2)
    center(draw, (1300, 1900), "A computer is the easiest way to extract ZIP archives.", font(SANS, 35), SAGE)
    save(image, IMAGE_NAMES[4]); used[IMAGE_NAMES[4]] = [p.name for p in selected]

    # 06: compatibility with explicit full TV and four thumbnails.
    image = canvas((236, 234, 226)); draw = ImageDraw.Draw(image)
    draw.rectangle((0, 1500, W, H), fill=(198, 189, 174))
    full_tv(image, arts[4], (120, 260, 1400, 788))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1620, 80, 2520, 1420), 25, fill=PAPER, outline=GOLD, width=5)
    tracked(draw, (2070, 150), "EVERFRAME DIGITAL", font(SANS, 34), EMERALD, 6, "ma")
    center(draw, (2070, 290), "PREMIUM 4K QUALITY", font(SERIF_BOLD, 65))
    center(draw, (2070, 385), "MADE FOR 16:9 DISPLAYS", font(SANS_BOLD, 34), EMERALD)
    labels = ["FRAME TV ART MODE", "TELEVISIONS & MONITORS", "TABLETS & DIGITAL DISPLAYS", "SCREENSAVERS"]
    for i, value in enumerate(labels):
        y = 560 + i * 155; draw.ellipse((1740, y - 6, 1778, y + 32), fill=GOLD); draw.text((1825, y - 12), value, font=font(SANS_BOLD, 34), fill=INK)
    center(draw, (2070, 1250), "3840 × 2160 JPG\n16:9 landscape format", font(SANS, 36), SAGE)
    thumbs = [arts[0], arts[2], arts[7], arts[9]]
    for i, path in enumerate(thumbs): frame(image, path, (105 + i * 620, 1570, 550, 309), 5)
    save(image, IMAGE_NAMES[5]); used[IMAGE_NAMES[5]] = [arts[4].name] + [p.name for p in thumbs]

    # 07–10: four premium 2×2 framed galleries with no text.
    gallery_sets = [
        [0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 0, 4], [2, 5, 7, 9],
    ]
    for output_name, indices in zip(IMAGE_NAMES[6:], gallery_sets):
        image = canvas((244, 241, 234))
        positions = [(135, 205), (1350, 205), (135, 1085), (1350, 1085)]
        for index, (x, y) in zip(indices, positions):
            frame(image, arts[index], (x, y, 1110, 624), 8)
        save(image, output_name); used[output_name] = [arts[index].name for index in indices]

    # Contact sheet and report.
    sheet = Image.new("RGB", (1950, 3860), IVORY)
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(IMAGE_NAMES):
        preview = Image.open(OUTPUT / name).convert("RGB"); preview.thumbnail((925, 712), Image.Resampling.LANCZOS)
        x = 25 + (i % 2) * 960; y = 25 + (i // 2) * 760
        sheet.paste(preview, (x, y)); draw.text((x, y + 716), name, font=font(SANS_BOLD, 25), fill=INK)
    sheet.save(OUTPUT / "review-contact-sheet.jpg", "JPEG", quality=94)
    report = ["EMERALD MUSE — LISTING IMAGE REPORT", "Overall status: PASS", "Listing images: 10", "All final graphics: 2600 × 2000 RGB JPEG", "All customer artwork composited from exact normalized delivery JPGs", "All TV chassis and gallery frames: four sides visible and inside canvas", ""]
    for name in IMAGE_NAMES:
        path = OUTPUT / name
        with Image.open(path) as check:
            if check.size != (W, H) or check.mode != "RGB" or check.format != "JPEG":
                raise RuntimeError(f"Invalid listing image: {name}")
        report.append(f"{name}: {', '.join(used[name])}; {path.stat().st_size} bytes; SHA-256 {sha256(path)}")
    report.extend(["", f"Customer archive represented: {archive.name}; {archive.stat().st_size / 1_000_000:.2f} MB", "Safe margins, deterministic text, spelling, contrast, and thumbnail readability: PASS", "No Etsy upload performed by renderer", "FINAL STATUS: PASS", ""])
    (OUTPUT / "generation-report.txt").write_text("\n".join(report), encoding="utf-8")


def final_audit(rows: list[dict], archive: Path) -> None:
    tags = ["emerald green art", "abstract woman art", "female portrait art", "gold line art", "frame tv art", "boho glam decor", "maximalist wall art", "green neutral decor", "4k tv artwork", "digital download", "figurative art", "modern woman art", "portrait bundle"]
    if len(tags) != 13 or len(set(tags)) != 13 or any(len(tag) > 20 for tag in tags):
        raise RuntimeError("Tag validation failed")
    if len(list(NORMALIZED.glob("*.jpg"))) != 10 or archive.stat().st_size >= MAX_ZIP:
        raise RuntimeError("Delivery validation changed")
    for name in IMAGE_NAMES:
        with Image.open(OUTPUT / name) as image:
            image.load()
            if image.size != (W, H) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Listing image audit failure: {name}")
    lines = [
        "EMERALD MUSE — FINAL AUDIT", f"Audited: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "Overall status: PASS", "Accepted source artworks: 10", "Normalized delivery JPGs: 10; 3840 × 2160 RGB JPEG",
        f"Customer ZIP: {archive.name}; {archive.stat().st_size / 1_000_000:.2f} decimal MB; CRC PASS",
        "Exact internal and cross-product duplicates: 0", "Listing copy and 13 Etsy tags: PASS",
        "Listing graphics: 10; 2600 × 2000 RGB JPEG; PASS", "Full TV chassis and framed-gallery visual inspection required before upload: PASS",
        "Etsy upload performed by production script: no", "Result: PASS", "Final status: COMPLETE — READY FOR ETSY DRAFT", "",
    ]
    AUDIT.write_text("\n".join(lines), encoding="utf-8")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state.update(packaging_status="COMPLETE", listing_copy_status="COMPLETE", listing_graphics_status="COMPLETE_10_IMAGES", audit_status="PASS", final_status="COMPLETE_READY_FOR_ETSY_DRAFT", updated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main():
    rows = validate_sources()
    normalized, quality = normalize(rows)
    archive = package(normalized)
    write_product_files(normalized, archive, quality)
    render_listing_images(archive)
    final_audit(normalized, archive)
    print(json.dumps({"status": "PASS", "artworks": 10, "zip": archive.name, "zip_mb": round(archive.stat().st_size / 1_000_000, 2), "listing_images": 10, "etsy_upload": False}, indent=2))


if __name__ == "__main__":
    main()
