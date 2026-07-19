from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "Vintage-scripture-paintings"
ART = PRODUCT / "customer-downloads-v3" / "_work" / "normalized-jpg"
DOWNLOADS = PRODUCT / "customer-downloads-v3"
LISTING = PRODUCT / "listing"
OUT = PRODUCT / "cover-premium-v2-review"
WORK = OUT / "_work"
SOURCE_MAPPING = LISTING / "filename-mapping.csv"
RENDER_REPORT = ART / "render-report.json"

COUNT = 100
W, H = 2600, 2000
MAX_ZIP_BYTES = 19_500_000

FONT_DIR = Path(r"C:\Windows\Fonts")
SERIF = FONT_DIR / "BASKVILL.TTF"
SERIF_BOLD = FONT_DIR / "BOOKOSB.TTF"
SANS = FONT_DIR / "arial.ttf"
SANS_BOLD = FONT_DIR / "arialbd.ttf"

IVORY = (247, 242, 231)
PAPER = (252, 249, 242)
INK = (47, 40, 33)
TAUPE = (116, 98, 76)
GOLD = (168, 126, 65)
RULE = (213, 196, 167)
CREAM = (236, 225, 207)


def ft(path: Path, size: int):
    return ImageFont.truetype(str(path), size)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def art_path(number: int) -> Path:
    return ART / f"Vintage-Scripture-Paintings-{number:03d}.jpg"


def art(number: int) -> Image.Image:
    return Image.open(art_path(number)).convert("RGB")


def fit_art(number: int, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(art(number), size, Image.Resampling.LANCZOS)


def save(image: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUT / name, "JPEG", quality=95, optimize=True, subsampling=0)


def text(draw, xy, value, font, fill=INK, anchor="la", spacing=8, align="left"):
    draw.multiline_text(xy, value, font=font, fill=fill, anchor=anchor, spacing=spacing, align=align)


def tracked(draw, xy, value, font, fill=INK, tracking=5, anchor="la"):
    widths = [draw.textlength(ch, font=font) for ch in value]
    total = sum(widths) + tracking * max(0, len(value) - 1)
    x, y = xy
    if anchor.startswith("m"):
        x -= total / 2
    elif anchor.startswith("r"):
        x -= total
    for ch, width in zip(value, widths):
        draw.text((x, y), ch, font=font, fill=fill, anchor="lm")
        x += width + tracking


def wrap(draw, value: str, font, max_width: int) -> str:
    lines, current = [], ""
    for word in value.split():
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def ornament(draw, cx: int, y: int, width: int = 420):
    draw.line((cx - width, y, cx - 18, y), fill=GOLD, width=3)
    draw.ellipse((cx - 7, y - 7, cx + 7, y + 7), fill=GOLD)
    draw.line((cx + 18, y, cx + width, y), fill=GOLD, width=3)


def textured(seed: int = 7) -> Image.Image:
    base = Image.new("RGB", (W, H), IVORY)
    noise = Image.effect_noise((W, H), 8).convert("L")
    paper = ImageOps.colorize(noise, "#dfd7ca", "#fffdf8")
    return Image.blend(base, paper, 0.08)


def shadow(canvas: Image.Image, box: tuple[int, int, int, int], blur=20):
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((x1 + 12, y1 + 16, x2 + 12, y2 + 16), 12, fill=(35, 26, 17, 92))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def framed(canvas: Image.Image, number: int, box: tuple[int, int, int, int]):
    x, y, width, height = box
    shadow(canvas, (x, y, x + width, y + height))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x - 9, y - 9, x + width + 9, y + height + 9), fill=(111, 78, 40))
    draw.rectangle((x - 5, y - 5, x + width + 5, y + height + 5), fill=(207, 170, 107))
    draw.rectangle((x - 1, y - 1, x + width + 1, y + height + 1), fill=(88, 63, 39))
    canvas.paste(fit_art(number, (width, height)), (x, y))


