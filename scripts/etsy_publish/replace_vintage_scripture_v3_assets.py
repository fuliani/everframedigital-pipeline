"""Replace all assets on the existing Vintage Scripture Etsy draft with V3.

The target must remain an unpublished EverframeDigital draft. Local V2 assets
are retained as rollback material. The script never activates the listing.
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
PRODUCT = REPO / "EverframeDigital" / "Products" / "Vintage-scripture-paintings"
STATE = PRODUCT / "listing" / "etsy-draft-state.json"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
NEW_IMAGES = PRODUCT / "cover-premium-v2-review"
NEW_FILES = PRODUCT / "customer-downloads-v3"
OLD_IMAGES = PRODUCT / "cover-premium-review"
OLD_FILES = PRODUCT / "customer-downloads-v2"
REPORT = NEW_IMAGES / "generation-report.txt"
BASE = "https://openapi.etsy.com/v3/application"
EXPECTED_TITLE = "100 Vintage Scripture Paintings Frame TV Art Bundle, KJV Bible Verse Christian 4K Digital Download"
IMAGE_NAMES = [
    "01-main-cover.jpg", "02-product-details.jpg", "03-collection-specs.jpg",
    "04-how-to-download.jpg", "05-compatibility.jpg", "06-premium-quality.jpg",
    "07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg",
    "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg",
]
ZIP_NAMES = [f"Vintage-Scripture-Paintings-100-Images-Part{i}of5.zip" for i in range(1, 6)]


def api(method: str, url: str, headers: dict, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=360, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(f"Etsy {method} failed with HTTP {response.status_code}: {response.text[:500]}")
    return response


def validate_local() -> tuple[list[Path], list[Path], list[Path], list[Path]]:
    if not REPORT.is_file() or "FINAL STATUS: PASS" not in REPORT.read_text(encoding="utf-8"):
        raise RuntimeError("V3 generation report is not PASS")
    new_images = [NEW_IMAGES / name for name in IMAGE_NAMES]
    old_images = [OLD_IMAGES / name for name in IMAGE_NAMES]
    new_files = [NEW_FILES / name for name in ZIP_NAMES]
    old_files = [OLD_FILES / name for name in ZIP_NAMES]
    for path in new_images + old_images:
        with Image.open(path) as image:
            image.load()
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid local listing image: {path}")
    for group in (new_files, old_files):
        members: list[str] = []
        for path in group:
            if not path.is_file() or not 0 < path.stat().st_size < 20_000_000:
                raise RuntimeError(f"Missing or oversized rollback/customer file: {path}")
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError(f"ZIP CRC failure: {path}")
                members.extend(archive.namelist())
        if len(members) != 100 or len(set(members)) != 100:
            raise RuntimeError("A local ZIP set does not contain exactly 100 unique files")
    return new_images, new_files, old_images, old_files


def upload_images(paths: list[Path], listing_id: int, shop_id: str, headers: dict, start_rank: int = 1) -> list[int]:
    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    result: list[int] = []
    for rank, path in enumerate(paths, start_rank):
        response = None
        for attempt in range(3):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/images",
                    headers=upload_headers,
                    files={"image": (path.name, stream, "image/jpeg")},
                    data={"rank": str(rank)}, timeout=360,
                )
            if response.status_code == 201:
                break
            time.sleep(1 + attempt)
        if response is None or response.status_code != 201:
            raise RuntimeError(f"Image upload failed for {path.name}: {getattr(response, 'text', '')[:500]}")
        result.append(int(response.json()["listing_image_id"]))
    return result


def upload_files(paths: list[Path], listing_id: int, shop_id: str, headers: dict, start_rank: int = 1) -> list[int]:
    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    result: list[int] = []
    for rank, path in enumerate(paths, start_rank):
        response = None
        for attempt in range(3):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/files",
                    headers=upload_headers,
                    files={"file": (path.name, stream, "application/zip")},
                    data={"name": path.name, "rank": str(rank)}, timeout=360,
                )
            if response.status_code == 201:
                break
            time.sleep(1 + attempt)
        if response is None or response.status_code != 201:
            raise RuntimeError(f"File upload failed for {path.name}: {getattr(response, 'text', '')[:500]}")
        result.append(int(response.json()["listing_file_id"]))
    return result


def delete_images(rows: list[dict], listing_id: int, shop_id: str, headers: dict) -> None:
    for row in rows:
        api("DELETE", f"{BASE}/shops/{shop_id}/listings/{listing_id}/images/{int(row['listing_image_id'])}", headers, expected=(204,))


def delete_files(rows: list[dict], listing_id: int, shop_id: str, headers: dict) -> None:
    for row in rows:
        api("DELETE", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files/{int(row['listing_file_id'])}", headers, expected=(204,))


def update_state(listing_id: int, result: dict) -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state.update(result)
    state.update({"listing_id": listing_id, "status": "DRAFT_ASSETS_REPLACED_V3_HIGH_QUALITY"})
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    log = json.loads(GENERAL_LOG.read_text(encoding="utf-8")) if GENERAL_LOG.exists() else []
    log = [row for row in log if row.get("bundle") != state.get("bundle")]
    log.append(state)
    GENERAL_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    new_images, new_files, old_images, old_files = validate_local()
    local_state = json.loads(STATE.read_text(encoding="utf-8"))
    listing_id = int(local_state["listing_id"])
    load_dotenv(REPO / ".env")
    shop_id = str(os.environ["ETSY_SHOP_ID"])
    auth = EtsyAuth(
        os.environ["ETSY_API_KEY"], os.environ["ETSY_API_SECRET"],
        os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/oauth/redirect"),
        str(REPO / "etsy_token.json"),
    )
    headers = auth.get_headers()
    if not headers:
        raise RuntimeError("Etsy authentication is unavailable")
    me = api("GET", f"{BASE}/users/me", headers).json()
    shop = api("GET", f"{BASE}/shops/{shop_id}", headers).json()
    before = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")
    if before.get("state") != "draft" or str(before.get("shop_id")) != shop_id or before.get("title") != EXPECTED_TITLE:
        raise RuntimeError("Target is not the expected unpublished Vintage Scripture draft")
    tags_before = list(before.get("tags", []))
    price_before = dict(before.get("price", {}))
    remote_images = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    remote_files = api("GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers).json().get("results", [])
    if not 1 <= len(remote_images) <= 10 or not 1 <= len(remote_files) <= 5:
        raise RuntimeError(f"Expected 1-10 images and 1-5 files before replacement; found {len(remote_images)} and {len(remote_files)}")

    # Etsy requires a draft to retain at least one image and one digital file.
    # Keep one old asset as a placeholder, upload up to the platform maximum,
    # then remove the placeholder and upload the final replacement asset.
    image_placeholder = remote_images[-1]
    delete_images(remote_images[:-1], listing_id, shop_id, headers)
    try:
        new_image_ids = upload_images(new_images[:9], listing_id, shop_id, headers)
        delete_images([image_placeholder], listing_id, shop_id, headers)
        new_image_ids += upload_images(new_images[9:], listing_id, shop_id, headers, start_rank=10)
    except Exception:
        raise

    file_placeholder = remote_files[-1]
    delete_files(remote_files[:-1], listing_id, shop_id, headers)
    try:
        new_file_ids = upload_files(new_files[:4], listing_id, shop_id, headers)
        delete_files([file_placeholder], listing_id, shop_id, headers)
        new_file_ids += upload_files(new_files[4:], listing_id, shop_id, headers, start_rank=5)
    except Exception:
        raise

    after = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    images_after = api("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
    files_after = api("GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers).json().get("results", [])
    remote_names = sorted(row.get("filename") or row.get("name") for row in files_after)
    if after.get("state") != "draft" or after.get("title") != EXPECTED_TITLE:
        raise RuntimeError("Listing identity/state changed during replacement")
    if list(after.get("tags", [])) != tags_before or after.get("price") != price_before:
        raise RuntimeError("Listing tags or price changed during replacement")
    if len(images_after) != 10 or {int(row["listing_image_id"]) for row in images_after} != set(new_image_ids):
        raise RuntimeError("Remote image verification failed")
    if len(files_after) != 5 or {int(row["listing_file_id"]) for row in files_after} != set(new_file_ids):
        raise RuntimeError("Remote file verification failed")
    if remote_names != sorted(ZIP_NAMES):
        raise RuntimeError(f"Remote customer filenames do not match: {remote_names}")

    result = {
        "state": "draft", "title": EXPECTED_TITLE, "title_matches": True,
        "price_matches": True, "tags": tags_before, "tags_match": len(tags_before) == 13,
        "images_uploaded": 10, "files_uploaded": 5, "remote_file_names": remote_names,
        "shop_matches": True, "asset_version": "V3 high-quality regenerated artwork",
        "image_ids": new_image_ids, "file_ids": new_file_ids,
        "review_url": f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}",
    }
    update_state(listing_id, result)
    print(json.dumps({"listing_id": listing_id, "status": "DRAFT_ASSETS_REPLACED_V3_HIGH_QUALITY", **result}, indent=2))


if __name__ == "__main__":
    main()
