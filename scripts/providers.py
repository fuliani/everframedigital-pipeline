"""
Image-generation backends. Each provider function takes a prompt and a
quality level ("standard" or "hd") and returns raw image bytes (PNG/JPEG).
"""

import base64
import time

import requests

# Rough per-image cost estimates in USD, for the printed cost summary only.
PRICE_PER_IMAGE = {
    "dalle3": {"standard": 0.08, "hd": 0.12},
    "gemini": {"standard": 0.02, "hd": 0.04},
    "falai": {"standard": 0.005, "hd": 0.01},  # Z-Image-Turbo, $0.005/megapixel
    "falai-hq": {"standard": 0.075, "hd": 0.075},  # flux/dev, $0.025/megapixel @ ~3MP
}

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


def generate_dalle3(client, prompt: str, size: str, quality: str) -> bytes:
    from openai import RateLimitError, APIError

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
                response_format="b64_json",
            )
            return base64.b64decode(response.data[0].b64_json)
        except RateLimitError:
            if attempt == MAX_RETRIES:
                raise
            wait = RETRY_BACKOFF_SECONDS * attempt
            print(f"  rate limited, retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
        except APIError as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  API error ({e}), retrying (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(RETRY_BACKOFF_SECONDS)


def generate_falai(client, prompt: str, size_config: dict, quality: str) -> bytes:
    import fal_client

    width, height = (1920, 1080) if quality == "hd" else (1280, 720)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = fal_client.subscribe(
                "fal-ai/z-image/turbo",
                arguments={
                    "prompt": prompt,
                    "image_size": {"width": width, "height": height},
                    "num_images": 1,
                    "output_format": "png",
                },
            )
            image_url = result["images"][0]["url"]
            resp = requests.get(image_url, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  API error ({e}), retrying (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(RETRY_BACKOFF_SECONDS)


def generate_falai_hq(client, prompt: str, size_config: dict, quality: str) -> bytes:
    """Higher-quality Fal.ai tier (flux/dev) - more atmosphere/depth than
    z-image/turbo. Use for bundles where visual quality matters more than cost."""
    import fal_client

    width, height = (1920, 1080) if quality == "hd" else (1280, 720)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = fal_client.subscribe(
                "fal-ai/flux/dev",
                arguments={
                    "prompt": prompt,
                    "image_size": {"width": width, "height": height},
                    "num_images": 1,
                    "output_format": "png",
                },
            )
            image_url = result["images"][0]["url"]
            resp = requests.get(image_url, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  API error ({e}), retrying (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(RETRY_BACKOFF_SECONDS)


def generate_gemini(client, prompt: str, size_config: dict, quality: str) -> bytes:
    image_size = "4K" if quality == "hd" else "2K"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            interaction = client.interactions.create(
                model="gemini-3.1-flash-image",
                input=prompt,
                response_format={
                    "type": "image",
                    "mime_type": "image/jpeg",
                    "aspect_ratio": size_config.get("aspect_ratio", "16:9"),
                    "image_size": image_size,
                },
            )
            return base64.b64decode(interaction.output_image.data)
        except Exception as e:
            error_name = type(e).__name__
            if "RateLimit" in error_name or "ResourceExhausted" in error_name:
                if attempt == MAX_RETRIES:
                    raise
                wait = RETRY_BACKOFF_SECONDS * attempt
                print(f"  rate limited, retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            if attempt == MAX_RETRIES:
                raise
            print(f"  API error ({e}), retrying (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(RETRY_BACKOFF_SECONDS)
