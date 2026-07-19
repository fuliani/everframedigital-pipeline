"""
Use DeepSeek (cheap) to auto-generate new subject/variation ideas for a style,
so we're not limited to hand-written variation lists. New variations are
appended to config/styles.json (deduped against what's already there).

Usage:
    python scripts/generate_variations.py --style coastal-landscape --count 20
    python scripts/generate_variations.py --style all --count 15
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "styles.json"

SYSTEM_PROMPT = """You generate short subject/variation phrases for an AI art prompt template, \
for a Samsung Frame TV Art Etsy shop. Given a style's name, its prompt template (which has a \
{variation} placeholder), and a list of variations already in use, generate NEW variation \
phrases that:

- Fit the same style/theme/mood as the existing ones
- Are visually distinct from each other and from all existing variations (no near-duplicates, \
no rephrasing of an existing one)
- Are short (roughly 3-8 words), concrete, and describe a specific visual subject/scene
- Would work naturally substituted into the {variation} slot of the prompt template
- Avoid brand names, real people, or copyrighted characters

Respond ONLY with valid JSON: {"variations": ["...", "...", ...]}"""


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def build_prompt(style: dict, count: int) -> str:
    existing = "\n".join(f"- {v}" for v in style["variations"])
    return f"""Style name: {style['name']}
Prompt template: {style['prompt_template']}

Variations already in use ({len(style['variations'])}):
{existing}

Generate {count} NEW variations now."""


def generate_variations(client: OpenAI, style: dict, count: int) -> list[str]:
    response = client.chat.completions.create(
        model="deepseek-chat",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(style, count)},
        ],
    )
    result = json.loads(response.choices[0].message.content)
    return result["variations"]


def dedupe(new_variations: list[str], existing: list[str]) -> list[str]:
    existing_lower = {v.lower().strip() for v in existing}
    out = []
    for v in new_variations:
        v_clean = v.strip()
        if v_clean.lower() not in existing_lower and v_clean.lower() not in {o.lower() for o in out}:
            out.append(v_clean)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--style", required=True, help="Style id, or 'all' for every style")
    parser.add_argument("--count", type=int, default=20, help="How many new variations to generate per style")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    client = OpenAI(api_key=__import__("os").getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    config = load_config()

    targets = config["styles"] if args.style == "all" else [s for s in config["styles"] if s["id"] == args.style]
    if not targets:
        raise SystemExit(f"Style '{args.style}' not found.")

    for style in targets:
        print(f"[{style['id']}] generating {args.count} new variations...")
        new_raw = generate_variations(client, style, args.count)
        new_deduped = dedupe(new_raw, style["variations"])
        dropped = len(new_raw) - len(new_deduped)

        style["variations"].extend(new_deduped)
        print(f"  added {len(new_deduped)} (dropped {dropped} duplicate/near-duplicate), total now {len(style['variations'])}")
        for v in new_deduped:
            print(f"    + {v}")

    save_config(config)
    print(f"\nDone. Saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
