from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KeywordSource(str, Enum):
    GENERATED = "Generated keyword"
    AUTOCOMPLETE = "Autocomplete keyword"
    MARKETPLACE = "Marketplace Insights keyword"
    OBSERVED = "Observed listing keyword"
    AI = "AI suggestion"
    SEED = "Seed keyword"


class DigitalClassificationSource(str, Enum):
    CONFIRMED = "ConfirmedProviderFlag"
    HEURISTIC = "Heuristic"
    UNKNOWN = "Unknown"


class ResearchRequest(BaseModel):
    seed_keywords: list[str] = Field(min_length=1, max_length=20)
    target_marketplace: str = "Etsy US"
    product_type: str = "digital art"
    digital_only: bool = True
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    listings_to_analyze: int = Field(default=20, ge=1, le=100)
    enrichment_mode: Literal["search_only", "top_10", "top_20"] = "search_only"
    country: str | None = "US"
    customer_or_style: str | None = None
    negative_keywords: list[str] = []
    include_generated_keywords: bool = True
    max_keywords: int = Field(default=3, ge=1, le=10)
    use_mock: bool = False
    score_weights: dict[str, float] | None = None

    @field_validator("seed_keywords")
    @classmethod
    def validate_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(v.strip().split()) for v in values if v.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty seed keyword is required")
        if any(len(v) > 120 for v in cleaned):
            raise ValueError("Keywords must be 120 characters or fewer")
        return cleaned

    @model_validator(mode="after")
    def validate_prices(self):
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("Minimum price cannot exceed maximum price")
        return self


class MarketplaceInsightInput(BaseModel):
    keyword: str = Field(min_length=1, max_length=120)
    searches_last_30_days: int = Field(ge=0)
    listings_last_30_days: int = Field(ge=0)
    trend_direction: str | None = Field(default=None, max_length=40)
    captured_at: str
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("captured_at")
    @classmethod
    def valid_date(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("CapturedAt must be an ISO date or datetime") from exc
        return value


class NormalizedListing(BaseModel):
    listing_id: str
    title: str | None = None
    url: str | None = None
    price: float | None = None
    price_usd: float | None = None
    currency: str | None = None
    favorites_count: int | None = None
    tags: list[str] = []
    categories: list[str] = []
    shop_id: str | None = None
    shop_name: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    is_active: bool | None = None
    is_in_stock: bool | None = None
    is_sold_out: bool | None = None
    is_digital: bool | None = None
    digital_classification_source: DigitalClassificationSource = DigitalClassificationSource.UNKNOWN
    is_made_to_order: bool | None = None
    is_bestseller: bool | None = None
    is_top_rated: bool | None = None
    is_featured: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None
    retrieved_at: str = Field(default_factory=utc_now)
    source_provider: str
    source_keyword: str
    detail_enriched: bool = False
    raw_fields_available: list[str] = []


class ScoreResult(BaseModel):
    evidence_score: float
    opportunity_score: float
    score_label: str
    warning: str | None
    components: dict[str, float]
    weights: dict[str, float]
    calculation: list[dict[str, Any]]


class ResearchProgress(BaseModel):
    keywords_total: int = 0
    keywords_processed: int = 0
    searches_completed: int = 0
    details_fetched: int = 0
    cache_hits: int = 0
    api_calls_made: int = 0
    errors: list[str] = []
    partial_results: bool = False


class AiAnalysis(BaseModel):
    summary: str
    opportunities: list[dict[str, Any]]
    risks: list[str]
    recommendedNextResearch: list[str]
    productRecommendations: list[dict[str, Any]]
