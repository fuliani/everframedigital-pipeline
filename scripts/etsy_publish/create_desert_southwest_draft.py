"""Create or verify the Desert-Southwest Etsy draft only.

This uploader is restricted to one product, requires the validated ten-image
listing set and five customer ZIPs, and never activates or publishes a listing.
"""

from __future__ import annotations

import json
import os
import time
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from scripts.etsy_publish.auth import EtsyAuth


REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Desert-Southwest"
STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
BASE = "https://openapi.etsy.com/v3/application"
BUNDLE = "Desert-Southwest"

TITLE = (
    "100 Desert & Southwest Frame TV Art Bundle, Desert Landscape 4K Digital Art, "
    "Southwestern Instant Download"
)
PRICE = 8.99
TAGS = [
    "southwest tv art",
    "desert tv art",
    "southwest frame art",
    "desert wall art",
    "southwest art",
    "southwestern decor",
    "desert digital art",
    "frame tv download",
    "southwest bundle",
    "terracotta art",
    "desert tv artwork",
    "4k digital art",
    "instant download",
]
MATERIALS = ["JPG", "digital download", "ZIP files", "4K artwork"]
DESCRIPTION = """Bring the warmth and spacious calm of the American Southwest to your screen with 100 coordinated desert landscape artworks. The collection blends terracotta, clay, sage, warm ochre, cream, muted rust, and restrained turquoise across mesas, canyons, cactus studies, adobe forms, desert flora, quiet horizons, and atmospheric skies.

WHAT IS INCLUDED
• 100 unique high-resolution JPG artworks
• 3840 × 2160 pixels (true 4K UHD)
• 16:9 landscape format
• Five ZIP downloads containing 20 consecutive images each
• Instant digital download; no physical item will be shipped

HOW TO DOWNLOAD
After purchase, open your Etsy Purchases page and download all five ZIP files. A computer is the easiest way to extract the archives. Unzip every file to access Desert-Southwest-001.jpg through Desert-Southwest-100.jpg.

HOW TO DISPLAY
Choose an artwork and transfer it to a compatible Frame TV using the SmartThings app or another supported device method. Open Art Mode, add the image, and adjust the display to your preference. These standard 16:9 JPGs are also suitable for compatible televisions, monitors, tablets, screensavers, and digital displays.

COMPATIBILITY NOTE
Device features and transfer methods vary. Screen colors may differ slightly depending on the display and its settings.

IMPORTANT
This is an instant digital download. No physical item will be shipped. Digital purchases are non-refundable and all sales are final.

AI DISCLOSURE
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital. The artwork is 100% AI-generated with human curation and review only. No hand painting, handmade creation, or manual artistic editing is claimed.

LICENSE
Personal use only. Files may not be resold, shared, redistributed, sublicensed, or used commercially."""

IMAGE_NAMES = [
    "01-main-cover.jpg",
    "02-collection-overview.jpg",
    "03-frame-tv-preview.jpg",
    "04-whats-included.jpg",
    "05-how-to-display.jpg",
    "06-quality-compatibility.jpg",
    "07-framed-gallery-one.jpg",
    "08-framed-gallery-two.jpg",
    "09-framed-gallery-three.jpg",
    "10-framed-gallery-four.jpg",
]
ZIP_NAMES = [f"Desert-Southwest-100-Images-Part{i}of5.zip" for i in range(1, 6)]


def api(method: str, url: str, headers: dict, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=240, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    return response


def validate_local() -> tuple[list[Path], list[Path]]:
    if len(TITLE) > 140 or "samsung" in TITLE.lower():
        raise RuntimeError("Title preflight failed")
    if len(TAGS) != 13 or len(set(TAGS)) != 13 or any(len(tag) > 20 for tag in TAGS):
        raise RuntimeError("Tag preflight failed")

    audit = PRODUCT / "listing" / "final-audit-report.txt"
    audit_text = audit.read_text(encoding="utf-8")
    if "Result: PASS" not in audit_text or "Listing graphics: 10" not in audit_text:
        raise RuntimeError("Final product audit is not PASS for ten listing images")
    report = PRODUCT / "cover-v2-review" / "generation-report.txt"
    if "Overall status: PASS" not in report.read_text(encoding="utf-8"):
        raise RuntimeError("Ten-image generation report is not PASS")

    images = [PRODUCT / "cover-v2-review" / name for name in IMAGE_NAMES]
    zips = [PRODUCT / "customer-downloads" / name for name in ZIP_NAMES]
    if not all(path.is_file() for path in images):
        raise RuntimeError("One or more required listing images are missing")
    if not all(path.is_file() and 0 < path.stat().st_size < 20_000_000 for path in zips):
        raise RuntimeError("One or more customer ZIP files are missing or too large")

    for path in images:
        with Image.open(path) as image:
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid listing image: {path.name}")

    members: list[str] = []
    for path in zips:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"ZIP integrity failure: {path.name}")
            members.extend(archive.namelist())
    expected = [f"Desert-Southwest-{number:03d}.jpg" for number in range(1, 101)]
    if sorted(members) != expected or len(members) != len(set(members)):
        raise RuntimeError("ZIP membership does not contain each delivery JPG exactly once")
    return images, zips


def known_listing_id() -> int | None:
    if STATE_PATH.exists():
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if value.get("listing_id"):
            return int(value["listing_id"])
    if GENERAL_LOG.exists():
        for row in reversed(json.loads(GENERAL_LOG.read_text(encoding="utf-8"))):
            if row.get("bundle") == BUNDLE and row.get("listing_id"):
                return int(row["listing_id"])
    return None


