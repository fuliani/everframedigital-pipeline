from __future__ import annotations

import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import requests

from .config import Settings
from .database import ResearchRepository
from .models import AiAnalysis, DigitalClassificationSource, NormalizedListing, utc_now


class EtsyResearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, keyword: str, run_id: str | None = None) -> dict: ...

    @abstractmethod
    def listing(self, listing_id: str, run_id: str | None = None) -> dict: ...


class KeywordSuggestionProvider(ABC):
    @abstractmethod
    def suggest(self, seed: str, context: str | None = None) -> list[str]: ...


class MarketplaceInsightsProvider(ABC):
    @abstractmethod
    def latest(self, keyword: str) -> dict | None: ...


class OpportunityScoringService(ABC):
    @abstractmethod
    def score(self, metrics: dict, insight: dict | None, weights: dict | None = None) -> dict: ...


class NicheRecommendationService(ABC):
    @abstractmethod
    def recommend(self, cluster: dict, context: dict) -> dict: ...


class AiAnalysisProvider(ABC):
    @abstractmethod
    def analyze(self, payload: dict) -> AiAnalysis: ...


class AiNicheRecommendationService(NicheRecommendationService):
    """Optional schema-validated AI recommendation adapter."""

    def __init__(self, provider: AiAnalysisProvider):
        self.provider = provider

    def recommend(self, cluster: dict, context: dict) -> dict:
        analysis = self.provider.analyze({
            "cluster": cluster,
            "normalized_evidence": context,
            "instruction": "Return recommendations grounded only in supplied evidence; never invent marketplace measurements.",
        })
        if not analysis.productRecommendations:
            raise ValueError("AI returned no product recommendations")
        recommendation = dict(analysis.productRecommendations[0])
        recommendation["source_type"] = "AI recommendation"
        return recommendation


class OmkarEtsyResearchProvider(EtsyResearchProvider):
    name = "Omkar Etsy Scraper API"

    def __init__(self, settings: Settings, repository: ResearchRepository):
        if not settings.omkar_api_key:
            raise ValueError("OMKAR_API_KEY is not configured")
        self.settings = settings
        self.repo = repository
        self.session = requests.Session()
        self.session.headers.update({"API-Key": settings.omkar_api_key, "Accept": "application/json"})
        self.stats = {"api_calls": 0, "cache_hits": 0, "errors": 0}

    def _get(self, path: str, params: dict, run_id: str | None) -> dict:
        clean = "&".join(f"{k}={params[k]}" for k in sorted(params))
        key = hashlib.sha256(f"{path}?{clean}".encode()).hexdigest()
        cached = self.repo.cache_get(key)
        if cached is not None:
            self.stats["cache_hits"] += 1
            self.repo.log_request(run_id, self.name, path, key, 200, True)
            return cached
        url = f"{self.settings.omkar_base_url}{path}"
        last_error = None
        for attempt in range(3):
            try:
                self.stats["api_calls"] += 1
                response = self.session.get(url, params=params, timeout=self.settings.timeout_seconds)
                if response.status_code == 429:
                    wait = min(float(response.headers.get("Retry-After", 2 ** attempt)), 10)
                    last_error = f"HTTP 429 rate limited; retry after {wait:g}s"
                    if attempt < 2:
                        time.sleep(wait)
                        continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Provider returned a non-object JSON response")
                self.repo.cache_set(key, self.name, data, self.settings.cache_hours)
                self.repo.log_request(run_id, self.name, path, key, response.status_code, False)
                return data
            except (requests.RequestException, ValueError) as exc:
                last_error = str(exc)
                if attempt < 2 and not (isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (400, 401, 403)):
                    time.sleep(min(2 ** attempt, 4))
                    continue
                break
        self.stats["errors"] += 1
        self.repo.log_request(run_id, self.name, path, key, None, False, last_error)
        raise RuntimeError(f"Omkar request failed for {path}: {last_error}")

    def search(self, keyword: str, run_id: str | None = None) -> dict:
        return self._get("/etsy/search", {"keyword": keyword}, run_id)

    def listing(self, listing_id: str, run_id: str | None = None) -> dict:
        return self._get("/etsy/listing", {"listing_id": str(listing_id)}, run_id)


class FixtureEtsyResearchProvider(EtsyResearchProvider):
    name = "Saved Omkar fixture"

    def __init__(self, fixture_dir: Path | None = None):
        self.fixture_dir = fixture_dir or Path(__file__).parent / "fixtures"
        self.stats = {"api_calls": 0, "cache_hits": 0, "errors": 0}
        self._search = json.loads((self.fixture_dir / "omkar_search.json").read_text(encoding="utf-8"))
        self._details = json.loads((self.fixture_dir / "omkar_details.json").read_text(encoding="utf-8"))

    def search(self, keyword: str, run_id: str | None = None) -> dict:
        data = json.loads(json.dumps(self._search))
        data["fixture_keyword"] = keyword
        return data

    def listing(self, listing_id: str, run_id: str | None = None) -> dict:
        return self._details.get(str(listing_id), {"listing_id": str(listing_id)})


