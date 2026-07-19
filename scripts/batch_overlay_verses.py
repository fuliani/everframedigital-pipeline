"""
Batch-apply overlay_verse.py across all generated Vintage-Scripture-Paintings
images, assigning one unique KJV verse per image (deterministic order so
re-runs are stable).

Usage:
    python scripts/batch_overlay_verses.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from overlay_verse import overlay_verse

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "output" / "falai-hq" / "vintage-scripture-paintings"
OUT_DIR = ROOT / "output" / "falai-hq" / "vintage-scripture-paintings-overlaid"
VERSES_PATH = ROOT / "config" / "bible_verses_vintage.json"


def main():
    images = sorted(p for p in SOURCE_DIR.glob("*.png"))
    verses = json.loads(VERSES_PATH.read_text(encoding="utf-8"))["verses"]

    if len(verses) < len(images):
        raise SystemExit(f"Not enough verses ({len(verses)}) for {len(images)} images.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping = []

    for i, (image_path, verse) in enumerate(zip(images, verses), 1):
        out_name = f"Vintage-Scripture-Paintings-{i:03d}.jpg"
        out_path = OUT_DIR / out_name
        overlay_verse(image_path, verse["text"], verse["ref"], out_path)
        mapping.append({"index": i, "source": image_path.name, "verse_ref": verse["ref"], "output": out_name})
        print(f"[{i}/{len(images)}] {verse['ref']} -> {out_name}")

    (OUT_DIR / "verse-mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"\nDone. {len(images)} images overlaid, saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
