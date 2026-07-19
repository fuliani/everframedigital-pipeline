"""Generate the Emerald Muse ten-artwork collection with FAL HD.

The script is resumable and never uploads to Etsy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import fal_client
import requests
from dotenv import load_dotenv
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "Emerald-Green-Abstract-Female-10-Collection"
LISTING = PRODUCT / "listing"
SOURCE = PRODUCT / "source-art"
STATE = LISTING / "full-production-state.json"
MANIFEST = LISTING / "generation-manifest.csv"
LOG = LISTING / "generation-log.txt"

CONCEPTS = [
    "a serene side profile drawn with one continuous gold contour",
    "a three-quarter portrait beneath a broad emerald architectural arch",
    "a back-facing silhouette wrapped in flowing abstract drapery",
    "a peaceful closed-eye portrait among simplified olive leaves",
    "two overlapping female profiles beneath a muted gold sun disc",
    "a sculptural female bust framed by asymmetric emerald blocks",
    "cropped shoulders and an elegant face beneath sweeping gold linework",
    "a graceful side profile merging into flat botanical silhouettes",
    "a fragmented geometric portrait surrounded by asymmetric negative space",
    "an elongated three-quarter portrait encircled by an emerald halo",
]

PREFIX = (
    "An original modern abstract fine-art portrait of {concept}, elegant adult female subject, "
    "sophisticated emerald green deep forest muted olive warm ivory oatmeal taupe charcoal "
    "and restrained antique-gold palette, refined gold-colored contour lines, modern maximalist "
    "and boho-glam composition, simplified painterly forms, subtle canvas plaster paper and "
    "dry-brush texture, editorial negative space, luxurious contemporary mood"
)
SUFFIX = (
    "horizontal 16:9 landscape, tasteful nonsexual presentation, adult subject only, no nudity, "
    "no hands near the face, anatomically coherent face, no duplicated features, no text, no letters, "
    "no numbers, no signature, no watermark, no logo, no stamped mark, all four corners blank and clean, "
    "flat 2D digital artwork filling the entire canvas edge to edge, not a photograph, no frame, "
    "no mat, no border, no wall, no room, no television, no gallery"
)


def prompt(concept: str) -> str:
    return f"{PREFIX.format(concept=concept)}, {SUFFIX}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(path)


def append_log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def validate(path: Path) -> tuple[bool, str]:
    try:
        with Image.open(path) as image:
            image.load()
            if image.size != (1920, 1080):
                return False, f"unexpected dimensions {image.size}"
            if image.mode not in ("RGB", "RGBA") or image.format != "PNG":
                return False, f"unexpected {image.format}/{image.mode}"
    except Exception as exc:
        return False, f"cannot open: {exc}"
    return True, "PASS"


def generate(full_prompt: str) -> bytes:
    result = fal_client.subscribe(
        "fal-ai/z-image/turbo",
        arguments={
            "prompt": full_prompt,
            "image_size": {"width": 1920, "height": 1080},
            "num_images": 1,
            "output_format": "png",
        },
    )
    response = requests.get(result["images"][0]["url"], timeout=120)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content)).convert("RGB")
    if image.size != (1920, 1080):
        image = image.resize((1920, 1080), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def initialize() -> dict:
    if len(CONCEPTS) != 10 or len(set(CONCEPTS)) != 10:
        raise RuntimeError("Expected ten unique concepts")
    LISTING.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    rows = []
    for number, concept in enumerate(CONCEPTS, 1):
        rows.append({
            "number": number,
            "concept": concept,
            "source_filename": f"Emerald-Muse-{number:03d}.png",
            "delivery_filename": f"Emerald-Muse-{number:03d}.jpg",
            "prompt": prompt(concept),
        })
    with MANIFEST.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
    else:
        state = {
            "product": "Emerald Muse — 10 Abstract Female Portraits",
            "provider": "fal-ai/z-image/turbo",
            "quality": "HD 1920x1080 source normalized later to 3840x2160",
            "required_count": 10,
            "items": [],
            "last_completed": 0,
            "status": "GENERATING",
        }
        for row in rows:
            state["items"].append({
                **row,
                "status": "PENDING",
                "path": str(SOURCE / row["source_filename"]),
                "dimensions": None,
                "sha256": None,
                "attempts": 0,
                "validation": None,
            })
    for item in state["items"]:
        path = Path(item["path"])
        passed, reason = validate(path) if path.exists() else (False, "MISSING")
        if passed:
            item.update(status="ACCEPTED", dimensions=[1920, 1080], sha256=sha256(path), validation="PASS")
        else:
            item.update(status="PENDING", dimensions=None, sha256=None, validation=reason)
    accepted = [item["number"] for item in state["items"] if item["status"] == "ACCEPTED"]
    state["last_completed"] = max(accepted, default=0)
    atomic_json(STATE, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--regenerate", type=int, nargs="*", default=[])
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY is not configured")
    state = initialize()
    for item in state["items"]:
        if item["number"] in set(args.regenerate):
            item.update(status="PENDING", validation="MANUAL_REGENERATION_REQUESTED")
    atomic_json(STATE, state)
    generated = 0
    for item in state["items"]:
        if item["status"] == "ACCEPTED" or generated >= args.limit:
            continue
        path = Path(item["path"])
        item["status"] = "GENERATING"
        item["attempts"] += 1
        atomic_json(STATE, state)
        print(f"[{item['number']:03d}/010] {item['concept']}", flush=True)
        try:
            content = generate(item["prompt"])
            temp = path.with_suffix(".tmp.png")
            temp.write_bytes(content)
            passed, reason = validate(temp)
            if not passed:
                temp.unlink(missing_ok=True)
                item.update(status="PENDING", validation=reason)
                append_log(f"REJECTED {item['number']:03d} {reason}")
                atomic_json(STATE, state)
                continue
            temp.replace(path)
            item.update(status="ACCEPTED", dimensions=[1920, 1080], sha256=sha256(path), validation="PASS")
            state["last_completed"] = item["number"]
            generated += 1
            append_log(f"ACCEPTED {item['number']:03d} {path.name} {item['sha256']}")
            atomic_json(STATE, state)
        except Exception as exc:
            item.update(status="PENDING", validation=f"ERROR: {exc}")
            append_log(f"ERROR {item['number']:03d} {type(exc).__name__}: {exc}")
            atomic_json(STATE, state)
            raise
    accepted = sum(item["status"] == "ACCEPTED" for item in state["items"])
    state["status"] = "ARTWORK_COMPLETE" if accepted == 10 else "GENERATING"
    atomic_json(STATE, state)
    print(f"Accepted artwork: {accepted}/10")


if __name__ == "__main__":
    main()
