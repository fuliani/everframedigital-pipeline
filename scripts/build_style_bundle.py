"""
Build a single-style bundle: packages one style's generated images into a
ZIP-based Etsy digital listing (its own folder under output/bundles/<style>/)
plus generates listing copy for it.

Usage:
    python scripts/build_style_bundle.py --style coastal-landscape --provider falai --price 8.99
"""

import argparse
import csv
import io
import json
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "styles.json"
KEYWORD_DATA_PATH = ROOT / "config" / "keyword_data.json"
OUTPUT_DIR = ROOT / "output"
BUNDLES_DIR = OUTPUT_DIR / "bundles"

ETSY_MAX_FILE_BYTES = 19 * 1024 * 1024
ETSY_MAX_FILES = 5
DELIVERY_JPEG_QUALITY = 78

SYSTEM_PROMPT = """You are an expert Etsy SEO copywriter specializing in Samsung Frame TV Art \
digital download BUNDLES (a set of images, all one cohesive style, sold as one listing, \
delivered as ZIP file(s)).

Write listing copy following Etsy's best practices:
- Title: HARD LIMIT 140 characters total, no exceptions — count carefully and stay at or under \
135 to be safe. Front-load high-value keywords, MUST mention the piece count (e.g. "Set of 28"), \
must mention "Frame TV Art" or "Samsung Frame TV", and should name the specific style/aesthetic \
(e.g. coastal, botanical, abstract) since this bundle is a single cohesive theme, not a mixed \
variety pack. If you can't fit everything under 135 characters, cut words — never exceed the limit.
- Tags: exactly 13 tags, each max 20 characters, no repeated words across tags.
- Description: 200-350 words. Open strong (shown in search snippets), emphasizing the specific \
style/aesthetic and the value of getting many pieces in one cohesive purchase. Explain the file \
format (ZIP of high-res JPGs, 4K 3840x2160, 16:9), how to use on a Samsung Frame TV, and a \
personal-use license note. Do NOT mention or imply any refund or money-back guarantee — as an \
instant digital download, this purchase is non-refundable and all sales are final; state that \
plainly instead. Do NOT claim "lifetime access" or promise future updates. Be honest about \
the exact count, don't inflate.

Respond ONLY with valid JSON: {"title": "...", "tags": ["...", ...], "description": "..."}"""


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_style(config: dict, style_id: str) -> dict:
    for s in config["styles"]:
        if s["id"] == style_id:
            return s
    raise SystemExit(f"Style '{style_id}' not found")


def collect_images(style_id: str, provider: str, count: int | None) -> list[Path]:
    manifest_path = OUTPUT_DIR / provider / style_id / "manifest.csv"
    if not manifest_path.exists():
        raise SystemExit(f"No manifest at {manifest_path} — generate images first.")
    paths = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            p = OUTPUT_DIR / provider / style_id / row["filename"]
            if p.exists():
                paths.append(p)
    if count:
        paths = paths[:count]
    return paths


def compress_for_delivery(path: Path) -> bytes:
    img = Image.open(path).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=DELIVERY_JPEG_QUALITY, optimize=True)
    return out.getvalue()


def build_zip_parts(images: list[Path], out_dir: Path, style_id: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    part_num = 1
    current_zip = None
    current_size = 0

    def open_new_part():
        nonlocal current_zip, current_size, part_num
        if current_zip is not None:
            current_zip.close()
        if part_num > ETSY_MAX_FILES:
            raise SystemExit(f"Bundle needs more than {ETSY_MAX_FILES} ZIP parts — reduce image count.")
        part_path = out_dir / f"{style_id}-bundle-part{part_num}.zip"
        parts.append(part_path)
        current_zip = zipfile.ZipFile(part_path, "w", zipfile.ZIP_DEFLATED)
        current_size = 0
        part_num += 1
        return current_zip

    current_zip = open_new_part()
    for img_path in images:
        data = compress_for_delivery(img_path)
        if current_size + len(data) > ETSY_MAX_FILE_BYTES and current_size > 0:
            current_zip = open_new_part()
        current_zip.writestr(img_path.stem + ".jpg", data)
        current_size += len(data)
    current_zip.close()
    return parts


def build_prompt(style: dict, count: int, keyword_data: dict) -> str:
    style_kw = keyword_data.get("styles", {}).get(style["id"], {})
    baseline = keyword_data.get("baseline", {})
    combined = {**baseline, **style_kw}
    kw_lines = "\n".join(
        f"- \"{term}\": avg searches {data.get('avg_searches', 'unknown')}, "
        f"competition {data.get('competition', 'unknown')} listings"
        for term, data in combined.items()
    )
    return f"""Bundle details:
- Style: {style['name']}
- Style description: {style['prompt_template']}
- Total pieces: {count} (all in this one style)

Real Etsy keyword research for this niche (use naturally where relevant):
{kw_lines}

Generate the Etsy bundle listing copy now. Exact count is {count}, be honest about it."""


def generate_listing(client: genai.Client, style: dict, count: int, keyword_data: dict) -> dict:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{SYSTEM_PROMPT}\n\n{build_prompt(style, count, keyword_data)}",
        config={"response_mime_type": "application/json"},
    )
    return json.loads(response.text)


def save_listing(out_dir: Path, style_id: str, listing: dict, price: float, count: int, zip_parts: list[Path]) -> None:
    txt_path = out_dir / f"{style_id}-listing.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"BUNDLE: {style_id} ({count} images, suggested price ${price:.2f})\n")
        f.write(f"Digital files to upload ({len(zip_parts)} of max 5, each under 20MB):\n")
        for part in zip_parts:
            size_mb = part.stat().st_size / (1024 * 1024)
            f.write(f"  - {part} ({size_mb:.1f} MB)\n")
        f.write("\n")
        f.write(f"TITLE ({len(listing['title'])} chars):\n{listing['title']}\n\n")
        f.write(f"TAGS ({len(listing['tags'])}):\n{', '.join(listing['tags'])}\n\n")
        f.write(f"DESCRIPTION:\n{listing['description']}\n")
    print(f"  -> {txt_path}")

    json_path = out_dir / f"{style_id}-listing.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {**listing, "price": price, "image_count": count, "zip_parts": [str(p) for p in zip_parts]}, f, indent=2
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--style", required=True)
    parser.add_argument("--provider", default="falai")
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--count", type=int, default=None)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = load_json(CONFIG_PATH)
    keyword_data = load_json(KEYWORD_DATA_PATH)
    style = get_style(config, args.style)

    images = collect_images(args.style, args.provider, args.count)
    if not images:
        raise SystemExit(f"No images found for style '{args.style}' under provider '{args.provider}'.")

    out_dir = BUNDLES_DIR / args.style
    print(f"Building bundle for '{style['name']}' with {len(images)} images...")

    zip_parts = build_zip_parts(images, out_dir, args.style)
    for part in zip_parts:
        print(f"Created: {part} ({part.stat().st_size / 1024 / 1024:.1f} MB)")

    client = genai.Client()
    listing = generate_listing(client, style, len(images), keyword_data)
    save_listing(out_dir, args.style, listing, args.price, len(images), zip_parts)

    print(f"\nDone. Bundle folder: {out_dir}")


if __name__ == "__main__":
    main()
