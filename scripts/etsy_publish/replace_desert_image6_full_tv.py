"""Replace only image 6 in the existing Desert-Southwest Etsy draft.

The replacement is uploaded before the prior rank-six image is removed. The
script verifies that the listing remains a draft and that the other images,
five customer ZIP files, title, price, and tags are unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from scripts.etsy_publish.auth import EtsyAuth


REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Desert-Southwest"
STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
IMAGE = PRODUCT / "cover-v2-review" / "06-quality-compatibility.jpg"
BASE = "https://openapi.etsy.com/v3/application"
LISTING_ID = 4540138990
EXPECTED_TITLE = (
    "100 Desert & Southwest Frame TV Art Bundle, Desert Landscape 4K Digital Art, "
    "Southwestern Instant Download"
)


def api(method: str, url: str, headers: dict, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=240, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    return response


def ordered_images(headers: dict) -> list[dict]:
    rows = api("GET", f"{BASE}/listings/{LISTING_ID}/images", headers).json().get("results", [])
    return sorted(rows, key=lambda row: int(row.get("rank", 999)))


def persist(result: dict) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.update(result)
    state["bundle"] = "Desert-Southwest"
    state["listing_id"] = LISTING_ID
    state["status"] = "DRAFT_IMAGE6_REPLACED_FULL_TV"
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    log = json.loads(GENERAL_LOG.read_text(encoding="utf-8")) if GENERAL_LOG.exists() else []
    log = [row for row in log if row.get("bundle") != "Desert-Southwest"]
    log.append(state)
    GENERAL_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    with Image.open(IMAGE) as image:
        if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
            raise RuntimeError("Local replacement image 6 failed validation")

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
    before = api("GET", f"{BASE}/listings/{LISTING_ID}", headers).json()
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")
    if (before.get("state") != "draft" or str(before.get("shop_id")) != shop_id
            or before.get("title") != EXPECTED_TITLE):
        raise RuntimeError("Target is not the expected unpublished Desert-Southwest draft")

    old_images = ordered_images(headers)
    if len(old_images) != 10 or [int(row["rank"]) for row in old_images] != list(range(1, 11)):
        raise RuntimeError("Expected exactly ten ranked draft images before replacement")
    old_ids = [int(row["listing_image_id"]) for row in old_images]
    old_rank6_id = old_ids[5]

    files_before = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{LISTING_ID}/files", headers
    ).json().get("results", [])
    if len(files_before) != 5:
        raise RuntimeError("Expected exactly five customer ZIP files")
    file_ids_before = {int(row["listing_file_id"]) for row in files_before}
    tags_before = list(before.get("tags", []))
    price_before = dict(before.get("price", {}))

    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    with IMAGE.open("rb") as stream:
        response = requests.post(
            f"{BASE}/shops/{shop_id}/listings/{LISTING_ID}/images",
            headers=upload_headers,
            files={"image": (IMAGE.name, stream, "image/jpeg")},
            data={"rank": "6"},
            timeout=240,
        )
    if response.status_code != 201:
        raise RuntimeError(
            f"Replacement upload failed with HTTP {response.status_code}; old image remains: "
            f"{response.text[:500]}"
        )
    new_image_id = int(response.json()["listing_image_id"])

    try:
        api(
            "DELETE",
            f"{BASE}/shops/{shop_id}/listings/{LISTING_ID}/images/{old_rank6_id}",
            headers,
            expected=(204,),
        )
    except Exception:
        # Keep the original set if the old image could not be removed.
        api(
            "DELETE",
            f"{BASE}/shops/{shop_id}/listings/{LISTING_ID}/images/{new_image_id}",
            headers,
            expected=(204,),
        )
        raise

    remote_images = ordered_images(headers)
    after = api("GET", f"{BASE}/listings/{LISTING_ID}", headers).json()
    files_after = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{LISTING_ID}/files", headers
    ).json().get("results", [])
    new_ids = [int(row["listing_image_id"]) for row in remote_images]
    unchanged_ids = set(old_ids) - {old_rank6_id}

    if len(remote_images) != 10 or new_image_id not in new_ids or old_rank6_id in new_ids:
        raise RuntimeError("Remote image count or replacement-ID verification failed")
    if set(new_ids) - {new_image_id} != unchanged_ids:
        raise RuntimeError("An image other than rank 6 changed unexpectedly")
    if new_ids[5] != new_image_id:
        raise RuntimeError("The replacement did not retain rank 6")
    if (after.get("state") != "draft" or after.get("title") != before.get("title")
            or after.get("price") != price_before or list(after.get("tags", [])) != tags_before):
        raise RuntimeError("Draft metadata changed unexpectedly")
    file_ids_after = {int(row["listing_file_id"]) for row in files_after}
    if len(files_after) != 5 or file_ids_after != file_ids_before:
        raise RuntimeError("Customer ZIP files changed unexpectedly")

    result = {
        "state": "draft",
        "review_url": f"https://www.etsy.com/your/shops/me/listing-editor/edit/{LISTING_ID}",
        "images_uploaded": 10,
        "files_uploaded": 5,
        "tags": tags_before,
        "tags_match": len(tags_before) == 13,
        "title_matches": True,
        "price_matches": True,
        "shop_matches": True,
        "image_ids": new_ids,
        "image6_id": new_image_id,
        "replaced_image6_id": old_rank6_id,
        "file_ids": sorted(file_ids_after),
        "image6_design": "complete four-sided television chassis",
    }
    persist(result)
    print(json.dumps({
        "status": "DRAFT_IMAGE6_REPLACED_FULL_TV",
        "listing_id": LISTING_ID,
        "state": "draft",
        "old_image6_id": old_rank6_id,
        "new_image6_id": new_image_id,
        "images": len(remote_images),
        "files": len(files_after),
        "tags": len(tags_before),
        "review_url": result["review_url"],
    }, indent=2))


if __name__ == "__main__":
    main()
