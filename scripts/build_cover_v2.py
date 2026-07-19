"""
Generalized version of the ChatGPT-produced render_v2.py cover/mockup system
(originally built one-off for Coastal-Landscape in cover-v2-review/), applied
across all 6 style bundles. Flat illustrated-room design (not photoreal),
gold double-border framed art, mosaic main cover, Georgia/Arial type system.
"""

import os
import re
import shutil
import zipfile
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "EverframeDigital" / "Products"
TMP = ROOT / "scratch_browser" / "_cover_v2_work"

W, H = 2600, 2000
IV = (244, 240, 231); SAND = (219, 207, 186); STONE = (65, 67, 62)
SAGE = (102, 112, 88); GOLD = (169, 133, 77); WHITE = (252, 250, 245); INK = (35, 36, 32)
FONT_DIR = Path("C:/Windows/Fonts")
SERIF = str(FONT_DIR / "georgia.ttf"); SERIFB = str(FONT_DIR / "georgiab.ttf")
SANS = str(FONT_DIR / "arial.ttf"); SANSB = str(FONT_DIR / "arialbd.ttf")


def f(path, size):
    return ImageFont.truetype(path, size)


STYLES = [
    dict(slug="Coastal-Landscape", label="COASTAL LANDSCAPES", singular="Coastal Landscape"),
    dict(slug="Neutral-Botanical", label="NEUTRAL BOTANICALS", singular="Neutral Botanical"),
    dict(slug="Modern-Abstract-Neutral", label="MODERN ABSTRACTS", singular="Modern Abstract"),
    dict(slug="Minimalist-Line-Art", label="MINIMALIST LINE ART", singular="Minimalist Line Art"),
    dict(slug="Vintage-Botanical", label="VINTAGE BOTANICALS", singular="Vintage Botanical"),
    dict(slug="Seasonal-Neutral", label="SEASONAL NATURE", singular="Seasonal Nature"),
]


def spread_indices(n, k):
    """k distinct 1-based indices spread evenly across 1..n."""
    if k >= n:
        return list(range(1, n + 1))[:k]
    idxs, seen = [], set()
    for i in range(k):
        idx = 1 + round(i * (n - 1) / (k - 1))
        while idx in seen:
            idx += 1
        seen.add(idx)
        idxs.append(idx)
    return idxs


