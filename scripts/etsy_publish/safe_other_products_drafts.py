"""Create or verify explicit EverframeDigital Etsy drafts without publishing."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from scripts.etsy_publish.auth import EtsyAuth
from scripts.etsy_publish.parse_product_details import parse_product_details


REPO = Path(__file__).resolve().parents[2]
EVERFRAME = REPO / "EverframeDigital"
PRODUCTS = EVERFRAME / "Products"
STATE_PATH = EVERFRAME / "etsy-other-products-draft-state.json"
LOG_PATH = EVERFRAME / "etsy-draft-log.json"
EXCLUDED = "All-Seasons-100-Collection"
IMAGE_NAMES = [
    "01-main-cover.jpg", "02-product-details.jpg", "03-collection-specs.jpg",
    "04-how-to-download.jpg", "05-compatibility.jpg", "06-premium-quality.jpg",
]
BASE = "https://openapi.etsy.com/v3/application"


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def review_url(listing_id: int) -> str:
    return f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}"


def request(method, url, headers, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=120, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(f"Etsy {method} failed ({response.status_code}) for {url.rsplit('/', 1)[-1]}")
    return response


def persist_identity(bundle: str, listing_id: int, status: str) -> None:
    state = read_json(STATE_PATH, {})
    state[bundle] = {"listing_id": listing_id, "status": status, "review_url": review_url(listing_id)}
    write_json(STATE_PATH, state)
    log = read_json(LOG_PATH, [])
    if not any(x.get("bundle") == bundle and int(x.get("listing_id", 0)) == listing_id for x in log):
        log.append({"bundle": bundle, "status": status.lower(), "listing_id": listing_id,
                    "review_url": review_url(listing_id)})
        write_json(LOG_PATH, log)


def existing_id(bundle: str):
    state = read_json(STATE_PATH, {})
    if bundle in state and state[bundle].get("listing_id"):
        return int(state[bundle]["listing_id"])
    for row in reversed(read_json(LOG_PATH, [])):
        if row.get("bundle") == bundle and row.get("listing_id"):
            return int(row["listing_id"])
    return None


def validate_local(bundle: str):
    if bundle == EXCLUDED:
        raise RuntimeError("Excluded product is never permitted")
    folder = PRODUCTS / bundle
    if not folder.is_dir():
        raise RuntimeError(f"Unknown product folder: {bundle}")
    details_path = folder / "listing" / "product-details.txt"
    listing = parse_product_details(details_path)
    if listing.qc_status.lower() != "ready" or listing.missing_items:
        raise RuntimeError(f"{bundle}: local listing QC is not Ready")
    title_lower = listing.title.lower()
    if len(listing.title) > 140 or "samsung" in title_lower:
        raise RuntimeError(f"{bundle}: invalid Etsy title")
    if len(listing.tags) != 13 or any(len(tag) > 20 for tag in listing.tags):
        raise RuntimeError(f"{bundle}: invalid Etsy tags")
    validation = folder / "listing" / "listing-validation-report.txt"
    generation = folder / "cover-publish-ready" / "generation-report.txt"
    if "FINAL STATUS: PASS" not in validation.read_text(encoding="utf-8"):
        raise RuntimeError(f"{bundle}: listing validation report is not PASS")
    if "FINAL STATUS: PASS" not in generation.read_text(encoding="utf-8"):
        raise RuntimeError(f"{bundle}: generation report is not PASS")
    images = [folder / "cover-publish-ready" / name for name in IMAGE_NAMES]
    if not all(path.is_file() for path in images):
        raise RuntimeError(f"{bundle}: exactly six ordered publish-ready images are required")
    zips = listing.zip_paths()
    if not 1 <= len(zips) <= 5 or any(not p.is_file() or p.stat().st_size >= 20_000_000 for p in zips):
        raise RuntimeError(f"{bundle}: ZIP count/path/size preflight failed")
    return listing, images, zips


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundles", nargs="+", help="Explicit product-folder allowlist")
    args = parser.parse_args()
    if EXCLUDED in args.bundles or len(set(args.bundles)) != len(args.bundles):
        raise SystemExit("Excluded or duplicate bundle supplied")

    load_dotenv(REPO / ".env")
    taxonomy_id = int(os.environ.get("ETSY_TAXONOMY_ID", "0"))
    configured_shop = str(os.environ.get("ETSY_SHOP_ID", ""))
    if not taxonomy_id or not configured_shop:
        raise SystemExit("Shop or taxonomy configuration is missing")
    auth = EtsyAuth(os.environ["ETSY_API_KEY"], os.environ["ETSY_API_SECRET"],
                    os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/oauth/redirect"),
                    str(REPO / "etsy_token.json"))
    headers = auth.get_headers()
    if not headers:
        raise SystemExit("Etsy authentication unavailable")
    me = request("GET", f"{BASE}/users/me", headers).json()
    if str(me.get("shop_id")) != configured_shop:
        raise SystemExit("Authenticated shop ID does not match configured shop ID")
    shop = request("GET", f"{BASE}/shops/{configured_shop}", headers).json()
    if shop.get("shop_name") != "EverframeDigital":
        raise SystemExit("Authenticated shop name is not EverframeDigital")

    print("PREFLIGHT_ALLOWLIST", json.dumps(args.bundles))
    for bundle in args.bundles:
        listing, images, zips = validate_local(bundle)
        known = existing_id(bundle)
        if known:
            remote = request("GET", f"{BASE}/listings/{known}", headers).json()
            if remote.get("state") != "draft" or str(remote.get("shop_id")) != configured_shop:
                print(json.dumps({"bundle": bundle, "status": "REMOTE_DISCREPANCY", "listing_id": known}))
                continue
            files = request("GET", f"{BASE}/shops/{configured_shop}/listings/{known}/files", headers).json().get("results", [])
            imgs = request("GET", f"{BASE}/listings/{known}/images", headers).json().get("results", [])
            persist_identity(bundle, known, "ALREADY_DRAFT")
            print(json.dumps({"bundle": bundle, "status": "ALREADY_DRAFT", "listing_id": known,
                              "review_url": review_url(known), "images": len(imgs), "files": len(files)}))
            continue

        create_headers = dict(headers)
        create_headers.pop("Content-Type", None)
        data = {"title": listing.title, "description": listing.full_description, "price": listing.price,
                "quantity": 999, "tags": listing.tags, "taxonomy_id": taxonomy_id, "who_made": "i_did",
                "is_supply": False, "when_made": "2020_2026", "is_digital": True, "type": "download"}
        if listing.materials:
            data["materials"] = listing.materials
        created = request("POST", f"{BASE}/shops/{configured_shop}/listings", create_headers,
                          expected=(201,), data=data).json()
        listing_id = int(created["listing_id"])
        persist_identity(bundle, listing_id, "INCOMPLETE_DRAFT")

        failed = []
        for rank, path in enumerate(images, 1):
            ok = False
            for attempt in range(2):
                with path.open("rb") as stream:
                    response = requests.post(f"{BASE}/shops/{configured_shop}/listings/{listing_id}/images",
                                             headers=create_headers, files={"image": (path.name, stream, "image/jpeg")},
                                             data={"rank": str(rank)}, timeout=120)
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
                    response = requests.post(f"{BASE}/shops/{configured_shop}/listings/{listing_id}/files",
                                             headers=create_headers, files={"file": (path.name, stream, "application/zip")},
                                             data={"name": path.name, "rank": rank}, timeout=180)
                if response.status_code == 201:
                    ok = True
                    break
                if attempt == 0:
                    time.sleep(1)
            if not ok:
                failed.append(path.name)

        remote = request("GET", f"{BASE}/listings/{listing_id}", headers).json()
        remote_images = request("GET", f"{BASE}/listings/{listing_id}/images", headers).json().get("results", [])
        remote_files = request("GET", f"{BASE}/shops/{configured_shop}/listings/{listing_id}/files", headers).json().get("results", [])
        price = remote.get("price") or {}
        remote_price = price.get("amount", 0) / price.get("divisor", 100)
        passed = (not failed and remote.get("state") == "draft" and remote.get("title") == listing.title
                  and abs(remote_price - listing.price) < 0.001 and len(remote_images) == 6
                  and len(remote_files) == len(zips))
        status = "DRAFT_CREATED" if passed else "INCOMPLETE_DRAFT"
        persist_identity(bundle, listing_id, status)
        print(json.dumps({"bundle": bundle, "status": status, "listing_id": listing_id,
                          "review_url": review_url(listing_id), "images": len(remote_images),
                          "files": len(remote_files), "failed_uploads": failed}))


if __name__ == "__main__":
    main()