def validate_customer_art() -> list[dict]:
    files = [art_path(i) for i in range(1, COUNT + 1)]
    hashes = set()
    records = []
    for index, path in enumerate(files, 1):
        if not path.is_file():
            raise RuntimeError(f"Missing premium artwork: {path.name}")
        with Image.open(path) as image:
            image.load()
            if image.size != (3840, 2160) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid customer artwork: {path.name}")
        digest = sha(path)
        if digest in hashes:
            raise RuntimeError(f"Exact duplicate customer artwork: {path.name}")
        hashes.add(digest)
        records.append({"number": index, "path": path, "bytes": path.stat().st_size, "sha256": digest})
    return records


def balanced_groups(records: list[dict]) -> list[list[dict]]:
    groups, start = [], 0
    remaining_bytes = sum(r["bytes"] for r in records)
    remaining_groups = 5
    for group_index in range(5):
        if group_index == 4:
            groups.append(records[start:])
            break
        target = remaining_bytes / remaining_groups
        total, end = 0, start
        min_left = remaining_groups - 1
        while end < len(records) - min_left:
            next_total = total + records[end]["bytes"]
            if total and abs(total - target) <= abs(next_total - target):
                break
            total = next_total
            end += 1
        groups.append(records[start:end])
        start = end
        remaining_bytes -= total
        remaining_groups -= 1
    if len(groups) != 5 or sum(map(len, groups)) != COUNT:
        raise RuntimeError("Unable to create five balanced sequential groups")
    return groups


def package(records: list[dict]) -> tuple[list[dict], dict[int, str]]:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for old in DOWNLOADS.glob("Vintage-Scripture-Paintings-100-Images-Part*of5.zip"):
        old.unlink()
    metadata, membership = [], {}
    for part, group in enumerate(balanced_groups(records), 1):
        path = DOWNLOADS / f"Vintage-Scripture-Paintings-100-Images-Part{part}of5.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for row in group:
                archive.write(row["path"], arcname=row["path"].name)
                membership[row["number"]] = path.name
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"CRC failure: {path.name}")
            if len(archive.namelist()) != len(group):
                raise RuntimeError(f"ZIP member mismatch: {path.name}")
        if path.stat().st_size > MAX_ZIP_BYTES:
            raise RuntimeError(f"ZIP exceeds 19.5 MB target: {path.name} ({path.stat().st_size})")
        metadata.append({"path": path, "count": len(group), "first": group[0]["number"], "last": group[-1]["number"], "bytes": path.stat().st_size, "sha256": sha(path)})
    return metadata, membership


