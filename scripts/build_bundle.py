"""
Package generated images into a downloadable ZIP bundle and generate
Etsy listing copy for the bundle as a single "Set of N" listing.

Usage:
    python scripts/build_bundle.py --name coastal-neutral-starter-bundle \
        --styles coastal-landscape neutral-botanical --price 9.99
    python scripts/build_bundle.py --name full-collection --styles all --price 14.99
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

# Etsy digital file limits: 20MB per file, max 5 files per listing.
ETSY_MAX_FILE_BYTES = 19 * 1024 * 1024  # leave headroom under the 20MB hard cap
ETSY_MAX_FILES = 5
DELIVERY_JPEG_QUALITY = 78  # re-encoded for delivery; source files are untouched

SYSTEM_PROMPT = """You are an expert Etsy SEO copywriter specializing in Samsung Frame TV Art \
digital download BUNDLES (a set of many images sold as one listing, delivered as a ZIP file).

Write listing copy following Etsy's best practices:
- Title: max 140 characters, front-load high-value keywords, MUST mention the piece count \
(e.g. "Set of 42"), must mention "Frame TV Art" or "Samsung Frame TV".
- Tags: exactly 13 tags, each max 20 characters, no repeated words across tags.
- Description: 200-350 words. Open strong (shown in search snippets). Emphasize the VARIETY \
and VALUE of getting many pieces in one purchase, list the included styles/themes, explain the \
file format (ZIP of high-res JPGs, 4K 3840x2160, 16:9), how to use on a Samsung Frame TV, and a \
personal-use license note. Do NOT claim "lifetime access" or promise future updates unless told \
to — this is a fixed, one-time set. Be honest about the exact count, don't inflate.

Respond ONLY with valid JSON: {"title": "...", "tags": ["...", ...], "description": "..."}"""


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_images(style_ids: list[str], config: dict) -> list[dict]:
    all_style_ids = [s["id"] for s in config["styles"]]
    targets = all_style_ids if "all" in style_ids else style_ids
    images = []
    for style_id in targets:
        manifest_path = OUTPUT_DIR / "gemini" / style_id / "manifest.csv"
        if not manifest_path.exists():
            continue
        with open(manifest_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                filepath = OUTPUT_DIR / "gemini" / style_id / row["filename"]
                if filepath.exists():
                    images.append({"path": filepath, "style_id": style_id, "style_name": row["style_name"]})
    return images


def compress_for_delivery(path: Path) -> bytes:
    img = Image.open(path).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=DELIVERY_JPEG_QUALITY, optimize=True)
    return out.getvalue()


def build_zip_parts(images: list[dict], base_zip_path: Path) -> list[Path]:
    """Split images across multiple ZIP parts, each under Etsy's 20MB per-file limit,
    up to Etsy's 5-files-per-listing max. Raises if that's not enough room."""
    base_zip_path.parent.mkdir(parents=True, exist_ok=True)
    stem = base_zip_path.stem

    parts: list[Path] = []
    part_num = 1
    current_zip = None
    current_size = 0

    def open_new_part():
        nonlocal current_zip, current_size, part_num
        if current_zip is not None:
            current_zip.close()
        if part_num > ETSY_MAX_FILES:
            raise SystemExit(
                f"Bundle needs more than {ETSY_MAX_FILES} ZIP parts even after compression — "
                f"reduce image count or lower DELIVERY_JPEG_QUALITY."
            )
        part_path = base_zip_path.with_name(f"{stem}-part{part_num}.zip")
        parts.append(part_path)
        current_zip = zipfile.ZipFile(part_path, "w", zipfile.ZIP_DEFLATED)
        current_size = 0
        part_num += 1
        return current_zip

    current_zip = open_new_part()

    for img in images:
        data = compress_for_delivery(img["path"])
        if current_size + len(data) > ETSY_MAX_FILE_BYTES and current_size > 0:
            current_zip = open_new_part()
        arcname = img["path"].stem + ".jpg"
        current_zip.writestr(arcname, data)
        current_size += len(data)

    current_zip.close()
    return parts


def build_bundle_prompt(images: list[dict], keyword_data: dict) -> str:
    style_counts = {}
    for img in images:
        style_counts[img["style_name"]] = style_counts.get(img["style_name"], 0) + 1
    styles_summary = "\n".join(f"- {name}: {count} pieces" for name, count in style_counts.items())

    baseline = keyword_data.get("baseline", {})
    kw_lines = "\n".join(
        f"- \"{term}\": avg searches {data.get('avg_searches', 'unknown')}, "
        f"competition {data.get('competition', 'unknown')} listings"
        for term, data in baseline.items()
    )

    return f"""Bundle details:
- Total pieces: {len(images)}
- Styles/themes included:
{styles_summary}

Real Etsy keyword research for this niche (use naturally where relevant):
{kw_lines}

Generate the Etsy bundle listing copy now. Remember: exact count is {len(images)}, be honest \
about it in both title and description."""


def generate_bundle_listing(client: genai.Client, images: list[dict], keyword_data: dict) -> dict:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{SYSTEM_PROMPT}\n\n{build_bundle_prompt(images, keyword_data)}",
        config={"response_mime_type": "application/json"},
    )
    return json.loads(response.text)


def save_bundle_listing(name: str, listing: dict, price: float, image_count: int, zip_parts: list[Path]) -> None:
    txt_path = BUNDLES_DIR / f"{name}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"BUNDLE: {name} ({image_count} images, suggested price ${price:.2f})\n")
        f.write(f"Digital files to upload ({len(zip_parts)} of max 5, each under 20MB):\n")
        for part in zip_parts:
            size_mb = part.stat().st_size / (1024 * 1024)
            f.write(f"  - {part} ({size_mb:.1f} MB)\n")
        f.write("\n")
        f.write(f"TITLE ({len(listing['title'])} chars):\n{listing['title']}\n\n")
        f.write(f"TAGS ({len(listing['tags'])}):\n{', '.join(listing['tags'])}\n\n")
        f.write(f"DESCRIPTION:\n{listing['description']}\n")
    print(f"  -> {txt_path}")

    json_path = BUNDLES_DIR / f"{name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {**listing, "price": price, "image_count": image_count, "zip_parts": [str(p) for p in zip_parts]},
            f,
            indent=2,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="Bundle name (used for filenames)")
    parser.add_argument("--styles", nargs="+", required=True, help="Style ids to include, or 'all'")
    parser.add_argument("--price", type=float, required=True, help="Suggested bundle price in USD")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = load_json(CONFIG_PATH)
    keyword_data = load_json(KEYWORD_DATA_PATH)

    images = collect_images(args.styles, config)
    if not images:
        raise SystemExit("No images found for the given styles. Generate images first.")

    print(f"Bundling {len(images)} images from styles: {', '.join(sorted(set(i['style_id'] for i in images)))}")

    zip_path = BUNDLES_DIR / f"{args.name}.zip"
    zip_parts = build_zip_parts(images, zip_path)
    for part in zip_parts:
        size_mb = part.stat().st_size / (1024 * 1024)
        print(f"Created: {part} ({size_mb:.1f} MB)")

    client = genai.Client()
    listing = generate_bundle_listing(client, images, keyword_data)
    save_bundle_listing(args.name, listing, args.price, len(images), zip_parts)

    print(f"\nDone. Bundle ready in: {BUNDLES_DIR}")


if __name__ == "__main__":
    main()
