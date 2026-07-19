"""Create and verify two EverframeDigital Etsy drafts.

This script is deliberately limited to the new Quiet Meadow Botanicals and
Emerald Muse products. It validates every local deliverable before making an
external change, creates drafts only, resumes incomplete uploads, and never
activates a listing.
"""

from __future__ import annotations

import json
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from scripts.etsy_publish.auth import EtsyAuth


REPO = Path(__file__).resolve().parents[2]
PRODUCTS = REPO / "EverframeDigital" / "Products"
GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
BASE = "https://openapi.etsy.com/v3/application"


@dataclass(frozen=True)
class Product:
    key: str
    folder: str
    title: str
    price: float
    tags: tuple[str, ...]
    materials: tuple[str, ...]
    description: str
    image_dir: str
    image_names: tuple[str, ...]
    zip_names: tuple[str, ...]
    delivery_prefix: str
    delivery_count: int

    @property
    def root(self) -> Path:
        return PRODUCTS / self.folder

    @property
    def state_path(self) -> Path:
        return self.root / "listing" / "etsy-draft-state.json"


NEUTRAL_DESCRIPTION = """Refresh your screen with Quiet Meadow Botanicals, a collection of 100 warm neutral artworks featuring airy meadows, delicate branches, soft grasses, and understated garden compositions in ivory, oatmeal, taupe, and muted sage.

WHAT IS INCLUDED
- 100 unique Quiet Meadow Botanicals JPG artworks
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

AI DISCLOSURE
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital.

The artwork is 100% AI-generated with human curation and review only. No claim of hand painting or manual artistic refinement is made."""


EMERALD_DESCRIPTION = """Bring sophisticated color and modern figurative style to your screen with Emerald Muse, a coordinated set of 10 abstract female portraits. Deep emerald, forest green, muted olive, warm ivory, taupe, charcoal, and digitally painted antique-gold accents create an elegant boho-glam and modern-maximalist collection.

WHAT IS INCLUDED
- 10 unique Emerald Muse JPG artworks
- 3840 x 2160 pixels (true 4K UHD)
- 16:9 landscape format
- 1 ZIP archive: Emerald-Muse-10-Images.zip
- Instant digital download
- Personal-use license

HOW TO DOWNLOAD
1. Sign in to Etsy and open Purchases and Reviews.
2. Download Emerald-Muse-10-Images.zip to a computer.
3. Extract the ZIP file to access Emerald-Muse-001.jpg through Emerald-Muse-010.jpg.
4. Choose an artwork and transfer it to your display.

HOW TO DISPLAY
Transfer a selected JPG using the SmartThings app or another compatible device method. Open Art Mode, add your image, and adjust the display to your preference. The files are also suitable for compatible 16:9 televisions, monitors, tablets, screensavers, and digital displays.

IMPORTANT
- This is a digital product. No physical item will be shipped.
- As an instant digital download, this purchase is non-refundable and all sales are final.
- Screen colors may vary by device and display settings.
- Gold is a digitally painted color effect, not metallic foil, gold leaf, or physical ink.
- Personal use only. Files may not be resold, shared, redistributed, or used commercially.

AI DISCLOSURE
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital.

The artwork is 100% AI-generated with human curation and review only. No hand painting or manual artistic refinement is claimed."""


