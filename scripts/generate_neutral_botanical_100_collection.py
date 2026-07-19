"""Generate the distinct Neutral Botanical II 100-image collection with FAL HD.

The script is intentionally resumable. Each successfully validated raster is
saved under the product before the state file is atomically updated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import fal_client
import requests
from dotenv import load_dotenv
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "EverframeDigital" / "Products" / "Neutral-Botanical-100-Collection"
LISTING = PRODUCT / "listing"
SOURCE = PRODUCT / "source-art"
STATE = LISTING / "full-production-state.json"
MANIFEST = LISTING / "generation-manifest.csv"
LOG = LISTING / "generation-log.txt"

STYLE_PREFIX = (
    "An original warm neutral botanical fine-art painting of {variation}, "
    "quiet refined composition, soft natural light, layered painterly brushwork, "
    "warm ivory, oatmeal, pale taupe, muted sage and dusty beige palette, "
    "elegant organic detail, calm contemporary cottage aesthetic"
)
FIXED_SUFFIX = (
    "flat 2D digital artwork filling the entire canvas edge to edge, landscape 16:9, "
    "not a photograph, not a photograph of a painting, no frame, no mat, no border, "
    "no wall, no room, no gallery, no television, no people, no text, no letters, "
    "no numbers, no logo, no watermark, no signature, no artist initials, no stamped marks, "
    "all four corners completely free of writing and artist marks"
)

# These concepts intentionally emphasize panoramic botanical compositions,
# layered meadow studies, and sparse organic abstractions so the collection is
# distinct from the existing 101-piece single-stem/bouquet bestseller.
VARIATIONS = [
    "a misty meadow of ivory cosmos and pale seed heads",
    "layered eucalyptus branches drifting across warm plaster tones",
    "a panoramic field of white yarrow beneath a pearl sky",
    "soft olive leaves casting delicate shadows over linen",
    "a quiet hillside covered in muted cream wildflowers",
    "arching pampas plumes against an oatmeal horizon",
    "a loose garden border of sage foliage and white blooms",
    "delicate fern silhouettes layered through morning mist",
    "a windswept meadow of beige grasses and tiny daisies",
    "pale magnolia branches floating across warm ivory space",
    "an abstract botanical canopy in taupe and dusty sage",
    "a low horizon of dried grasses beneath diffused light",
    "white clover blossoms scattered through muted green ground",
    "a serene bank of reeds reflected in still pale water",
    "soft hydrangea clouds blending into a chalky background",
    "an airy grove of slender olive trees in morning haze",
    "a cascading veil of neutral wisteria and muted leaves",
    "wild oat stems crossing in a gentle evening breeze",
    "a pale botanical arch formed from leaves and seed pods",
    "a distant cream flower field fading into atmospheric fog",
    "layered ginkgo leaves in parchment and soft sage",
    "a sweeping curve of dried bracken across warm stone",
    "white meadow blooms gathered along a quiet country path",
    "a minimalist horizon of cattails and silver grasses",
    "delicate dogwood branches opening over a beige wash",
    "a soft-focus garden of hellebore and feathery foliage",
    "neutral prairie grasses glowing beneath an ivory sunset",
    "a tranquil marsh of pale reeds and floating seed fluff",
    "a rhythmic pattern of eucalyptus leaves and slender stems",
    "white anemones emerging from layered sage brushwork",
    "a panoramic almond orchard in understated spring bloom",
    "dried lunaria discs shimmering against muted taupe",
    "a quiet botanical shoreline with dune grass and sea oats",
    "cream foxglove spires rising through a misty garden",
    "a loose sweep of chamomile across a linen-colored field",
    "delicate willow branches trailing over pale still water",
    "an organic study of overlapping leaves in tonal beige",
    "white blossom petals drifting across a soft sage sky",
    "a meadow edge of Queen Anne lace in filtered sunlight",
    "pale rose vines weaving through weathered garden foliage",
    "a layered woodland floor of ferns and muted botanicals",
    "soft pear branches with sparse leaves and cream fruit",
    "a serene field of flax flowers in dusty neutral blue",
    "a botanical cloud of baby's breath over warm parchment",
    "curving palm fronds simplified in ivory and sage",
    "a distant grove framed by tall translucent wild grasses",
    "cream tulip rows dissolving into soft atmospheric color",
    "an abstract herb garden of rosemary thyme and sage",
    "pale poppies scattered across a warm chalk meadow",
    "a graceful branch network with tiny neutral buds",
    "layered fern shadows moving across textured ivory",
    "a quiet field of dried asters under a dove-gray sky",
    "soft camellia foliage with sparse porcelain-white flowers",
    "a sweeping botanical wave of grasses and pale petals",
    "white lilac clusters emerging from muted olive shadow",
    "a narrow garden stream bordered by cream wildflowers",
    "delicate birch leaves suspended in warm autumn neutrals",
    "a pale trellis of jasmine vines without architectural detail",
    "muted sage hills patterned with tiny ivory blossoms",
    "a close botanical rhythm of teasel and feather grass",
    "white iris shapes reflected in softly rippled water",
    "a drifting arrangement of translucent leaves and petals",
    "cream roses growing loosely through silvery garden foliage",
    "a panoramic dune meadow of sea grass and pale blooms",
    "soft flowering branches framing an open ivory center",
    "a field of pale scabiosa beneath warm clouded light",
    "layered botanical shadows in ecru sage and mushroom",
    "a quiet orchard floor scattered with white petals",
    "delicate maidenhair fern forming a flowing horizontal study",
    "a warm neutral meadow with sparse blush wildflowers",
    "pale clematis vines curling through soft olive leaves",
    "a minimalist row of dried stems along a foggy horizon",
    "white lupine spires receding into a tranquil field",
    "a gentle tangle of honeysuckle and cream foliage",
    "soft botanical reflections of reeds and willow leaves",
    "a broad garden vista of ivory peonies and sage shrubs",
    "neutral lotus leaves floating across warm misty water",
    "a cascading hillside of dried grasses and tiny blooms",
    "pale ranunculus shapes blended into loose abstract foliage",
    "a calm grove of eucalyptus trunks and silver leaves",
    "white flowering thyme spreading across muted stone ground",
    "a serene horizontal composition of grasses and seed heads",
    "delicate cream orchids nestled in layered green-gray leaves",
    "a misted garden gate implied only by climbing botanicals",
    "pale botanical forms rising from a textured oatmeal wash",
    "a distant field of white narcissus beneath soft haze",
    "layered olive branches and ivory blossoms in gentle motion",
    "a windswept bank of neutral wildflowers beside still water",
    "cream delphinium silhouettes against a warm taupe sky",
    "a subtle botanical mosaic of leaves buds and seed pods",
    "pale garden roses scattered along a quiet hedgerow",
    "a tranquil reed bed with ivory plumes and muted reflections",
    "soft almond blossoms crossing a wide parchment sky",
    "a low meadow of white buttercups in diffuse morning light",
    "layered grasses forming an elegant neutral botanical tapestry",
    "a spacious composition of floating sage leaves and petals",
    "cream hydrangea hedges fading toward a misty horizon",
    "a quiet botanical valley filled with pale flowering shrubs",
    "delicate wild stems illuminated against warm linen texture",
    "an expansive ivory flower meadow under a muted sage sky",
]


def atomic_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        temp.replace(path)
    except PermissionError:
        # Windows editors/indexers can briefly hold the destination open. A
        # direct overwrite is safer than losing generation progress entirely.
        path.write_text(temp.read_text(encoding="utf-8"), encoding="utf-8")


def prompt_for(variation: str) -> str:
    return f"{STYLE_PREFIX.format(variation=variation)}, {FIXED_SUFFIX}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_log(message: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {message}\n")


def validate(path: Path) -> tuple[bool, str]:
    try:
        with Image.open(path) as image:
            image.load()
            if image.size != (1920, 1080):
                return False, f"unexpected dimensions {image.size}"
            if image.mode not in ("RGB", "RGBA"):
                return False, f"unexpected mode {image.mode}"
    except Exception as exc:
        return False, f"cannot open: {exc}"
    return True, "PASS"


def generate(prompt: str) -> bytes:
    result = fal_client.subscribe(
        "fal-ai/z-image/turbo",
        arguments={
            "prompt": prompt,
            "image_size": {"width": 1920, "height": 1080},
            "num_images": 1,
            "output_format": "png",
        },
    )
    response = requests.get(result["images"][0]["url"], timeout=90)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content)).convert("RGB")
    if image.size != (1920, 1080):
        image = image.resize((1920, 1080), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def initialize() -> dict:
    if len(VARIATIONS) != 100 or len(set(VARIATIONS)) != 100:
        raise RuntimeError("The manifest must contain exactly 100 unique concepts")
    LISTING.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    rows = []
    for number, variation in enumerate(VARIATIONS, 1):
        rows.append(
            {
                "number": number,
                "concept": variation,
                "filename": f"Neutral-Botanical-II-{number:03d}.png",
                "prompt": prompt_for(variation),
            }
        )
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
    else:
        state = {
            "product": "Neutral Botanical II — 100-Piece Frame TV Art Collection",
            "provider": "fal-ai/z-image/turbo",
            "quality": "HD 1920x1080 source normalized later to 3840x2160",
            "required_count": 100,
            "items": [],
            "last_completed": 0,
            "status": "GENERATING",
        }
        for row in rows:
            state["items"].append(
                {
                    **row,
                    "status": "PENDING",
                    "path": str(SOURCE / row["filename"]),
                    "dimensions": None,
                    "sha256": None,
                    "attempts": 0,
                    "validation": None,
                }
            )
    # Reconcile state with valid local files.
    for item in state["items"]:
        path = Path(item["path"])
        if path.exists():
            passed, reason = validate(path)
            if passed:
                item.update(status="ACCEPTED", dimensions=[1920, 1080], sha256=sha256(path), validation="PASS")
            else:
                item.update(status="PENDING", validation=reason)
        else:
            item.update(status="PENDING", dimensions=None, sha256=None, validation="MISSING")
    accepted = [item["number"] for item in state["items"] if item["status"] == "ACCEPTED"]
    state["last_completed"] = max(accepted, default=0)
    atomic_json(STATE, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="Maximum new images to generate in this run")
    parser.add_argument("--regenerate", type=int, nargs="*", default=[], help="Artwork numbers to regenerate even if accepted")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY is not configured")
    state = initialize()
    regenerate = set(args.regenerate)
    for item in state["items"]:
        if item["number"] in regenerate:
            item.update(status="PENDING", validation="MANUAL_REGENERATION_REQUESTED")
    atomic_json(STATE, state)
    generated = 0
    for item in state["items"]:
        if item["status"] == "ACCEPTED":
            continue
        if generated >= args.limit:
            break
        path = Path(item["path"])
        item["status"] = "GENERATING"
        item["attempts"] += 1
        atomic_json(STATE, state)
        print(f"[{item['number']:03d}/100] {item['concept']}", flush=True)
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
            item.update(
                status="ACCEPTED",
                dimensions=[1920, 1080],
                sha256=sha256(path),
                validation="PASS",
            )
            state["last_completed"] = item["number"]
            append_log(f"ACCEPTED {item['number']:03d} {path.name} {item['sha256']}")
            generated += 1
            atomic_json(STATE, state)
        except Exception as exc:
            item.update(status="PENDING", validation=f"ERROR: {exc}")
            append_log(f"ERROR {item['number']:03d} {type(exc).__name__}: {exc}")
            atomic_json(STATE, state)
            print(f"ERROR {item['number']:03d}: {exc}", flush=True)
            time.sleep(3)
    accepted = sum(item["status"] == "ACCEPTED" for item in state["items"])
    state["status"] = "ARTWORK_COMPLETE" if accepted == 100 else "GENERATING"
    atomic_json(STATE, state)
    print(f"Accepted artwork: {accepted}/100", flush=True)


if __name__ == "__main__":
    main()
