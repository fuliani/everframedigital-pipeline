"""
Publish a reviewed Etsy draft listing (flip state draft -> active).

This is a deliberately separate, explicit step from create_draft.py: nothing
this integration does goes live on Etsy without you running this script by
hand against a specific listing_id you've already reviewed.

Usage:
    python -m scripts.etsy_publish.activate_listing 1234567890
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.etsy_publish.auth import EtsyAuth
from scripts.etsy_publish.listings import EtsyListings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("listing_id", type=int)
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    auth = EtsyAuth(
        os.environ["ETSY_API_KEY"],
        os.environ["ETSY_API_SECRET"],
        os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/oauth/redirect"),
        str(REPO_ROOT / "etsy_token.json"),
    )
    if not auth.is_authenticated():
        logger.info("Not authenticated yet -- starting OAuth flow.")
        if not auth.start_oauth_flow():
            sys.exit(1)

    client = EtsyListings(auth, shop_id=os.environ.get("ETSY_SHOP_ID") or None)

    info = client.get_listing(args.listing_id)
    if not info:
        print(f"Could not fetch listing {args.listing_id}.")
        sys.exit(1)

    print(f"Listing {args.listing_id}: '{info.get('title')}' -- current state: {info.get('state')}")
    if info.get("state") == "active":
        print("Already active. Nothing to do.")
        return

    if not args.yes:
        answer = input("Publish this listing to your live Etsy shop now? [y/N] ").strip().lower()
        if answer != "y":
            print("Cancelled.")
            return

    result = client.activate_listing(args.listing_id)
    if result:
        print(f"Published: https://www.etsy.com/listing/{args.listing_id}")
    else:
        print("Activation failed -- see log above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
