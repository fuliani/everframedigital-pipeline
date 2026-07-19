"""
Batch-generate Frame TV Art wall art images via DALL-E 3 or Gemini.

Usage:
    python scripts/generate_images.py --list-styles
    python scripts/generate_images.py --provider gemini --style abstract-expressionist --count 5
    python scripts/generate_images.py --provider dalle3 --style moody-botanical --count 3 --quality hd
    python scripts/generate_images.py --provider gemini --style art-deco --count 1 --variations "a sunburst pattern"

Images are saved to output/<provider>/<style_id>/ with a manifest.csv logging
the prompt used for each file, so the listing generator (step 3) can read it
back.
"""

import argparse
import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

import providers

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "styles.json"
OUTPUT_DIR = ROOT / "output"
FRAME_TV_SIZE = (3840, 2160)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def slugify(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def get_style(config: dict, style_id: str) -> dict:
    for style in config["styles"]:
        if style["id"] == style_id:
            return style
    raise SystemExit(f"Unknown style '{style_id}'. Run --list-styles to see options.")


def build_prompt(config: dict, style: dict, variation: str) -> str:
    base = style["prompt_template"].format(variation=variation)
    return f"{base}, {config['prompt_suffix']}"


def make_client(provider: str):
    if provider == "dalle3":
        from openai import OpenAI

        return OpenAI()
    elif provider == "gemini":
        from google import genai

        return genai.Client()
    elif provider in ("falai", "falai-hq"):
        import os

        os.environ.setdefault("FAL_KEY", os.environ.get("FAL_KEY", ""))
        return None
    raise SystemExit(f"Unknown provider '{provider}'")


def generate_one(provider: str, client, prompt: str, size_config, quality: str) -> bytes:
    if provider == "dalle3":
        return providers.generate_dalle3(client, prompt, size_config, quality)
    elif provider == "gemini":
        return providers.generate_gemini(client, prompt, size_config, quality)
    elif provider == "falai":
        return providers.generate_falai(client, prompt, size_config, quality)
    elif provider == "falai-hq":
        return providers.generate_falai_hq(client, prompt, size_config, quality)
    raise SystemExit(f"Unknown provider '{provider}'")


def upscale_to_frame_tv(image_bytes: bytes, fmt: str) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    resized = img.resize(FRAME_TV_SIZE, Image.LANCZOS)
    out = io.BytesIO()
    resized.save(out, format=fmt, quality=95 if fmt == "JPEG" else None)
    return out.getvalue()


def append_manifest(manifest_path: Path, row: dict) -> None:
    is_new = not manifest_path.exists()
    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["gemini", "dalle3", "falai", "falai-hq"], default="falai")
    parser.add_argument("--style", help="Style id from config/styles.json")
    parser.add_argument("--list-styles", action="store_true", help="List available styles and exit")
    parser.add_argument("--count", type=int, default=5, help="Number of images to generate (default 5)")
    parser.add_argument("--quality", choices=["standard", "hd"], default="standard")
    parser.add_argument(
        "--variations",
        nargs="+",
        default=None,
        help="Override the style's built-in variation list with custom subjects",
    )
    args = parser.parse_args()

    config = load_config()

    if args.list_styles:
        print("Available styles:")
        for style in config["styles"]:
            print(f"  {style['id']:<24} {style['name']}")
        return

    if not args.style:
        parser.error("--style is required (or use --list-styles)")

    load_dotenv(ROOT / ".env")
    client = make_client(args.provider)

    style = get_style(config, args.style)
    variations = args.variations or style["variations"]
    size_config = config["provider_sizes"][args.provider]

    style_dir = OUTPUT_DIR / args.provider / style["id"]
    style_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = style_dir / "manifest.csv"

    print(f"Generating {args.count} image(s) for style '{style['name']}' via {args.provider} ({args.quality})")

    ext = "jpg" if args.provider == "gemini" else "png"

    for i in range(args.count):
        variation = variations[i % len(variations)]
        prompt = build_prompt(config, style, variation)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{style['id']}-{slugify(variation)}-{timestamp.lower()}.{ext}"
        filepath = style_dir / filename

        print(f"[{i + 1}/{args.count}] {variation} -> {filename}")
        try:
            image_bytes = generate_one(args.provider, client, prompt, size_config, args.quality)
            image_bytes = upscale_to_frame_tv(image_bytes, "JPEG" if ext == "jpg" else "PNG")
        except Exception as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            continue

        filepath.write_bytes(image_bytes)
        append_manifest(
            manifest_path,
            {
                "filename": filename,
                "provider": args.provider,
                "style_id": style["id"],
                "style_name": style["name"],
                "variation": variation,
                "prompt": prompt,
                "quality": args.quality,
                "created_at": timestamp,
            },
        )

    price = providers.PRICE_PER_IMAGE[args.provider][args.quality]
    cost = args.count * price
    print(f"\nDone. Estimated cost: ${cost:.2f} ({args.count} x ${price:.2f}) -- $0 if within {args.provider} free tier")
    print(f"Saved to: {style_dir}")


if __name__ == "__main__":
    main()
