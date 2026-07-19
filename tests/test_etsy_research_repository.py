import csv
import io

import pytest

from etsy_research.database import ResearchRepository
from etsy_research.models import MarketplaceInsightInput


def test_cache_behavior(tmp_path):
    repo=ResearchRepository(tmp_path/"research.sqlite3")
    repo.cache_set("key","provider",{"ok":True},24)
    assert repo.cache_get("key")=={"ok":True}


def test_marketplace_insight_validation_and_duplicate(tmp_path):
    repo=ResearchRepository(tmp_path/"research.sqlite3")
    model=MarketplaceInsightInput(keyword="Japandi",searches_last_30_days=5,listings_last_30_days=10,captured_at="2026-07-18")
    repo.add_insight(model)
    assert repo.get_latest_insight(" japandi ")["searches_last_30_days"]==5
    with pytest.raises(Exception):repo.add_insight(model)


def test_negative_insights_rejected():
    with pytest.raises(Exception): MarketplaceInsightInput(keyword="x",searches_last_30_days=-1,listings_last_30_days=0,captured_at="2026-07-18")
