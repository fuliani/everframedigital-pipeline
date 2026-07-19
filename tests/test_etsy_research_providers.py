import json

import pytest

from etsy_research.models import AiAnalysis, DigitalClassificationSource
from etsy_research.providers import FixtureEtsyResearchProvider, normalize_listing


def test_fixture_search_and_detail_parse():
    provider=FixtureEtsyResearchProvider()
    result=provider.search("japandi")
    assert result["result_count"]==1405
    item=normalize_listing(provider.listing("1001"),"japandi",provider.name,True)
    assert item.is_digital is True
    assert item.digital_classification_source==DigitalClassificationSource.CONFIRMED
    assert item.shop_name=="QuietCanvas"


def test_missing_fields_remain_none_not_zero():
    item=normalize_listing({"listing_id":"x","name":"Unknown object"},"test","fixture")
    assert item.price is None and item.favorites_count is None and item.is_digital is None
    assert item.digital_classification_source==DigitalClassificationSource.UNKNOWN


def test_digital_heuristic_is_labeled():
    item=normalize_listing({"listing_id":"x","name":"Printable PDF instant download"},"test","fixture")
    assert item.is_digital is True
    assert item.digital_classification_source==DigitalClassificationSource.HEURISTIC


def test_provider_schema_change_safe_for_non_list_tags():
    item=normalize_listing({"listing_id":"x","name":"Art","tags":None,"flags":None},"test","fixture")
    assert item.tags==[]


def test_ai_json_schema_validation_rejects_incomplete_output():
    valid=AiAnalysis.model_validate({"summary":"Evidence only","opportunities":[],"risks":[],"recommendedNextResearch":[],"productRecommendations":[]})
    assert valid.summary=="Evidence only"
    with pytest.raises(Exception):
        AiAnalysis.model_validate({"summary":"missing required arrays"})
