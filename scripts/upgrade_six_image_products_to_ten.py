"""Add four exact-art 2x2 gallery images to every six-image premium product.

The seven configured products retain their approved six core listing graphics.
Customer artwork is read from the original ZIP archives, validated, and copied
only into each premium review directory's temporary work area. Nothing is
uploaded to Etsy by this script.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


REPO = Path(__file__).resolve().parents[1]
PRODUCTS_ROOT = REPO / "EverframeDigital" / "Products"
MASTER_REPORT = REPO / "EverframeDigital" / "all-products-ten-image-upgrade-report.txt"

TARGETS = {
    "Coastal-Landscape": (101, "#eef0ec", "#d7dfe0", "#b39a69"),
    "Everframe-100-Collection": (100, "#f3eee5", "#ded2c2", "#a98957"),
    "Minimalist-Line-Art": (99, "#f5f1ea", "#ddd6cb", "#a88e65"),
    "Modern-Abstract-Neutral": (100, "#eee9e0", "#d5cabd", "#aa8a5b"),
    "Neutral-Botanical": (101, "#f0f1e9", "#d7ddcf", "#9d9867"),
    "Seasonal-Neutral": (100, "#f2ede5", "#d8cbbd", "#aa8758"),
    "Vintage-Botanical": (100, "#f0eadf", "#d9cdb9", "#9b7948"),
}

CORE_NAMES = [
    "01-main-cover.jpg",
    "02-product-details.jpg",
    "03-collection-specs.jpg",
    "04-how-to-download.jpg",
    "05-compatibility.jpg",
    "06-premium-quality.jpg",
]
GALLERY_NAMES = [
    "07-framed-gallery-one.jpg",
    "08-framed-gallery-two.jpg",
    "09-framed-gallery-three.jpg",
    "10-framed-gallery-four.jpg",
]
ALL_NAMES = CORE_NAMES + GALLERY_NAMES
W, H = 2600, 2000
FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_jpeg_atomic(image: Image.Image, path: Path) -> None:
    temp = path.with_suffix(".tmp.jpg")
    image.convert("RGB").save(temp, "JPEG", quality=95, optimize=True, subsampling=0)
    os.replace(temp, path)


def customer_inventory(product: Path, expected_count: int) -> list[dict]:
    archives = sorted((product / "customer-downloads").glob("*.zip"))
    if not archives:
        raise RuntimeError("no customer ZIP archives")
    records: list[dict] = []
    seen_names: set[str] = set()
    for archive_path in archives:
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"CRC failure in {archive_path.name}")
            for member in archive.namelist():
                if member.endswith("/") or Path(member).name.startswith("."):
                    continue
                basename = Path(member).name
                if Path(basename).suffix.lower() not in {".jpg", ".jpeg"}:
                    raise RuntimeError(f"unexpected customer file: {member}")
                if basename in seen_names:
                    raise RuntimeError(f"duplicate archive filename: {basename}")
                seen_names.add(basename)
                data = archive.read(member)
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
                    if image.size != (3840, 2160) or image.mode != "RGB" or image.format != "JPEG":
                        raise RuntimeError(
                            f"invalid artwork {basename}: {image.size}, {image.mode}, {image.format}"
                        )
                records.append({
                    "name": basename,
                    "archive": archive_path,
                    "member": member,
                    "bytes": data,
                    "sha256": sha256_bytes(data),
                })
    records.sort(key=lambda row: row["name"].lower())
    if len(records) != expected_count:
        raise RuntimeError(f"expected {expected_count} customer images; found {len(records)}")
    if len({row["sha256"] for row in records}) != len(records):
        raise RuntimeError("exact duplicate customer artwork detected")
    return records


def evenly_spaced(records: list[dict], count: int = 16) -> list[dict]:
    indices = [round(index * (len(records) - 1) / (count - 1)) for index in range(count)]
    selected = [records[index] for index in indices]
    if len({row["name"] for row in selected}) != count:
        raise RuntimeError("gallery selection did not produce 16 unique files")
    return selected


def warm_wall(top_color: str, bottom_color: str) -> Image.Image:
    top = Image.new("RGB", (W, H), top_color)
    bottom = Image.new("RGB", (W, H), bottom_color)
    gradient = Image.linear_gradient("L").resize((W, H))
    wall = Image.composite(bottom, top, gradient)
    grain = Image.effect_noise((W, H), 9).convert("L")
    paper = ImageOps.colorize(grain, "#dfd8ce", "#fffdf9")
    return Image.blend(wall, paper, 0.10)


def fit_art(record: dict) -> Image.Image:
    with Image.open(io.BytesIO(record["bytes"])) as image:
        return ImageOps.fit(
            image.convert("RGB"), (1080, 608), Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )


def add_frame(canvas: Image.Image, record: dict, x: int, y: int, metal: str) -> None:
    outer_w, outer_h = 1120, 648
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (x + 15, y + 18, x + outer_w + 15, y + outer_h + 18), radius=5, fill=135
    )
    shadow = Image.new("RGBA", canvas.size, (65, 50, 35, 0))
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(20)))
    canvas.paste(shadow, (0, 0), shadow)

    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y, x + outer_w, y + outer_h), fill="#765934")
    draw.rectangle((x + 3, y + 3, x + outer_w - 3, y + outer_h - 3), fill=metal)
    draw.rectangle((x + 8, y + 8, x + outer_w - 8, y + outer_h - 8), fill="#9c7849")
    draw.rectangle((x + 13, y + 13, x + outer_w - 13, y + outer_h - 13), fill="#e8d4aa")
    draw.rectangle((x + 18, y + 18, x + outer_w - 18, y + outer_h - 18), fill="#6f522f")
    canvas.paste(fit_art(record), (x + 20, y + 20))
    draw.line((x + 5, y + 5, x + outer_w - 5, y + 5), fill="#f0ddb2", width=2)
    draw.line((x + 5, y + 5, x + 5, y + outer_h - 5), fill="#f0ddb2", width=2)


def build_gallery(records: list[dict], palette: tuple[str, str, str]) -> Image.Image:
    canvas = warm_wall(palette[0], palette[1])
    positions = [(140, 260), (1340, 260), (140, 1092), (1340, 1092)]
    for record, (x, y) in zip(records, positions, strict=True):
        add_frame(canvas, record, x, y, palette[2])
    return canvas


def validate_core(output: Path) -> None:
    for name in CORE_NAMES:
        path = output / name
        if not path.is_file():
            raise RuntimeError(f"missing core listing image: {name}")
        with Image.open(path) as image:
            if image.size != (W, H) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"invalid core listing image: {name}")


def contact_sheet(output: Path) -> None:
    sheet = Image.new("RGB", (2600, 1180), "#e9e4dc")
    draw = ImageDraw.Draw(sheet)
    title_font = ImageFont.truetype(str(FONT_DIR / "arialbd.ttf"), 32)
    label_font = ImageFont.truetype(str(FONT_DIR / "arial.ttf"), 21)
    draw.text((80, 35), "TEN-IMAGE ETSY LISTING SET — LOCAL REVIEW", font=title_font, fill="#292a27")
    thumb_w, thumb_h = 448, 345
    for index, name in enumerate(ALL_NAMES):
        row, col = divmod(index, 5)
        x, y = 80 + col * 500, 105 + row * 515
        with Image.open(output / name) as image:
            thumb = ImageOps.fit(image.convert("RGB"), (thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y, x + thumb_w, y + thumb_h), outline="#9d875f", width=2)
        draw.text((x, y + thumb_h + 14), name, font=label_font, fill="#3d3e3a")
    save_jpeg_atomic(sheet, output / "review-contact-sheet.jpg")


def process_product(name: str, expected: int, palette: tuple[str, str, str]) -> dict:
    product = PRODUCTS_ROOT / name
    output = product / "cover-premium-review"
    work = output / "_work"
    source_dir = work / "gallery-source"
    source_dir.mkdir(parents=True, exist_ok=True)
    validate_core(output)
    records = customer_inventory(product, expected)
    selected = evenly_spaced(records)

    # Preserve prior review sheet before replacing it with the ten-image sheet.
    old_sheet = output / "review-contact-sheet.jpg"
    backup_sheet = work / "review-contact-sheet-before-ten-images.jpg"
    if old_sheet.exists() and not backup_sheet.exists():
        shutil.copy2(old_sheet, backup_sheet)

    for record in selected:
        extracted = source_dir / record["name"]
        if not extracted.exists() or sha256_file(extracted) != record["sha256"]:
            extracted.write_bytes(record["bytes"])

    used: dict[str, list[str]] = {}
    for index, filename in enumerate(GALLERY_NAMES):
        group = selected[index * 4:(index + 1) * 4]
        save_jpeg_atomic(build_gallery(group, palette), output / filename)
        used[filename] = [row["name"] for row in group]

    # Validate exactly ten intended listing deliverables; review sheet is not a deliverable.
    rows = []
    for name_out in ALL_NAMES:
        path = output / name_out
        with Image.open(path) as image:
            if image.size != (W, H) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"invalid final image: {name_out}")
        rows.append((name_out, path.stat().st_size, sha256_file(path)))
    if len({item for values in used.values() for item in values}) != 16:
        raise RuntimeError("gallery artwork repeat detected")
    contact_sheet(output)

    report_lines = [
        "TEN-IMAGE LISTING UPGRADE REPORT",
        f"Product folder: {name}",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "Status: PASS",
        f"Verified customer artwork: {len(records)} exact 3840 × 2160 RGB JPG files",
        "Approved core listing graphics preserved: 6",
        "New framed-gallery listing graphics: 4",
        "Final intended Etsy listing graphics: 10",
        "Gallery system: four separate 2 × 2 layouts; exact 16:9 customer art",
        "Distinct gallery artwork selections: 16; repeats: 0",
        "Gallery text, controls, logos, and watermarks: none",
        "Etsy upload performed: no",
        "",
    ]
    for filename, size, digest in rows:
        suffix = f"; sources: {', '.join(used[filename])}" if filename in used else ""
        report_lines.append(f"{filename}: {size} bytes; SHA-256 {digest}{suffix}")
    report_path = output / "ten-image-upgrade-report.txt"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return {
        "product": name,
        "customer_count": len(records),
        "output": str(output),
        "new_images": len(GALLERY_NAMES),
        "report": str(report_path),
    }


def main() -> None:
    results = []
    failures = []
    for name, (expected, top, bottom, metal) in TARGETS.items():
        try:
            results.append(process_product(name, expected, (top, bottom, metal)))
            print(f"PASS {name}")
        except Exception as exc:
            failures.append((name, str(exc)))
            print(f"FAIL {name}: {exc}")

    lines = [
        "ALL PRODUCTS — TEN-IMAGE UPGRADE REPORT",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Products targeted: {len(TARGETS)}",
        f"Products completed: {len(results)}",
        f"Products failed: {len(failures)}",
        f"New listing images created: {sum(row['new_images'] for row in results)}",
        "Etsy upload performed: no",
        "",
    ]
    for row in results:
        lines.append(
            f"COMPLETED | {row['product']} | customer art {row['customer_count']} | "
            f"new images {row['new_images']} | {row['output']}"
        )
    for name, reason in failures:
        lines.append(f"FAILED | {name} | {reason}")
    MASTER_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if failures:
        raise RuntimeError(f"{len(failures)} product upgrade(s) failed; see {MASTER_REPORT}")
    print(f"MASTER PASS: {MASTER_REPORT}")


if __name__ == "__main__":
    main()
