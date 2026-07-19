"""Finalize, package, document, and render Quiet Meadow Botanicals.

This script never uploads to Etsy. It expects 100 accepted 1920x1080 source
PNGs created by generate_neutral_botanical_100_collection.py.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "Neutral-Botanical-100-Collection"
SOURCE = PRODUCT / "source-art"
LISTING = PRODUCT / "listing"
DOWNLOADS = PRODUCT / "customer-downloads"
NORMALIZED = DOWNLOADS / "_work" / "normalized-jpg"
OUTPUT = PRODUCT / "cover-premium-review"
STATE = LISTING / "full-production-state.json"
MAPPING = LISTING / "filename-mapping.csv"
BUNDLE_REPORT = PRODUCT / "bundle-report.txt"
AUDIT = LISTING / "final-audit-report.txt"
COUNT = 100
MAX_ZIP_BYTES = 19_500_000
DELIVERY_PREFIX = "Neutral-Botanical-II"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dhash(image: Image.Image) -> int:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def validate_sources() -> list[dict]:
    records = []
    hashes = set()
    perceptual = []
    for number in range(1, COUNT + 1):
        path = SOURCE / f"{DELIVERY_PREFIX}-{number:03d}.png"
        if not path.is_file():
            raise RuntimeError(f"Missing source artwork: {path.name}")
        with Image.open(path) as image:
            image.load()
            if image.size != (1920, 1080) or image.format != "PNG":
                raise RuntimeError(f"Invalid source artwork: {path.name} {image.size} {image.format}")
            phash = dhash(image)
        digest = sha256(path)
        if digest in hashes:
            raise RuntimeError(f"Exact duplicate source artwork: {path.name}")
        hashes.add(digest)
        records.append({"number": number, "source": path, "source_sha256": digest, "dhash": phash})
        perceptual.append((number, phash))
    nearest = 64
    nearest_pair = None
    for index, (left_number, left_hash) in enumerate(perceptual):
        for right_number, right_hash in perceptual[index + 1:]:
            distance = (left_hash ^ right_hash).bit_count()
            if distance < nearest:
                nearest = distance
                nearest_pair = (left_number, right_number)
    if nearest <= 1:
        raise RuntimeError(f"Likely perceptual duplicate: {nearest_pair}, dHash distance {nearest}")
    return records


def normalize(records: list[dict]) -> tuple[list[dict], int]:
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    # Clear only this new product's mechanical normalized outputs.
    for path in NORMALIZED.glob("*.jpg"):
        path.unlink()
    chosen_quality = 90
    while True:
        normalized = []
        for row in records:
            destination = NORMALIZED / f"{DELIVERY_PREFIX}-{row['number']:03d}.jpg"
            with Image.open(row["source"]) as image:
                source_rgb = image.convert("RGB")
                # FAL occasionally places a tiny signature-like flourish in an
                # extreme corner despite negative prompting. A uniform 2% edge
                # safety crop removes those artifacts without changing the
                # intended 16:9 composition or stretching the artwork.
                crop_x = round(source_rgb.width * 0.02)
                crop_y = round(source_rgb.height * 0.02)
                source_rgb = source_rgb.crop((crop_x, crop_y, source_rgb.width - crop_x, source_rgb.height - crop_y))
                final = source_rgb.resize((3840, 2160), Image.Resampling.LANCZOS)
                final.save(destination, "JPEG", quality=chosen_quality, optimize=True, subsampling=0)
            with Image.open(destination) as check:
                check.load()
                if check.size != (3840, 2160) or check.mode != "RGB" or check.format != "JPEG":
                    raise RuntimeError(f"Normalized validation failed: {destination.name}")
            normalized.append({
                **row,
                "delivery": destination,
                "delivery_sha256": sha256(destination),
                "delivery_bytes": destination.stat().st_size,
            })
        # 97.5 MB is the five-file conservative ceiling. Leave additional
        # archive overhead headroom by targeting 95 MB total.
        if sum(row["delivery_bytes"] for row in normalized) <= 95_000_000:
            return normalized, chosen_quality
        chosen_quality -= 3
        if chosen_quality < 72:
            raise RuntimeError("Unable to package five visually acceptable 4K ZIP files")


def partition(records: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    current_bytes = 0
    for row in records:
        projected = current_bytes + row["delivery_bytes"] + 4096
        if current and projected > 19_200_000:
            groups.append(current)
            current = []
            current_bytes = 0
        current.append(row)
        current_bytes += row["delivery_bytes"] + 256
    if current:
        groups.append(current)
    if len(groups) > 5:
        raise RuntimeError(f"Packaging requires {len(groups)} ZIPs; Etsy supports at most five")
    return groups


def package(records: list[dict]) -> tuple[list[dict], dict[int, str]]:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for path in DOWNLOADS.glob("Neutral-Botanical-II-100-Images-Part*of*.zip"):
        path.unlink()
    groups = partition(records)
    metadata = []
    membership = {}
    total = len(groups)
    for index, group in enumerate(groups, 1):
        path = DOWNLOADS / f"Neutral-Botanical-II-100-Images-Part{index}of{total}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for row in group:
                archive.write(row["delivery"], arcname=row["delivery"].name)
                membership[row["number"]] = path.name
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"CRC failure in {path.name}: {bad}")
            members = [name for name in archive.namelist() if name.lower().endswith(".jpg")]
            if len(members) != len(group):
                raise RuntimeError(f"Archive count mismatch in {path.name}")
        if path.stat().st_size > MAX_ZIP_BYTES:
            raise RuntimeError(f"Archive exceeds conservative Etsy limit: {path.name}")
        metadata.append({
            "path": path,
            "count": len(group),
            "first": group[0]["number"],
            "last": group[-1]["number"],
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    if len(membership) != COUNT:
        raise RuntimeError("Not every delivery image appears exactly once in the ZIP set")
    return metadata, membership


def write_mapping(records: list[dict], membership: dict[int, str]) -> None:
    with MAPPING.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "artwork_number", "concept", "source_png", "delivery_jpg", "customer_zip",
            "source_dimensions", "final_dimensions", "jpg_bytes", "source_sha256", "final_sha256",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        manifest_rows = {}
        with (LISTING / "generation-manifest.csv").open(newline="", encoding="utf-8") as manifest:
            for row in csv.DictReader(manifest):
                manifest_rows[int(row["number"])] = row
        for row in records:
            writer.writerow({
                "artwork_number": row["number"],
                "concept": manifest_rows[row["number"]]["concept"],
                "source_png": row["source"].name,
                "delivery_jpg": row["delivery"].name,
                "customer_zip": membership[row["number"]],
                "source_dimensions": "1920x1080",
                "final_dimensions": "3840x2160",
                "jpg_bytes": row["delivery_bytes"],
                "source_sha256": row["source_sha256"],
                "final_sha256": row["delivery_sha256"],
            })


def write_copy(zips: list[dict], jpeg_quality: int) -> None:
    zip_names = ", ".join(row["path"].name for row in zips)
    zip_lines = "\n".join(
        f"- {row['path'].name} ({row['count']} images; {row['bytes']/1_000_000:.2f} MB)"
        for row in zips
    )
    tags = [
        "frame tv art", "neutral botanical", "botanical tv art", "wildflower art",
        "beige wall art", "sage green decor", "cottagecore decor", "digital download",
        "4k tv artwork", "neutral wall decor", "flower meadow art", "instant download",
        "botanical bundle",
    ]
    if len(tags) != 13 or any(len(tag) > 20 for tag in tags):
        raise RuntimeError("Invalid Etsy tag set")
    title = "100 Quiet Meadow Neutral Botanical Frame TV Art Bundle, Beige Wildflower Collection, 4K Digital Download"
    if len(title) > 140:
        raise RuntimeError("Etsy title exceeds 140 characters")
    text = f"""PRODUCT NAME:
