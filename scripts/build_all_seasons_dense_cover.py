"""Build a dense, premium All-Seasons Etsy cover from exact customer artwork."""

from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "All-Seasons-100-Collection"
ART = PRODUCT / "customer-downloads" / "_work" / "normalized-jpg"
OUT = PRODUCT / "cover-v2-review" / "01-main-cover.jpg"
WORK = PRODUCT / "cover-v2-review" / "_work"

W, H = 2600, 2000
COLS, ROWS = 6, 8
MARGIN_X, MARGIN_Y = 22, 20
GAP_X, GAP_Y = 14, 14
CELL_W = (W - 2 * MARGIN_X - (COLS - 1) * GAP_X) // COLS
CELL_H = round(CELL_W * 9 / 16)

IVORY = "#F5F1E8"
GOLD = "#B99A5D"
INK = "#171715"
TAUPE = "#887565"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
             fnt: ImageFont.FreeTypeFont, fill: str) -> None:
    box = draw.textbbox((0, 0), text, font=fnt)
    x = xy[0] - (box[2] - box[0]) / 2
    y = xy[1] - (box[3] - box[1]) / 2 - box[1]
    draw.text((x, y), text, font=fnt, fill=fill)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        backup = WORK / "01-main-cover-before-dense-collage.jpg"
        if not backup.exists():
            shutil.copy2(OUT, backup)

    # Forty-eight evenly distributed, unique customer artworks span all seasons.
    numbers = [round(1 + i * 99 / 47) for i in range(48)]
    paths = [ART / f"All-Seasons-{n:03d}.jpg" for n in numbers]
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing customer artworks: {missing}")

    canvas = Image.new("RGB", (W, H), IVORY)

    # Dense edge-to-edge gallery grid with restrained shadows and gold frames.
    for i, path in enumerate(paths):
        row, col = divmod(i, COLS)
        x = MARGIN_X + col * (CELL_W + GAP_X)
        y = MARGIN_Y + row * (CELL_H + GAP_Y)
        with Image.open(path) as source:
            tile = ImageOps.fit(source.convert("RGB"), (CELL_W - 10, CELL_H - 10),
                                method=Image.Resampling.LANCZOS)
        shadow = Image.new("RGBA", (CELL_W + 12, CELL_H + 12), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((7, 8, CELL_W + 5, CELL_H + 6), radius=3,
                             fill=(38, 31, 25, 80))
        shadow = shadow.filter(ImageFilter.GaussianBlur(5))
        canvas.paste(shadow, (x - 6, y - 5), shadow)
        frame = Image.new("RGB", (CELL_W, CELL_H), GOLD)
        frame.paste(tile, (5, 5))
        canvas.paste(frame, (x, y))

    # Central editorial panel overlays the grid while leaving a broad artwork border.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    panel = (225, 635, W - 225, 1370)
    shadow_box = (panel[0] + 12, panel[1] + 18, panel[2] + 12, panel[3] + 18)
    od.rounded_rectangle(shadow_box, radius=18, fill=(20, 17, 14, 105))
    overlay = overlay.filter(ImageFilter.GaussianBlur(13))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    panel_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel_layer)
    pd.rounded_rectangle(panel, radius=14, fill=(249, 247, 241, 250),
                         outline=(185, 154, 93, 255), width=5)
    canvas = Image.alpha_composite(canvas, panel_layer)
    draw = ImageDraw.Draw(canvas)

    centered(draw, (W // 2, 712), "EVERFRAME DIGITAL", font("arialbd.ttf", 42), TAUPE)

    # Mixed serif/sans hierarchy echoes editorial collection covers without copying.
    num_font = font("georgiab.ttf", 220)
    season_font = font("arialbd.ttf", 112)
    num_box = draw.textbbox((0, 0), "100", font=num_font)
    season_box = draw.textbbox((0, 0), "ALL-SEASONS", font=season_font)
    total = (num_box[2] - num_box[0]) + 50 + (season_box[2] - season_box[0])
    start = (W - total) / 2
    draw.text((start, 775), "100", font=num_font, fill=INK)
    draw.text((start + (num_box[2] - num_box[0]) + 50, 868),
              "ALL-SEASONS", font=season_font, fill=INK)

    centered(draw, (W // 2, 1115), "FRAME TV ART COLLECTION",
             font("georgiab.ttf", 82), INK)
    draw.rounded_rectangle((690, 1212, W - 690, 1218), radius=3, fill=GOLD)
    centered(draw, (W // 2, 1280), "4K UHD  •  16:9  •  INSTANT DOWNLOAD",
             font("arialbd.ttf", 44), TAUPE)

    canvas.convert("RGB").save(OUT, "JPEG", quality=94, optimize=True,
                               progressive=True, subsampling=0)
    with Image.open(OUT) as check:
        if check.size != (W, H) or check.mode != "RGB" or check.format != "JPEG":
            raise RuntimeError("Final cover validation failed")

    report = WORK / "dense-cover-source-art.txt"
    report.write_text(
        "Dense cover uses these exact normalized customer files:\n"
        + "\n".join(p.name for p in paths)
        + "\n",
        encoding="utf-8",
    )
    print(OUT)
    print(f"customer_artworks={len(paths)} dimensions={W}x{H}")


if __name__ == "__main__":
    main()
