# Etsy listing video generation

Generates a short (~10s) Etsy listing preview video for a finished product:
5 real customer artworks, soft crossfade + gentle Ken Burns zoom, no audio,
no text overlays of static product info (that's what the 6 cover-v2 slide
images are for). Complements the static listing images rather than
duplicating them.

## Architecture note

The original spec for this feature assumed a Node.js/Revideo renderer inside
a web app with a database and UI. This project has none of that - it's a
Python script pipeline with no web frontend, no DB, and no Node/TypeScript
tooling. The video is rendered with **FFmpeg directly** (`zoompan` + `xfade`
filters), which fully satisfies the same technical output spec (H.264,
yuv420p, 1920x960, 30fps, no audio, 3-15s duration, <100MB) without adding a
new rendering framework. State that would normally live in a database (which
artworks were selected, checksums, validation results) lives in the JSON
manifest file next to the video instead.

## Requirements

- `ffmpeg` and `ffprobe` on PATH (verify: `ffmpeg -version`)
- Python with Pillow (already a project dependency)
- A product folder under `EverframeDigital/Products/<Product>/` with a
  `customer-downloads/` folder containing the delivery ZIP(s)

## Commands

```
python scripts/build_listing_video.py generate --product Coastal-Landscape
python scripts/build_listing_video.py generate --product Coastal-Landscape --dry-run
python scripts/build_listing_video.py preview --product Coastal-Landscape
python scripts/build_listing_video.py validate --product Coastal-Landscape
python scripts/build_listing_video.py regenerate --product Coastal-Landscape
python scripts/build_listing_video.py status --product Coastal-Landscape
```

- `generate` selects 5 artworks and renders. If a valid, up-to-date video
  already exists (see staleness below), it skips the render and tells you.
- `regenerate` forces a fresh render regardless of current status.
- `preview` prints the 5 selected artworks (filename, dimensions, why each
  was picked) without rendering anything - use this to sanity-check the
  selection first.
- `validate` re-runs the ffprobe checks against an already-rendered video.
- `status` reports `Not Started` / `Rendered` / `Needs Regeneration` /
  `Validation Failed` without touching anything.

### Manual override

Replace one auto-selected slot with a specific file:

```
python scripts/build_listing_video.py generate --product Coastal-Landscape --replace 3:Coastal-Landscape-042.jpg
```

`--replace` can be passed multiple times (one per slot, 1-5). The filename
must exist among that product's delivered artwork (validated against the
extracted customer-downloads ZIP contents).

## How the 5 artworks are selected

Artwork is extracted from `customer-downloads/*.zip` (the actual files a
buyer receives) - covers, mockups, and listing-info graphics are excluded by
filename pattern. Selection is deterministic: 5 indices evenly spaced across
the full collection (`round(i * (n-1) / 4)` for i=0..4), which guarantees
spread across the set instead of 5 consecutive/near-identical pieces. Pass
`--seed` to get a different (still deterministic) spread if you want to
compare options.

## Staleness detection

The manifest (`<Product>-Etsy-Preview-Manifest.json`) stores a SHA-256
checksum (first 16 hex chars) for each of the 5 source artwork files, plus
the template ID/version used to render. `status` and `generate` compare the
current file checksums on disk against what's stored:

- A selected artwork file changed or was deleted → `Needs Regeneration`
- The video template was updated (`TEMPLATE_ID`/`TEMPLATE_VERSION` constants
  in the script changed) → `Needs Regeneration`
- The rendered MP4 file is missing → `Needs Regeneration`
- Everything matches and the last validation passed → `Rendered`

Regeneration never happens automatically - `generate` just skips a fresh
render when the existing one is still valid; `status` is read-only.

## Output structure

```
EverframeDigital/Products/<Product>/Listing/Videos/
  <Product>-Etsy-Preview.mp4
  <Product>-Etsy-Preview-Manifest.json
  QC/
    <Product>-Etsy-Preview-Contact-Sheet.jpg
    <Product>-Etsy-Preview-Validation.json
```

## Validation

`ffprobe`-based checks, all must pass for the manifest to mark
`validation_status: PASSED`:

| Check | Requirement |
|---|---|
| Codec | H.264 |
| Pixel format | yuv420p |
| Resolution | exactly 1920x960 |
| Frame rate | ~30 FPS |
| Duration | 3-15 seconds |
| File size | under 100 MB |
| Audio | none |

## QC contact sheet

One frame per artwork, sampled at the midpoint of that artwork's visible
window (`PER_IMAGE_SECONDS * (i + 0.5)` per slot) - not fixed timestamps,
since those don't line up with the actual per-image timing and can sample
the same artwork twice. Use the contact sheet for a fast visual gut-check
before manually approving a video (approval itself is just you looking at
the contact sheet + video and deciding it's good - there's no UI workflow
state to click through in this project).

## Known limitations

- No automated test suite - this project has no test framework installed.
  Verification so far has been live runs against a real product
  (Coastal-Landscape), inspected manually (contact sheet, ffprobe output).
- No web UI - everything is CLI-driven, matching the rest of the pipeline.
- No render queue/concurrency control - runs are synchronous and single-shot;
  fine for a one-person operation generating videos on demand, not built for
  concurrent multi-user rendering.
- Approval is manual (you review the contact sheet/video yourself) - there's
  no persisted "approved" flag beyond `approval_status` in the manifest,
  which is written as `"Rendered - pending human approval"` and isn't
  currently updated by any command after that.
