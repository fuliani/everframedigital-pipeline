"""
Parser for EverframeDigital/Products/<Bundle>/listing/product-details.txt
into the fields needed to create an Etsy draft listing.

The file format is produced by the audit/report pipeline in this repo (see
EverframeDigital/etsy-readiness-report.md). This parser is intentionally
strict: it raises rather than silently defaulting, because a wrong price or
truncated description going to Etsy is worse than a crash.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ProductListing:
    bundle_dir: Path
    product_name: str
    title: str
    full_description: str
    tags: List[str]
    price: float
    image_count: int
    zip_filenames: List[str]
    qc_status: str
    missing_items: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)

    @property
    def cover_dir(self) -> Path:
        return self.bundle_dir / "cover"

    @property
    def downloads_dir(self) -> Path:
        return self.bundle_dir / "customer-downloads"

    def cover_images(self) -> List[Path]:
        """Cover images in filename order (01-, 02-, ...), max 10 (Etsy limit)."""
        imgs = sorted(
            p for p in self.cover_dir.glob("*")
            if p.suffix.lower() in (".jpg", ".jpeg", ".png")
        )
        if len(imgs) > 10:
            raise ValueError(
                f"{self.bundle_dir.name}: {len(imgs)} cover images found, "
                "Etsy allows a max of 10 listing photos."
            )
        return imgs

    def zip_paths(self) -> List[Path]:
        paths = [self.downloads_dir / z for z in self.zip_filenames]
        missing = [p for p in paths if not p.exists()]
        if missing:
            raise FileNotFoundError(f"Missing ZIP file(s): {missing}")
        if len(paths) > 5:
            raise ValueError(
                f"{self.bundle_dir.name}: {len(paths)} ZIP files, "
                "Etsy allows a max of 5 digital files per listing."
            )
        return paths


def _section(text: str, header: str) -> str:
    """Extract the body of a 'HEADER:\\n...' section up to the next
    ALL-CAPS header line or end of file."""
    pattern = rf"^{re.escape(header)}:\s*\n(.*?)(?=\n[A-Z][A-Z \-]{{2,}}:\s*\n|\Z)"
    m = re.search(pattern, text, re.M | re.S)
    if not m:
        raise ValueError(f"Section '{header}' not found in product-details.txt")
    return m.group(1).strip()


def parse_product_details(path: Path) -> ProductListing:
    text = path.read_text(encoding="utf-8")
    bundle_dir = path.parent.parent  # listing/product-details.txt -> Bundle/

    product_name = _section(text, "PRODUCT NAME")

    title_block = _section(text, "ETSY TITLE")
    title = title_block.splitlines()[0].strip()
    if len(title) > 140:
        raise ValueError(f"Title is {len(title)} chars, exceeds Etsy's 140-char limit.")

    full_description = _section(text, "FULL DESCRIPTION")
    # AI disclosure sits between FULL DESCRIPTION and WHAT IS INCLUDED as its
    # own paragraph in this project's report format; fold it into the
    # description body Etsy stores, since Etsy has no separate field for it.
    m = re.search(
        r"\n\n(AI DISCLOSURE.*?)\n\nWHAT IS INCLUDED:", text, re.S
    )
    if m:
        full_description = f"{full_description}\n\n{m.group(1).strip()}"
    # Append the customer-facing sections that belong in the Etsy description.
    for header in ("HOW TO DOWNLOAD", "HOW TO USE", "IMPORTANT", "LICENSE"):
        try:
            full_description += f"\n\n{header}:\n{_section(text, header)}"
        except ValueError:
            pass

    tags_block = _section(text, "TAGS")
    tags_line = tags_block.splitlines()[0]
    tags = [t.strip() for t in tags_line.split(",") if t.strip()]
    if len(tags) != 13:
        raise ValueError(f"Expected 13 tags, found {len(tags)}: {tags}")
    long_tags = [t for t in tags if len(t) > 20]
    if long_tags:
        raise ValueError(f"Tag(s) exceed Etsy's 20-char limit: {long_tags}")

    price_block = _section(text, "SUGGESTED PRICE")
    price_match = re.search(r"[\d.]+", price_block)
    if not price_match:
        raise ValueError(f"Could not parse price from: {price_block!r}")
    price = float(price_match.group())

    image_count = int(_section(text, "IMAGE COUNT").strip())

    files_block = _section(text, "CUSTOMER DOWNLOAD FILES")
    zip_filenames = [
        line.strip("- ").split(" (")[0].strip()
        for line in files_block.splitlines()
        if line.strip().startswith("-")
    ]
    if not zip_filenames:
        raise ValueError("No customer download ZIP files listed.")

    qc_status = _section(text, "QUALITY-CONTROL STATUS").strip()

    missing_block = _section(text, "MISSING ITEMS")
    missing_items = [
        line.strip("- ").strip()
        for line in missing_block.splitlines()
        if line.strip().startswith("-")
    ]
    missing_items = [m for m in missing_items if m.lower() not in ("none.", "none")]

    materials_block = _section(text, "MATERIALS")
    materials = [m.strip() for m in materials_block.split(",") if m.strip()]

    return ProductListing(
        bundle_dir=bundle_dir,
        product_name=product_name,
        title=title,
        full_description=full_description,
        tags=tags,
        price=price,
        image_count=image_count,
        zip_filenames=zip_filenames,
        qc_status=qc_status,
        missing_items=missing_items,
        materials=materials,
    )


def find_all_products(everframe_root: Path) -> List[Path]:
    """Return every product-details.txt under EverframeDigital/Products/."""
    return sorted(everframe_root.glob("Products/*/listing/product-details.txt"))