Quiet Meadow Botanicals — Frame TV Art Bundle (100 images)

ETSY TITLE:
{title}

SHORT DESCRIPTION:
Refresh your screen with 100 warm neutral botanical artworks featuring airy meadows, delicate branches, soft grasses, and understated garden compositions in ivory, oatmeal, taupe, and muted sage.

FULL DESCRIPTION:
Bring a calm botanical gallery to your Frame TV with the Quiet Meadow Botanicals collection. This collection includes 100 original, coordinated digital artworks inspired by misty wildflower meadows, graceful branches, layered leaves, quiet gardens, and organic neutral landscapes.

Every artwork is supplied as a high-resolution 3840 × 2160 JPG in a 16:9 landscape format. Download all {len(zips)} ZIP archives, extract them on a computer, and transfer your chosen image using the SmartThings app or another compatible device method. The files are also suitable for other 16:9 televisions, monitors, tablets, screensavers, and compatible digital displays.

WHAT IS INCLUDED:
- 100 unique Quiet Meadow Botanicals JPG artworks
- 3840 × 2160 pixels (4K UHD)
- 16:9 landscape format
- {len(zips)} ZIP archives: {zip_names}
- Instant digital download
- Personal-use license

HOW TO DOWNLOAD:
1. Sign in to Etsy and open Purchases and Reviews.
2. Download all {len(zips)} ZIP archives to a computer.
3. Extract every ZIP file to access all 100 numbered JPG images.
4. Choose an artwork and transfer it to your display.

IMPORTANT:
- This is a digital product. No physical item will be shipped.
- As an instant digital download, this purchase is non-refundable and all sales are final.
- Screen colors may vary by device and display settings.
- A computer is the easiest way to extract ZIP archives.
- Personal use only. Files may not be resold, shared, redistributed, or used commercially.

AI DISCLOSURE:
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital

AI PRODUCTION NOTE:
The artwork is 100% AI-generated with human curation and review only. No claim of hand painting or manual artistic refinement is made.

TAGS:
{', '.join(tags)}

MATERIALS:
Digital download, JPG, ZIP

