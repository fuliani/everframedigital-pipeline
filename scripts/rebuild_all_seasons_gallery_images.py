"""Rebuild All-Seasons supporting Etsy graphics with richer art previews."""

from __future__ import annotations

from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "All-Seasons-100-Collection"
ART = PRODUCT / "customer-downloads" / "_work" / "normalized-jpg"
OUT = PRODUCT / "cover-v2-review"
WORK = OUT / "_work" / "before-expanded-gallery"
W, H = 2600, 2000

IVORY = "#F5F1E8"
PANEL = "#EAE2D5"
GOLD = "#B99A5D"
INK = "#26231F"
SAGE = "#7E8B7D"
TAUPE = "#917C6C"


def fnt(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def center(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
           font: ImageFont.FreeTypeFont, fill=INK) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (box[2] - box[0]) / 2,
               xy[1] - (box[3] - box[1]) / 2 - box[1]),
              text, font=font, fill=fill)


def art(number: int) -> Path:
    path = ART / f"All-Seasons-{number:03d}.jpg"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def paste_art(canvas: Image.Image, number: int, box: tuple[int, int, int, int],
              border: int = 6) -> None:
    x1, y1, x2, y2 = box
    fw, fh = x2 - x1, y2 - y1
    shadow = Image.new("RGBA", (fw + 18, fh + 18), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle((9, 10, fw + 7, fh + 8), fill=(20, 17, 14, 65))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))
    canvas.paste(shadow, (x1 - 8, y1 - 7), shadow)
    with Image.open(art(number)) as src:
        image = ImageOps.fit(src.convert("RGB"), (fw - border * 2, fh - border * 2),
                             method=Image.Resampling.LANCZOS)
    frame = Image.new("RGB", (fw, fh), GOLD)
    frame.paste(image, (border, border))
    canvas.paste(frame, (x1, y1))