def find_matching_remote_draft(headers: dict, shop_id: str) -> int | None:
    response = api(
        "GET",
        f"{BASE}/shops/{shop_id}/listings",
        headers,
        params={"state": "draft", "limit": 100},
    ).json()
    matches = [row for row in response.get("results", []) if row.get("title") == TITLE]
    if len(matches) > 1:
        raise RuntimeError("Multiple matching Desert-Southwest drafts already exist")
    return int(matches[0]["listing_id"]) if matches else None


def persist(listing_id: int, status: str, result: dict) -> None:
    review_url = f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}"
    state = {
        "bundle": BUNDLE,
        "listing_id": listing_id,
        "status": status,
        "review_url": review_url,
        **result,
    }
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    log = json.loads(GENERAL_LOG.read_text(encoding="utf-8")) if GENERAL_LOG.exists() else []
    log = [row for row in log if row.get("bundle") != BUNDLE]
    log.append(state)
    GENERAL_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def remote_result(listing_id: int, headers: dict, shop_id: str) -> dict:
    listing = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    images = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    files = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers
    ).json().get("results", [])
    price = listing.get("price") or {}
    remote_price = price.get("amount", 0) / price.get("divisor", 100)
    remote_tags = listing.get("tags") or []
    return {
        "state": listing.get("state"),
        "title_matches": listing.get("title") == TITLE,
        "price_matches": abs(remote_price - PRICE) < 0.001,
        "tags_match": set(remote_tags) == set(TAGS) and len(remote_tags) == 13,
        "tags": remote_tags,
        "images_uploaded": len(images),
        "files_uploaded": len(files),
        "shop_matches": str(listing.get("shop_id")) == shop_id,
        "image_ids": [int(row["listing_image_id"]) for row in images],
        "file_ids": [int(row["listing_file_id"]) for row in files],
    }


def main() -> None:
    images, zips = validate_local()
    load_dotenv(REPO / ".env")
    shop_id = str(os.environ["ETSY_SHOP_ID"])
    taxonomy_id = int(os.environ["ETSY_TAXONOMY_ID"])
    auth = EtsyAuth(
        os.environ["ETSY_API_KEY"],
        os.environ["ETSY_API_SECRET"],
        os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/oauth/redirect"),
        str(REPO / "etsy_token.json"),
    )
    headers = auth.get_headers()
    if not headers:
        raise RuntimeError("Etsy authentication is unavailable")

    me = api("GET", f"{BASE}/users/me", headers).json()
    shop = api("GET", f"{BASE}/shops/{shop_id}", headers).json()
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")

    listing_id = known_listing_id() or find_matching_remote_draft(headers, shop_id)
    if listing_id:
        result = remote_result(listing_id, headers, shop_id)
        complete = (
            result["state"] == "draft"
            and result["shop_matches"]
            and result["title_matches"]
            and result["price_matches"]
            and result["tags_match"]
            and result["images_uploaded"] == 10
            and result["files_uploaded"] == 5
        )
        status = "ALREADY_DRAFT" if complete else "REMOTE_DISCREPANCY"
        persist(listing_id, status, result)
        print(json.dumps({"listing_id": listing_id, "status": status, **result}, indent=2))
        return

    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    created = api(
        "POST",
        f"{BASE}/shops/{shop_id}/listings",
        upload_headers,
        expected=(201,),
        data={
            "title": TITLE,
            "description": DESCRIPTION,
            "price": PRICE,
            "quantity": 999,
            "tags": ",".join(TAGS),
            "materials": ",".join(MATERIALS),
            "taxonomy_id": taxonomy_id,
            "who_made": "i_did",
            "is_supply": False,
            "when_made": "2020_2026",
            "is_digital": True,
            "type": "download",
        },
    ).json()
    listing_id = int(created["listing_id"])
    persist(listing_id, "INCOMPLETE_DRAFT", {"stage": "listing_created"})

    failed: list[str] = []
    for rank, path in enumerate(images, 1):
        response = None
        for attempt in range(2):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/images",
                    headers=upload_headers,
                    files={"image": (path.name, stream, "image/jpeg")},
                    data={"rank": str(rank)},
                    timeout=240,
                )
            if response.status_code == 201:
                break
            if attempt == 0:
                time.sleep(1)
        if response is None or response.status_code != 201:
            failed.append(path.name)

    for rank, path in enumerate(zips, 1):
        response = None
        for attempt in range(2):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/files",
                    headers=upload_headers,
                    files={"file": (path.name, stream, "application/zip")},
                    data={"name": path.name, "rank": str(rank)},
                    timeout=300,
                )
            if response.status_code == 201:
                break
            if attempt == 0:
                time.sleep(1)
        if response is None or response.status_code != 201:
            failed.append(path.name)

    result = remote_result(listing_id, headers, shop_id)
    passed = (
        not failed
        and result["state"] == "draft"
        and result["shop_matches"]
        and result["title_matches"]
        and result["price_matches"]
        and result["tags_match"]
        and result["images_uploaded"] == 10
        and result["files_uploaded"] == 5
    )
    result["failed_uploads"] = failed
    status = "DRAFT_CREATED" if passed else "INCOMPLETE_DRAFT"
    persist(listing_id, status, result)
    print(json.dumps({"listing_id": listing_id, "status": status, **result}, indent=2))


if __name__ == "__main__":
    main()
