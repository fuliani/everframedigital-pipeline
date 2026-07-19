"""
Composite real product art onto a photorealistic TV-in-room mockup, then
build explainer marketing slides (product details, guarantee, how-to-download,
collection specs, compatibility, premium-quality zoom) in an editorial /
agency-brochure type system - always showing one of THAT bundle's own actual
images on the screen (personalized), in the EverframeDigital color palette.

Template v3 is a flux-pro-ultra portrait room photo with generous headroom
above and below the TV, chosen specifically so the photo can be shown in full
(never cropping into the TV or screen) when placed in a portrait-shaped panel.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "scratch_browser" / "tv_mockup_template3_final.png"
SCREEN_BOX = (293, 741, 1437, 1415)  # left, top, right, bottom - measured on template3 (flux-pro-ultra)

CANVAS_SIZE = (2600, 2000)
BG_COLOR = (241, 238, 231)
TEXT_COLOR = (32, 30, 27)
MUTED = (128, 120, 108)
ACCENT = (94, 108, 74)        # deep olive - kickers, numerals, small marks
GOLD = (163, 132, 82)         # muted bronze - large editorial numerals
RULE = (211, 204, 190)        # hairline dividers

FONT_DIR = Path("C:/Windows/Fonts")
F_HEADLINE = FONT_DIR / "georgiab.ttf"      # serif bold - display headlines
F_HEADLINE_I = FONT_DIR / "georgiaz.ttf"    # serif bold italic - emphasis
F_NUMERAL = FONT_DIR / "georgiai.ttf"       # serif italic - editorial numerals
F_KICKER = FONT_DIR / "segoeuisl.ttf"       # sans semilight - tracked labels
F_BODY = FONT_DIR / "segoeui.ttf"           # sans regular - body copy
F_BODY_LIGHT = FONT_DIR / "segoeuil.ttf"    # sans light - secondary copy
F_BODY_BOLD = FONT_DIR / "segoeuib.ttf"     # sans bold - spec titles


def font(path, size):
    return ImageFont.truetype(str(path), size)


def composite_art_on_tv(art_path: Path) -> Image.Image:
    template = Image.open(TEMPLATE_PATH).convert("RGB")
    art = Image.open(art_path).convert("RGB")

    x0, y0, x1, y1 = SCREEN_BOX
    box_w, box_h = x1 - x0, y1 - y0
    art_resized = art.resize((box_w, box_h), Image.LANCZOS)
    template.paste(art_resized, (x0, y0))
    return template


def paste_photo_panel(canvas: Image.Image, photo: Image.Image, x: int, y: int, panel_w: int, panel_h: int) -> None:
    """Cover-fill a panel with the room photo, cropped centered on the TV screen
    (not the raw image center) so the screen is never sliced off."""
    scr_x0, scr_y0, scr_x1, scr_y1 = SCREEN_BOX
    screen_cx = (scr_x0 + scr_x1) / 2
    screen_cy = (scr_y0 + scr_y1) / 2

    ratio = max(panel_w / photo.width, panel_h / photo.height)
    new_w, new_h = int(photo.width * ratio), int(photo.height * ratio)
    resized = photo.resize((new_w, new_h), Image.LANCZOS)

    cx, cy = screen_cx * ratio, screen_cy * ratio
    crop_x = min(max(0, int(cx - panel_w / 2)), new_w - panel_w)
    crop_y = min(max(0, int(cy - panel_h / 2)), new_h - panel_h)
    cropped = resized.crop((crop_x, crop_y, crop_x + panel_w, crop_y + panel_h))
    canvas.paste(cropped, (x, y))


# ---------------------------------------------------------------- type tools

def tracked_width(draw, text, text_font, tracking):
    return sum(draw.textlength(ch, font=text_font) + tracking for ch in text) - tracking


def draw_tracked(draw, xy, text, text_font, fill, tracking=6):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=text_font, fill=fill)
        x += draw.textlength(ch, font=text_font) + tracking
    return x


def draw_kicker(draw, x, y, text="EVERFRAME DIGITAL"):
    draw_tracked(draw, (x, y), text, font(F_KICKER, 34), ACCENT, tracking=6)
    return y + 66


def hline(draw, x0, x1, y, fill=RULE, width=1):
    draw.line((x0, y, x1, y), fill=fill, width=width)


def draw_wrapped(draw, xy, text, text_font, fill, max_width, line_spacing=1.3):
    x, y = xy
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=text_font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    line_h = int(text_font.size * line_spacing)
    for line in lines:
        draw.text((x, y), line, font=text_font, fill=fill)
        y += line_h
    return y


def wrap_lines(draw, text, text_font, max_width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=text_font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_editorial_step(draw, x, y, num, text, col_w, rule_right, num_col_w=150):
    """Large thin italic-serif numeral in a left gutter, body text in a second
    column, hairline rule beneath - an editorial numbered-list pattern instead
    of a filled circle badge."""
    num_font = font(F_NUMERAL, 72)
    body_font = font(F_BODY, 40)

    draw.text((x, y), f"{num:02d}", font=num_font, fill=GOLD)

    text_x = x + num_col_w
    text_w = col_w - num_col_w
    lines = wrap_lines(draw, text, body_font, text_w)
    ty = y + 10
    for line in lines:
        draw.text((text_x, ty), line, font=body_font, fill=TEXT_COLOR)
        ty += int(body_font.size * 1.32)

    block_h = max(ty - y, 80)
    rule_y = y + block_h + 26
    hline(draw, x, rule_right, rule_y)
    return rule_y + 46


def slide_header(draw, right_x, right_w, headline, headline_size=110, headline_font=None):
    y = draw_kicker(draw, right_x, 110)
    y += 26
    hf = headline_font or font(F_HEADLINE, headline_size)
    lines = wrap_lines(draw, headline, hf, right_w)
    for line in lines:
        draw.text((right_x, y), line, font=hf, fill=TEXT_COLOR)
        y += int(hf.size * 1.08)
    y += 28
    hline(draw, right_x, right_x + right_w, y, width=2)
    return y + 60


def new_canvas_with_photo(art_path: Path):
    canvas = Image.new("RGB", CANVAS_SIZE, BG_COLOR)
    mockup = composite_art_on_tv(art_path)
    paste_photo_panel(canvas, mockup, 0, 0, CANVAS_SIZE[0] // 2, CANVAS_SIZE[1])
    return canvas


# ---------------------------------------------------------------- slides

def build_product_details_slide(art_path: Path, piece_count: int, num_zips: int, out_path: Path):
    canvas = new_canvas_with_photo(art_path)
    draw = ImageDraw.Draw(canvas)
    right_x = CANVAS_SIZE[0] // 2 + 110
    right_w = CANVAS_SIZE[0] - right_x - 110

    y = slide_header(draw, right_x, right_w, "Product Details")

    steps = [
        f"Purchase your {piece_count}-piece Frame TV Art collection and receive instant digital files.",
        f"Download all {num_zips} ZIP file(s) from your Etsy purchases page.",
        "Unzip to access your high-resolution JPG images.",
        "Transfer to your Samsung Frame TV via USB or the free SmartThings app.",
        "Select Art Mode, choose your artwork, and enjoy — with or without a mat.",
    ]
    for i, step in enumerate(steps, 1):
        y = draw_editorial_step(draw, right_x, y, i, step, right_w, right_x + right_w)

    canvas.save(out_path, quality=95)
    print(f"Saved: {out_path}")


def build_how_to_download_slide(art_path: Path, out_path: Path):
    canvas = new_canvas_with_photo(art_path)
    draw = ImageDraw.Draw(canvas)
    right_x = CANVAS_SIZE[0] // 2 + 110
    right_w = CANVAS_SIZE[0] - right_x - 110

    y = slide_header(draw, right_x, right_w, "How to Download", headline_size=98)

    steps = [
        "Log in to your Etsy account.",
        "Click “You” (top right), then “Purchases and reviews.”",
        "Find your order and click “Download Files.”",
        "Your ZIP file(s) will save to your Downloads folder.",
        "Unzip and transfer the images to your Frame TV.",
    ]
    for i, step in enumerate(steps, 1):
        y = draw_editorial_step(draw, right_x, y, i, step, right_w, right_x + right_w)

    canvas.save(out_path, quality=95)
    print(f"Saved: {out_path}")


def build_guarantee_slide(art_path: Path, out_path: Path):
    canvas = new_canvas_with_photo(art_path)
    draw = ImageDraw.Draw(canvas)
    right_x = CANVAS_SIZE[0] // 2 + 110
    right_w = CANVAS_SIZE[0] - right_x - 110

    y = draw_kicker(draw, right_x, 130)
    y += 38

    # oversized numeral "30" beside a stacked headline - graphic focal point
    num_font = font(F_NUMERAL, 260)
    draw.text((right_x, y), "30", font=num_font, fill=GOLD)
    num_w = draw.textlength("30", font=num_font)

    head_font = font(F_HEADLINE, 68)
    hx = right_x + num_w + 48
    hy = y + 30
    for line in ["DAY MONEY-BACK", "GUARANTEE"]:
        draw.text((hx, hy), line, font=head_font, fill=TEXT_COLOR)
        hy += int(head_font.size * 1.12)

    y += 292
    hline(draw, right_x, right_x + right_w, y, width=2)
    y += 64

    body = "Not fully satisfied with your purchase? Message us within 30 days for a full, no-hassle refund. We stand behind the quality of every piece in this collection."
    y = draw_wrapped(draw, (right_x, y), body, font(F_BODY, 42), MUTED, int(right_w * 0.9), line_spacing=1.45)

    y += 76
    draw_tracked(draw, (right_x, y), "QUESTIONS BEFORE YOU BUY?", font(F_KICKER, 30), ACCENT, tracking=4)
    y += 60
    draw_wrapped(draw, (right_x, y), "Just send us a message — we're happy to help.", font(F_BODY_LIGHT, 40), TEXT_COLOR, right_w)

    canvas.save(out_path, quality=95)
    print(f"Saved: {out_path}")


def build_collection_specs_slide(art_path: Path, piece_count: int, style_name: str, out_path: Path):
    canvas = new_canvas_with_photo(art_path)
    draw = ImageDraw.Draw(canvas)
    right_x = CANVAS_SIZE[0] // 2 + 110
    right_w = CANVAS_SIZE[0] - right_x - 110

    y = slide_header(draw, right_x, right_w, "Collection Specs")

    specs = [
        (f"{piece_count} JPG Artworks", f"All in the {style_name} style"),
        ("3840 × 2160 Pixels", "True 4K UHD resolution"),
        ("16:9 Aspect Ratio", "Fills the Frame TV screen edge-to-edge"),
        ("Digital Download Only", "No physical item will be shipped"),
        ("Personal Use License", "Not for resale or redistribution"),
    ]
    title_font = font(F_BODY_BOLD, 46)
    sub_font = font(F_BODY_LIGHT, 36)
    num_font = font(F_NUMERAL, 44)
    for i, (title, subtitle) in enumerate(specs, 1):
        draw.text((right_x, y), f"{i:02d}", font=num_font, fill=GOLD)
        draw.text((right_x + 96, y - 4), title, font=title_font, fill=TEXT_COLOR)
        draw.text((right_x + 96, y + 52), subtitle, font=sub_font, fill=MUTED)
        row_bottom = y + 118
        hline(draw, right_x, right_x + right_w, row_bottom)
        y = row_bottom + 44

    canvas.save(out_path, quality=95)
    print(f"Saved: {out_path}")


def build_compatibility_slide(art_path: Path, out_path: Path):
    """Honest compatibility slide - our files are 16:9 4K JPGs, so they work on
    any 16:9 digital frame/display, not just Samsung. No unverified brand claims."""
    canvas = new_canvas_with_photo(art_path)
    draw = ImageDraw.Draw(canvas)
    right_x = CANVAS_SIZE[0] // 2 + 110
    right_w = CANVAS_SIZE[0] - right_x - 110

    y = draw_kicker(draw, right_x, 140)
    y += 46

    head_font = font(F_HEADLINE, 80)
    for line, col in [("Built for Samsung", TEXT_COLOR), ("Frame TV.", TEXT_COLOR)]:
        draw.text((right_x, y), line, font=head_font, fill=col)
        y += int(head_font.size * 1.1)
    italic_font = font(F_HEADLINE_I, 80)
    draw.text((right_x, y), "Works on any 16:9 display.", font=italic_font, fill=ACCENT)
    y += int(italic_font.size * 1.25)

    hline(draw, right_x, right_x + right_w, y, width=2)
    y += 62

    body = "Every file is a standard 3840 × 2160 JPG (16:9). It's sized and tested for Samsung's Art Mode, and also works as wallpaper or screensaver art on any other 16:9 TV, monitor, or digital photo frame."
    draw_wrapped(draw, (right_x, y), body, font(F_BODY, 44), MUTED, int(right_w * 0.9), line_spacing=1.5)

    canvas.save(out_path, quality=95)
    print(f"Saved: {out_path}")


def build_premium_quality_slide(art_path: Path, out_path: Path):
    """Top: full uncropped room photo with a refined tracked wordmark on a
    soft gradient scrim. Bottom: a tight zoomed detail crop of the actual art."""
    canvas = Image.new("RGB", CANVAS_SIZE, (18, 20, 16))
    mockup = composite_art_on_tv(art_path)

    top_h = int(CANVAS_SIZE[1] * 0.62)
    paste_photo_panel(canvas, mockup, 0, 0, CANVAS_SIZE[0], top_h)

    # soft dark scrim behind the wordmark for legibility on any photo
    scrim = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(scrim)
    for i in range(260):
        alpha = int(120 * (1 - i / 260))
        sdraw.line((0, i, CANVAS_SIZE[0], i), fill=(10, 12, 8, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), scrim).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    draw_tracked(draw, (90, 84), "EVERFRAME DIGITAL", font(F_KICKER, 32), (222, 214, 196), tracking=6)
    draw_tracked(draw, (90, 138), "PREMIUM QUALITY", font(F_HEADLINE, 90), (255, 255, 255), tracking=5)
    hline(draw, 90, 640, 254, fill=(210, 190, 150), width=2)

    art = Image.open(art_path).convert("RGB")
    zoom_w, zoom_h = art.width // 3, art.height // 3
    left = (art.width - zoom_w) // 2
    upper = (art.height - zoom_h) // 2
    detail = art.crop((left, upper, left + zoom_w, upper + zoom_h))
    detail = detail.resize((CANVAS_SIZE[0], CANVAS_SIZE[1] - top_h), Image.LANCZOS)
    canvas.paste(detail, (0, top_h))

    draw = ImageDraw.Draw(canvas)
    draw_tracked(draw, (90, top_h + 44), "EVERY DETAIL, TRUE 4K", font(F_KICKER, 30), (255, 255, 255), tracking=5)

    canvas.save(out_path, quality=95)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    import sys
    art = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "output" / "falai" / "coastal-landscape" / "coastal-landscape-a-lighthouse-in-fog-20260717t000000z.jpg"
    out_dir = ROOT / "scratch_browser" / "mockup_prototype_v4"
    build_product_details_slide(art, 99, 2, out_dir / "01-product-details.jpg")
    build_guarantee_slide(art, out_dir / "02-guarantee.jpg")
    build_collection_specs_slide(art, 99, "Coastal Landscape", out_dir / "03-collection-specs.jpg")
    build_how_to_download_slide(art, out_dir / "04-how-to-download.jpg")
    build_compatibility_slide(art, out_dir / "05-compatibility.jpg")
    build_premium_quality_slide(art, out_dir / "06-premium-quality.jpg")
