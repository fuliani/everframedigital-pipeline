"""
Generate a Claude-in-Chrome publish prompt for a single-style bundle, from
its listing JSON + cover image + ZIP parts (all already built).

Usage:
    python scripts/build_publish_prompt.py --style coastal-landscape
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLES_DIR = ROOT / "output" / "bundles"

TEMPLATE = """You are helping me publish one listing to my Etsy shop "EverframeDigital". I'm logged into my Etsy account in this browser already.

IMPORTANT SAFETY RULE: Fill in all fields, then STOP and show me a summary (title, price, tags count, number of files) and wait for my explicit "yes, publish" before clicking the final Publish/List it button. Do not publish without my confirmation — it costs a $0.20 listing fee and goes publicly live immediately.

IMPORTANT COMPLIANCE NOTE: If the listing form has any field asking about AI-generated content, how the item was made/created, or a "creation method" disclosure — answer it honestly: this artwork was created using AI image generation tools. Do not skip or leave that blank if it's present.

STEP 0 — SHOP NAME CHECK
The shop should already be named "EverframeDigital". Go to Shop Manager > Settings and confirm. If it shows something different, STOP and tell me — don't change it yourself.

=====================================================
BUNDLE LISTING — {style_name} ({count}-piece collection)
=====================================================
This is a bundle of {count} images, all in the {style_name} style, sold as one purchase, delivered as {num_zips} ZIP file(s) (Etsy caps digital files at 20MB each, max 5 files per listing).

1. Go to Shop Manager > Listings > Add a listing
2. Listing photos: upload these {num_photos} images IN THIS ORDER (Etsy allows up to 10 listing photos — these are preview/marketing images shown in search results and the listing page, NOT the delivered files):
{photo_list}
3. Listing type: Digital / Digital download
4. Category: "Digital Prints & Patterns" > Wall Décor / Digital Wall Art
5. Title: paste exactly as given below
6. Price: ${price:.2f}
7. Tags: add all 13 tags exactly as given below
8. Description: paste exactly as given below
9. Digital files: upload {num_zips} ZIP file(s) as the digital files for this listing (these are the actual delivered files, separate from the listing photos above):
{zip_list}
10. Personalization: off
11. Renewal options: automatic
12. Then STOP and show me the summary before publishing, per the safety rule above.

TITLE:
{title}

TAGS:
{tags}

DESCRIPTION:
{description}

=====================================================
Once done (or if you stop for my confirmation), give me a clear summary: whether it published, at what price, and anything that needs my attention.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", required=True)
    args = parser.parse_args()

    style_dir = BUNDLES_DIR / args.style
    listing_json = style_dir / f"{args.style}-listing.json"
    cover_path = style_dir / f"{args.style}-cover.jpg"
    photos_dir = style_dir / "photos"

    if not listing_json.exists():
        raise SystemExit(f"Missing {listing_json} — run build_style_bundle.py first.")
    if not cover_path.exists():
        raise SystemExit(f"Missing {cover_path} — run build_mosaic_cover.py or build_style_cover.py first.")

    with open(listing_json, "r", encoding="utf-8") as f:
        listing = json.load(f)

    zip_list = "\n".join(f"   - {p}" for p in listing["zip_parts"])

    photos = [cover_path]
    if photos_dir.exists():
        photos.extend(sorted(photos_dir.glob("*.jpg")))
    photo_list = "\n".join(f"   {i+1}. {p}" for i, p in enumerate(photos))

    style_name = args.style.replace("-", " ").title()

    prompt = TEMPLATE.format(
        style_name=style_name,
        count=listing["image_count"],
        num_zips=len(listing["zip_parts"]),
        num_photos=len(photos),
        photo_list=photo_list,
        price=listing["price"],
        zip_list=zip_list,
        title=listing["title"],
        tags=", ".join(listing["tags"]),
        description=listing["description"],
    )

    out_path = style_dir / f"{args.style}-publish-prompt.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"Prompt saved: {out_path}")


if __name__ == "__main__":
    main()
