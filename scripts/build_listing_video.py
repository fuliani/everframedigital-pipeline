"""
Build a short Etsy listing preview video (~10s, 5 real customer artworks,
soft crossfade + gentle zoom, no audio) for a product in
EverframeDigital/Products/<ProductName>/.

Sources artwork directly from the product's customer-facing delivery ZIPs
(customer-downloads/*.zip) - never covers, mockups, or listing graphics.
Uses FFmpeg (zoompan + xfade filters) rather than Revideo/Node, since this
project has no existing Node/TypeScript tooling and FFmpeg alone fully meets
the technical spec (H.264, yuv420p, 1920x960, 30fps, no audio, <15s, <100MB).

Usage:
    python scripts/build_listing_video.py generate --product Coastal-Landscape
    python scripts/build_listing_video.py preview --product Coastal-Landscape
    python scripts/build_listing_video.py validate --product Coastal-Landscape
    python scripts/build_listing_video.py regenerate --product Coastal-Landscape
    python scripts/build_listing_video.py status --product Coastal-Landscape
    python scripts/build_listing_video.py generate --product Coastal-Landscape --dry-run
    python scripts/build_listing_video.py generate --product Coastal-Landscape --replace 3:Coastal-Landscape-042.jpg

See docs/etsy-video-generation.md for the full workflow.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "EverframeDigital" / "Products"

CANVAS_W, CANVAS_H = 1920, 960
FPS = 30
MOCKUP_PATH = ROOT / "scratch_browser" / "VideoMochUp.png"
MOCKUP_SCREEN_BOX = (558, 141, 1302, 566)  # measured: left, top, right, bottom
PER_IMAGE_SECONDS = 2.3  # visible hold per artwork before next crossfade begins
XFADE_SECONDS = 0.7
FINAL_HOLD_SECONDS = 0.9
TARGET_DURATION_RANGE = (3, 15)
MAX_FILE_MB = 100
TEMPLATE_ID = "ffmpeg-crossfade-kenburns-v1"
TEMPLATE_VERSION = "1.1"  # 1.1: removed Ken Burns zoom - static frames, pure crossfade dissolve

EXCLUDE_SUBSTRINGS = ("cover", "mockup", "preview", "details", "specs", "compat", "quality", "download")


# --------------------------------------------------------------------------- paths

def product_paths(product: str, template: str = "plain") -> dict:
    product_dir = PRODUCTS / product
    videos_dir = product_dir / "Listing" / "Videos"
    qc_dir = videos_dir / "QC"
    suffix = "-TV-Mockup" if template == "tv-mockup" else ""
    base = f"{product}-Etsy-Preview{suffix}"
    return {
        "product_dir": product_dir,
        "videos_dir": videos_dir,
        "qc_dir": qc_dir,
        "video_path": videos_dir / f"{base}.mp4",
        "manifest_path": videos_dir / f"{base}-Manifest.json",
        "contact_sheet_path": qc_dir / f"{base}-Contact-Sheet.jpg",
        "validation_path": qc_dir / f"{base}-Validation.json",
    }


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- selection

def extract_candidate_artworks(product_dir: Path) -> list[Path]:
    zips = sorted((product_dir / "customer-downloads").glob("*.zip"))
    if not zips:
        raise SystemExit(f"No customer-downloads ZIPs found in {product_dir}")

    work_dir = ROOT / "scratch_browser" / "_video_work" / product_dir.name
    work_dir.mkdir(parents=True, exist_ok=True)
    for zp in zips:
        with zipfile.ZipFile(zp) as z:
            z.extractall(work_dir)

    images = sorted(work_dir.glob("*.jpg")) + sorted(work_dir.glob("*.jpeg")) + sorted(work_dir.glob("*.png"))
    images = [p for p in images if not any(x in p.stem.lower() for x in EXCLUDE_SUBSTRINGS)]
    return images


def describe_artwork(p: Path, reason: str, collection_index: int) -> dict:
    with Image.open(p) as im:
        w, h = im.size
    return {
        "path": p,
        "filename": p.name,
        "checksum": sha256_of(p),
        "width": w,
        "height": h,
        "aspect_ratio_ok": abs((w / h) - (16 / 9)) < 0.01,
        "selection_reason": reason,
        "collection_index": collection_index,
    }


REASONS = [
    "Hero piece - opens the video",
    "Different composition from the hero",
    "Different subject/subcategory within the collection",
    "Different color balance and mood",
    "Closing piece - representative of the collection's range",
]


def select_five_artworks(product_dir: Path, seed: int = 42, overrides: dict[int, str] | None = None) -> list[dict]:
    """Deterministically pick 5 artworks spread evenly across the delivered
    set, so the selection favors variety over five near-identical/consecutive
    pieces. `overrides` maps a 1-based slot number to an exact filename to
    force into that slot instead of the automatic pick (manual replace)."""
    overrides = overrides or {}
    images = extract_candidate_artworks(product_dir)
    if len(images) < 5:
        raise SystemExit(f"Only found {len(images)} candidate artworks in {product_dir.name} - need at least 5.")

    n = len(images)
    idxs = sorted({round(i * (n - 1) / 4) for i in range(5)})
    while len(idxs) < 5:
        for i in range(n):
            if i not in idxs:
                idxs.add(i)
                break
    idxs = sorted(idxs)[:5]

    by_name = {p.name: p for p in images}
    selected = []
    for slot, i in enumerate(idxs, start=1):
        if slot in overrides:
            override_name = overrides[slot]
            if override_name not in by_name:
                raise SystemExit(f"--replace slot {slot}: '{override_name}' not found among candidate artworks.")
            p = by_name[override_name]
            reason = f"Manually replaced (slot {slot})"
        else:
            p = images[i]
            reason = REASONS[slot - 1]
        selected.append(describe_artwork(p, reason, i + 1))
    return selected


# --------------------------------------------------------------------------- render

def prep_frame(src: Path, out: Path) -> None:
    """Letterbox/pad the source artwork (native aspect preserved, not
    stretched) into the fixed CANVAS_W x CANVAS_H frame the video uses."""
    img = Image.open(src).convert("RGB")
    ratio = min(CANVAS_W / img.width, CANVAS_H / img.height)
    new_w, new_h = int(img.width * ratio), int(img.height * ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (18, 18, 16))
    canvas.paste(resized, ((CANVAS_W - new_w) // 2, (CANVAS_H - new_h) // 2))
    canvas.save(out, quality=95)


def prep_frame_tv_mockup(src: Path, out: Path) -> None:
    """Composite the artwork into the user-provided TV mockup's screen area
    (cover-fill, cropped to the exact screen box - no stretching), then
    letterbox the whole room image (native aspect preserved) into the fixed
    CANVAS_W x CANVAS_H video frame."""
    if not MOCKUP_PATH.exists():
        raise SystemExit(f"TV mockup template not found: {MOCKUP_PATH}")

    room = Image.open(MOCKUP_PATH).convert("RGB")
    art = Image.open(src).convert("RGB")

    x0, y0, x1, y1 = MOCKUP_SCREEN_BOX
    box_w, box_h = x1 - x0, y1 - y0
    ratio = max(box_w / art.width, box_h / art.height)
    new_w, new_h = int(art.width * ratio), int(art.height * ratio)
    art_resized = art.resize((new_w, new_h), Image.LANCZOS)
    crop_x = (new_w - box_w) // 2
    crop_y = (new_h - box_h) // 2
    art_cropped = art_resized.crop((crop_x, crop_y, crop_x + box_w, crop_y + box_h))
    room.paste(art_cropped, (x0, y0))

    ratio = min(CANVAS_W / room.width, CANVAS_H / room.height)
    new_w, new_h = int(room.width * ratio), int(room.height * ratio)
    resized = room.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (18, 18, 16))
    canvas.paste(resized, ((CANVAS_W - new_w) // 2, (CANVAS_H - new_h) // 2))
    canvas.save(out, quality=95)


def build_video(artworks: list[dict], out_path: Path, template: str = "plain") -> None:
    work_dir = out_path.parent / "_frames"
    work_dir.mkdir(parents=True, exist_ok=True)
    frame_fn = prep_frame_tv_mockup if template == "tv-mockup" else prep_frame

    frame_paths = []
    for i, art in enumerate(artworks, 1):
        fp = work_dir / f"frame{i}.jpg"
        frame_fn(art["path"], fp)
        frame_paths.append(fp)

    inputs = []
    filters = []
    for i, fp in enumerate(frame_paths):
        inputs += ["-loop", "1", "-t", str(PER_IMAGE_SECONDS + XFADE_SECONDS + 0.5), "-i", str(fp)]
        # static frame, no zoom/pan - artworks simply dissolve in/out via the xfade chain below
        filters.append(f"[{i}:v]scale={CANVAS_W}:{CANVAS_H},fps={FPS},format=yuv420p[v{i}]")

    xfade_chain = []
    prev_label = "v0"
    offset = PER_IMAGE_SECONDS
    for i in range(1, len(frame_paths)):
        out_label = f"x{i}"
        xfade_chain.append(
            f"[{prev_label}][v{i}]xfade=transition=fade:duration={XFADE_SECONDS}:offset={offset:.2f}[{out_label}]"
        )
        prev_label = out_label
        offset += PER_IMAGE_SECONDS

    filter_complex = ";".join(filters + xfade_chain)
    final_label = prev_label

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{final_label}]",
        "-t", str(round(offset - PER_IMAGE_SECONDS + FINAL_HOLD_SECONDS + XFADE_SECONDS, 2)),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-color_range", "tv",
        "-an",
        "-movflags", "+faststart",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-3000:]}")


# --------------------------------------------------------------------------- validation

def ffprobe_json(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def validate_video(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {"exists": False, "passed": False}

    probe = ffprobe_json(path)
    fmt = probe.get("format", {})
    video_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
    audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]

    size_mb = path.stat().st_size / (1024 * 1024)
    duration = float(fmt.get("duration", 0))
    vs = video_streams[0] if video_streams else {}

    checks = {"exists": True}
    checks["codec_h264"] = vs.get("codec_name") == "h264"
    checks["pix_fmt_yuv420p"] = vs.get("pix_fmt") == "yuv420p"
    checks["resolution"] = f"{vs.get('width')}x{vs.get('height')}"
    checks["resolution_ok"] = (vs.get("width"), vs.get("height")) == (CANVAS_W, CANVAS_H)
    fr = vs.get("r_frame_rate", "0/1")
    num, den = fr.split("/")
    fps_actual = float(num) / float(den) if float(den) else 0
    checks["fps"] = round(fps_actual, 2)
    checks["fps_ok"] = abs(fps_actual - FPS) < 1
    checks["duration_seconds"] = round(duration, 2)
    checks["duration_ok"] = TARGET_DURATION_RANGE[0] <= duration <= TARGET_DURATION_RANGE[1]
    checks["size_mb"] = round(size_mb, 2)
    checks["size_ok"] = size_mb < MAX_FILE_MB
    checks["no_audio"] = len(audio_streams) == 0
    checks["passed"] = all([
        checks["codec_h264"], checks["pix_fmt_yuv420p"], checks["resolution_ok"],
        checks["fps_ok"], checks["duration_ok"], checks["size_ok"], checks["no_audio"],
    ])
    return checks


def build_contact_sheet(video_path: Path, out_path: Path, num_artworks: int = 5) -> None:
    timestamps = [round(PER_IMAGE_SECONDS * (i + 0.5), 2) for i in range(num_artworks)]
    work_dir = out_path.parent / "_contact_frames"
    work_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for t in timestamps:
        fp = work_dir / f"t{t}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(video_path), "-frames:v", "1", str(fp)], capture_output=True)
        if fp.exists():
            frames.append(fp)
    if not frames:
        return
    thumb_w = 480
    imgs = [Image.open(f) for f in frames]
    thumb_h = int(thumb_w * imgs[0].height / imgs[0].width)
    sheet = Image.new("RGB", (thumb_w * len(imgs), thumb_h), (20, 20, 20))
    for i, im in enumerate(imgs):
        sheet.paste(im.resize((thumb_w, thumb_h), Image.LANCZOS), (i * thumb_w, 0))
    sheet.save(out_path, quality=95)


# --------------------------------------------------------------------------- manifest / staleness

def write_manifest(product: str, product_dir: Path, artworks: list[dict], paths: dict, validation: dict, seed: int, template: str = "plain") -> dict:
    ffmpeg_ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    template_id = f"{TEMPLATE_ID}-{template}"
    manifest = {
        "product_id": product,
        "product_name": product,
        "product_directory": str(product_dir),
        "template_id": template_id,
        "template_version": TEMPLATE_VERSION,
        "template": template,
        "mockup_source": str(MOCKUP_PATH) if template == "tv-mockup" else None,
        "selected_artworks": [
            {
                "path": str(a["path"]),
                "filename": a["filename"],
                "checksum_sha256_16": a["checksum"],
                "selection_reason": a["selection_reason"],
                "collection_index": a["collection_index"],
                "width": a["width"],
                "height": a["height"],
                "aspect_ratio_ok": a["aspect_ratio_ok"],
            }
            for a in artworks
        ],
        "selection_seed": seed,
        "output_path": str(paths["video_path"]),
        "resolution": f"{CANVAS_W}x{CANVAS_H}",
        "frame_rate": FPS,
        "duration_seconds": validation.get("duration_seconds"),
        "codec": "h264",
        "pixel_format": "yuv420p",
        "file_size_mb": validation.get("size_mb"),
        "ffmpeg_version": ffmpeg_ver,
        "renderer": "ffmpeg (not Revideo - no Node/TS tooling in this project; ffmpeg xfade+zoompan meets the same technical spec)",
        "creation_date": datetime.now(timezone.utc).isoformat(),
        "validation_status": "PASSED" if validation.get("passed") else "FAILED",
        "validation_details": validation,
        "approval_status": "Rendered - pending human approval",
    }
    paths["manifest_path"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def check_staleness(product: str, template: str = "plain") -> dict:
    """Compare the manifest's stored artwork checksums against the current
    files on disk. Returns status without regenerating anything."""
    paths = product_paths(product, template)
    if not paths["manifest_path"].exists():
        return {"status": "Not Started", "reason": "No manifest found - video never generated."}

    manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    stale_reasons = []
    for entry in manifest["selected_artworks"]:
        p = Path(entry["path"])
        if not p.exists():
            stale_reasons.append(f"Artwork missing: {entry['filename']}")
            continue
        current_checksum = sha256_of(p)
        if current_checksum != entry["checksum_sha256_16"]:
            stale_reasons.append(f"Artwork changed since last render: {entry['filename']}")

    expected_template_id = f"{TEMPLATE_ID}-{template}"
    if manifest.get("template_id") != expected_template_id or manifest.get("template_version") != TEMPLATE_VERSION:
        stale_reasons.append(f"Template changed: manifest has {manifest.get('template_id')} v{manifest.get('template_version')}, current is {expected_template_id} v{TEMPLATE_VERSION}")

    if not paths["video_path"].exists():
        stale_reasons.append("Video file missing from disk.")

    if stale_reasons:
        return {"status": "Needs Regeneration", "reasons": stale_reasons, "manifest": manifest}
    if manifest.get("validation_status") != "PASSED":
        return {"status": "Validation Failed", "manifest": manifest}
    return {"status": "Rendered", "manifest": manifest}


# --------------------------------------------------------------------------- commands

def cmd_preview(args):
    product_dir = PRODUCTS / args.product
    if not product_dir.exists():
        raise SystemExit(f"Product folder not found: {product_dir}")
    overrides = parse_overrides(args.replace)
    artworks = select_five_artworks(product_dir, seed=args.seed, overrides=overrides)
    print(f"Selected artworks for '{args.product}' (seed={args.seed}):")
    for a in artworks:
        print(f"  [{a['collection_index']}] {a['filename']} - {a['selection_reason']} ({a['width']}x{a['height']}, 16:9 ok={a['aspect_ratio_ok']})")


def cmd_status(args):
    result = check_staleness(args.product, args.template)
    print(f"Status for '{args.product}' ({args.template}): {result['status']}")
    if result.get("reasons"):
        for r in result["reasons"]:
            print(f"  - {r}")


def cmd_validate(args):
    paths = product_paths(args.product, args.template)
    if not paths["video_path"].exists():
        raise SystemExit(f"No video found at {paths['video_path']} - run 'generate' first.")
    validation = validate_video(paths["video_path"])
    paths["validation_path"].write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(f"{'PASSED' if validation.get('passed') else 'FAILED'}: {json.dumps(validation, indent=2)}")
    if not validation.get("passed"):
        sys.exit(1)


def parse_overrides(replace_args: list[str] | None) -> dict[int, str]:
    overrides = {}
    for item in replace_args or []:
        slot_str, _, filename = item.partition(":")
        if not filename:
            raise SystemExit(f"--replace must be in the form SLOT:FILENAME, got '{item}'")
        overrides[int(slot_str)] = filename
    return overrides


def cmd_generate(args, force: bool = False):
    product_dir = PRODUCTS / args.product
    if not product_dir.exists():
        raise SystemExit(f"Product folder not found: {product_dir}")

    if not force and not args.dry_run:
        status = check_staleness(args.product, args.template)
        if status["status"] == "Rendered":
            print(f"Video already rendered and valid for '{args.product}' ({args.template}). Use 'regenerate' to force a re-render.")
            return

    overrides = parse_overrides(args.replace)
    print(f"Selecting 5 artworks from {args.product}...")
    artworks = select_five_artworks(product_dir, seed=args.seed, overrides=overrides)
    for a in artworks:
        print(f"  [{a['collection_index']}] {a['filename']} - {a['selection_reason']} ({a['width']}x{a['height']})")

    if args.dry_run:
        print("\n--dry-run: selection only, no video rendered.")
        return

    paths = product_paths(args.product, args.template)
    paths["videos_dir"].mkdir(parents=True, exist_ok=True)
    paths["qc_dir"].mkdir(parents=True, exist_ok=True)

    print(f"Rendering video with ffmpeg (template={args.template})...")
    build_video(artworks, paths["video_path"], template=args.template)
    print(f"  Saved: {paths['video_path']}")

    print("Validating with ffprobe...")
    validation = validate_video(paths["video_path"])
    paths["validation_path"].write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(f"  {'PASSED' if validation['passed'] else 'FAILED'}: {validation}")

    print("Building QC contact sheet...")
    build_contact_sheet(paths["video_path"], paths["contact_sheet_path"], num_artworks=len(artworks))
    print(f"  Saved: {paths['contact_sheet_path']}")

    manifest = write_manifest(args.product, product_dir, artworks, paths, validation, args.seed, template=args.template)
    print(f"  Saved: {paths['manifest_path']}")

    print(f"\n{'DONE' if validation['passed'] else 'DONE WITH VALIDATION FAILURES'}")


def cmd_regenerate(args):
    cmd_generate(args, force=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--product", required=True, help="Folder name under EverframeDigital/Products/")
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--replace", action="append", default=[], metavar="SLOT:FILENAME", help="Override one selection slot (1-5), e.g. --replace 3:Coastal-Landscape-042.jpg")
        p.add_argument("--template", choices=["plain", "tv-mockup"], default="plain", help="'plain' = full-bleed artwork; 'tv-mockup' = composited into scratch_browser/VideoMochUp.png")

    p_gen = sub.add_parser("generate", help="Select artworks and render the video (skips if already rendered and valid)")
    add_common(p_gen)
    p_gen.add_argument("--dry-run", action="store_true", help="Only print the selection, don't render")
    p_gen.set_defaults(func=cmd_generate)

    p_regen = sub.add_parser("regenerate", help="Force a fresh render even if one already exists")
    add_common(p_regen)
    p_regen.add_argument("--dry-run", action="store_true")
    p_regen.set_defaults(func=cmd_regenerate)

    p_preview = sub.add_parser("preview", help="Print the 5 selected artworks without rendering")
    add_common(p_preview)
    p_preview.set_defaults(func=cmd_preview)

    p_val = sub.add_parser("validate", help="Run ffprobe validation against an existing rendered video")
    p_val.add_argument("--product", required=True)
    p_val.add_argument("--template", choices=["plain", "tv-mockup"], default="plain")
    p_val.set_defaults(func=cmd_validate)

    p_status = sub.add_parser("status", help="Check whether the video is Not Started / Rendered / Needs Regeneration")
    p_status.add_argument("--product", required=True)
    p_status.add_argument("--template", choices=["plain", "tv-mockup"], default="plain")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
