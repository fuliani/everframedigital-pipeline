"""Replace only the images on the existing Japandi-Minimalist Etsy draft.

The replacement is rollback-safe: all nine new images are uploaded before any
old image is deleted. If an upload fails, newly uploaded images are removed and
the original draft image set is preserved. This script never activates a listing.
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
PRODUCT = REPO / "EverframeDigital" / "Products" / "Japandi-Minimalist"
STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
IMAGE_DIR = PRODUCT / "cover-v3-review"
REPORT = IMAGE_DIR / "generation-report.json"
BASE = "https://openapi.etsy.com/v3/application"
EXPECTED_TITLE = (
    "100 Japandi Minimalist Frame TV Art Bundle, Neutral 4K Digital Art, "
    "Wabi Sabi Scandinavian Instant Download"
)
IMAGE_NAMES = [
    "01-main-cover.jpg",
    "02-collection-overview.jpg",
    "03-gallery-one.jpg",
    "04-gallery-two.jpg",
    "05-gallery-three.jpg",
    "06-frame-tv-preview.jpg",
    "07-whats-included.jpg",
    "08-how-to-display.jpg",
    "09-quality-compatibility.jpg",
]


def api(method, url, headers, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=180, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    return response


def validate_local():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or len(report.get("files", [])) != 9:
        raise RuntimeError("V3 generation report is not PASS")
    images = [IMAGE_DIR / name for name in IMAGE_NAMES]
    for path in images:
        with Image.open(path) as image:
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid V3 image: {path.name}")
    return images


def update_logs(listing_id, result):
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.update(result)
    state["listing_id"] = listing_id
    state["status"] = "DRAFT_IMAGES_REPLACED_V3"
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    log = json.loads(GENERAL_LOG.read_text(encoding="utf-8")) if GENERAL_LOG.exists() else []
    log = [row for row in log if row.get("bundle") != "Japandi-Minimalist"]
    log.append(state)
    GENERAL_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def main():
    images = validate_local()
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    listing_id = int(state["listing_id"])

    load_dotenv(REPO / ".env")
    shop_id = str(os.environ["ETSY_SHOP_ID"])
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
    listing = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")
    if (listing.get("state") != "draft" or str(listing.get("shop_id")) != shop_id
            or listing.get("title") != EXPECTED_TITLE):
        raise RuntimeError("Target listing is not the expected unpublished Japandi draft")

    old_images = api(
        "GET", f"{BASE}/listings/{listing_id}/images", headers
    ).json().get("results", [])
    if len(old_images) != 9:
        raise RuntimeError(f"Expected 9 existing draft images; found {len(old_images)}")
    old_ids = [int(row["listing_image_id"]) for row in old_images]

    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    new_ids = []
    failed = None
    for rank, path in enumerate(images, 1):
        response = None
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
                break
            if attempt == 0:
                time.sleep(1)
        if response is None or response.status_code != 201:
            failed = path.name
            break
        new_ids.append(int(response.json()["listing_image_id"]))

    if failed:
        for image_id in new_ids:
            api(
                "DELETE",
                f"{BASE}/shops/{shop_id}/listings/{listing_id}/images/{image_id}",
                headers,
                expected=(204,),
            )
        raise RuntimeError(f"V3 image upload failed at {failed}; original images preserved")

    for image_id in old_ids:
        api(
            "DELETE",
            f"{BASE}/shops/{shop_id}/listings/{listing_id}/images/{image_id}",
            headers,
            expected=(204,),
        )

    remote_images = api(
        "GET", f"{BASE}/listings/{listing_id}/images", headers
    ).json().get("results", [])
    remote_ids = {int(row["listing_image_id"]) for row in remote_images}
    if len(remote_images) != 9 or remote_ids != set(new_ids):
        raise RuntimeError("Remote verification failed after V3 image replacement")
    listing = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    if listing.get("state") != "draft":
        raise RuntimeError("Listing unexpectedly left draft state")

    result = {
        "state": "draft",
        "images_uploaded": 9,
        "image_design_version": "V3 premium editorial",
        "image_ids": new_ids,
        "review_url": f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}",
    }
    update_logs(listing_id, result)
    print(json.dumps({"listing_id": listing_id, "status": "DRAFT_IMAGES_REPLACED_V3", **result}, indent=2))


if __name__ == "__main__":
    main()
