"""Create and verify the premium Vintage Scripture Paintings Etsy draft.

This script is intentionally draft-only. It validates the rebuilt local bundle,
creates one idempotent Etsy draft, uploads ten listing images and five ZIP files,
and never activates/publishes the listing.
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from scripts.etsy_publish import create_two_new_product_drafts as etsy
from scripts.etsy_publish.auth import EtsyAuth


REPO = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = REPO / "EverframeDigital" / "Products" / "Vintage-scripture-paintings"
IMAGE_NAMES = (
    "01-main-cover.jpg", "02-product-details.jpg", "03-collection-specs.jpg",
    "04-how-to-download.jpg", "05-compatibility.jpg", "06-premium-quality.jpg",
    "07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg",
    "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg",
)
ZIP_NAMES = tuple(
    f"Vintage-Scripture-Paintings-100-Images-Part{i}of5.zip"
    for i in range(1, 6)
)

DESCRIPTION = """Create a peaceful rotating scripture gallery on your Frame TV with 100 vintage-inspired Christian paintings. Each landscape-format artwork includes a different King James Version Bible verse, composed with professional typography, balanced spacing, a warm parchment panel, and restrained antique-gold details.

WHAT IS INCLUDED
- 100 unique vintage scripture painting JPG artworks
- 100 different KJV Bible verses
- 3840 x 2160 pixels (4K UHD)
- 16:9 landscape format
- 5 ZIP archives
- Instant digital download
- Personal-use license

HOW TO DOWNLOAD
1. Sign in to Etsy and open Purchases and Reviews.
2. Download all 5 ZIP archives to a computer.
3. Extract every ZIP file to access all 100 numbered JPG images.
4. Choose an artwork and transfer it to your display.

HOW TO DISPLAY
Transfer a selected JPG using the SmartThings app or another compatible device method. Open Art Mode, add your image, and adjust the display to your preference. The files are also suitable for compatible 16:9 televisions, monitors, tablets, screensavers, and digital displays.

IMPORTANT
- This is a digital product. No physical item will be shipped.
- As an instant digital download, this purchase is non-refundable and all sales are final.
- Screen colors may vary by device and display settings.
- A computer is the easiest way to extract ZIP archives.
- Personal use only. Files may not be resold, shared, redistributed, or used commercially.

SCRIPTURE
King James Version (KJV). Scripture wording and references were programmatically placed for consistent spelling and typography.

AI DISCLOSURE
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital.

The underlying artwork is 100% AI-generated with human curation and review. Scripture typography and layout were composed deterministically for accuracy and consistency. No claim of hand painting or manual artistic refinement is made."""

PRODUCT = etsy.Product(
    key="Vintage-Scripture-Paintings-100-Premium",
    folder="Vintage-scripture-paintings",
    title="100 Vintage Scripture Paintings Frame TV Art Bundle, KJV Bible Verse Christian 4K Digital Download",
    price=8.99,
    tags=(
        "frame tv art", "scripture wall art", "bible verse art",
        "christian tv art", "vintage bible art", "kjv scripture art",
        "religious wall art", "faith home decor", "4k tv artwork",
        "digital download", "christian gift", "vintage landscape",
        "scripture bundle",
    ),
    materials=("Digital download", "JPG", "ZIP"),
    description=DESCRIPTION,
    image_dir="cover-premium-review",
    image_names=IMAGE_NAMES,
    zip_names=ZIP_NAMES,
    delivery_prefix="Vintage-Scripture-Paintings",
    delivery_count=100,
)


def validate_local() -> tuple[list[Path], list[Path]]:
    if len(PRODUCT.title) > 140 or "samsung" in PRODUCT.title.lower():
        raise RuntimeError("Invalid Etsy title")
    if len(PRODUCT.tags) != 13 or len(set(PRODUCT.tags)) != 13 or any(len(tag) > 20 for tag in PRODUCT.tags):
        raise RuntimeError("Invalid Etsy tag set")
    report = PRODUCT_ROOT / "cover-premium-review" / "generation-report.txt"
    if not report.is_file() or "FINAL STATUS: PASS" not in report.read_text(encoding="utf-8"):
        raise RuntimeError("Premium generation report is not PASS")

    images = [PRODUCT_ROOT / "cover-premium-review" / name for name in IMAGE_NAMES]
    archives = [PRODUCT_ROOT / "customer-downloads-v2" / name for name in ZIP_NAMES]
    for path in images:
        with Image.open(path) as image:
            image.load()
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"Invalid listing image: {path.name}")
    members = []
    for path in archives:
        if not path.is_file() or not 0 < path.stat().st_size < 20_000_000:
            raise RuntimeError(f"Missing or oversized ZIP: {path.name}")
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"ZIP CRC failure: {path.name}")
            members.extend(Path(name).name for name in archive.namelist())
    expected = [f"Vintage-Scripture-Paintings-{number:03d}.jpg" for number in range(1, 101)]
    if sorted(members) != sorted(expected) or len(members) != len(set(members)):
        raise RuntimeError("ZIP membership is incomplete or duplicated")
    return images, archives


def main() -> None:
    load_dotenv(REPO / ".env")
    shop_id = str(os.environ["ETSY_SHOP_ID"])
    taxonomy_id = int(os.environ["ETSY_TAXONOMY_ID"])
    auth = EtsyAuth(
        os.environ["ETSY_API_KEY"], os.environ["ETSY_API_SECRET"],
        os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/oauth/redirect"),
        str(REPO / "etsy_token.json"),
    )
    headers = auth.get_headers()
    if not headers:
        raise RuntimeError("Etsy authentication is unavailable")
    me = etsy.api("GET", f"{etsy.BASE}/users/me", headers).json()
    shop = etsy.api("GET", f"{etsy.BASE}/shops/{shop_id}", headers).json()
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")

    images, archives = validate_local()
    listing_id = etsy.known_listing_id(PRODUCT)
    if listing_id is None:
        matches = etsy.list_matching(headers, shop_id, PRODUCT)
        if len(matches) > 1:
            raise RuntimeError("Multiple remote exact-title listings exist")
        if matches:
            if matches[0].get("state") != "draft":
                raise RuntimeError("An active exact-title listing already exists")
            listing_id = int(matches[0]["listing_id"])
        else:
            listing_id = etsy.create_listing(PRODUCT, headers, shop_id, taxonomy_id)
            etsy.persist(PRODUCT, listing_id, "INCOMPLETE_DRAFT", {"stage": "listing_created"})

    etsy.upload_remaining(PRODUCT, listing_id, images, archives, headers, shop_id)
    result = etsy.remote_result(PRODUCT, listing_id, headers, shop_id)
    passed = (
        result["state"] == "draft" and result["shop_matches"] and result["title_matches"]
        and result["price_matches"] and result["tags_match"]
        and result["images_uploaded"] == 10 and result["files_uploaded"] == 5
        and result["remote_file_names"] == sorted(ZIP_NAMES)
    )
    status = "DRAFT_VERIFIED" if passed else "INCOMPLETE_DRAFT"
    etsy.persist(PRODUCT, listing_id, status, result)
    if not passed:
        raise RuntimeError(f"Remote Etsy verification failed: {result}")
    print(json.dumps({"shop": shop.get("shop_name"), "listing_id": listing_id, "status": status, **result}, indent=2))


if __name__ == "__main__":
    main()
