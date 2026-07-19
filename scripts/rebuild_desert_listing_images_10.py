"""Build the final ten-image Desert-Southwest Etsy listing set.

The six approved deterministic graphics are retained and renamed into the
current standard order. Four additional 2x2 framed-gallery mockups are built
from exact normalized customer JPGs. Legacy files are backed up before the
final directory is normalized to exactly ten JPEG deliverables.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


REPO = Path(__file__).resolve().parents[1]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Desert-Southwest"
NORMALIZED = PRODUCT / "customer-downloads" / "_work" / "normalized-jpg"
OUTPUT = PRODUCT / "cover-v2-review"
WORK = OUTPUT / "_work"
BACKUP = WORK / "legacy-nine-image-set"
STATE = PRODUCT / "listing" / "full-production-state.json"
AUDIT = PRODUCT / "listing" / "final-audit-report.txt"

FINAL_NAMES = [
    "01-main-cover.jpg",
    "02-collection-overview.jpg",
    "03-frame-tv-preview.jpg",
    "04-whats-included.jpg",
    "05-how-to-display.jpg",
    "06-quality-compatibility.jpg",
    "07-framed-gallery-one.jpg",
    "08-framed-gallery-two.jpg",
    "09-framed-gallery-three.jpg",
    "10-framed-gallery-four.jpg",
]

CORE_SOURCES = {
    "01-main-cover.jpg": "01-main-cover.jpg",
    "02-collection-overview.jpg": "02-collection-overview.jpg",
    "03-frame-tv-preview.jpg": "06-frame-tv-preview.jpg",
    "04-whats-included.jpg": "07-whats-included.jpg",
    "05-how-to-display.jpg": "08-how-to-display.jpg",
    "06-quality-compatibility.jpg": "09-quality-compatibility.jpg",
}

GALLERY_IDS = {
    "07-framed-gallery-one.jpg": [2, 9, 17, 24],
    "08-framed-gallery-two.jpg": [31, 38, 46, 53],
    "09-framed-gallery-three.jpg": [61, 68, 74, 81],
    "10-framed-gallery-four.jpg": [87, 92, 96, 100],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_jpeg_atomic(image: Image.Image, path: Path) -> None:
    temp = path.with_suffix(".tmp.jpg")
    image.convert("RGB").save(temp, "JPEG", quality=95, optimize=True, subsampling=0)
    os.replace(temp, path)


def warm_wall() -> Image.Image:
    width, height = 2600, 2000
    top = Image.new("RGB", (width, height), "#f7f3eb")
    bottom = Image.new("RGB", (width, height), "#eee7dc")
    gradient = Image.linear_gradient("L").resize((width, height))
    wall = Image.composite(bottom, top, gradient)
    grain = Image.effect_noise((width, height), 11).convert("L")
    paper = ImageOps.colorize(grain, "#e8dfd1", "#fffdf8")
    return Image.blend(wall, paper, 0.13)


def fitted_art(number: int) -> Image.Image:
    path = NORMALIZED / f"Desert-Southwest-{number:03d}.jpg"
    if not path.is_file():
        raise RuntimeError(f"Missing normalized customer artwork: {path.name}")
    with Image.open(path) as source:
        if source.size != (3840, 2160) or source.mode != "RGB":
            raise RuntimeError(f"Invalid normalized customer artwork: {path.name}")
        return ImageOps.fit(
            source.convert("RGB"),
            (1080, 608),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def add_frame(canvas: Image.Image, art: Image.Image, x: int, y: int) -> None:
    outer_w, outer_h = 1120, 648
    shadow_mask = Image.new("L", canvas.size, 0)
    shadow_draw = ImageDraw.Draw(shadow_mask)
    shadow_draw.rounded_rectangle(
        (x + 14, y + 18, x + outer_w + 14, y + outer_h + 18),
        radius=4,
        fill=118,
    )
    shadow = Image.new("RGBA", canvas.size, (72, 54, 35, 0))
    shadow.putalpha(shadow_mask.filter(ImageFilter.GaussianBlur(20)))
    canvas.paste(shadow, (0, 0), shadow)

    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y, x + outer_w, y + outer_h), fill="#87663a")
    draw.rectangle((x + 3, y + 3, x + outer_w - 3, y + outer_h - 3), fill="#d6bd86")
    draw.rectangle((x + 8, y + 8, x + outer_w - 8, y + outer_h - 8), fill="#a77e48")
    draw.rectangle((x + 14, y + 14, x + outer_w - 14, y + outer_h - 14), fill="#e1c995")
    draw.rectangle((x + 18, y + 18, x + outer_w - 18, y + outer_h - 18), fill="#75552f")
    canvas.paste(art, (x + 20, y + 20))
    draw.line((x + 5, y + 5, x + outer_w - 5, y + 5), fill="#f2deb0", width=2)
    draw.line((x + 5, y + 5, x + 5, y + outer_h - 5), fill="#f2deb0", width=2)


def build_gallery(numbers: list[int]) -> Image.Image:
    canvas = warm_wall()
    positions = [(140, 260), (1340, 260), (140, 1092), (1340, 1092)]
    for number, (x, y) in zip(numbers, positions, strict=True):
        add_frame(canvas, fitted_art(number), x, y)
    return canvas


def validate_final() -> list[dict]:
    present = sorted(path.name for path in OUTPUT.glob("*.jpg"))
    if present != FINAL_NAMES:
        raise RuntimeError(f"Final filename mismatch: {present}")
    rows = []
    for name in FINAL_NAMES:
        path = OUTPUT / name
        with Image.open(path) as image:
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid final listing image: {name}")
        rows.append({"filename": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return rows


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    BACKUP.mkdir(parents=True, exist_ok=True)

    # Preserve every prior flattened listing image before changing final names.
    for path in OUTPUT.glob("*.jpg"):
        backup = BACKUP / path.name
        if not backup.exists():
            shutil.copy2(path, backup)

    # Copy the six already-approved core graphics into the new standard order.
    for destination_name, legacy_name in CORE_SOURCES.items():
        source = BACKUP / legacy_name
        if not source.is_file():
            source = OUTPUT / legacy_name
        if not source.is_file():
            raise RuntimeError(f"Missing approved core graphic: {legacy_name}")
        destination = OUTPUT / destination_name
        if source.resolve() != destination.resolve():
            temp = destination.with_suffix(".tmp.jpg")
            shutil.copy2(source, temp)
            os.replace(temp, destination)

    # Create the four requested no-text 2x2 framed-gallery mockups.
    for filename, numbers in GALLERY_IDS.items():
        save_jpeg_atomic(build_gallery(numbers), OUTPUT / filename)

    # Remove obsolete final JPG names only after replacements exist; backups remain.
    for path in OUTPUT.glob("*.jpg"):
        if path.name not in FINAL_NAMES:
            path.unlink()

    rows = validate_final()
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    report = [
        "DESERT & SOUTHWEST — TEN LISTING IMAGE GENERATION REPORT",
        "",
        f"Generated: {generated}",
        "Overall status: PASS",
        "Final listing images: 10",
        "Technical standard: 2600 × 2000 RGB JPEG",
        "Customer artwork source: exact normalized 3840 × 2160 delivery JPGs",
        "Core approved graphics retained: 6",
        "New framed-gallery mockups: 4",
        "Gallery layout: exact 2 × 2 horizontal 16:9 openings",
        "Gallery artwork repeats: 0 across 16 distinct selections",
        "Visible text, arrows, browser controls, logos, and watermarks in gallery mockups: none",
        "",
    ]
    for row in rows:
        used = GALLERY_IDS.get(row["filename"])
        suffix = f"; artworks {', '.join(f'{n:03d}' for n in used)}" if used else ""
        report.append(
            f'{row["filename"]}: {row["bytes"]} bytes; SHA-256 {row["sha256"]}{suffix}'
        )
    (OUTPUT / "generation-report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")

    audit_text = AUDIT.read_text(encoding="utf-8")
    audit_text = audit_text.replace(
        "Listing graphics: 9; 2600 × 2000 RGB JPG; PASS",
        "Listing graphics: 10; 2600 × 2000 RGB JPG; PASS",
    )
    AUDIT.write_text(audit_text, encoding="utf-8")

    state = json.loads(STATE.read_text(encoding="utf-8"))
    state["listing_graphic_status"] = "COMPLETE_10_IMAGES"
    state["audit_status"] = "COMPLETE"
    state["final_status"] = "COMPLETE"
    state["updated_at"] = generated
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"status": "PASS", "images": len(rows), "output": str(OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