PRODUCT_CONFIGS = (
    Product(
        key="Neutral-Botanical-II-100",
        folder="Neutral-Botanical-100-Collection",
        title="100 Quiet Meadow Neutral Botanical Frame TV Art Bundle, Beige Wildflower Collection, 4K Digital Download",
        price=8.99,
        tags=(
            "frame tv art", "neutral botanical", "botanical tv art",
            "wildflower art", "beige wall art", "sage green decor",
            "cottagecore decor", "digital download", "4k tv artwork",
            "neutral wall decor", "flower meadow art", "instant download",
            "botanical bundle",
        ),
        materials=("Digital download", "JPG", "ZIP"),
        description=NEUTRAL_DESCRIPTION,
        image_dir="cover-premium-review",
        image_names=(
            "01-main-cover.jpg", "02-product-details.jpg",
            "03-collection-specs.jpg", "04-how-to-download.jpg",
            "05-compatibility.jpg", "06-premium-quality.jpg",
            "07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg",
            "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg",
        ),
        zip_names=tuple(
            f"Neutral-Botanical-II-100-Images-Part{i}of5.zip"
            for i in range(1, 6)
        ),
        delivery_prefix="Neutral-Botanical-II",
        delivery_count=100,
    ),
    Product(
        key="Emerald-Muse-10",
        folder="Emerald-Green-Abstract-Female-10-Collection",
        title="10 Emerald Green Abstract Woman Portraits, Gold Line Art Frame TV Bundle, Boho Glam 4K Digital Download",
        price=4.99,
        tags=(
            "emerald green art", "abstract woman art", "female portrait art",
            "gold line art", "frame tv art", "boho glam decor",
            "maximalist wall art", "green neutral decor", "4k tv artwork",
            "digital download", "figurative art", "modern woman art",
            "portrait bundle",
        ),
        materials=("Digital download", "JPG", "ZIP"),
        description=EMERALD_DESCRIPTION,
        image_dir="cover-premium-review",
        image_names=(
            "01-main-cover.jpg", "02-collection-overview.jpg",
            "03-frame-tv-preview.jpg", "04-whats-included.jpg",
            "05-how-to-display.jpg", "06-quality-compatibility.jpg",
            "07-framed-gallery-one.jpg", "08-framed-gallery-two.jpg",
            "09-framed-gallery-three.jpg", "10-framed-gallery-four.jpg",
        ),
        zip_names=("Emerald-Muse-10-Images.zip",),
        delivery_prefix="Emerald-Muse",
        delivery_count=10,
    ),
)


