"""Rename the Neutral Botanical II draft to Quiet Meadow Botanicals.

Updates customer-facing listing copy and replaces only the two listing images
whose visible text changed. The listing must remain a draft throughout; the
validated customer ZIP files, price, and tags are preserved.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from scripts.etsy_publish.auth import EtsyAuth
from scripts.etsy_publish.create_two_new_product_drafts import PRODUCT_CONFIGS


REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Neutral-Botanical-100-Collection"
STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
IMAGE_DIR = PRODUCT / "cover-premium-review"
BASE = "https://openapi.etsy.com/v3/application"
CONFIG = PRODUCT_CONFIGS[0]
CHANGED_IMAGES = ((1, "01-main-cover.jpg"), (2, "02-product-details.jpg"))


def api(method: str, url: str, headers: dict, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=300, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: {response.text[:700]}"
        )
    return response


def validate_local() -> dict[str, str]:
    if len(CONFIG.title) > 140 or "samsung" in CONFIG.title.lower():
        raise RuntimeError("The renamed title is not Etsy-safe")
    if len(CONFIG.tags) != 13 or any(len(tag) > 20 for tag in CONFIG.tags):
        raise RuntimeError("The preserved tag set is invalid")
    hashes = {}
    for _, name in CHANGED_IMAGES:
        path = IMAGE_DIR / name
        with Image.open(path) as image:
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid replacement image: {name}")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def main() -> None:
    hashes = validate_local()
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
    listing_before = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")
    if listing_before.get("state") != "draft" or str(listing_before.get("shop_id")) != shop_id:
        raise RuntimeError("The target listing is not the expected unpublished shop draft")

    images_before = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    files_before = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers
    ).json().get("results", [])
    if len(images_before) != 10 or len(files_before) != 5:
        raise RuntimeError("Expected 10 images and 5 customer files before update")
    old_by_rank = {int(row["rank"]): int(row["listing_image_id"]) for row in images_before}
    file_ids_before = {int(row["listing_file_id"]) for row in files_before}
    price_before = dict(listing_before.get("price") or {})
    tags_before = list(listing_before.get("tags") or [])
    if set(tags_before) != set(CONFIG.tags) or len(tags_before) != 13:
        raise RuntimeError("Remote tag set differs from the approved 13 tags")

    update_headers = dict(headers)
    update_headers.pop("Content-Type", None)
    api(
        "PATCH",
        f"{BASE}/shops/{shop_id}/listings/{listing_id}",
        update_headers,
        data={"title": CONFIG.title, "description": CONFIG.description},
    )

    new_ids: dict[int, int] = {}
    for rank, name in CHANGED_IMAGES:
        old_id = old_by_rank[rank]
        api(
            "DELETE",
            f"{BASE}/shops/{shop_id}/listings/{listing_id}/images/{old_id}",
            headers,
            expected=(204,),
        )
        path = IMAGE_DIR / name
        response = None
        for attempt in range(3):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/images",
                    headers=update_headers,
                    files={"image": (name, stream, "image/jpeg")},
                    data={"rank": str(rank)},
                    timeout=300,
                )
            if response.status_code == 201:
                break
            time.sleep(1 + attempt)
        if response is None or response.status_code != 201:
            raise RuntimeError(
                f"Replacement upload failed for {name}: {getattr(response, 'text', '')[:500]}"
            )
        new_ids[rank] = int(response.json()["listing_image_id"])

    listing_after = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    images_after = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    files_after = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers
    ).json().get("results", [])
    file_ids_after = {int(row["listing_file_id"]) for row in files_after}
    ranks_after = {int(row["rank"]): int(row["listing_image_id"]) for row in images_after}
    checks = {
        "draft": listing_after.get("state") == "draft",
        "title": listing_after.get("title") == CONFIG.title,
        "price_preserved": listing_after.get("price") == price_before,
        "tags_preserved": list(listing_after.get("tags") or []) == tags_before,
        "images": len(images_after) == 10,
        "changed_ranks": all(ranks_after.get(rank) == image_id for rank, image_id in new_ids.items()),
        "files_preserved": len(files_after) == 5 and file_ids_after == file_ids_before,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Remote verification failed after rename: {checks}")

    state.update({
        "status": "DRAFT_RENAMED_QUIET_MEADOW_BOTANICALS",
        "state": "draft",
        "title": CONFIG.title,
        "title_matches": True,
        "images_uploaded": 10,
        "files_uploaded": 5,
        "cover_image_id": new_ids[1],
        "renamed_collection": "Quiet Meadow Botanicals",
        "replacement_hashes": hashes,
        "review_url": f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}",
    })
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    log = json.loads(GENERAL_LOG.read_text(encoding="utf-8")) if GENERAL_LOG.exists() else []
    log = [row for row in log if row.get("bundle") != state.get("bundle")]
    log.append(state)
    GENERAL_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "listing_id": listing_id,
        "status": state["status"],
        "state": "draft",
        "title": CONFIG.title,
        "images": len(images_after),
        "files": len(files_after),
        "tags": len(tags_before),
        "review_url": state["review_url"],
        "checks": checks,
    }, indent=2))


if __name__ == "__main__":
    main()
