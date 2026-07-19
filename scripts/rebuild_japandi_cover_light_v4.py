"""Create a lighter V4 cover while preserving the approved V3 layout."""

from pathlib import Path

from PIL import Image, ImageDraw

from scripts.rebuild_japandi_listing_images_v3 import (
    ART_DIR,
    GOLD,
    INK,
    OLIVE,
    PAPER,
    REPO,
    W,
    H,
    art_tile,
    centered,
    font,
    save as save_v3,
    tracking,
)


PRODUCT = REPO / "EverframeDigital" / "Products" / "Japandi-Minimalist"
OUT = PRODUCT / "cover-v4-review"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    arts = {}
    for number in range(1, 101):
        path = ART_DIR / f"Japandi-Minimalist-{number:03d}.jpg"
        image = Image.open(path).convert("RGB")
        if image.size != (3840, 2160):
            raise RuntimeError(f"Invalid customer artwork: {path.name}")
        arts[number] = image

    canvas = Image.new("RGB", (W, H), PAPER)
    ids = [
        1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23,
        25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47,
        54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76,
        78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100,
    ]
    for start_y, offset in [(28, 0), (1180, 24)]:
        for row in range(4):
            for column in range(6):
                art_tile(
                    canvas,
                    arts[ids[offset + row * 6 + column]],
                    (55 + column * 421, start_y + row * 204, 390, 219),
                    border=3,
                    shadow=False,
                )

    draw = ImageDraw.Draw(canvas)
    # Lighter warm-linen center panel with dark typography for thumbnail clarity.
    draw.rounded_rectangle(
        (155, 830, 2445, 1160),
        radius=24,
        fill="#E7DDD0",
        outline=GOLD,
        width=6,
    )
    draw.text((240, 868), "100", font=font(156, serif=True, bold=True), fill=INK)
    draw.line((590, 875, 590, 1112), fill=GOLD, width=3)
    tracking(draw, (1480, 872), "JAPANDI MINIMALIST", font(45, serif=True, bold=True), INK, 5)
    tracking(draw, (1480, 957), "FRAME TV ART COLLECTION", font(28, bold=True), "#665D53", 4)
    draw.rounded_rectangle((785, 1042, 2175, 1110), radius=30, fill=OLIVE)
    tracking(
        draw,
        (1480, 1053),
        "4K UHD  •  16:9  •  INSTANT DOWNLOAD",
        font(23, bold=True),
        "#FFFDF8",
        2,
    )

    # Reuse the audited encoder without changing any V3 files.
    import scripts.rebuild_japandi_listing_images_v3 as v3

    previous_out = v3.OUT
    try:
        v3.OUT = OUT
        path = save_v3(canvas, "01-main-cover.jpg")
    finally:
        v3.OUT = previous_out

    for image in arts.values():
        image.close()
    print(path)


if __name__ == "__main__":
    main()