def api(method: str, url: str, headers: dict, *, expected=(200,), **kwargs):
    response = requests.request(method, url, headers=headers, timeout=300, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(
            f"Etsy {method} failed with HTTP {response.status_code}: "
            f"{response.text[:800]}"
        )
    return response


def validate_local(product: Product) -> tuple[list[Path], list[Path]]:
    if len(product.title) > 140 or "samsung" in product.title.lower():
        raise RuntimeError(f"{product.key}: invalid Etsy title")
    if (
        len(product.tags) != 13
        or len(set(product.tags)) != 13
        or any(len(tag) > 20 for tag in product.tags)
    ):
        raise RuntimeError(f"{product.key}: invalid Etsy tags")

    audit = product.root / "listing" / "final-audit-report.txt"
    audit_text = audit.read_text(encoding="utf-8")
    if "PASS" not in audit_text or "READY FOR" not in audit_text:
        raise RuntimeError(f"{product.key}: final audit is not PASS/ready")

    report = product.root / product.image_dir / "generation-report.txt"
    if "PASS" not in report.read_text(encoding="utf-8"):
        raise RuntimeError(f"{product.key}: listing-image report is not PASS")

    images = [product.root / product.image_dir / name for name in product.image_names]
    archives = [product.root / "customer-downloads" / name for name in product.zip_names]
    if not all(path.is_file() for path in images):
        raise RuntimeError(f"{product.key}: one or more listing images are missing")
    if not all(path.is_file() and 0 < path.stat().st_size < 20_000_000 for path in archives):
        raise RuntimeError(f"{product.key}: a ZIP is missing or at least 20 MB")

    for path in images:
        with Image.open(path) as image:
            if image.size != (2600, 2000) or image.mode != "RGB" or image.format != "JPEG":
                raise RuntimeError(f"{product.key}: invalid listing image {path.name}")

    members: list[str] = []
    for path in archives:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise RuntimeError(f"{product.key}: ZIP CRC failed at {bad}")
            members.extend(name.rsplit("/", 1)[-1] for name in archive.namelist())
    expected = [
        f"{product.delivery_prefix}-{number:03d}.jpg"
        for number in range(1, product.delivery_count + 1)
    ]
    if sorted(members) != sorted(expected) or len(members) != len(set(members)):
        raise RuntimeError(f"{product.key}: ZIP membership is incomplete or duplicated")
    return images, archives


def read_state(product: Product) -> dict:
    if product.state_path.exists():
        return json.loads(product.state_path.read_text(encoding="utf-8"))
    return {}


def load_general_log() -> list[dict]:
    if not GENERAL_LOG.exists():
        return []
    value = json.loads(GENERAL_LOG.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else []


def known_listing_id(product: Product) -> int | None:
    state = read_state(product)
    if state.get("listing_id"):
        return int(state["listing_id"])
    for row in reversed(load_general_log()):
        if row.get("bundle") == product.key and row.get("listing_id"):
            return int(row["listing_id"])
    return None


def persist(product: Product, listing_id: int, status: str, result: dict) -> None:
    review_url = f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}"
    state = {
        "bundle": product.key,
        "listing_id": listing_id,
        "status": status,
        "review_url": review_url,
        **result,
    }
    product.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    log = [row for row in load_general_log() if row.get("bundle") != product.key]
    log.append(state)
    GENERAL_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def list_matching(headers: dict, shop_id: str, product: Product) -> list[dict]:
    matches: list[dict] = []
    for state in ("draft", "active"):
        offset = 0
        while True:
            payload = api(
                "GET",
                f"{BASE}/shops/{shop_id}/listings",
                headers,
                params={"state": state, "limit": 100, "offset": offset},
            ).json()
            rows = payload.get("results", [])
            matches.extend(row for row in rows if row.get("title") == product.title)
            if len(rows) < 100:
                break
            offset += 100
    return matches


def remote_result(product: Product, listing_id: int, headers: dict, shop_id: str) -> dict:
    listing = api("GET", f"{BASE}/listings/{listing_id}", headers).json()
    image_rows = api(
        "GET", f"{BASE}/listings/{listing_id}/images", headers
    ).json().get("results", [])
    file_rows = api(
        "GET", f"{BASE}/shops/{shop_id}/listings/{listing_id}/files", headers
    ).json().get("results", [])
    price = listing.get("price") or {}
    remote_price = price.get("amount", 0) / price.get("divisor", 100)
    remote_tags = listing.get("tags") or []
    return {
        "state": listing.get("state"),
        "title": listing.get("title"),
        "title_matches": listing.get("title") == product.title,
        "price": remote_price,
        "price_matches": abs(remote_price - product.price) < 0.001,
        "tags": remote_tags,
        "tags_match": set(remote_tags) == set(product.tags) and len(remote_tags) == 13,
        "images_uploaded": len(image_rows),
        "files_uploaded": len(file_rows),
        "remote_file_names": sorted(row.get("filename", "") for row in file_rows),
        "shop_matches": str(listing.get("shop_id")) == shop_id,
    }


def create_listing(product: Product, headers: dict, shop_id: str, taxonomy_id: int) -> int:
    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    created = api(
        "POST",
        f"{BASE}/shops/{shop_id}/listings",
        upload_headers,
        expected=(201,),
        data={
            "title": product.title,
            "description": product.description,
            "price": product.price,
            "quantity": 999,
            "tags": ",".join(product.tags),
            "materials": ",".join(product.materials),
            "taxonomy_id": taxonomy_id,
            "who_made": "i_did",
            "is_supply": False,
            "when_made": "2020_2026",
            "is_digital": True,
            "type": "download",
        },
    ).json()
    return int(created["listing_id"])


def upload_remaining(
    product: Product,
    listing_id: int,
    images: list[Path],
    archives: list[Path],
    headers: dict,
    shop_id: str,
) -> None:
    upload_headers = dict(headers)
    upload_headers.pop("Content-Type", None)
    current = remote_result(product, listing_id, headers, shop_id)
    if current["state"] != "draft":
        raise RuntimeError(f"{product.key}: refusing to change non-draft listing {listing_id}")

    start_rank = int(current["images_uploaded"]) + 1
    for rank in range(start_rank, len(images) + 1):
        path = images[rank - 1]
        response = None
        for attempt in range(3):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/images",
                    headers=upload_headers,
                    files={"image": (path.name, stream, "image/jpeg")},
                    data={"rank": str(rank)},
                    timeout=300,
                )
            if response.status_code == 201:
                break
            time.sleep(1 + attempt)
        if response is None or response.status_code != 201:
            raise RuntimeError(
                f"{product.key}: image upload failed for {path.name}: "
                f"{getattr(response, 'text', '')[:500]}"
            )
        persist(product, listing_id, "INCOMPLETE_DRAFT", {"stage": f"image_{rank}_uploaded"})

    current = remote_result(product, listing_id, headers, shop_id)
    existing_names = set(current["remote_file_names"])
    for rank, path in enumerate(archives, 1):
        if path.name in existing_names:
            continue
        response = None
        for attempt in range(3):
            with path.open("rb") as stream:
                response = requests.post(
                    f"{BASE}/shops/{shop_id}/listings/{listing_id}/files",
                    headers=upload_headers,
                    files={"file": (path.name, stream, "application/zip")},
                    data={"name": path.name, "rank": str(rank)},
                    timeout=360,
                )
            if response.status_code == 201:
                break
            time.sleep(1 + attempt)
        if response is None or response.status_code != 201:
            raise RuntimeError(
                f"{product.key}: file upload failed for {path.name}: "
                f"{getattr(response, 'text', '')[:500]}"
            )
        persist(product, listing_id, "INCOMPLETE_DRAFT", {"stage": f"file_{rank}_uploaded"})