def base(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGB", (W, H), IVORY)
    draw = ImageDraw.Draw(canvas)
    draw.text((110, 65), "EVERFRAME DIGITAL", font=fnt("arialbd.ttf", 35), fill=SAGE)
    draw.line((110, 125, W - 110, 125), fill=GOLD, width=3)
    center(draw, (W // 2, 205), title, fnt("georgiab.ttf", 76), INK)
    center(draw, (W // 2, 285), subtitle, fnt("arialbd.ttf", 34), TAUPE)
    return canvas, draw


def save(canvas: Image.Image, name: str) -> None:
    path = OUT / name
    WORK.mkdir(parents=True, exist_ok=True)
    backup = WORK / name
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    canvas.save(path, "JPEG", quality=94, optimize=True, progressive=True, subsampling=0)
    with Image.open(path) as check:
        assert check.size == (W, H) and check.mode == "RGB" and check.format == "JPEG"


def seasonal_breakdown() -> None:
    canvas, draw = base("100 ARTWORKS • EVERY SEASON", "20 ARTWORKS IN EACH OF FIVE COLLECTIONS")
    groups = [
        ("20 VALENTINE'S", [1, 5, 10, 16]),
        ("20 SPRING & EASTER", [21, 26, 34, 39]),
        ("20 SUMMER & PATRIOTIC", [41, 47, 53, 59]),
        ("20 FALL • HALLOWEEN • THANKSGIVING", [61, 68, 74, 79]),
        ("20 WINTER & CHRISTMAS", [81, 86, 92, 98]),
    ]
    y = 350
    for label, numbers in groups:
        draw.rounded_rectangle((90, y, W - 90, y + 285), radius=18, fill=PANEL)
        if label.startswith("20 FALL"):
            draw.text((135, y + 83), "20 FALL • HALLOWEEN",
                      font=fnt("georgiab.ttf", 30), fill=INK)
            draw.text((135, y + 137), "• THANKSGIVING",
                      font=fnt("georgiab.ttf", 30), fill=INK)
        else:
            draw.text((135, y + 113), label, font=fnt("georgiab.ttf", 35), fill=INK)
        for i, number in enumerate(numbers):
            x = 790 + i * 420
            paste_art(canvas, number, (x, y + 28, x + 390, y + 257), border=5)
        y += 305
    save(canvas, "02-seasonal-breakdown.jpg")


def gallery(name: str, title: str, subtitle: str, numbers: list[int]) -> None:
    canvas, draw = base(title, subtitle)
    x0, y0 = 95, 355
    tw, th, gx, gy = 580, 326, 28, 30
    for i, number in enumerate(numbers):
        row, col = divmod(i, 4)
        x, y = x0 + col * (tw + gx), y0 + row * (th + gy)
        paste_art(canvas, number, (x, y, x + tw, y + th), border=6)
    draw.rounded_rectangle((280, 1500, W - 280, 1870), radius=18,
                           fill=PANEL, outline=GOLD, width=3)
    center(draw, (W // 2, 1605), "REPRESENTATIVE ART FROM THE ACTUAL DOWNLOAD",
           fnt("arialbd.ttf", 31), SAGE)
    center(draw, (W // 2, 1715), "100 HIGH-RESOLUTION ARTWORKS",
           fnt("georgiab.ttf", 55), INK)
    center(draw, (W // 2, 1810), "4K UHD  •  16:9 LANDSCAPE  •  DIGITAL DOWNLOAD",
           fnt("arialbd.ttf", 30), TAUPE)
    save(canvas, name)


def whats_included() -> None:
    canvas, draw = base("WHAT YOU RECEIVE", "A COMPLETE, ORGANIZED DIGITAL COLLECTION")
    draw.rounded_rectangle((90, 350, 1340, 1250), radius=20, fill="#D9D0C3")
    paste_art(canvas, 33, (155, 430, 1275, 1060), border=22)
    # Display base beneath the large screen.
    draw.rectangle((590, 1060, 840, 1120), fill=INK)
    draw.rectangle((470, 1120, 960, 1150), fill=INK)
    facts = [
        "100 HIGH-RESOLUTION JPG FILES",
        "3840 × 2160 • 4K UHD",
        "16:9 LANDSCAPE FORMAT",
        "5 ORGANIZED ZIP DOWNLOADS",
        "DIGITAL PRODUCT • NO SHIPPING",
    ]
    for i, text in enumerate(facts):
        y = 420 + i * 155
        draw.ellipse((1470, y - 20, 1520, y + 30), fill=SAGE)
        draw.text((1570, y - 18), text, font=fnt("arialbd.ttf", 33), fill=INK)
    # Five category previews add visible proof of collection breadth.
    for i, number in enumerate([5, 27, 53, 72, 94]):
        x = 100 + i * 500
        paste_art(canvas, number, (x, 1380, x + 465, 1642), border=5)
    center(draw, (W // 2, 1745), "INSTANT DIGITAL DOWNLOAD", fnt("georgiab.ttf", 58), INK)
    center(draw, (W // 2, 1825), "NO PHYSICAL ITEM WILL BE SHIPPED",
           fnt("arialbd.ttf", 30), TAUPE)
    save(canvas, "07-whats-included.jpg")


def how_to_display() -> None:
    canvas, draw = base("HOW TO DISPLAY", "FOUR SIMPLE STEPS")
    steps = [
        ("1", "DOWNLOAD", "Save all five ZIP archives", 12),
        ("2", "UNZIP", "Extract the JPG files", 31),
        ("3", "TRANSFER", "Use a compatible app or USB", 58),
        ("4", "DISPLAY", "Select artwork in Art Mode", 87),
    ]
    for i, (num, title, desc, artwork) in enumerate(steps):
        x = 75 + i * 630
        draw.rounded_rectangle((x, 350, x + 575, 1590), radius=18,
                               fill=PANEL, outline=GOLD, width=4)
        paste_art(canvas, artwork, (x + 28, 390, x + 547, 682), border=5)
        draw.ellipse((x + 215, 750, x + 360, 895), fill=SAGE)
        center(draw, (x + 287, 823), num, fnt("georgiab.ttf", 67), IVORY)
        center(draw, (x + 287, 1010), title, fnt("georgiab.ttf", 47), INK)
        center(draw, (x + 287, 1120), desc, fnt("arial.ttf", 26), TAUPE)
    center(draw, (W // 2, 1735), "DOWNLOAD  •  EXTRACT  •  TRANSFER  •  ENJOY",
           fnt("arialbd.ttf", 43), SAGE)
    center(draw, (W // 2, 1815), "Device features and transfer methods may vary.",
           fnt("arial.ttf", 27), INK)
    save(canvas, "08-how-to-display.jpg")


def quality_compatibility() -> None:
    canvas, draw = base("DESIGNED FOR FRAME TV ART MODE", "PREMIUM 4K QUALITY • 16:9 LANDSCAPE")
    # Large display preview.
    draw.rounded_rectangle((80, 350, 1600, 1260), radius=18, fill="#D9D0C3")
    paste_art(canvas, 88, (155, 420, 1525, 1191), border=24)
    draw.rectangle((690, 1191, 990, 1270), fill=INK)
    draw.rectangle((560, 1270, 1120, 1300), fill=INK)
    # Four additional seasonal examples.
    for i, number in enumerate([9, 37, 54, 76]):
        row, col = divmod(i, 2)
        x, y = 1690 + col * 410, 380 + row * 270
        paste_art(canvas, number, (x, y, x + 380, y + 214), border=5)
    facts = ["100 UNIQUE ARTWORKS", "3840 × 2160 JPG", "INSTANT DOWNLOAD"]
    for i, fact in enumerate(facts):
        draw.rounded_rectangle((1690, 980 + i * 115, 2500, 1065 + i * 115),
                               radius=12, fill=PANEL)
        center(draw, (2095, 1023 + i * 115), fact, fnt("arialbd.ttf", 31), INK)
    draw.rounded_rectangle((220, 1480, W - 220, 1865), radius=18,
                           fill="#FBF8F1", outline=GOLD, width=4)
    center(draw, (W // 2, 1585), "4K UHD  •  16:9  •  3840 × 2160",
           fnt("arialbd.ttf", 37), INK)
    center(draw, (W // 2, 1690), "100 UNIQUE SEASONAL ARTWORKS",
           fnt("georgiab.ttf", 52), INK)
    center(draw, (W // 2, 1785), "INSTANT DIGITAL DOWNLOAD",
           fnt("arialbd.ttf", 31), SAGE)
    save(canvas, "09-quality-compatibility.jpg")


def main() -> None:
    seasonal_breakdown()
    gallery("03-valentine-spring-preview.jpg", "40 ROMANTIC & SPRING ARTWORKS",
            "20 VALENTINE'S • 20 SPRING & EASTER",
            [1, 3, 5, 8, 11, 15, 21, 24, 27, 31, 36, 39])
    gallery("04-summer-patriotic-preview.jpg", "20 SUMMER & PATRIOTIC ARTWORKS",
            "COASTAL • FLORAL • AMERICANA",
            [41, 42, 43, 44, 46, 47, 49, 52, 53, 54, 56, 59])
    gallery("05-fall-halloween-thanksgiving-preview.jpg", "20 AUTUMN ARTWORKS",
            "FALL • HALLOWEEN • THANKSGIVING",
            [61, 62, 64, 66, 68, 69, 71, 72, 74, 76, 78, 80])
    gallery("06-winter-christmas-preview.jpg", "20 WINTER & CHRISTMAS ARTWORKS",
            "SNOWY VILLAGES • EVERGREENS • HOLIDAY STILL LIFES",
            [81, 82, 83, 84, 85, 86, 87, 88, 90, 92, 96, 98])
    whats_included()
    how_to_display()
    quality_compatibility()
    print("Rebuilt eight supporting images with expanded exact-art previews.")


if __name__ == "__main__":
    main()
