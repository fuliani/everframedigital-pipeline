"""Replace the Japandi-Minimalist Etsy draft images with the approved V5 set.

All nine V5 files are uploaded before any prior listing image is deleted.  If
an upload fails, newly uploaded images are removed and the prior draft image
set remains intact.  The script never activates or publishes the listing.
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


REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Japandi-Minimalist"
STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
IMAGE_DIR = PRODUCT / "cover-v5-review"
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


def api(method: str, url: str, headers: dict, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=180, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    return response


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_local() -> list[Path]:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("design_version") != "V5 bright dense gallery":
        raise RuntimeError("V5 generation report is not PASS")
    declared = {row["filename"]: row for row in report.get("files", [])}
    if set(declared) != set(IMAGE_NAMES):
        raise RuntimeError("V5 generation report does not contain the exact nine expected files")
    images = [IMAGE_DIR / name for name in IMAGE_NAMES]
    for path in images:
        if sha256(path) != declared[path.name]["sha256"]:
            raise RuntimeError(f"V5 hash mismatch: {path.name}")
        with Image.open(path) as image:
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid V5 image: {path.name}")
    return images


def update_logs(listing_id: int, result: dict) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.update(result)
    state["listing_id"] = listing_id
    state["status"] = "DRAFT_IMAGES_REPLACED_V5_BRIGHT"
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    log = json.loads(GENERAL_LOG.read_text(encoding="utf-8")) if GENERAL_LOG.exists() else []
    log = [row for row in log if row.get("bundle") != "Japandi-Minimalist"]
    log.append(state)
    GENERAL_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def main() -> None:
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
    listing_before = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")
    if (listing_before.get("state") != "draft"
            or str(listing_before.get("shop_id")) != shop_id
            or listing_before.get("title") != EXPECTED_TITLE):
        raise RuntimeError("Target listing is not the expected unpublished Japandi draft")

    files_before = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers
    ).json().get("results", [])
    if len(files_before) != 5:
        raise RuntimeError(f"Expected 5 customer ZIP files; found {len(files_before)}")
    file_ids_before = {int(row["listing_file_id"]) for row in files_before}
    tags_before = list(listing_before.get("tags", []))
    price_before = dict(listing_before.get("price", {}))

    old_images = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    if len(old_images) != 9:
        raise RuntimeError(f"Expected 9 existing draft images; found {len(old_images)}")
    old_ids = [int(row["listing_image_id"]) for row in old_images]

    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    new_ids: list[int] = []
    failed: str | None = None
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
        raise RuntimeError(f"V5 image upload failed at {failed}; original images preserved")

    for image_id in old_ids:
        api(
            "DELETE",
            f"{BASE}/shops/{shop_id}/listings/{listing_id}/images/{image_id}",
            headers,
            expected=(204,),
        )

    remote_images = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    remote_ids = {int(row["listing_image_id"]) for row in remote_images}
    listing_after = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    files_after = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers
    ).json().get("results", [])
    file_ids_after = {int(row["listing_file_id"]) for row in files_after}

    if len(remote_images) != 9 or remote_ids != set(new_ids):
        raise RuntimeError("Remote image verification failed after V5 replacement")
    if listing_after.get("state") != "draft":
        raise RuntimeError("Listing unexpectedly left draft state")
    if listing_after.get("title") != listing_before.get("title"):
        raise RuntimeError("Listing title changed during image replacement")
    if listing_after.get("price") != price_before:
        raise RuntimeError("Listing price changed during image replacement")
    if list(listing_after.get("tags", [])) != tags_before:
        raise RuntimeError("Listing tags changed during image replacement")
    if len(files_after) != 5 or file_ids_after != file_ids_before:
        raise RuntimeError("Customer ZIP files changed during image replacement")

    result = {
        "state": "draft",
        "images_uploaded": 9,
        "files_uploaded": 5,
        "tags": tags_before,
        "tags_match": len(tags_before) == 13,
        "title_matches": True,
        "price_matches": True,
        "shop_matches": True,
        "image_design_version": "V5 bright dense gallery",
        "image_ids": new_ids,
        "cover_image_id": new_ids[0],
        "review_url": f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}",
    }
    update_logs(listing_id, result)
    print(json.dumps({
        "listing_id": listing_id,
        "status": "DRAFT_IMAGES_REPLACED_V5_BRIGHT",
        "state": "draft",
        "images": len(remote_images),
        "files": len(files_after),
        "tags": len(tags_before),
        "review_url": result["review_url"],
    }, indent=2))


if __name__ == "__main__":
    main()
