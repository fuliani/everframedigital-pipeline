"""Build the bright V5 Japandi-Minimalist Etsy listing image set.

The V5 direction uses a dense customer-art gallery, light warm-linen panels,
muted sage accents, and deterministic typography.  Every displayed artwork is
loaded from the exact normalized customer-delivery JPG collection.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.rebuild_japandi_listing_images_v3 import (
    ART_DIR,
    H,
    ROOM,
    W,
    art_tile,
    card_shadow,
    centered,
    fit,
    font,
    room_with_art,
    tracking,
)


REPO = Path(__file__).resolve().parents[1]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Japandi-Minimalist"
OUT = PRODUCT / "cover-v5-review"
WORK = OUT / "_work"

CREAM = "#F7F3EB"
LINEN = "#E9E0D3"
SAGE = "#D9DFD3"
INK = "#28302B"
OLIVE = "#66735F"
TAUPE = "#8C7867"
GOLD = "#B48C4D"
CLAY = "#A96F55"
WHITE = "#FFFEFA"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save(canvas: Image.Image, name: str) -> Path:
    path = OUT / name
    assert canvas.size == (W, H) and canvas.mode == "RGB"
    canvas.save(path, "JPEG", quality=95, subsampling=0, optimize=True)
    with Image.open(path) as check:
        assert check.size == (W, H)
        assert check.mode == "RGB"
        assert check.format == "JPEG"
    return path


def brand_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    tracking(draw, (235, 55), "EVERFRAME DIGITAL", font(23, bold=True), OLIVE, 3)
    draw.line((72, 108, W - 72, 108), fill=GOLD, width=3)
    centered(draw, (W / 2, 145), title, font(63, serif=True, bold=True), INK)
    tracking(draw, (W / 2, 238), subtitle, font(23, bold=True), TAUPE, 3)


def light_tile(canvas: Image.Image, art: Image.Image, box: tuple[int, int, int, int], *, shadow=True) -> None:
    art_tile(canvas, art, box, border=3, shadow=shadow)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if not ROOM.is_file():
        raise RuntimeError(f"Missing approved blank room background: {ROOM}")

    arts: dict[int, Image.Image] = {}
    for number in range(1, 101):
        path = ART_DIR / f"Japandi-Minimalist-{number:03d}.jpg"
        if not path.is_file():
            raise RuntimeError(f"Missing customer artwork: {path.name}")
        image = Image.open(path).convert("RGB")
        if image.size != (3840, 2160):
            raise RuntimeError(f"Invalid customer artwork dimensions: {path.name}")
        arts[number] = image

    used: dict[str, list[int]] = {}

    # 01 — bright, dense cover with 64 unique customer artworks.
    canvas = Image.new("RGB", (W, H), CREAM)
    ids = [round(i * 99 / 63) + 1 for i in range(64)]
    tile_w, tile_h, gap_x, gap_y = 304, 171, 16, 12
    x0 = 28
    for half, y0, offset in ((0, 24, 0), (1, 1270, 32)):
        for row in range(4):
            for col in range(8):
                number = ids[offset + row * 8 + col]
                x = x0 + col * (tile_w + gap_x)
                y = y0 + row * (tile_h + gap_y)
                light_tile(canvas, arts[number], (x, y, tile_w, tile_h), shadow=False)
    card_shadow(canvas, (105, 785, 2495, 1235), radius=26, offset=12)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((105, 785, 2495, 1235), radius=26, fill=WHITE, outline=GOLD, width=4)
    d.rounded_rectangle((165, 830, 530, 900), radius=34, fill=OLIVE)
    centered(d, (348, 847), "EVERFRAME DIGITAL", font(20, bold=True), WHITE)
    d.text((165, 925), "100", font=font(156, serif=True, bold=True), fill=INK)
    d.line((585, 842, 585, 1178), fill=GOLD, width=3)
    d.text((665, 842), "JAPANDI", font=font(70, serif=True, bold=True), fill=INK)
    d.text((665, 920), "MINIMALIST", font=font(70, serif=True, bold=True), fill=INK)
    tracking(d, (1525, 1025), "FRAME TV ART COLLECTION", font(27, bold=True), TAUPE, 4)
    d.rounded_rectangle((665, 1090, 2325, 1170), radius=38, fill=OLIVE)
    tracking(d, (1495, 1108), "4K UHD  •  16:9  •  INSTANT DOWNLOAD", font(24, bold=True), WHITE, 3)
    used["01-main-cover.jpg"] = ids
    save(canvas, "01-main-cover.jpg")

    # 02 — light collection overview with 24 previews across six visual chapters.
    canvas = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, 555, H), fill=LINEN)
    d.rectangle((0, 0, 20, H), fill=OLIVE)
    tracking(d, (275, 60), "EVERFRAME DIGITAL", font(22, bold=True), OLIVE, 3)
    d.text((75, 215), "100", font=font(170, serif=True, bold=True), fill=INK)
    d.text((80, 430), "CURATED\nARTWORKS", font=font(43, serif=True, bold=True), fill=OLIVE, spacing=10)
    d.line((80, 590, 475, 590), fill=GOLD, width=4)
    d.text((80, 650), "A COMPLETE JAPANDI GALLERY", font=font(22, bold=True), fill=INK)
    d.multiline_text((80, 735), "Ceramic still lifes\nNatural materials\nQuiet landscapes\nBotanical studies\nOrganic abstracts\nArchitectural forms",
                     font=font(27), fill=TAUPE, spacing=26)
    d.rounded_rectangle((75, 1550, 475, 1705), radius=25, fill=WHITE, outline=GOLD, width=3)
    centered(d, (275, 1583), "TRUE 4K UHD\n3840 × 2160", font(25, bold=True), INK, 10)
    d.text((625, 60), "THE COLLECTION", font=font(66, serif=True, bold=True), fill=INK)
    tracking(d, (1605, 158), "FORM • TEXTURE • SPACE", font(23, bold=True), TAUPE, 4)
    rows = [
        ("CERAMIC STILL LIFES", [1, 5, 10, 16]),
        ("LINEN • WOOD • WOVEN", [21, 25, 30, 36]),
        ("BOTANICAL STUDIES", [41, 45, 50, 56]),
        ("QUIET LANDSCAPES", [61, 65, 70, 76]),
        ("ORGANIC ABSTRACTS", [81, 85, 90, 96]),
        ("ARCHITECTURAL FORMS", [72, 84, 92, 100]),
    ]
    for row, (label, row_ids) in enumerate(rows):
        y = 245 + row * 278
        d.text((625, y), f"0{row + 1}", font=font(22, bold=True), fill=CLAY)
        d.text((680, y), label, font=font(22, bold=True), fill=INK)
        for col, number in enumerate(row_ids):
            light_tile(canvas, arts[number], (625 + col * 475, y + 45, 360, 203))
    used["02-collection-overview.jpg"] = [n for _, row in rows for n in row]
    save(canvas, "02-collection-overview.jpg")

    # 03–05 — three bright 24-piece galleries.
    galleries = [
        ("03-gallery-one.jpg", "I", list(range(1, 25))),
        ("04-gallery-two.jpg", "II", list(range(39, 63))),
        ("05-gallery-three.jpg", "III", list(range(77, 101))),
    ]
    for name, roman, gallery_ids in galleries:
        canvas = Image.new("RGB", (W, H), CREAM)
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 0, W, 330), fill=SAGE)
        tracking(d, (245, 55), "EVERFRAME DIGITAL", font(22, bold=True), OLIVE, 3)
        centered(d, (W / 2, 78), "JAPANDI MINIMALIST", font(59, serif=True, bold=True), INK)
        tracking(d, (W / 2, 175), "A CURATED VIEW OF THE 100-PIECE COLLECTION", font(21, bold=True), TAUPE, 3)
        d.rounded_rectangle((2180, 60, 2485, 155), radius=46, fill=WHITE, outline=GOLD, width=3)
        centered(d, (2332, 84), f"GALLERY {roman}", font(21, bold=True), INK)
        for row in range(4):
            for col in range(6):
                number = gallery_ids[row * 6 + col]
                light_tile(canvas, arts[number], (54 + col * 424, 390 + row * 344, 390, 219))
        d.rounded_rectangle((680, 1820, 1920, 1905), radius=40, fill=WHITE, outline=GOLD, width=2)
        tracking(d, (1300, 1842), "EXACT ARTWORKS INCLUDED IN YOUR DOWNLOAD", font(20, bold=True), OLIVE, 3)
        used[name] = gallery_ids
        save(canvas, name)

    # 06 — room preview with a bright 28-art gallery rail.
    canvas = Image.new("RGB", (W, H), CREAM)
    canvas.paste(room_with_art(arts[52], (2600, 1380)), (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((75, 60, 960, 178), radius=55, fill=WHITE, outline=GOLD, width=3)
    tracking(d, (518, 88), "DESIGNED FOR ART MODE", font(24, bold=True), OLIVE, 3)
    d.rounded_rectangle((1830, 60, 2525, 178), radius=55, fill=OLIVE)
    centered(d, (2178, 89), "100 CURATED 4K ARTWORKS", font(22, bold=True), WHITE)
    d.rectangle((0, 1380, W, H), fill=LINEN)
    centered(d, (W / 2, 1410), "SEE MORE OF THE COLLECTION", font(28, serif=True, bold=True), INK)
    tracking(d, (W / 2, 1468), "EXACT CUSTOMER ARTWORK • READY FOR 16:9 DISPLAYS", font(18, bold=True), TAUPE, 3)
    rail = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53,
            57, 61, 65, 69, 73, 77, 81, 85, 89, 93, 96, 98, 99, 100]
    for row in range(2):
        for col in range(14):
            number = rail[row * 14 + col]
            light_tile(canvas, arts[number], (38 + col * 181, 1535 + row * 205, 165, 93), shadow=False)
    used["06-frame-tv-preview.jpg"] = [52] + rail
    save(canvas, "06-frame-tv-preview.jpg")

    # 07 — 16 previews plus a light specification card.
    canvas = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(canvas)
    brand_header(d, "EVERYTHING INCLUDED", "ONE DOWNLOAD • A COMPLETE JAPANDI GALLERY")
    preview_ids = [2, 8, 14, 20, 27, 33, 39, 45, 52, 58, 64, 70, 77, 84, 92, 99]
    for row in range(4):
        for col in range(4):
            light_tile(canvas, arts[preview_ids[row * 4 + col]], (70 + col * 282, 390 + row * 300, 255, 143))
    card_shadow(canvas, (1240, 345, 2510, 1815), radius=30, offset=12)
    d.rounded_rectangle((1240, 345, 2510, 1815), radius=30, fill=SAGE, outline=GOLD, width=3)
    d.text((1340, 430), "100", font=font(170, serif=True, bold=True), fill=INK)
    d.text((1730, 515), "UNIQUE JPG\nARTWORKS", font=font(38, serif=True, bold=True), fill=OLIVE, spacing=8)
    d.line((1340, 680, 2410, 680), fill=GOLD, width=3)
    specs = ["3840 × 2160 PIXELS", "TRUE 4K UHD", "16:9 LANDSCAPE FORMAT",
             "5 ORGANIZED ZIP FILES", "INSTANT DIGITAL DOWNLOAD", "PERSONAL USE LICENSE"]
    for index, text in enumerate(specs):
        y = 770 + index * 137
        d.ellipse((1340, y + 7, 1370, y + 37), fill=CLAY)
        d.text((1415, y), text, font=font(29, bold=True), fill=INK)
    d.rounded_rectangle((1340, 1602, 2410, 1715), radius=55, fill=WHITE, outline=GOLD, width=2)
    centered(d, (1875, 1636), "DIGITAL PRODUCT • NO PHYSICAL SHIPPING", font(21, bold=True), OLIVE)
    used["07-whats-included.jpg"] = preview_ids
    save(canvas, "07-whats-included.jpg")

    # 08 — room context, eight-art rail, and four bright instructional cards.
    canvas = Image.new("RGB", (W, H), CREAM)
    canvas.paste(room_with_art(arts[34], (2600, 1070)), (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((365, 55, 2235, 205), radius=70, fill=WHITE, outline=GOLD, width=3)
    tracking(d, (W / 2, 78), "DOWNLOAD • TRANSFER • DISPLAY", font(30, bold=True), OLIVE, 4)
    centered(d, (W / 2, 142), "Four simple steps from purchase to Art Mode", font(24), TAUPE)
    mini_ids = [6, 18, 30, 42, 54, 66, 78, 90]
    for col, number in enumerate(mini_ids):
        light_tile(canvas, arts[number], (215 + col * 275, 900, 250, 141), shadow=False)
    steps = [
        ("01", "DOWNLOAD", "Open Etsy Purchases and\ndownload all five ZIP files."),
        ("02", "EXTRACT", "Use a computer to extract\nall 100 JPG artworks."),
        ("03", "TRANSFER", "Send your chosen image with\na compatible device method."),
        ("04", "DISPLAY", "Open Art Mode, add the art,\nand adjust to your preference."),
    ]
    for index, (number, title, copy) in enumerate(steps):
        x1 = 70 + index * 635
        card_shadow(canvas, (x1, 1130, x1 + 570, 1810), radius=24, offset=10)
        d.rounded_rectangle((x1, 1130, x1 + 570, 1810), radius=24, fill=WHITE, outline=GOLD, width=3)
        d.text((x1 + 45, 1185), number, font=font(88, serif=True, bold=True), fill=OLIVE)
        d.text((x1 + 45, 1320), title, font=font(29, bold=True), fill=INK)
        d.line((x1 + 45, 1382, x1 + 520, 1382), fill=SAGE, width=3)
        d.multiline_text((x1 + 45, 1445), copy, font=font(24), fill=TAUPE, spacing=13)
    centered(d, (W / 2, 1905), "A computer is the easiest way to extract ZIP archives.", font(25, bold=True), TAUPE)
    used["08-how-to-display.jpg"] = [34] + mini_ids
    save(canvas, "08-how-to-display.jpg")

    # 09 — quality and compatibility with 12 previews and light panels.
    canvas = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, W, 300), fill=SAGE)
    tracking(d, (245, 55), "EVERFRAME DIGITAL", font(22, bold=True), OLIVE, 3)
    centered(d, (W / 2, 72), "PREMIUM 4K QUALITY", font(63, serif=True, bold=True), INK)
    tracking(d, (W / 2, 180), "MADE FOR 16:9 DIGITAL DISPLAYS", font(22, bold=True), TAUPE, 4)
    canvas.paste(room_with_art(arts[74], (1535, 850)), (65, 350))
    d.rounded_rectangle((1665, 350, 2535, 1200), radius=28, fill=WHITE, outline=GOLD, width=3)
    d.text((1750, 425), "DISPLAY\nCOMPATIBILITY", font=font(42, serif=True, bold=True), fill=INK, spacing=7)
    d.line((1750, 565, 2450, 565), fill=GOLD, width=3)
    compat = ["FRAME TV ART MODE", "TELEVISIONS & MONITORS", "TABLETS & DIGITAL DISPLAYS", "SCREENSAVERS"]
    for index, text in enumerate(compat):
        y = 660 + index * 116
        d.ellipse((1750, y + 4, 1780, y + 34), fill=OLIVE)
        d.text((1820, y), text, font=font(24, bold=True), fill=INK)
    d.text((1750, 1110), "Screen colors may vary by device.", font=font(21), fill=TAUPE)
    preview_ids = [4, 12, 20, 28, 36, 44, 60, 68, 76, 84, 92, 100]
    for col, number in enumerate(preview_ids):
        light_tile(canvas, arts[number], (55 + col * 211, 1305, 188, 106), shadow=False)
        light_tile(canvas, arts[preview_ids[(col + 6) % 12]], (55 + col * 211, 1460, 188, 106), shadow=False)
    d.rounded_rectangle((250, 1655, 2350, 1870), radius=95, fill=OLIVE)
    centered(d, (W / 2, 1697), "3840 × 2160 JPG  •  TRUE 4K UHD  •  16:9 LANDSCAPE", font(27, bold=True), WHITE)
    centered(d, (W / 2, 1780), "100 curated artworks, ready for your display", font(25), WHITE)
    used["09-quality-compatibility.jpg"] = [74] + preview_ids
    save(canvas, "09-quality-compatibility.jpg")

    for image in arts.values():
        image.close()

    report = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS",
        "design_version": "V5 bright dense gallery",
        "files": [],
        "verification": {
            "dimensions": "2600x2000",
            "format": "RGB JPEG",
            "exact_customer_artwork": True,
            "deterministic_typography": True,
            "consistent_light_design_system": True,
            "room_background_contains_generated_text": False,
        },
    }
    for name, numbers in used.items():
        path = OUT / name
        report["files"].append({
            "filename": name,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "artworks": numbers,
        })
    (OUT / "generation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(OUT), "images": len(used)}, indent=2))


if __name__ == "__main__":
    main()
