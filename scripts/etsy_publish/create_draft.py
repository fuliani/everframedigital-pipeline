"""
Create an Etsy DRAFT listing from an EverframeDigital product folder.

Drafts are never visible to buyers and are not billed a listing fee until
activated, so this is safe to run freely for review. Nothing goes live on
Etsy until you separately run activate_listing.py on a listing_id you've
reviewed in your Etsy shop manager.

Usage:
    python -m scripts.etsy_publish.create_draft Coastal-Landscape
    python -m scripts.etsy_publish.create_draft --all
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.etsy_publish.auth import EtsyAuth
from scripts.etsy_publish.listings import EtsyListings
from scripts.etsy_publish.parse_product_details import (
    ProductListing,
    find_all_products,
    parse_product_details,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
EVERFRAME_ROOT = REPO_ROOT / "EverframeDigital"
RESULTS_LOG = EVERFRAME_ROOT / "etsy-draft-log.json"


def get_client() -> EtsyListings:
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ["ETSY_API_KEY"]
    api_secret = os.environ["ETSY_API_SECRET"]
    redirect_uri = os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/oauth/redirect")
    token_file = str(REPO_ROOT / "etsy_token.json")

    auth = EtsyAuth(api_key, api_secret, redirect_uri, token_file)
    if not auth.is_authenticated():
        logger.info("Not authenticated yet -- starting OAuth flow.")
        if not auth.start_oauth_flow():
            logger.error("Authentication failed.")
            sys.exit(1)

    shop_id = os.environ.get("ETSY_SHOP_ID") or None
    return EtsyListings(auth, shop_id=shop_id)


def create_draft_for(client: EtsyListings, listing: ProductListing, taxonomy_id: int) -> dict:
    print(f"\n=== {listing.bundle_dir.name} ===")

    if listing.qc_status.lower() not in ("ready",):
        print(f"  QC status is '{listing.qc_status}', not 'Ready'.")
        for item in listing.missing_items:
            print(f"    - {item}")
        answer = input("  Create draft anyway? [y/N] ").strip().lower()
        if answer != "y":
            print("  Skipped.")
            return {"bundle": listing.bundle_dir.name, "status": "skipped"}

    covers = listing.cover_images()
    zips = listing.zip_paths()
    print(f"  {len(covers)} cover images, {len(zips)} ZIP file(s), price ${listing.price}")

    result = client.create_listing(
        title=listing.title,
        description=listing.full_description,
        price=listing.price,
        quantity=999,
        tags=listing.tags,
        taxonomy_id=taxonomy_id,
        materials=listing.materials or None,
        is_draft=True,
    )
    if not result:
        print("  FAILED to create listing -- see log above.")
        return {"bundle": listing.bundle_dir.name, "status": "failed_create"}

    listing_id = result["listing_id"]
    print(f"  Draft created: listing_id={listing_id}")

    for i, img in enumerate(covers, start=1):
        r = client.upload_listing_image(listing_id, str(img), rank=i)
        print(f"    image {i}/{len(covers)} ({img.name}): {'ok' if r else 'FAILED'}")

    for i, zp in enumerate(zips, start=1):
        r = client.upload_digital_file(listing_id, str(zp), rank=i)
        print(f"    file {i}/{len(zips)} ({zp.name}): {'ok' if r else 'FAILED'}")

    files_ok = client.verify_digital_files(listing_id, expected_count=len(zips))
    print(f"  Digital file verification: {'OK' if files_ok else 'MISMATCH -- check manually'}")

    edit_url = f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}"
    print(f"  Review before publishing: {edit_url}")

    return {
        "bundle": listing.bundle_dir.name,
        "status": "draft_created",
        "listing_id": listing_id,
        "review_url": edit_url,
        "images_uploaded": len(covers),
        "files_uploaded": len(zips),
        "files_verified": files_ok,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", help="Bundle folder name, e.g. Coastal-Landscape")
    parser.add_argument("--all", action="store_true", help="Create drafts for every bundle")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    taxonomy_id = int(os.environ.get("ETSY_TAXONOMY_ID", "0"))
    if not taxonomy_id:
        print("ETSY_TAXONOMY_ID is not set in .env. Run:\n"
              "  python -m scripts.etsy_publish.list_taxonomy digital\n"
              "to find the right id, then set it before creating drafts.")
        sys.exit(1)

    if not args.all and not args.bundle:
        parser.print_help()
        sys.exit(1)

    detail_files = find_all_products(EVERFRAME_ROOT)
    if args.bundle:
        detail_files = [p for p in detail_files if p.parent.parent.name == args.bundle]
        if not detail_files:
            print(f"No product-details.txt found for bundle '{args.bundle}'.")
            sys.exit(1)

    client = get_client()
    if not client.shop_id:
        print("Could not determine shop_id. Check ETSY_SHOP_ID or your Etsy app permissions.")
        sys.exit(1)

    results = []
    for path in detail_files:
        listing = parse_product_details(path)
        results.append(create_draft_for(client, listing, taxonomy_id))

    RESULTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(RESULTS_LOG.read_text()) if RESULTS_LOG.exists() else []
    existing.extend(results)
    RESULTS_LOG.write_text(json.dumps(existing, indent=2))
    print(f"\nLogged {len(results)} result(s) to {RESULTS_LOG}")


if __name__ == "__main__":
    main()
