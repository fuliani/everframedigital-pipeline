"""Create or verify the All-Seasons-100-Collection Etsy draft only.

This script is intentionally restricted to one product and never activates a
listing. It uploads the nine reviewed listing images, five customer ZIP files,
and exactly thirteen tags, then verifies the resulting Etsy draft.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from scripts.etsy_publish.auth import EtsyAuth


REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "EverframeDigital" / "Products" / "All-Seasons-100-Collection"
STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
BASE = "https://openapi.etsy.com/v3/application"
BUNDLE = "All-Seasons-100-Collection"

TITLE = (
    "100 All Seasons Frame TV Art Bundle, Seasonal Holiday Artwork, "
    "4K Digital Download, Spring Fall Christmas Collection"
)
PRICE = 8.99
TAGS = [
    "frame tv art",
    "seasonal tv art",
    "all seasons art",
    "digital tv art",
    "instant download",
    "4k tv artwork",
    "valentines tv art",
    "spring easter art",
    "summer tv art",
    "fall halloween art",
    "christmas tv art",
    "holiday tv art",
    "tv art bundle",
]
MATERIALS = ["JPG", "digital download", "ZIP files", "4K artwork"]
DESCRIPTION = """Refresh your digital display throughout the year with 100 curated seasonal artworks in one coordinated Frame TV art collection.

WHAT IS INCLUDED
• 100 high-resolution RGB JPG artworks
• 3840 × 2160 pixels (4K UHD)
• 16:9 landscape format
• 5 organized ZIP archives
• Instant digital download

SEASONAL BREAKDOWN
• 20 Valentine's Day artworks
• 20 Spring and Easter artworks
• 20 Summer and Patriotic artworks
• 20 Fall, Halloween, and Thanksgiving artworks
• 20 Winter and Christmas artworks

HOW TO DOWNLOAD
Sign in to Etsy and open Purchases and Reviews. Download all five ZIP archives to a computer, then extract the files to access the 100 JPG images. A computer is the easiest way to extract ZIP archives.

HOW TO DISPLAY
Choose an artwork and transfer it using the SmartThings app or another compatible device method. Open Art Mode, add the image, and adjust the display to your preference. The files are also suitable for compatible 16:9 televisions, monitors, tablets, digital displays, and screensavers.

IMPORTANT
This is a digital product. No physical item will be shipped. Screen colors may vary by device and display settings. Because this is an instant digital download, the purchase is non-refundable and all sales are final.

AI DISCLOSURE
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital. The artwork is 100% AI-generated with human curation and review only.

LICENSE
Personal use only. The files may not be resold, shared, redistributed, sublicensed, or used commercially."""

IMAGE_NAMES = [
    "01-main-cover.jpg",
    "02-seasonal-breakdown.jpg",
    "03-valentine-spring-preview.jpg",
    "04-summer-patriotic-preview.jpg",
    "05-fall-halloween-thanksgiving-preview.jpg",
    "06-winter-christmas-preview.jpg",
    "07-whats-included.jpg",
    "08-how-to-display.jpg",
    "09-quality-compatibility.jpg",
]
ZIP_NAMES = [
    f"All-Seasons-100-Collection-100-Images-Part{i}of5.zip" for i in range(1, 6)
]


def api(method: str, url: str, headers: dict, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=180, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )
    return response


def validate_local() -> tuple[list[Path], list[Path]]:
    if len(TITLE) > 140 or "samsung" in TITLE.lower():
        raise RuntimeError("Title preflight failed")
    if len(TAGS) != 13 or len(set(TAGS)) != 13 or any(len(tag) > 20 for tag in TAGS):
        raise RuntimeError("Tag preflight failed")
    audit = PRODUCT / "listing" / "final-audit-report.txt"
    if "Result: PASS" not in audit.read_text(encoding="utf-8"):
        raise RuntimeError("Final product audit is not PASS")

    images = [PRODUCT / "cover-v2-review" / name for name in IMAGE_NAMES]
    zips = [PRODUCT / "customer-downloads" / name for name in ZIP_NAMES]
    if not all(path.is_file() for path in images):
        raise RuntimeError("One or more listing images are missing")
    if not all(path.is_file() and path.stat().st_size < 20_000_000 for path in zips):
        raise RuntimeError("One or more customer ZIP files are missing or too large")
    for path in images:
        with Image.open(path) as image:
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid listing image: {path.name}")
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

    listing_id = known_listing_id()
    if listing_id:
        result = remote_result(listing_id, headers, shop_id)
        if result["state"] == "draft" and not result["tags_match"]:
            update_headers = dict(headers)
            update_headers.pop("Content-Type", None)
            api(
                "PATCH",
                f"{BASE}/shops/{shop_id}/listings/{listing_id}",
                update_headers,
                data={"tags": ",".join(TAGS), "materials": ",".join(MATERIALS)},
            )
            result = remote_result(listing_id, headers, shop_id)
        complete = (
            result["state"] == "draft"
            and result["shop_matches"]
            and result["title_matches"]
            and result["price_matches"]
            and result["tags_match"]
            and result["images_uploaded"] == 9
            and result["files_uploaded"] == 5
        )
        status = "ALREADY_DRAFT" if complete else "REMOTE_DISCREPANCY"
        persist(listing_id, status, result)
        print(json.dumps({"listing_id": listing_id, "status": status, **result}, indent=2))
        return

    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    data = {
        "title": TITLE,
        "description": DESCRIPTION,
        "price": PRICE,
        "quantity": 999,
        # Etsy's form API documents these arrays as comma-separated values.
        "tags": ",".join(TAGS),
        "materials": ",".join(MATERIALS),
        "taxonomy_id": taxonomy_id,
        "who_made": "i_did",
        "is_supply": False,
        "when_made": "2020_2026",
        "is_digital": True,
        "type": "download",
    }
    created = api(
        "POST",
        f"{BASE}/shops/{shop_id}/listings",
        upload_headers,
        expected=(201,),
        data=data,
    ).json()
    listing_id = int(created["listing_id"])
    persist(listing_id, "INCOMPLETE_DRAFT", {"stage": "listing_created"})

    failed: list[str] = []
    for rank, path in enumerate(images, 1):
        ok = False
        for attempt in range(2):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/images",
                    headers=upload_headers,
                    files={"image": (path.name, stream, "image/jpeg")},
                    data={"rank": str(rank)},
                    timeout=180,
                )
            if response.status_code == 201:
                ok = True
                break
            if attempt == 0:
                time.sleep(1)
        if not ok:
            failed.append(path.name)

    for rank, path in enumerate(zips, 1):
        ok = False
        for attempt in range(2):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/files",
                    headers=upload_headers,
                    files={"file": (path.name, stream, "application/zip")},
                    data={"name": path.name, "rank": str(rank)},
                    timeout=240,
                )
            if response.status_code == 201:
                ok = True
                break
            if attempt == 0:
                time.sleep(1)
        if not ok:
            failed.append(path.name)

    result = remote_result(listing_id, headers, shop_id)
    passed = (
        not failed
        and result["state"] == "draft"
        and result["shop_matches"]
        and result["title_matches"]
        and result["price_matches"]
        and result["tags_match"]
        and result["images_uploaded"] == 9
        and result["files_uploaded"] == 5
    )
    result["failed_uploads"] = failed
    status = "DRAFT_CREATED" if passed else "INCOMPLETE_DRAFT"
    persist(listing_id, status, result)
    print(json.dumps({"listing_id": listing_id, "status": status, **result}, indent=2))


if __name__ == "__main__":
    main()
