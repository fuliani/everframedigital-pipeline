"""
Daily eRank keyword-collection automation (Phase 1: collection only, no
auto-spend / no auto-generation triggered by results).

Each run:
  1. Pops the next 10 terms off config/keyword_seed_queue.json (5 per account).
  2. For each account's persistent Chrome profile, logs into eRank (session
     already saved in the profile) and searches each term via the Keyword Tool.
  3. Screenshots the results panel for each term (eRank renders the numbers
     as canvas/image, not selectable text, so this step can't be skipped).
  4. Sends each screenshot to GPT-4o vision to extract avg_searches,
     avg_clicks, ctr, and competition as structured JSON.
  5. Appends results to config/keyword_data.json under a dated
     "discovery_<date>" section, and logs a summary to daily_keyword_log.txt.

Run manually:
    .venv/Scripts/python.exe scripts/erank_daily_collect.py

Intended to also run unattended via Windows Task Scheduler (see
scripts/register_erank_task.ps1).
"""

import base64
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "config" / "keyword_seed_queue.json"
DATA_PATH = ROOT / "config" / "keyword_data.json"
LOG_PATH = ROOT / "scratch_browser" / "daily_keyword_log.txt"
SHOT_DIR = ROOT / "scratch_browser" / "erank_daily"

ACCOUNTS = [
    {"name": "account1", "profile": ROOT / "scratch_browser" / "erank_profile"},
    {"name": "account2", "profile": ROOT / "scratch_browser" / "erank_profile_2"},
]
TERMS_PER_ACCOUNT = 5
LOW_QUEUE_WARNING = 10

VISION_PROMPT = """This is a screenshot of an eRank Keyword Tool results page for a searched \
keyword. Read the "Keyword Statistics" panel and extract these exact values if visible:
- avg_searches (Avg. Searches per month - a number, or "<20" if that's what's shown)
- avg_clicks (Avg. Clicks, if shown)
- ctr (Click-through rate, e.g. "93%", if shown)
- competition (the Competition number - total competing Etsy listings)

Respond with ONLY a JSON object, no other text, using this exact shape (omit a field entirely \
if it isn't visible in the screenshot, don't guess):
{"avg_searches": <number or "<20" or "unknown">, "avg_clicks": <number>, "ctr": "<string>", "competition": <number>}
"""


def slugify(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def load_queue() -> dict:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def save_queue(data: dict) -> None:
    QUEUE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def take_screenshot(context, term: str, out_path: Path) -> bool:
    page = context.new_page()
    try:
        url = f"https://members.erank.com/keyword-tool?keyword={term.replace(' ', '%20')}&country=USA&source=etsy"
        page.goto(url, timeout=30000)
        page.wait_for_timeout(4000)  # let the canvas/results panel render
        page.screenshot(path=str(out_path))
        return True
    except Exception as e:
        print(f"  FAILED to screenshot '{term}': {e}", file=sys.stderr)
        return False
    finally:
        page.close()


def extract_with_vision(client, image_path: Path) -> dict:
    from google.genai import types

    image_bytes = image_path.read_bytes()
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            VISION_PROMPT,
        ],
    )
    raw = (resp.text or "").strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  Could not parse vision response: {raw[:200]}", file=sys.stderr)
        return {}


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--counts",
        help="Comma-separated per-account term counts to override the default "
        "(e.g. '4,5' if one account already used some of today's quota). "
        "Must match the number of accounts in ACCOUNTS.",
    )
    args = parser.parse_args()
    per_account_counts = (
        [int(x) for x in args.counts.split(",")] if args.counts else [TERMS_PER_ACCOUNT] * len(ACCOUNTS)
    )

    load_dotenv(ROOT / ".env")
    from google import genai

    vision_client = genai.Client()

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    queue_data = load_queue()
    queue = queue_data["queue"]

    total_needed = sum(per_account_counts)
    if len(queue) < total_needed:
        print(f"WARNING: only {len(queue)} terms left in queue (need {total_needed}). Add more to config/keyword_seed_queue.json.")
    terms_today = queue[:total_needed]
    if not terms_today:
        print("Queue is empty. Nothing to collect today.")
        return

    today = date.today().isoformat()
    results = {}
    log_lines = [f"\n=== {datetime.now().isoformat(timespec='seconds')} ==="]

    with sync_playwright() as pw:
        term_idx = 0
        for account, n in zip(ACCOUNTS, per_account_counts):
            account_terms = terms_today[term_idx: term_idx + n]
            term_idx += n
            if not account_terms:
                continue

            print(f"\n--- {account['name']} ({len(account_terms)} terms) ---")
            context = pw.chromium.launch_persistent_context(
                str(account["profile"]), headless=False
            )
            try:
                for term in account_terms:
                    shot_path = SHOT_DIR / f"{today}-{slugify(term)}.png"
                    print(f"  searching: {term}")
                    ok = take_screenshot(context, term, shot_path)
                    if not ok:
                        log_lines.append(f"  FAILED: {term} ({account['name']})")
                        continue
                    extracted = extract_with_vision(vision_client, shot_path)
                    if extracted:
                        results[term] = extracted
                        log_lines.append(f"  OK: {term} -> {extracted}")
                        print(f"    -> {extracted}")
                    else:
                        log_lines.append(f"  VISION-FAILED: {term} ({account['name']})")
            finally:
                context.close()

    # merge into keyword_data.json under a dated discovery section
    kw_data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    section_key = f"discovery_{today}"
    section = kw_data.get(section_key, {"_comment": "Auto-collected via scripts/erank_daily_collect.py"})
    section.update(results)
    kw_data[section_key] = section
    DATA_PATH.write_text(json.dumps(kw_data, indent=2), encoding="utf-8")

    # remove consumed terms from queue
    consumed = set(terms_today)
    queue_data["queue"] = [t for t in queue if t not in consumed] + [t for t in queue if t in consumed and t not in terms_today]
    remaining = len(queue_data["queue"])
    save_queue(queue_data)

    if remaining < LOW_QUEUE_WARNING:
        log_lines.append(f"  LOW QUEUE WARNING: only {remaining} terms left, add more to config/keyword_seed_queue.json")
        print(f"\nLOW QUEUE WARNING: only {remaining} terms left in the seed queue.")

    log_lines.append(f"  Collected {len(results)}/{len(terms_today)} terms. {remaining} remain in queue.")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    print(f"\nDone. {len(results)}/{len(terms_today)} terms collected, saved to config/keyword_data.json under '{section_key}'.")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    main()
