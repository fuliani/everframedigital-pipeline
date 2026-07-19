"""Create or verify the Japandi-Minimalist Etsy draft only.

This reuses the already-audited, draft-only Etsy publishing workflow while
restricting all product facts and assets to Japandi-Minimalist. It never
activates or publishes the listing.
"""

from pathlib import Path

from scripts.etsy_publish import create_all_seasons_100_draft as publisher


REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "EverframeDigital" / "Products" / "Japandi-Minimalist"

publisher.PRODUCT = PRODUCT
publisher.STATE_PATH = PRODUCT / "listing" / "etsy-draft-state.json"
publisher.GENERAL_LOG = REPO / "EverframeDigital" / "etsy-draft-log.json"
publisher.BUNDLE = "Japandi-Minimalist"
publisher.TITLE = (
    "100 Japandi Minimalist Frame TV Art Bundle, Neutral 4K Digital Art, "
    "Wabi Sabi Scandinavian Instant Download"
)
publisher.PRICE = 8.99
publisher.TAGS = [
    "japandi tv art",
    "minimalist tv art",
    "neutral frame art",
    "japandi wall art",
    "scandinavian art",
    "wabi sabi decor",
    "neutral digital art",
    "frame tv download",
    "minimalist bundle",
    "earth tone art",
    "zen tv artwork",
    "4k digital art",
    "instant download",
]
publisher.MATERIALS = ["JPG", "digital download", "ZIP files", "4K artwork"]
publisher.DESCRIPTION = """Bring a quiet Japanese–Scandinavian mood to your screen with 100 coordinated Japandi minimalist artworks. The collection blends warm oatmeal, clay, sage, charcoal, sand, and warm-white tones with negative space, natural forms, still lifes, gentle landscapes, organic abstractions, and architectural studies.

WHAT IS INCLUDED
• 100 unique high-resolution JPG artworks
• 3840 × 2160 pixels (true 4K UHD)
• 16:9 landscape format
• Five ZIP downloads containing 20 consecutive images each
• Instant digital download; no physical item will be shipped

HOW TO DOWNLOAD
After purchase, open your Etsy Purchases page and download all five ZIP files. A computer is the easiest way to extract the archives. Unzip every file to access Japandi-Minimalist-001.jpg through Japandi-Minimalist-100.jpg.

HOW TO DISPLAY
Choose an artwork and transfer it to a compatible Frame TV using the SmartThings app or another supported device method. Open Art Mode, add the image, and adjust the display to your preference. These standard 16:9 JPGs are also suitable for compatible televisions, monitors, tablets, screensavers, and digital displays.

COMPATIBILITY NOTE
Device features and transfer methods vary. Screen colors may differ slightly depending on the display and its settings.

IMPORTANT
This is an instant digital download. No physical item will be shipped. Digital purchases are non-refundable and all sales are final.

AI DISCLOSURE
This artwork was created with AI image-generation tools and curated, reviewed, and prepared by EverframeDigital. The artwork is 100% AI-generated with human curation and review only. No hand painting, handmade creation, or manual artistic editing is claimed.

LICENSE
Personal use only. Files may not be resold, shared, redistributed, sublicensed, or used commercially."""
publisher.IMAGE_NAMES = [
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
publisher.ZIP_NAMES = [
    f"Japandi-Minimalist-100-Images-Part{i}of5.zip" for i in range(1, 6)
]


if __name__ == "__main__":
    publisher.main()
