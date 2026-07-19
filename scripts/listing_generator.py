"""
Generate SEO-friendly Etsy listing copy (title, tags, description) for
generated Frame TV Art images, using real keyword research data to steer
which terms actually get used.

Usage:
    python scripts/listing_generator.py --style coastal-landscape --file coastal-landscape-a-foggy-coastal-marshland-with-a-lighthouse-20260716t171726z.jpg
    python scripts/listing_generator.py --style coastal-landscape --all
    python scripts/listing_generator.py --style coastal-landscape --all --provider deepseek

Output: one JSON + one human-readable .txt per image in output/listings/,
ready to copy-paste into Etsy's listing form.
"""

import argparse
import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "styles.json"
KEYWORD_DATA_PATH = ROOT / "config" / "keyword_data.json"
OUTPUT_DIR = ROOT / "output"
LISTINGS_DIR = OUTPUT_DIR / "listings"

SYSTEM_PROMPT = """You are an expert Etsy SEO copywriter specializing in Samsung Frame TV Art \
digital downloads. Write listing copy that follows Etsy's best practices:

- Title: max 140 characters, front-load the highest-value keywords, human-readable (not keyword \
soup), must mention "Frame TV Art" or "Samsung Frame TV".
- Tags: exactly 13 tags, each max 20 characters, no repeated words across tags, mix of broad and \
specific/long-tail terms.
- Description: 150-300 words. First 1-2 sentences must be strong (shown in search snippets) and \
keyword-rich. Include: what the buyer gets, how to use it (download, transfer to USB or Samsung \
Art Store app, select in Art Mode), and a one-line personal-use license note. Warm, human tone, \
not robotic.

CRITICAL ACCURACY RULE: The buyer receives EXACTLY ONE JPG file at 3840x2160 pixels (16:9 aspect \
ratio), 4K resolution. Do NOT claim, imply, or invent additional file formats, sizes, aspect \
ratios, or variants (e.g. do not say "plus common ratios," "multiple sizes included," "4:3 and \
square versions," etc.) unless the image details explicitly say otherwise. Only describe exactly \
what is being delivered — nothing more.

Respond ONLY with valid JSON: {"title": "...", "tags": ["...", ...], "description": "..."}"""


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_manifest_row(style_id: str, filename: str) -> dict:
    manifest_path = OUTPUT_DIR / "gemini" / style_id / "manifest.csv"
    with open(manifest_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["filename"] == filename:
                return row
    raise SystemExit(f"'{filename}' not found in {manifest_path}")


def relevant_keywords(style_id: str, keyword_data: dict) -> dict:
    combined = dict(keyword_data.get("baseline", {}))
    combined.update(keyword_data.get("styles", {}).get(style_id, {}))
    return combined


def build_user_prompt(row: dict, keywords: dict) -> str:
    kw_lines = "\n".join(
        f"- \"{term}\": avg searches {data.get('avg_searches', 'unknown')}, "
        f"competition {data.get('competition', 'unknown')} listings"
        + (f" ({data['note']})" if data.get("note") else "")
        for term, data in keywords.items()
    )
    return f"""Image details:
- Style: {row['style_name']}
- Subject/variation: {row['variation']}
- Original art generation prompt: {row['prompt']}

Real Etsy keyword research for this niche (use the low-competition / high-relevance terms as \
tags where they genuinely fit, don't force irrelevant ones):
{kw_lines}

Generate the Etsy listing copy now."""


def generate_listing_gemini(client: genai.Client, row: dict, keywords: dict) -> dict:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{SYSTEM_PROMPT}\n\n{build_user_prompt(row, keywords)}",
        config={"response_mime_type": "application/json"},
    )
    return json.loads(response.text)


def generate_listing_deepseek(client: OpenAI, row: dict, keywords: dict) -> dict:
    response = client.chat.completions.create(
        model="deepseek-chat",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(row, keywords)},
        ],
    )
    return json.loads(response.choices[0].message.content)


def generate_listing(provider: str, client, row: dict, keywords: dict) -> dict:
    if provider == "gemini":
        return generate_listing_gemini(client, row, keywords)
    elif provider == "deepseek":
        return generate_listing_deepseek(client, row, keywords)
    raise SystemExit(f"Unknown provider '{provider}'")


def save_listing(filename: str, listing: dict) -> None:
    LISTINGS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem

    json_path = LISTINGS_DIR / f"{stem}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(listing, f, indent=2)

    txt_path = LISTINGS_DIR / f"{stem}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"TITLE ({len(listing['title'])} chars):\n{listing['title']}\n\n")
        f.write(f"TAGS ({len(listing['tags'])}):\n{', '.join(listing['tags'])}\n\n")
        f.write(f"DESCRIPTION:\n{listing['description']}\n")

    print(f"  -> {txt_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--style", required=True, help="Style id (folder under output/gemini/)")
    parser.add_argument("--file", help="Single image filename to generate copy for")
    parser.add_argument("--all", action="store_true", help="Generate copy for every image in this style's manifest")
    parser.add_argument("--provider", choices=["gemini", "deepseek"], default="gemini")
    args = parser.parse_args()

    if not args.file and not args.all:
        parser.error("Provide --file <filename> or --all")

    load_dotenv(ROOT / ".env")
    if args.provider == "gemini":
        client = genai.Client()
    else:
        client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    keyword_data = load_json(KEYWORD_DATA_PATH)
    keywords = relevant_keywords(args.style, keyword_data)

    manifest_path = OUTPUT_DIR / "gemini" / args.style / "manifest.csv"
    with open(manifest_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    targets = rows if args.all else [r for r in rows if r["filename"] == args.file]
    if not targets:
        raise SystemExit(f"No matching image(s) found in {manifest_path}")

    print(f"Generating listing copy for {len(targets)} image(s)...")
    for row in targets:
        print(f"[{row['filename']}]")
        listing = generate_listing(args.provider, client, row, keywords)
        save_listing(row["filename"], listing)

    print(f"\nDone. Listings saved to: {LISTINGS_DIR}")


if __name__ == "__main__":
    main()
