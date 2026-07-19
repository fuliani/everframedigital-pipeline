"""Replace only the first image on the existing Japandi Etsy draft."""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from scripts.etsy_publish.auth import EtsyAuth


REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Japandi-Minimalist"
STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
COVER = PRODUCT / "cover-v4-review" / "01-main-cover.jpg"
BASE = "https://openapi.etsy.com/v3/application"
EXPECTED_TITLE = (
    "100 Japandi Minimalist Frame TV Art Bundle, Neutral 4K Digital Art, "
    "Wabi Sabi Scandinavian Instant Download"
)


def api(method, url, headers, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=180, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    return response


def main():
    with Image.open(COVER) as image:
        if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
            raise RuntimeError("The lighter cover failed technical validation")

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
        raise RuntimeError("Target is not the expected unpublished Japandi draft")

    before = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    if len(before) != 9:
        raise RuntimeError(f"Expected 9 existing images; found {len(before)}")
    old_cover = min(before, key=lambda row: int(row.get("rank", 999)))
    old_cover_id = int(old_cover["listing_image_id"])

    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    with COVER.open("rb") as stream:
        response = requests.post(
            f"{BASE}/shops/{shop_id}/listings/{listing_id}/images",
            headers=upload_headers,
            files={"image": (COVER.name, stream, "image/jpeg")},
            data={"rank": "1"},
            timeout=180,
        )
    if response.status_code != 201:
        raise RuntimeError(f"New cover upload failed: HTTP {response.status_code} {response.text[:500]}")
    new_cover_id = int(response.json()["listing_image_id"])

    try:
        api(
            "DELETE",
            f"{BASE}/shops/{shop_id}/listings/{listing_id}/images/{old_cover_id}",
            headers,
            expected=(204,),
        )
    except Exception:
        api(
            "DELETE",
            f"{BASE}/shops/{shop_id}/listings/{listing_id}/images/{new_cover_id}",
            headers,
            expected=(204,),
        )
        raise

    after = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    files = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers
    ).json().get("results", [])
    ids = {int(row["listing_image_id"]) for row in after}
    listing = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    if (len(after) != 9 or new_cover_id not in ids or old_cover_id in ids
            or len(files) != 5 or listing.get("state") != "draft"
            or len(listing.get("tags") or []) != 13):
        raise RuntimeError("Final remote verification failed after cover replacement")

    state.update({
        "status": "DRAFT_COVER_REPLACED_V4_LIGHT",
        "state": "draft",
        "images_uploaded": 9,
        "files_uploaded": 5,
        "cover_design_version": "V4 lighter warm-linen",
        "cover_image_id": new_cover_id,
        "image_ids": [int(row["listing_image_id"]) for row in after],
    })
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "listing_id": listing_id,
        "status": state["status"],
        "state": "draft",
        "images": len(after),
        "files": len(files),
        "tags": len(listing.get("tags") or []),
        "review_url": state["review_url"],
    }, indent=2))


if __name__ == "__main__":
    main()