def build_for_style(style):
    slug, label, singular = style["slug"], style["label"], style["singular"]
    print(f"\n=== {slug} ===")
    root = PRODUCTS / slug
    out = root / "cover"
    backup = root / "cover-v1-backup"
    downloads = root / "customer-downloads"
    work_art = TMP / slug / "art"
    work_art.mkdir(parents=True, exist_ok=True)

    zips = sorted(downloads.glob("*.zip"))
    num_zips = len(zips)
    for zp in zips:
        with zipfile.ZipFile(zp) as z:
            z.extractall(work_art)

    art_files = sorted(work_art.glob(f"{slug}-*.jpg"))
    count = len(art_files)
    if count == 0:
        print(f"  SKIP: no art files found for {slug}")
        return

    def art(n):
        return Image.open(work_art / f"{slug}-{n:03d}.jpg").convert("RGB")

    def fit(im, box):
        x, y, w, h = box
        r = im.copy()
        r.thumbnail((w, h), Image.Resampling.LANCZOS)
        bg = Image.new("RGB", (w, h), (25, 25, 23))
        bg.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
        return bg

    def framed(c, n, box):
        x, y, w, h = box
        d = ImageDraw.Draw(c)
        d.rounded_rectangle((x - 18, y - 18, x + w + 18, y + h + 18), 8, fill=(107, 84, 57))
        d.rectangle((x - 7, y - 7, x + w + 7, y + h + 7), fill=(199, 169, 119))
        c.paste(fit(art(n), (x, y, w, h)), (x, y))

    def txt(d, xy, s, font, fill=INK, anchor="la", spacing=4, align="left"):
        d.multiline_text(xy, s, font=font, fill=fill, anchor=anchor, spacing=spacing, align=align)

    def centered(d, y, s, font, fill=INK):
        txt(d, (W // 2, y), s, font, fill, "ma", align="center")

    def brand(d, x=140, y=110, anchor="la", fill=SAGE):
        txt(d, (x, y), "EVERFRAME DIGITAL", f(SANSB, 38), fill, anchor)

    def room_base():
        im = Image.new("RGB", (W, H), IV)
        d = ImageDraw.Draw(im)
        for y in range(H):
            t = y / H
            col = tuple(int(239 * (1 - t) + 213 * t) for _ in range(3))
            d.line((0, y, W, y), fill=(col[0] + 4, col[1] + 1, col[2] - 6))
        d.rectangle((0, 1550, W, H), fill=(183, 164, 137))
        d.rectangle((0, 1530, W, 1565), fill=(235, 228, 214))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.polygon([(0, 250), (900, 0), (1450, 1550), (680, 1550)], fill=(255, 247, 221, 65))
        im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((260, 1320, 1700, 1600), 20, fill=(158, 126, 91), outline=(112, 88, 62), width=8)
        d.rectangle((310, 1360, 1650, 1540), fill=(202, 176, 139))
        for x in (350, 760, 1170):
            d.line((x, 1360, x, 1540), fill=(148, 119, 85), width=5)
        d.polygon([(340, 1600), (395, 1600), (360, 1810), (320, 1810)], fill=(105, 81, 58))
        d.polygon([(1570, 1600), (1625, 1600), (1655, 1810), (1615, 1810)], fill=(105, 81, 58))
        return im

    def tv(c, n, box):
        x, y, w, h = box
        sh = Image.new("RGBA", c.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle((x + 20, y + 25, x + w + 35, y + h + 45), 18, fill=(0, 0, 0, 85))
        sh = sh.filter(ImageFilter.GaussianBlur(20))
        c.paste(sh, (0, 0), sh)
        d = ImageDraw.Draw(c)
        d.rectangle((x - 22, y - 22, x + w + 22, y + h + 22), fill=(82, 68, 53))
        d.rectangle((x - 10, y - 10, x + w + 10, y + h + 10), fill=(190, 156, 108))
        c.paste(fit(art(n), (x, y, w, h)), (x, y))

    def panel(c, box, fill=WHITE):
        ImageDraw.Draw(c).rounded_rectangle(box, 30, fill=fill)

    def save(c, name):
        out.mkdir(parents=True, exist_ok=True)
        p = out / name
        c.convert("RGB").save(p, "JPEG", quality=94, subsampling=0, dpi=(300, 300))
        print(f"  Saved: {p}")

    idxs = spread_indices(count, 21)
    mosaic_idx, spec_idx, hero_idx = idxs[:12], idxs[12:18], idxs[18:21]
    hero_details, hero_compat, hero_premium = hero_idx

    zip_labels = []
    for zp in zips:
        size_mb = zp.stat().st_size / (1024 * 1024)
        zip_labels.append((zp.name, f"{size_mb:.2f} MB"))

    # back up existing photoreal cover set once
    if out.exists() and not backup.exists():
        shutil.copytree(out, backup)
        print(f"  Backed up existing cover/ to cover-v1-backup/")

    # 01: mosaic cover
    c = Image.new("RGB", (W, H), IV)
    d = ImageDraw.Draw(c)
    boxes = []
    for r, y in enumerate((115, 510, 1425)):
        for col, x in enumerate((115, 725, 1335, 1945)):
            boxes.append((x, y, 528, 297))
    for n, b in zip(mosaic_idx, boxes):
        framed(c, n, b)
    panel(c, (250, 845, 2350, 1320), WHITE)
    brand(d, W // 2, 905, "ma")
    centered(d, 1020, str(count), f(SERIFB, 190), GOLD)
    centered(d, 1190, label, f(SERIFB, 76))
    centered(d, 1285, "FRAME TV ART COLLECTION", f(SANSB, 45), SAGE)
    centered(d, 1370, "4K UHD • 16:9 • INSTANT DOWNLOAD", f(SANSB, 38), STONE)
    save(c, "01-main-cover.jpg")

    # 02: room + product details
    c = room_base()
    d = ImageDraw.Draw(c)
    tv(c, hero_details, (180, 420, 1120, 630))
    d.rectangle((1370, 0, W, H), fill=WHITE)
    brand(d, 1985, 130, "ma")
    txt(d, (1985, 250), "PRODUCT DETAILS", f(SERIFB, 72), INK, "ma")
    d.line((1510, 350, 2460, 350), fill=GOLD, width=3)
    steps = [
        f"Purchase the {count}-piece {singular} Frame TV Art Collection.",
        f"Download {'both' if num_zips == 2 else 'all ' + str(num_zips)} ZIP file{'s' if num_zips != 1 else ''} from your Etsy Purchases page.",
        f"Extract the ZIP files to access {count} high-resolution JPG artworks.",
        "Transfer a selected image using the SmartThings app or a compatible device method.",
        "Open Art Mode, add your image, and adjust the display to your preference.",
    ]
    for i, s in enumerate(steps, 1):
        y = 470 + (i - 1) * 290
        txt(d, (1500, y), f"{i:02d}", f(SERIFB, 70), GOLD)
        txt(d, (1680, y), textwrap.fill(s, 39), f(SANS, 39), INK, spacing=12)
        d.line((1500, y + 205, 2460, y + 205), fill=SAND, width=3)
    save(c, "02-product-details.jpg")

    # 03: six artworks + specs
    c = Image.new("RGB", (W, H), IV)
    d = ImageDraw.Draw(c)
    brand(d)
    txt(d, (140, 195), "COLLECTION\nSPECIFICATIONS", f(SERIFB, 68), INK, spacing=5)
    positions = [(140, 510), (735, 510), (140, 880), (735, 880), (140, 1250), (735, 1250)]
    for n, (x, y) in zip(spec_idx, positions):
        framed(c, n, (x, y, 512, 288))
    panel(c, (1360, 120, 2480, 1880), WHITE)
    brand(d, 1920, 210, "ma")
    txt(d, (1920, 350), "THE COLLECTION", f(SERIFB, 64), INK, "ma")
    specs = [
        f"{count} UNIQUE JPG ARTWORKS", "3840 × 2160 PIXELS", "TRUE 4K UHD",
        "16:9 LANDSCAPE FORMAT", f"{num_zips} ZIP DOWNLOAD{'S' if num_zips != 1 else ''}",
        "DIGITAL DOWNLOAD ONLY", "PERSONAL USE LICENSE",
    ]
    for i, s in enumerate(specs):
        y = 525 + i * 165
        d.ellipse((1510, y + 8, 1540, y + 38), fill=GOLD)
        txt(d, (1580, y), s, f(SANSB, 39), STONE)
        d.line((1510, y + 100, 2330, y + 100), fill=SAND, width=2)
    txt(d, (1920, 1745), "No physical item will be shipped.", f(SANS, 37), SAGE, "ma")
    save(c, "03-collection-specs.jpg")

    # 04: how to download
    c = Image.new("RGB", (W, H), IV)
    d = ImageDraw.Draw(c)
    brand(d)
    txt(d, (140, 205), "HOW TO DOWNLOAD", f(SERIFB, 82))
    d.rounded_rectangle((140, 430, 1110, 1120), 28, fill=(76, 77, 73))
    d.rounded_rectangle((180, 470, 1070, 1080), 12, fill=WHITE)
    d.rectangle((100, 1120, 1150, 1180), fill=(132, 131, 125))
    d.polygon([(100, 1180), (1150, 1180), (1040, 1240), (210, 1240)], fill=(101, 100, 96))
    txt(d, (250, 545), "YOUR DOWNLOADS", f(SANSB, 38), SAGE)
    dl_rows = zip_labels[:2] if num_zips >= 2 else zip_labels
    for row_i, (y, (name, size)) in enumerate(zip([675, 865], dl_rows)):
        label_text = name.replace("-", "-\n", 1) if len(name) > 30 else name
        d.rounded_rectangle((240, y, 1010, y + 145), 18, fill=IV, outline=SAND, width=3)
        d.rectangle((275, y + 35, 345, y + 105), fill=GOLD)
        txt(d, (380, y + 25), label_text, f(SANSB, 26), STONE, spacing=5)
        txt(d, (965, y + 50), size, f(SANS, 28), SAGE, "ra")
    steps = [
        "Sign in to Etsy and open Purchases and Reviews.",
        "Select Download Files for your order.",
        f"Download {'both' if num_zips == 2 else 'all ' + str(num_zips)} ZIP archive{'s' if num_zips != 1 else ''} to a computer.",
        f"Extract {'both' if num_zips == 2 else 'all'} ZIP files to access all {count} JPG images.",
        "Choose your artwork and transfer it to your display.",
    ]
    for i, s in enumerate(steps, 1):
        y = 410 + (i - 1) * 225
        d.ellipse((1325, y, 1425, y + 100), outline=GOLD, width=5)
        txt(d, (1375, y + 50), f"{i:02d}", f(SANSB, 35), GOLD, "mm")
        txt(d, (1490, y + 5), textwrap.fill(s, 42), f(SANS, 40), INK, spacing=10)
        d.line((1490, y + 165, 2460, y + 165), fill=SAND, width=3)
    panel(c, (190, 1610, 2410, 1880), (226, 219, 204))
    txt(d, (1300, 1745), "A computer is the easiest way to extract ZIP archives.", f(SERIFB, 46), STONE, "mm")
    save(c, "04-how-to-download.jpg")

    # 05: room + compatibility
    c = room_base()
    d = ImageDraw.Draw(c)
    tv(c, hero_compat, (170, 400, 1120, 630))
    d.rectangle((1370, 0, W, H), fill=WHITE)
    brand(d, 1985, 130, "ma")
    txt(d, (1985, 255), "MADE FOR\n16:9 DISPLAYS", f(SERIFB, 72), INK, "ma", spacing=4, align="center")
    d.line((1510, 455, 2460, 455), fill=GOLD, width=3)
    items = ["FRAME TV ART MODE", "TELEVISIONS & MONITORS", "TABLETS & DIGITAL DISPLAYS", "SCREENSAVERS"]
    for i, s in enumerate(items):
        y = 580 + i * 180
        d.rounded_rectangle((1510, y, 1585, y + 75), 16, outline=GOLD, width=5)
        d.line((1530, y + 38, 1565, y + 38), fill=SAGE, width=5)
        txt(d, (1640, y + 15), s, f(SANSB, 39), STONE)
    txt(d, (1510, 1400), textwrap.fill("Every artwork is supplied as a standard 3840 × 2160 JPG in a 16:9 landscape format.", 43), f(SANS, 38), INK, spacing=11)
    txt(d, (1510, 1710), textwrap.fill("Screen colors may vary by device and display settings.", 43), f(SANS, 34), SAGE, spacing=9)
    save(c, "05-compatibility.jpg")

    # 06: full-bleed premium quality
    c = room_base()
    d = ImageDraw.Draw(c)
    tv(c, hero_premium, (404, 290, 1792, 1008))
    brand(d, W // 2, 115, "ma", WHITE)
    panel(c, (230, 1460, 2370, 1840), (41, 48, 45))
    txt(d, (1300, 1530), "PREMIUM 4K QUALITY", f(SERIFB, 78), WHITE, "ma")
    txt(d, (1300, 1645), "EVERY DETAIL, READY FOR DISPLAY", f(SANSB, 40), (215, 198, 160), "ma")
    txt(d, (1300, 1760), f"{count} curated {singular.lower()} artworks • 3840 × 2160 JPG • 16:9 landscape", f(SANS, 36), WHITE, "ma")
    save(c, "06-premium-quality.jpg")


if __name__ == "__main__":
    TMP.mkdir(parents=True, exist_ok=True)
    for style in STYLES:
        build_for_style(style)
    shutil.rmtree(TMP, ignore_errors=True)
    print("\nAll 6 bundles rebuilt with cover v2 system.")
