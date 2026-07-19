from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    omkar_api_key: str = os.getenv("OMKAR_API_KEY", "").strip()
    omkar_base_url: str = os.getenv(
        "OMKAR_API_BASE_URL", "https://etsy-scraper.omkar.cloud"
    ).rstrip("/")
    ai_provider: str = os.getenv("AI_PROVIDER", "").strip().lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    cache_hours: int = _int("ETSY_RESEARCH_CACHE_HOURS", 24)
    max_details: int = _int("ETSY_MAX_DETAIL_REQUESTS_PER_RESEARCH", 20)
    timeout_seconds: int = _int("ETSY_REQUEST_TIMEOUT_SECONDS", 30)
    database_path: Path = Path(
        os.getenv(
            "ETSY_RESEARCH_DB_PATH",
            str(ROOT / "etsy_research" / "data" / "etsy_research.sqlite3"),
        )
    )

    @property
    def live_provider_configured(self) -> bool:
        return bool(self.omkar_api_key)

    @property
    def ai_configured(self) -> bool:
        return self.ai_provider == "openai" and bool(self.openai_api_key)