class DeterministicKeywordSuggestionProvider(KeywordSuggestionProvider):
    modifiers = [
        "instant download", "large bundle", "neutral decor", "living room",
        "seasonal collection", "16:9 digital art", "100 artwork bundle",
        "minimalist", "vintage", "coastal",
    ]

    @staticmethod
    def normalize(value: str) -> str:
        value = re.sub(r"[^\w\s&'-]", " ", value.lower())
        return " ".join(value.split())

    def suggest(self, seed: str, context: str | None = None) -> list[str]:
        base = self.normalize(seed)
        context = self.normalize(context or "")
        candidates = [
            f"neutral {base}", f"{base} instant download", f"100 {base} bundle",
            f"minimalist {base}", f"{base} for living room", f"seasonal {base}",
            f"{context} {base}" if context else "",
        ]
        seen, output = set(), []
        for item in candidates:
            item = self.normalize(item)
            if item and item not in seen and item != base:
                seen.add(item); output.append(item)
        return output


class ManualMarketplaceInsightsProvider(MarketplaceInsightsProvider):
    def __init__(self, repository: ResearchRepository):
        self.repository = repository

    def latest(self, keyword: str) -> dict | None:
        return self.repository.get_latest_insight(keyword)


DIGITAL_TERMS = re.compile(
    r"\b(digital download|instant download|printable|digital file|jpe?g|png|pdf|frame tv art|samsung frame|downloadable)\b",
    re.I,
)


def normalize_listing(raw: dict, keyword: str, provider: str, enriched: bool = False) -> NormalizedListing:
    flags = raw.get("flags") if isinstance(raw.get("flags"), dict) else {}
    shop = raw.get("shop") if isinstance(raw.get("shop"), dict) else {}
    images = raw.get("images") if isinstance(raw.get("images"), list) else []
    title = raw.get("name") or raw.get("title")
    explicit = flags.get("digital") if "digital" in flags else raw.get("is_digital")
    text = " ".join([title or "", *[str(t) for t in raw.get("tags") or []], *[str(c) for c in raw.get("categories") or []]])
    if isinstance(explicit, bool):
        is_digital = explicit
        source = DigitalClassificationSource.CONFIRMED
    elif DIGITAL_TERMS.search(text):
        is_digital = True
        source = DigitalClassificationSource.HEURISTIC
    else:
        is_digital = None
        source = DigitalClassificationSource.UNKNOWN
    image_url = raw.get("image_url") or (images[0].get("url") if images and isinstance(images[0], dict) else None)
    thumbnail = raw.get("thumbnail_url") or (images[0].get("thumbnail_url") if images and isinstance(images[0], dict) else image_url)
    available = [key for key, value in raw.items() if value is not None]
    return NormalizedListing(
        listing_id=str(raw.get("listing_id") or raw.get("id") or ""),
        title=title, url=raw.get("url"), price=_float(raw.get("price")),
        price_usd=_float(raw.get("price_usd")), currency=raw.get("currency"),
        favorites_count=_int_or_none(raw.get("favorites_count")),
        tags=[str(v) for v in raw.get("tags") or []], categories=[str(v) for v in raw.get("categories") or []],
        shop_id=str(shop.get("shop_id") or raw.get("shop_id")) if (shop.get("shop_id") or raw.get("shop_id")) is not None else None,
        shop_name=shop.get("name") or raw.get("shop_name"), image_url=image_url, thumbnail_url=thumbnail,
        is_active=_bool(flags, raw, "active"), is_in_stock=_bool(flags, raw, "in_stock"),
        is_sold_out=_bool(flags, raw, "sold_out"), is_digital=is_digital,
        digital_classification_source=source, is_made_to_order=_bool(flags, raw, "made_to_order"),
        is_bestseller=_bool(flags, raw, "bestseller"), is_top_rated=_bool(flags, raw, "top_rated"),
        is_featured=_bool(flags, raw, "featured"), created_at=raw.get("created_at"), updated_at=raw.get("updated_at"),
        retrieved_at=utc_now(), source_provider=provider, source_keyword=keyword,
        detail_enriched=enriched, raw_fields_available=available,
    )


def merge_listing(search_item: dict, detail: dict) -> dict:
    merged = dict(search_item)
    for key, value in detail.items():
        if value is not None:
            merged[key] = value
    return merged


def _float(value: Any) -> float | None:
    try: return float(value) if value is not None else None
    except (TypeError, ValueError): return None


def _int_or_none(value: Any) -> int | None:
    try: return int(value) if value is not None else None
    except (TypeError, ValueError): return None


def _bool(flags: dict, raw: dict, key: str) -> bool | None:
    value = flags.get(key) if key in flags else raw.get(f"is_{key}")
    return value if isinstance(value, bool) else None


class OpenAiAnalysisProvider(AiAnalysisProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def analyze(self, payload: dict) -> AiAnalysis:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        schema = AiAnalysis.model_json_schema()
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "system", "content": "Analyze only the supplied evidence. Never invent searches, sales, revenue, conversions, or competition counts."}, {"role": "user", "content": json.dumps(payload)}],
            text={"format": {"type": "json_schema", "name": "etsy_analysis", "schema": schema, "strict": True}},
        )
        return AiAnalysis.model_validate_json(response.output_text)