def write_mapping(records: list[dict], membership: dict[int, str]):
    source_rows = list(csv.DictReader(SOURCE_MAPPING.open(encoding="utf-8-sig")))
    render_rows = {r["index"]: r for r in json.loads(RENDER_REPORT.read_text(encoding="utf-8"))}
    path = LISTING / "filename-mapping-v3.csv"
    fields = ["index", "source_image", "verse_ref", "delivery_jpg", "customer_zip", "placement", "verse_font_size", "final_dimensions", "final_bytes", "final_sha256"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for record, source in zip(records, source_rows):
            rr = render_rows[record["number"]]
            writer.writerow({
                "index": record["number"], "source_image": source["source_image"], "verse_ref": source["verse_ref"],
                "delivery_jpg": record["path"].name, "customer_zip": membership[record["number"]],
                "placement": rr["side"], "verse_font_size": rr["font_size"], "final_dimensions": "3840x2160",
                "final_bytes": record["bytes"], "final_sha256": record["sha256"],
            })


def copy_room_assets():
    source = ROOT / "EverframeDigital" / "Products" / "Neutral-Botanical" / "cover-premium-review" / "_work"
    WORK.mkdir(parents=True, exist_ok=True)
    for name in ["room-product-details-v2.png", "room-compatibility-v2.png", "room-premium-v2.png"]:
        if not (source / name).is_file():
            raise RuntimeError(f"Missing approved room asset: {name}")
        shutil.copy2(source / name, WORK / name)


def build_cover():
    canvas = Image.new("RGBA", (W, H), (244, 239, 228, 255))
    draw = ImageDraw.Draw(canvas)
    numbers = [round(1 + i * 99 / 55) for i in range(56)]
    positions = []
    for row in range(10):
        for col in range(8):
            if row < 3 or row > 6 or col in (0, 7):
                positions.append((col, row))
    for number, (col, row) in zip(numbers, positions):
        x, y = 15 + col * 322, 20 + row * 195
        draw.rectangle((x - 6, y - 6, x + 316, y + 180), fill=(242, 236, 224, 255))
        draw.rectangle((x - 3, y - 3, x + 313, y + 177), outline=(*GOLD, 255), width=4)
        canvas.paste(fit_art(number, (310, 174)), (x, y))
    shadow(canvas, (320, 575, 2280, 1425), blur=28)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((320, 575, 2280, 1425), 24, fill=(250, 247, 239, 252), outline=(*GOLD, 255), width=8)
    draw.rounded_rectangle((342, 597, 2258, 1403), 16, outline=(*RULE, 235), width=2)
    tracked(draw, (1300, 655), "EVERFRAME DIGITAL", ft(SANS_BOLD, 38), TAUPE, 7, "ma")
    ornament(draw, 1300, 735, 430)
    text(draw, (855, 970), "100", ft(SERIF, 215), GOLD, "mm")
    text(draw, (1630, 900), "VINTAGE SCRIPTURE", ft(SERIF_BOLD, 79), INK, "mm")
    text(draw, (1630, 1000), "PAINTINGS", ft(SERIF_BOLD, 92), INK, "mm")
    tracked(draw, (1300, 1150), "FRAME TV ART COLLECTION", ft(SANS_BOLD, 46), TAUPE, 6, "ma")
    draw.line((690, 1240, 1910, 1240), fill=(*GOLD, 230), width=2)
    tracked(draw, (1300, 1320), "KJV  •  4K UHD  •  16:9  •  INSTANT DOWNLOAD", ft(SANS_BOLD, 36), INK, 3, "ma")
    save(canvas, "01-main-cover.jpg")


def build_product_details():
    canvas = Image.open(WORK / "room-product-details-v2.png").convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((585, 670, 1315, 1125), fill=(171, 133, 83))
    canvas.paste(fit_art(6, (700, 394)), (600, 698))
    draw.rectangle((1380, 0, W, H), fill=PAPER)
    tracked(draw, (1990, 105), "EVERFRAME DIGITAL", ft(SANS_BOLD, 39), TAUPE, 7, "ma")
    text(draw, (1990, 225), "PRODUCT DETAILS", ft(SERIF_BOLD, 78), INK, "ma")
    ornament(draw, 1990, 350, 400)
    steps = [
        "Purchase the 100-piece Vintage Scripture Paintings collection.",
        "Download all 5 ZIP files from your Etsy Purchases page.",
        "Extract the ZIP files to access 100 high-resolution JPG artworks.",
        "Transfer a selected image using the SmartThings app or a compatible device method.",
        "Open Art Mode, add your image, and adjust the display to your preference.",
    ]
    for index, value in enumerate(steps):
        y = 450 + index * 292
        text(draw, (1495, y), f"{index + 1:02d}", ft(SERIF, 78), GOLD)
        text(draw, (1695, y + 8), wrap(draw, value, ft(SANS, 41), 770), ft(SANS, 41), INK)
        draw.line((1495, y + 225, 2480, y + 225), fill=RULE, width=2)
    save(canvas, "02-product-details.jpg")


def build_specs():
    canvas = textured().convert("RGBA")
    boxes = [(65, 70, 610, 343), (725, 60, 630, 354), (65, 485, 560, 315), (670, 470, 685, 385), (65, 920, 700, 394), (815, 940, 540, 304)]
    for number, box in zip([1, 18, 37, 55, 74, 93], boxes):
        framed(canvas, number, box)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((1440, 55, 2510, 1945), 30, fill=(251, 248, 240, 246), outline=(*GOLD, 140), width=3)
    tracked(draw, (1975, 130), "EVERFRAME DIGITAL", ft(SANS_BOLD, 37), TAUPE, 7, "ma")
    text(draw, (1975, 245), "COLLECTION\nSPECIFICATIONS", ft(SERIF_BOLD, 68), INK, "ma", 5, "center")
    ornament(draw, 1975, 430, 365)
    specs = ["100 UNIQUE JPG ARTWORKS", "100 KJV BIBLE VERSES", "3840 × 2160 PIXELS", "TRUE 4K UHD", "16:9 LANDSCAPE FORMAT", "5 ZIP DOWNLOADS", "PERSONAL USE LICENSE"]
    for index, value in enumerate(specs):
        y = 525 + index * 165
        draw.ellipse((1555, y, 1635, y + 80), fill=CREAM, outline=(*GOLD, 150), width=2)
        text(draw, (1595, y + 40), f"{index + 1:02d}", ft(SANS_BOLD, 28), GOLD, "mm")
        text(draw, (1690, y + 40), value, ft(SANS_BOLD, 37), INK, "lm")
        draw.line((1545, y + 110, 2400, y + 110), fill=RULE, width=2)
    text(draw, (1975, 1815), "Digital download only • No physical item shipped", ft(SANS, 34), TAUPE, "ma")
    save(canvas, "03-collection-specs.jpg")


def build_download(zips: list[dict]):
    canvas = textured(seed=12).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    tracked(draw, (1300, 100), "EVERFRAME DIGITAL", ft(SANS_BOLD, 38), TAUPE, 7, "ma")
    text(draw, (1300, 225), "HOW TO DOWNLOAD", ft(SERIF_BOLD, 80), INK, "ma")
    ornament(draw, 1300, 345, 440)
    # Original vector laptop with exact archive details.
    draw.rounded_rectangle((120, 520, 1210, 1370), 28, fill=(61, 55, 49), outline=(150, 120, 82), width=6)
    draw.rounded_rectangle((165, 565, 1165, 1325), 16, fill=PAPER)
    text(draw, (665, 640), "YOUR DOWNLOADS", ft(SANS_BOLD, 42), TAUPE, "ma")
    for index, row in enumerate(zips):
        y = 735 + index * 105
        draw.rounded_rectangle((235, y, 1095, y + 82), 12, fill=CREAM, outline=RULE, width=2)
        text(draw, (280, y + 41), f"PART {index + 1} OF 5", ft(SANS_BOLD, 30), INK, "lm")
        text(draw, (1045, y + 41), f"{row['bytes'] / 1_000_000:.2f} MB", ft(SANS, 29), TAUPE, "rm")
    draw.polygon([(65, 1370), (1265, 1370), (1140, 1470), (190, 1470)], fill=(165, 150, 135), outline=(91, 78, 67))
    steps = ["Sign in to Etsy and open Purchases and Reviews.", "Select Download Files for your order.", "Download all 5 ZIP archives to a computer.", "Extract every ZIP file to access all 100 JPG images.", "Choose your artwork and transfer it to your display."]
    for index, value in enumerate(steps):
        y = 520 + index * 245
        draw.ellipse((1380, y, 1475, y + 95), fill=CREAM, outline=(*GOLD, 180), width=3)
        text(draw, (1428, y + 48), f"{index + 1:02d}", ft(SANS_BOLD, 31), GOLD, "mm")
        text(draw, (1535, y + 12), wrap(draw, value, ft(SANS, 41), 875), ft(SANS, 41), INK)
        draw.line((1535, y + 175, 2480, y + 175), fill=RULE, width=2)
    text(draw, (1300, 1840), "A computer is the easiest way to extract ZIP archives.", ft(SANS_BOLD, 37), TAUPE, "ma")
    save(canvas, "04-how-to-download.jpg")


def build_compatibility():
    canvas = Image.open(WORK / "room-compatibility-v2.png").convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((530, 540, 1260, 975), fill=(171, 133, 83))
    canvas.paste(fit_art(61, (700, 394)), (545, 560))
    draw.rectangle((1450, 0, W, H), fill=PAPER)
    tracked(draw, (2025, 100), "EVERFRAME DIGITAL", ft(SANS_BOLD, 38), TAUPE, 7, "ma")
    text(draw, (2025, 215), "MADE FOR\n16:9 DISPLAYS", ft(SERIF_BOLD, 70), INK, "ma", 4, "center")
    ornament(draw, 2025, 430, 370)
    for index, value in enumerate(["FRAME TV ART MODE", "TELEVISIONS & MONITORS", "TABLETS & DIGITAL DISPLAYS", "SCREENSAVERS"]):
        y = 550 + index * 190
        draw.rounded_rectangle((1570, y, 1655, y + 70), 9, outline=GOLD, width=4)
        text(draw, (1720, y + 35), value, ft(SANS_BOLD, 38), INK, "lm")
        draw.line((1560, y + 125, 2480, y + 125), fill=RULE, width=2)
    text(draw, (2025, 1390), "Every artwork is supplied as a standard\n3840 × 2160 JPG in a 16:9 landscape format.", ft(SANS, 38), INK, "ma", 8, "center")
    ornament(draw, 2025, 1580, 360)
    text(draw, (2025, 1665), "Screen colors may vary by device and display settings.", ft(SANS, 34), TAUPE, "ma")
    save(canvas, "05-compatibility.jpg")


def build_quality():
    canvas = Image.open(WORK / "room-premium-v2.png").convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    canvas.paste(fit_art(88, (943, 530)), (1070, 706))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((105, 80, 1505, 480), 22, fill=(249, 246, 238, 224), outline=(*GOLD, 150), width=3)
    tracked(draw, (165, 145), "EVERFRAME DIGITAL", ft(SANS_BOLD, 38), TAUPE, 7)
    text(draw, (165, 245), "PREMIUM 4K QUALITY", ft(SERIF_BOLD, 78), INK)
    tracked(draw, (165, 400), "EVERY DETAIL, READY FOR DISPLAY", ft(SANS_BOLD, 35), INK, 3)
    draw.rounded_rectangle((290, 1685, 2310, 1875), 24, fill=(40, 34, 29, 205))
    text(draw, (1300, 1780), "100 vintage scripture paintings • 3840 × 2160 JPG • 16:9 landscape", ft(SANS, 38), (250, 247, 239), "mm")
    save(canvas, "06-premium-quality.jpg")


def build_galleries():
    chosen = [1, 8, 15, 22, 29, 36, 43, 50, 57, 64, 71, 78, 85, 90, 95, 100]
    names = ["07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg", "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg"]
    positions = [(140, 260), (1340, 260), (140, 1092), (1340, 1092)]
    for group_index, name in enumerate(names):
        canvas = textured(seed=30 + group_index).convert("RGBA")
        for number, (x, y) in zip(chosen[group_index * 4:(group_index + 1) * 4], positions):
            framed(canvas, number, (x, y, 1080, 608))
        save(canvas, name)


def build_listing_images(zips: list[dict]):
    copy_room_assets()
    build_cover()
    build_product_details()
    build_specs()
    build_download(zips)
    build_compatibility()
    build_quality()
    build_galleries()


def write_copy_and_reports(records: list[dict], zips: list[dict]):
    tags = ["frame tv art", "scripture wall art", "bible verse art", "christian tv art", "vintage bible art", "kjv scripture art", "religious wall art", "faith home decor", "4k tv artwork", "digital download", "christian gift", "vintage landscape", "scripture bundle"]
    if len(tags) != 13 or any(len(tag) > 20 for tag in tags):
        raise RuntimeError("Invalid Etsy tag set")
    title = "100 Vintage Scripture Paintings Frame TV Art Bundle, KJV Bible Verse Christian 4K Digital Download"
    if len(title) > 140 or "Samsung" in title:
        raise RuntimeError("Invalid Etsy title")
    zip_lines = "\n".join(f"- {row['path'].name} ({row['count']} images; {row['bytes']/1_000_000:.2f} MB)" for row in zips)
    details = f"""PRODUCT NAME:
Vintage Scripture Paintings — Frame TV Art Bundle (100 images)

ETSY TITLE:
{title}

SHORT DESCRIPTION:
Display 100 coordinated vintage-inspired paintings paired with timeless King James Version Bible verses in a refined, readable book-style design.

FULL DESCRIPTION:
Create a peaceful rotating scripture gallery on your Frame TV with this set of 100 vintage-inspired Christian artworks. Each landscape-format painting includes a different King James Version Bible verse, composed with professional typography, balanced line spacing, a warm parchment panel, and restrained antique-gold details.

Every artwork is supplied as a high-resolution 3840 × 2160 JPG in a 16:9 landscape format. Download all five ZIP archives, extract them on a computer, and transfer your chosen image using the SmartThings app or another compatible device method. The files are also suitable for other 16:9 televisions, monitors, tablets, screensavers, and compatible digital displays.

WHAT IS INCLUDED:
- 100 unique vintage scripture painting JPG artworks
- 100 different KJV Bible verses
- 3840 × 2160 pixels (4K UHD)
- 16:9 landscape format
- 5 ZIP archives
- Instant digital download
- Personal-use license

HOW TO DOWNLOAD:
1. Sign in to Etsy and open Purchases and Reviews.
2. Download all 5 ZIP archives to a computer.
3. Extract every ZIP file to access all 100 numbered JPG images.
4. Choose an artwork and transfer it to your display.

IMPORTANT:
- This is a digital product. No physical item will be shipped.
- As an instant digital download, this purchase is non-refundable and all sales are final.
- Screen colors may vary by device and display settings.
- A computer is the easiest way to extract ZIP archives.
- Personal use only. Files may not be resold, shared, redistributed, or used commercially.

SCRIPTURE:
King James Version (KJV). Scripture wording and references were programmatically placed for consistent spelling and typography.

AI DISCLOSURE:
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital

AI PRODUCTION NOTE:
The underlying artwork is 100% AI-generated with human curation and review. Scripture typography and layout were composed deterministically for accuracy and consistency. No claim of hand painting or manual artistic refinement is made.

TAGS:
{', '.join(tags)}

MATERIALS:
Digital download, JPG, ZIP

ETSY CATEGORY:
Art & Collectibles > Prints > Digital Prints

SUGGESTED PRICE:
$8.99

CUSTOMER DOWNLOAD FILES:
{zip_lines}

QUALITY-CONTROL STATUS:
PASS
"""
    (LISTING / "product-details-v3.txt").write_text(details, encoding="utf-8")
    image_names = ["01-main-cover.jpg", "02-product-details.jpg", "03-collection-specs.jpg", "04-how-to-download.jpg", "05-compatibility.jpg", "06-premium-quality.jpg", "07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg", "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg"]
    report_lines = [
        "VINTAGE SCRIPTURE PAINTINGS — PREMIUM REGENERATION REPORT",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "Status: PASS",
        "Customer artworks: 100 unique 3840 × 2160 RGB JPG files",
        "Scripture design: Baskerville body, Bookman Old Style reference, adaptive side placement, parchment contrast panel",
        "Scripture source: King James Version data file in config/bible_verses_vintage.json",
        "Exact duplicate check: PASS",
        "Customer ZIP archives: 5; CRC PASS; each under 19.5 decimal MB",
        "Listing graphics: 10; exact 2600 × 2000 RGB JPEG",
        "Etsy upload performed by this production script: no",
        "",
        "ZIP FILES",
    ]
    report_lines += [f"{row['path'].name}: {row['count']} files; range {row['first']:03d}-{row['last']:03d}; {row['bytes']} bytes; SHA-256 {row['sha256']}" for row in zips]
    report_lines += ["", "LISTING FILES"]
    for name in image_names:
        path = OUT / name
        with Image.open(path) as image:
            if image.size != (W, H) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid listing image: {name}")
        report_lines.append(f"{name}: {path.stat().st_size} bytes; SHA-256 {sha(path)}")
    report_lines += ["", "FINAL STATUS: PASS — READY FOR ETSY DRAFT REVIEW"]
    (OUT / "generation-report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (PRODUCT / "bundle-report-v3.txt").write_text("\n".join(report_lines[:12]) + "\n", encoding="utf-8")


def main():
    records = validate_customer_art()
    zips, membership = package(records)
    write_mapping(records, membership)
    build_listing_images(zips)
    write_copy_and_reports(records, zips)
    print(json.dumps({"status": "PASS", "artworks": 100, "zips": len(zips), "listing_images": 10, "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