def process_product(
    product: Product, headers: dict, shop_id: str, taxonomy_id: int
) -> dict:
    images, archives = validate_local(product)
    listing_id = known_listing_id(product)
    if listing_id is None:
        matches = list_matching(headers, shop_id, product)
        if len(matches) > 1:
            raise RuntimeError(f"{product.key}: multiple remote listings have the exact title")
        if matches:
            if matches[0].get("state") != "draft":
                raise RuntimeError(f"{product.key}: an active exact-title listing already exists")
            listing_id = int(matches[0]["listing_id"])
        else:
            listing_id = create_listing(product, headers, shop_id, taxonomy_id)
            persist(product, listing_id, "INCOMPLETE_DRAFT", {"stage": "listing_created"})

    upload_remaining(product, listing_id, images, archives, headers, shop_id)
    result = remote_result(product, listing_id, headers, shop_id)
    passed = (
        result["state"] == "draft"
        and result["shop_matches"]
        and result["title_matches"]
        and result["price_matches"]
        and result["tags_match"]
        and result["images_uploaded"] == len(images)
        and result["files_uploaded"] == len(archives)
        and result["remote_file_names"] == sorted(product.zip_names)
    )
    status = "DRAFT_VERIFIED" if passed else "INCOMPLETE_DRAFT"
    persist(product, listing_id, status, result)
    if not passed:
        raise RuntimeError(f"{product.key}: remote verification failed: {result}")
    return {"bundle": product.key, "listing_id": listing_id, "status": status, **result}


def main() -> None:
    load_dotenv(REPO / ".env")
    shop_id = str(os.environ["ETSY_SHOP_ID"])
    taxonomy_id = int(os.environ["ETSY_TAXONOMY_ID"])
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
    if str(me.get("shop_id")) != shop_id or shop.get("shop_name") != "EverframeDigital":
        raise RuntimeError("Authenticated Etsy identity is not EverframeDigital")

    results = []
    for product in PRODUCT_CONFIGS:
        results.append(process_product(product, headers, shop_id, taxonomy_id))
    print(json.dumps({"shop": shop.get("shop_name"), "results": results}, indent=2))


if __name__ == "__main__":
    main()
