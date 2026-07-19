from etsy_research.analysis import (
    RuleBasedOpportunityScoringService, analyze_competitors, dedupe_keywords,
    filter_listings, normalize_keyword,
)
from etsy_research.models import DigitalClassificationSource, NormalizedListing


def listing(**kwargs):
    values={"listing_id":"1","title":"Digital download Frame TV art","price_usd":9.0,"favorites_count":20,"tags":["instant download"],"categories":["Digital Prints"],"shop_name":"Shop","is_digital":True,"digital_classification_source":DigitalClassificationSource.CONFIRMED,"is_bestseller":False,"source_provider":"fixture","source_keyword":"frame tv art","detail_enriched":True}
    values.update(kwargs);return NormalizedListing(**values)


def test_keyword_normalization_and_case_insensitive_deduplication():
    assert normalize_keyword("  Frame-TV ART!! ")=="frame-tv art"
    result=dedupe_keywords([("Frame TV Art","Seed keyword"),(" frame   tv art ","Generated keyword"),("Japandi Art","Generated keyword")])
    assert len(result)==2


def test_digital_filter_and_negative_keywords():
    rows=[listing(),listing(listing_id="2",title="Physical canvas",is_digital=False,tags=[])]
    assert [x.listing_id for x in filter_listings(rows,True,None,None,[])]==["1"]
    assert filter_listings(rows,False,None,None,["canvas"])==[rows[0]]


def test_competitor_metrics_do_not_infer_missing_zero():
    metrics=analyze_competitors([listing(),listing(listing_id="2",price_usd=None,price=None,favorites_count=None,shop_name="Other")],1405)
    assert metrics["median_price"]==9.0
    assert metrics["median_favorites"]==20
    assert metrics["observed_result_count"]==1405


def test_duplicate_titles_and_dimension_signals_are_explicit():
    rows=[listing(title="Neutral coastal landscape bundle",tags=["blue","coastal"]),listing(listing_id="2",title="Neutral coastal landscape bundle",tags=["blue","coastal"])]
    metrics=analyze_competitors(rows,100)
    assert metrics["duplicate_title_percentage"]==50.0
    assert metrics["common_styles"][0][0]=="coastal"
    assert "blue" in dict(metrics["common_colors"])


def test_provisional_score_has_warning_and_explanation():
    score=RuleBasedOpportunityScoringService().score(analyze_competitors([listing()],1000),None)
    assert score["score_label"]=="Provisional Opportunity Score"
    assert "does not include verified Etsy search volume" in score["warning"]
    assert round(sum(x["contribution"] for x in score["calculation"]),1)==score["opportunity_score"]


def test_marketplace_insight_changes_score_type():
    metrics=analyze_competitors([listing()],1000)
    insight={"searches_last_30_days":500,"listings_last_30_days":100}
    score=RuleBasedOpportunityScoringService().score(metrics,insight)
    assert score["score_label"]=="Opportunity Score"
    assert score["warning"] is None


def test_custom_score_weights_are_used():
    metrics=analyze_competitors([listing()],1000)
    score=RuleBasedOpportunityScoringService().score(metrics,None,{"buyer_demand":100,"evidence_quality":0})
    assert score["weights"]["buyer_demand"]==100