TARGET CUSTOMER:
Neutral botanical, cottagecore, organic-modern, farmhouse, and calming nature decor shoppers using a 16:9 digital display.

ETSY CATEGORY:
Art & Collectibles > Prints > Digital Prints

SUGGESTED PRICE:
$8.99

CUSTOMER DOWNLOAD FILES:
{zip_lines}

NORMALIZATION:
Source FAL HD artwork normalized to 3840 × 2160 JPG at quality {jpeg_quality} with a uniform 2% edge-safety crop and high-quality Lanczos resampling.

QUALITY-CONTROL STATUS:
PASS
"""
    (LISTING / "product-details.txt").write_text(text, encoding="utf-8")


def write_reports(records: list[dict], zips: list[dict], jpeg_quality: int) -> None:
    nearest = 64
    pair = None
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            distance = (left["dhash"] ^ right["dhash"]).bit_count()
            if distance < nearest:
                nearest, pair = distance, (left["number"], right["number"])
    zip_lines = "\n".join(
        f"{row['path'].name}: {row['count']} images; {row['bytes']} bytes; range {row['first']:03d}-{row['last']:03d}; SHA-256 {row['sha256']}"
        for row in zips
    )
    BUNDLE_REPORT.write_text(
        f"""QUIET MEADOW BOTANICALS — BUNDLE REPORT
Status: PASS
Customer artwork: 100 unique files
Source: FAL HD, 1920 × 1080 PNG
Delivery: 3840 × 2160 RGB JPG, quality {jpeg_quality}
Aspect ratio: 16:9 landscape
Exact duplicate check: PASS
Closest internal dHash pair: {pair}; distance {nearest}
ZIP count: {len(zips)}
ZIP integrity/CRC: PASS
Every delivery JPG occurs exactly once across archives: PASS
Original source PNG files modified: no

{zip_lines}
""",
        encoding="utf-8",
    )


def render_listing_images() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    work = OUTPUT / "_work"
    work.mkdir(parents=True, exist_ok=True)
    reference = ROOT / "EverframeDigital" / "Products" / "Neutral-Botanical" / "cover-premium-review" / "_work"
    for name in ["render_premium.py", "room-product-details-v2.png", "laptop-download-v2.png", "room-compatibility-v2.png", "room-premium-v2.png"]:
        source = reference / name
        if not source.is_file():
            raise RuntimeError(f"Missing approved local listing template asset: {source}")
        shutil.copy2(source, work / name)
    subprocess.run([sys.executable, str(work / "render_premium.py")], cwd=ROOT, check=True)
    code = (
        "from scripts.upgrade_six_image_products_to_ten import process_product; "
        "process_product('Neutral-Botanical-100-Collection',100,('#f4f1e9','#dce1d4','#a79b68'))"
    )
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def final_audit(records: list[dict], zips: list[dict]) -> None:
    intended = [
        "01-main-cover.jpg", "02-product-details.jpg", "03-collection-specs.jpg",
        "04-how-to-download.jpg", "05-compatibility.jpg", "06-premium-quality.jpg",
        "07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg",
        "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg",
    ]
    for name in intended:
        path = OUTPUT / name
        with Image.open(path) as image:
            image.load()
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid listing image: {name}")
    if len(list(NORMALIZED.glob("*.jpg"))) != COUNT:
        raise RuntimeError("Normalized delivery count changed during listing production")
    lines = [
        "QUIET MEADOW BOTANICALS — FINAL AUDIT",
        f"Audited: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "Overall status: PASS",
        "Accepted source artworks: 100",
        "Normalized delivery JPGs: 100; 3840 × 2160 RGB JPEG",
        f"Customer ZIP archives: {len(zips)}; CRC PASS; each under 19.5 decimal MB",
        "Listing copy and 13 Etsy tags: PASS",
        "Listing graphics: 10; 2600 × 2000 RGB JPEG; PASS",
        "Four-sided TV chassis requirement for TV mockups: inherited approved premium template; human review required before upload",
        "Etsy upload or publication performed: no",
        "Final status: COMPLETE — READY FOR HUMAN REVIEW",
    ]
    AUDIT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state.update(
        packaging_status="COMPLETE",
        listing_copy_status="COMPLETE",
        listing_graphics_status="COMPLETE_10_IMAGES",
        audit_status="PASS",
        final_status="COMPLETE_READY_FOR_HUMAN_REVIEW",
        updated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main() -> None:
    records = validate_sources()
    normalized, jpeg_quality = normalize(records)
    zips, membership = package(normalized)
    write_mapping(normalized, membership)
    write_copy(zips, jpeg_quality)
    write_reports(normalized, zips, jpeg_quality)
    render_listing_images()
    final_audit(normalized, zips)
    print(json.dumps({
        "status": "PASS",
        "product": str(PRODUCT),
        "artworks": len(normalized),
        "zip_files": len(zips),
        "listing_images": 10,
        "etsy_upload": False,
    }, indent=2))


if __name__ == "__main__":
    main()
