"""
One-off bundle builder for Vintage-Scripture-Paintings, reusing
build_style_bundle.py's ZIP-packaging and listing-generation logic but
sourcing images directly from the verse-overlaid folder (which has its own
naming/verse-mapping, not the standard manifest.csv format).

Usage:
    python scripts/build_scripture_bundle.py --price 8.99
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_style_bundle as bsb

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "output" / "falai-hq" / "vintage-scripture-paintings-overlaid"
STYLE_ID = "vintage-scripture-paintings"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--price", type=float, required=True)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = bsb.load_json(bsb.CONFIG_PATH)
    keyword_data = bsb.load_json(bsb.KEYWORD_DATA_PATH)
    style = bsb.get_style(config, STYLE_ID)

    images = sorted(SOURCE_DIR.glob("Vintage-Scripture-Paintings-*.jpg"))
    if not images:
        raise SystemExit(f"No images found in {SOURCE_DIR}")
    print(f"Building bundle for '{style['name']}' with {len(images)} images...")

    out_dir = bsb.BUNDLES_DIR / STYLE_ID
    zip_parts = bsb.build_zip_parts(images, out_dir, STYLE_ID)
    for part in zip_parts:
        print(f"Created: {part} ({part.stat().st_size / 1024 / 1024:.1f} MB)")

    client = genai.Client()
    listing = bsb.generate_listing(client, style, len(images), keyword_data)
    bsb.save_listing(out_dir, STYLE_ID, listing, args.price, len(images), zip_parts)

    print(f"\nDone. Bundle folder: {out_dir}")


if __name__ == "__main__":
    main()
