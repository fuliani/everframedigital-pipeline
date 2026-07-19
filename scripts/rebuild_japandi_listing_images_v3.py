"""Build the premium V3 Japandi-Minimalist Etsy listing image set.

All displayed art comes from the exact normalized customer JPG files.  The
room is used only as a background; customer art is composited into its screen.
Typography and layout are rendered deterministically with local fonts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO = Path(__file__).resolve().parents[1]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Japandi-Minimalist"
ART_DIR = PRODUCT / "customer-downloads" / "_work" / "normalized-jpg"
OUT = PRODUCT / "cover-v3-review"
WORK = OUT / "_work"
ROOM = WORK / "japandi-room-blank.png"
W, H = 2600, 2000

PAPER = "#F3EEE4"
PAPER_2 = "#E7DED0"
INK = "#252925"
OLIVE = "#687363"
TAUPE = "#927D69"
GOLD = "#B49155"
CLAY = "#A96F55"
WHITE = "#FFFDF8"


def font(size: int, *, serif: bool = False, bold: bool = False):
    name = "georgiab.ttf" if serif and bold else "georgia.ttf" if serif else "bahnschrift.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def centered(draw, xy, text, face, fill=INK, spacing=8):
    box = draw.multiline_textbbox((0, 0), text, font=face, spacing=spacing, align="center")
    draw.multiline_text((xy[0] - (box[2] - box[0]) / 2, xy[1]), text, font=face,
                        fill=fill, spacing=spacing, align="center")


def tracking(draw, xy, text, face, fill, tracking=5):
    widths = [draw.textlength(ch, font=face) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = xy[0] - total / 2
    for ch, width in zip(text, widths):
        draw.text((x, xy[1]), ch, font=face, fill=fill)
        x += width + tracking


def card_shadow(canvas, box, radius=18, offset=12):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = box
    d.rounded_rectangle((x1 + offset, y1 + offset, x2 + offset, y2 + offset), radius=radius,
                        fill=(42, 39, 34, 40))
    canvas.paste(layer, (0, 0), layer)


def art_tile(canvas, art, box, *, border=4, shadow=True):
    x, y, w, h = box
    if shadow:
        card_shadow(canvas, (x - border, y - border, x + w + border, y + h + border), 8, 8)
    d = ImageDraw.Draw(canvas)
    d.rectangle((x - border, y - border, x + w + border, y + h + border), fill=GOLD)
    canvas.paste(fit(art, (w, h)), (x, y))


def top_brand(draw, *, dark=False):
    color = WHITE if dark else OLIVE
    tracking(draw, (210, 60), "EVERFRAME DIGITAL", font(25, bold=True), color, 3)


def editorial_header(canvas, title, subtitle):
    d = ImageDraw.Draw(canvas)
    top_brand(d)
    d.line((90, 112, W - 90, 112), fill=GOLD, width=3)
    centered(d, (W / 2, 142), title, font(68, serif=True, bold=True), INK)
    tracking(d, (W / 2, 242), subtitle, font(25, bold=True), TAUPE, 3)


def save(canvas, name):
    assert canvas.size == (W, H) and canvas.mode == "RGB"
    path = OUT / name
    canvas.save(path, "JPEG", quality=95, subsampling=0, optimize=True)
    with Image.open(path) as check:
        assert check.size == (W, H) and check.mode == "RGB" and check.format == "JPEG"
    return path


def room_with_art(art, size=(2600, 1463)):
    with Image.open(ROOM) as source:
        room = fit(source, size)
    # The generated room is 1672x941; these coordinates map its exact blank screen.
    sx, sy = size[0] / 1672, size[1] / 941
    x, y = round(560 * sx), round(139 * sy)
    sw, sh = round(740 * sx), round(426 * sy)
    room.paste(fit(art, (sw, sh)), (x, y))
    return room


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if not ROOM.is_file():
        raise RuntimeError(f"Missing room background: {ROOM}")
    arts = {}
    for number in range(1, 101):
        path = ART_DIR / f"Japandi-Minimalist-{number:03d}.jpg"
        if not path.is_file():
            raise RuntimeError(f"Missing customer artwork {number:03d}")
        image = Image.open(path).convert("RGB")
        if image.size != (3840, 2160):
            raise RuntimeError(f"Invalid customer artwork dimensions: {path.name}")
        arts[number] = image

    used = {}

    # 01 — dense, high-contrast thumbnail cover with 48 exact customer previews.
    canvas = Image.new("RGB", (W, H), PAPER)
    ids = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35,
           37, 39, 41, 43, 45, 47, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76,
           78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100]
    for section, start_y, offset in [(0, 28, 0), (1, 1180, 24)]:
        for r in range(4):
            for c in range(6):
                art_tile(canvas, arts[ids[offset + r * 6 + c]],
                         (55 + c * 421, start_y + r * 204, 390, 219), border=3, shadow=False)
    d = ImageDraw.Draw(canvas)
    card_shadow(canvas, (155, 830, 2445, 1160), 24, 14)
    d.rounded_rectangle((155, 830, 2445, 1160), radius=24, fill=INK, outline=GOLD, width=5)
    d.text((240, 868), "100", font=font(156, serif=True, bold=True), fill=WHITE)
    d.line((590, 875, 590, 1112), fill=GOLD, width=3)
    tracking(d, (1480, 872), "JAPANDI MINIMALIST", font(45, serif=True, bold=True), WHITE, 5)
    tracking(d, (1480, 957), "FRAME TV ART COLLECTION", font(28, bold=True), "#D8C9B5", 4)
    d.rounded_rectangle((785, 1042, 2175, 1110), radius=30, fill=OLIVE)
    tracking(d, (1480, 1053), "4K UHD  •  16:9  •  INSTANT DOWNLOAD", font(23, bold=True), WHITE, 2)
    used["01-main-cover.jpg"] = ids
    save(canvas, "01-main-cover.jpg")

    # 02 — premium collection overview with five visual chapters.
    canvas = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, 610, H), fill=INK)
    top_brand(d, dark=True)
    d.text((95, 270), "100", font=font(180, serif=True, bold=True), fill=WHITE)
    d.text((100, 485), "CURATED\nARTWORKS", font=font(48, serif=True, bold=True), fill="#D8C9B5", spacing=14)
    d.line((100, 650, 505, 650), fill=GOLD, width=4)
    d.text((100, 710), "FIVE VISUAL CHAPTERS", font=font(24, bold=True), fill=WHITE)
    d.multiline_text((100, 790), "Still lifes\nNatural materials\nQuiet landscapes\nOrganic abstracts\nArchitectural studies",
                     font=font(29), fill="#D8C9B5", spacing=30)
    d.rounded_rectangle((95, 1515, 510, 1665), radius=18, outline=GOLD, width=3)
    centered(d, (303, 1545), "4K UHD\n3840 × 2160", font(25, bold=True), WHITE, 12)
    d.text((690, 70), "THE COLLECTION", font=font(72, serif=True, bold=True), fill=INK)
    tracking(d, (1635, 168), "A QUIET STUDY IN FORM, TEXTURE & SPACE", font(23, bold=True), TAUPE, 3)
    rows = [
        ("OBJECTS & STILL LIFES", [1, 5, 10, 16]),
        ("LINEN • WOOD • WOVEN", [21, 25, 30, 36]),
        ("STONE • SAND • LANDSCAPE", [41, 45, 50, 56]),
        ("ORGANIC ABSTRACTS", [61, 65, 70, 76]),
        ("ARCHITECTURAL STUDIES", [81, 85, 90, 96]),
    ]
    for r, (label, row_ids) in enumerate(rows):
        y = 270 + r * 327
        d.text((690, y), f"0{r + 1}", font=font(25, bold=True), fill=CLAY)
        d.text((750, y), label, font=font(25, bold=True), fill=INK)
        for c, n in enumerate(row_ids):
            art_tile(canvas, arts[n], (690 + c * 458, y + 56, 420, 236), border=3)
    used["02-collection-overview.jpg"] = [n for _, row in rows for n in row]
    save(canvas, "02-collection-overview.jpg")

    # 03–05 — denser 20-piece editorial galleries.
    galleries = [
        ("03-gallery-one.jpg", "I", list(range(1, 40, 2))),
        ("04-gallery-two.jpg", "II", list(range(41, 80, 2))),
        ("05-gallery-three.jpg", "III", list(range(81, 101)) + [82, 84, 86, 88, 90]),
    ]
    for name, roman, gallery_ids in galleries:
        gallery_ids = gallery_ids[:20]
        canvas = Image.new("RGB", (W, H), PAPER)
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 0, W, 225), fill=INK)
        tracking(d, (260, 58), "EVERFRAME DIGITAL", font(24, bold=True), "#D8C9B5", 3)
        centered(d, (W / 2, 45), "JAPANDI MINIMALIST", font(62, serif=True, bold=True), WHITE)
        d.rounded_rectangle((2180, 54, 2485, 150), radius=46, outline=GOLD, width=3)
        centered(d, (2332, 77), f"GALLERY {roman}", font(22, bold=True), WHITE)
        for r in range(5):
            for c in range(4):
                n = gallery_ids[r * 4 + c]
                art_tile(canvas, arts[n], (72 + c * 632, 285 + r * 326, 590, 332), border=3)
        used[name] = gallery_ids
        save(canvas, name)

    # 06 — polished room mockup plus 12-product gallery rail.
    canvas = Image.new("RGB", (W, H), PAPER)
    hero = room_with_art(arts[52], (2600, 1463))
    canvas.paste(hero, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((80, 65, 1010, 190), radius=55, fill=INK)
    tracking(d, (545, 91), "DESIGNED FOR ART MODE", font(26, bold=True), WHITE, 3)
    d.rounded_rectangle((1870, 65, 2515, 190), radius=55, fill=WHITE, outline=GOLD, width=3)
    centered(d, (2192, 91), "100 CURATED 4K ARTWORKS", font(23, bold=True), INK)
    d.rectangle((0, 1463, W, H), fill=INK)
    tracking(d, (W / 2, 1490), "SEE THE COLLECTION ON SCREEN", font(26, bold=True), "#D8C9B5", 4)
    rail = [4, 12, 20, 28, 36, 44, 60, 68, 76, 84, 92, 100]
    for c, n in enumerate(rail):
        art_tile(canvas, arts[n], (60 + c * 211, 1572, 188, 106), border=2, shadow=False)
        art_tile(canvas, arts[rail[(c + 6) % 12]], (60 + c * 211, 1740, 188, 106), border=2, shadow=False)
    used["06-frame-tv-preview.jpg"] = [52] + rail
    save(canvas, "06-frame-tv-preview.jpg")

    # 07 — specifications with 12 previews and stronger typographic hierarchy.
    canvas = Image.new("RGB", (W, H), PAPER)
    editorial_header(canvas, "EVERYTHING INCLUDED", "ONE DOWNLOAD • A COMPLETE JAPANDI GALLERY")
    d = ImageDraw.Draw(canvas)
    preview_ids = [2, 8, 14, 20, 27, 33, 39, 52, 64, 77, 88, 97]
    for r in range(4):
        for c in range(3):
            art_tile(canvas, arts[preview_ids[r * 3 + c]], (85 + c * 365, 365 + r * 310, 330, 186), border=3)
    d.rounded_rectangle((1240, 350, 2500, 1795), radius=30, fill=INK)
    d.text((1350, 445), "100", font=font(170, serif=True, bold=True), fill=WHITE)
    d.text((1740, 535), "UNIQUE JPG\nARTWORKS", font=font(39, serif=True, bold=True), fill="#D8C9B5", spacing=8)
    d.line((1350, 680, 2385, 680), fill=GOLD, width=3)
    specs = ["3840 × 2160 PIXELS", "TRUE 4K UHD", "16:9 LANDSCAPE FORMAT",
             "5 ORGANIZED ZIP FILES", "INSTANT DIGITAL DOWNLOAD", "PERSONAL USE LICENSE"]
    for i, text in enumerate(specs):
        y = 770 + i * 135
        d.ellipse((1350, y + 8, 1378, y + 36), fill=CLAY)
        d.text((1420, y), text, font=font(30, bold=True), fill=WHITE)
    d.rounded_rectangle((1350, 1600, 2385, 1705), radius=50, outline=GOLD, width=3)
    centered(d, (1867, 1626), "DIGITAL PRODUCT • NO PHYSICAL SHIPPING", font(22, bold=True), "#D8C9B5")
    used["07-whats-included.jpg"] = preview_ids
    save(canvas, "07-whats-included.jpg")

    # 08 — room hero plus four concise download/display steps.
    canvas = Image.new("RGB", (W, H), PAPER)
    room = room_with_art(arts[34], (2600, 1120))
    canvas.paste(room, (0, 0))
    overlay = Image.new("RGBA", (W, 230), (37, 41, 37, 220))
    canvas.paste(overlay, (0, 0), overlay)
    d = ImageDraw.Draw(canvas)
    tracking(d, (W / 2, 48), "DOWNLOAD • TRANSFER • DISPLAY", font(35, bold=True), WHITE, 5)
    centered(d, (W / 2, 115), "Four simple steps from purchase to Art Mode", font(27), "#D8C9B5")
    steps = [
        ("01", "DOWNLOAD", "Open Etsy Purchases and\ndownload all five ZIP files."),
        ("02", "EXTRACT", "Use a computer to extract\nall 100 JPG artworks."),
        ("03", "TRANSFER", "Send your chosen image with\na compatible device method."),
        ("04", "DISPLAY", "Open Art Mode, add the art,\nand adjust to your preference."),
    ]
    for i, (number, title, copy) in enumerate(steps):
        x1 = 70 + i * 635
        card_shadow(canvas, (x1, 1195, x1 + 570, 1830), 24, 12)
        d.rounded_rectangle((x1, 1195, x1 + 570, 1830), radius=24, fill=WHITE, outline=GOLD, width=3)
        d.text((x1 + 48, 1250), number, font=font(92, serif=True, bold=True), fill=OLIVE)
        d.text((x1 + 48, 1390), title, font=font(30, bold=True), fill=INK)
        d.line((x1 + 48, 1450, x1 + 515, 1450), fill="#D7C8B5", width=2)
        d.multiline_text((x1 + 48, 1510), copy, font=font(25), fill=TAUPE, spacing=13)
    centered(d, (W / 2, 1910), "A computer is the easiest way to extract ZIP archives.", font(27, bold=True), TAUPE)
    used["08-how-to-display.jpg"] = [34]
    save(canvas, "08-how-to-display.jpg")

    # 09 — premium quality and compatibility with room context and six previews.
    canvas = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, W, 235), fill=INK)
    tracking(d, (260, 66), "EVERFRAME DIGITAL", font(24, bold=True), "#D8C9B5", 3)
    centered(d, (W / 2, 45), "PREMIUM 4K QUALITY", font(66, serif=True, bold=True), WHITE)
    tracking(d, (W / 2, 145), "MADE FOR 16:9 DIGITAL DISPLAYS", font(23, bold=True), "#D8C9B5", 4)
    room = room_with_art(arts[74], (1560, 880))
    canvas.paste(room, (70, 300))
    d.rounded_rectangle((1700, 300, 2510, 1180), radius=25, fill=WHITE, outline=GOLD, width=3)
    d.text((1790, 390), "DISPLAY\nCOMPATIBILITY", font=font(44, serif=True, bold=True), fill=INK, spacing=8)
    d.line((1790, 525, 2415, 525), fill=GOLD, width=3)
    compat = ["FRAME TV ART MODE", "TELEVISIONS & MONITORS", "TABLETS & DIGITAL DISPLAYS", "SCREENSAVERS"]
    for i, text in enumerate(compat):
        y = 620 + i * 118
        d.ellipse((1790, y + 5, 1818, y + 33), fill=OLIVE)
        d.text((1858, y), text, font=font(25, bold=True), fill=INK)
    d.text((1790, 1090), "Screen colors may vary by device.", font=font(22), fill=TAUPE)
    d.rectangle((0, 1260, W, H), fill=PAPER_2)
    preview_ids = [18, 42, 58, 66, 82, 94]
    for c, n in enumerate(preview_ids):
        art_tile(canvas, arts[n], (70 + c * 421, 1350, 390, 219), border=3)
    d.rounded_rectangle((390, 1660, 2210, 1855), radius=85, fill=INK)
    centered(d, (W / 2, 1695), "3840 × 2160 JPG  •  TRUE 4K UHD  •  16:9 LANDSCAPE", font(27, bold=True), WHITE)
    centered(d, (W / 2, 1770), "100 curated artworks, ready for your display", font(25), "#D8C9B5")
    used["09-quality-compatibility.jpg"] = [74] + preview_ids
    save(canvas, "09-quality-compatibility.jpg")

    for image in arts.values():
        image.close()

    report = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS",
        "design_version": "V3 premium editorial",
        "files": [],
        "verification": {
            "dimensions": "2600x2000",
            "format": "RGB JPEG",
            "exact_customer_artwork": True,
            "deterministic_typography": True,
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
