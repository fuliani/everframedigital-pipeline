"""
Etsy API v3 listing operations: create draft, upload images/files, activate.

Adapted from devonjhills/etsy-digital-mockup-tools (MIT license),
src/services/etsy/listings.py. Added activate_listing(), which that project's
create_listing() alone does not provide (it only sets state at creation time).
"""

import logging
import os
from typing import Dict, List, Optional

import requests

from scripts.etsy_publish.auth import EtsyAuth

logger = logging.getLogger(__name__)


class EtsyListings:
    BASE_URL = "https://openapi.etsy.com/v3"

    def __init__(self, auth: EtsyAuth, shop_id: Optional[str] = None):
        self.auth = auth
        self.shop_id = shop_id or os.environ.get("ETSY_SHOP_ID")
        if not self.shop_id:
            self.shop_id = self._get_shop_id()

    def _get_shop_id(self) -> Optional[str]:
        if not self.auth.is_authenticated():
            logger.error("Not authenticated with Etsy.")
            return None
        url = f"{self.BASE_URL}/application/users/me/shops"
        resp = requests.get(url, headers=self.auth.get_headers())
        if resp.status_code != 200:
            logger.error("Error getting shop id: %s %s", resp.status_code, resp.text)
            return None
        shops = resp.json().get("results", [])
        if not shops:
            logger.error("No shops found for authenticated user.")
            return None
        shop_id = str(shops[0].get("shop_id"))
        os.environ["ETSY_SHOP_ID"] = shop_id
        return shop_id

    def get_shipping_profiles(self) -> Optional[List[Dict]]:
        url = f"{self.BASE_URL}/application/shops/{self.shop_id}/shipping-profiles"
        resp = requests.get(url, headers=self.auth.get_headers())
        if resp.status_code == 200:
            return resp.json().get("results", [])
        logger.error("Error getting shipping profiles: %s %s", resp.status_code, resp.text)
        return None

    def get_shop_sections(self) -> Optional[List[Dict]]:
        url = f"{self.BASE_URL}/application/shops/{self.shop_id}/sections"
        resp = requests.get(url, headers=self.auth.get_headers())
        if resp.status_code == 200:
            return resp.json().get("results", [])
        logger.error("Error getting shop sections: %s %s", resp.status_code, resp.text)
        return None

    def create_listing(
        self,
        title: str,
        description: str,
        price: float,
        quantity: int,
        tags: List[str],
        taxonomy_id: int,
        who_made: str = "i_did",
        is_supply: bool = False,
        when_made: str = "2020_2026",
        is_digital: bool = True,
        materials: Optional[List[str]] = None,
        shop_section_id: Optional[int] = None,
        is_draft: bool = True,
    ) -> Optional[Dict]:
        """Create a listing. is_draft=True (the default here) creates it in
        Etsy's 'draft' state so nothing goes live until you explicitly
        activate it with activate_listing()."""
        if not self.shop_id:
            logger.error("No shop id available.")
            return None

        url = f"{self.BASE_URL}/application/shops/{self.shop_id}/listings"
        headers = self.auth.get_headers()
        # createDraftListing expects application/x-www-form-urlencoded.
        headers.pop("Content-Type", None)
        data = {
            "title": title,
            "description": description,
            "price": price,
            "quantity": quantity,
            "tags": tags,
            "taxonomy_id": taxonomy_id,
            "who_made": who_made,
            "is_supply": is_supply,
            "when_made": when_made,
            "is_digital": is_digital,
        }
        if materials:
            data["materials"] = materials
        if shop_section_id:
            data["shop_section_id"] = shop_section_id
        if is_digital:
            data["type"] = "download"

        resp = requests.post(url, headers=headers, data=data)
        if resp.status_code == 201:
            return resp.json()
        logger.error("Error creating listing: %s %s", resp.status_code, resp.text)
        return None

    def get_listing(self, listing_id: int) -> Optional[Dict]:
        url = f"{self.BASE_URL}/application/listings/{listing_id}"
        resp = requests.get(url, headers=self.auth.get_headers())
        if resp.status_code == 200:
            return resp.json()
        logger.error("Error getting listing: %s %s", resp.status_code, resp.text)
        return None

    def activate_listing(self, listing_id: int) -> Optional[Dict]:
        """Flip a draft listing to active (publishes it to the live shop).
        Call this only after you've reviewed the draft on Etsy."""
        if not self.shop_id:
            logger.error("No shop id available.")
            return None
        url = f"{self.BASE_URL}/application/shops/{self.shop_id}/listings/{listing_id}"
        resp = requests.patch(url, headers=self.auth.get_headers(), json={"state": "active"})
        if resp.status_code == 200:
            logger.info("Listing %s activated.", listing_id)
            return resp.json()
        logger.error("Error activating listing: %s %s", resp.status_code, resp.text)
        return None

    def upload_listing_image(self, listing_id: int, image_path: str, rank: int = 1) -> Optional[Dict]:
        if not self.shop_id:
            return None
        url = f"{self.BASE_URL}/application/shops/{self.shop_id}/listings/{listing_id}/images"
        headers = self.auth.get_headers()
        headers.pop("Content-Type", None)
        ext = os.path.splitext(image_path)[1].lower()
        content_type = "image/png" if ext == ".png" else "image/jpeg"
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, content_type)}
            data = {"rank": str(rank)}
            resp = requests.post(url, headers=headers, files=files, data=data)
        if resp.status_code == 201:
            return resp.json()
        logger.error("Error uploading image %s: %s %s", image_path, resp.status_code, resp.text)
        return None

    def upload_digital_file(self, listing_id: int, file_path: str, rank: int = 1) -> Optional[Dict]:
        if not self.shop_id:
            return None
        url = f"{self.BASE_URL}/application/shops/{self.shop_id}/listings/{listing_id}/files"
        headers = self.auth.get_headers()
        headers.pop("Content-Type", None)
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/zip")}
            data = {"name": os.path.basename(file_path), "rank": rank}
            resp = requests.post(url, headers=headers, files=files, data=data)
        if resp.status_code == 201:
            file_data = resp.json()
            logger.info(
                "Digital file uploaded: %s (file id %s)",
                os.path.basename(file_path),
                file_data.get("listing_file_id"),
            )
            return file_data
        logger.error("Error uploading digital file %s: %s %s", file_path, resp.status_code, resp.text)
        return None

    def get_listing_files(self, listing_id: int) -> Optional[List[Dict]]:
        url = f"{self.BASE_URL}/application/shops/{self.shop_id}/listings/{listing_id}/files"
        resp = requests.get(url, headers=self.auth.get_headers())
        if resp.status_code == 200:
            return resp.json().get("results", [])
        logger.error("Error getting listing files: %s %s", resp.status_code, resp.text)
        return None

    def verify_digital_files(self, listing_id: int, expected_count: int) -> bool:
        files = self.get_listing_files(listing_id)
        if files is None:
            return False
        if len(files) != expected_count:
            logger.error(
                "Expected %s digital files on listing %s, found %s",
                expected_count, listing_id, len(files),
            )
            return False
        return True
