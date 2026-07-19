from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import NormalizedListing
from .providers import NicheRecommendationService, OpportunityScoringService

STOP = {"the","and","for","with","from","this","that","your","art","digital","download","print","wall","tv","frame","set","of","a","to","in","on"}
DIMENSIONS = {
    "style": ["minimalist","vintage","japandi","modern","abstract","farmhouse","boho","coastal","southwest","dark academia"],
    "subject": ["landscape","botanical","desert","mountain","ocean","flower","christian","scripture","animal","city"],
    "season": ["spring","summer","fall","autumn","winter","seasonal"],
    "holiday": ["christmas","halloween","easter","valentine","thanksgiving"],
    "room": ["living room","bedroom","nursery","office","kitchen"],
    "color": ["neutral","sage","blue","pink","black","white","terracotta","beige"],
    "format": ["printable","bundle","collection","gallery","16:9","4k"],
    "occasion": ["wedding","housewarming","birthday","memorial","gift","new home"],
}


def normalize_keyword(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s&'-]", " ", value.lower()).split())


def dedupe_keywords(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen, out = set(), []
    for keyword, source in items:
        normalized = normalize_keyword(keyword)
        if normalized and normalized not in seen:
            seen.add(normalized); out.append((" ".join(keyword.split()), source))
    return out


def filter_listings(listings: list[NormalizedListing], digital_only: bool, min_price: float | None, max_price: float | None, negatives: list[str]) -> list[NormalizedListing]:
    negatives = [normalize_keyword(v) for v in negatives]
    result = []
    for item in listings:
        text = normalize_keyword(" ".join([item.title or "", *item.tags]))
        if any(n and n in text for n in negatives): continue
        if digital_only and item.is_digital is not True: continue
        price = item.price_usd if item.price_usd is not None else item.price
        if min_price is not None and price is not None and price < min_price: continue
        if max_price is not None and price is not None and price > max_price: continue
        result.append(item)
    return result


def analyze_competitors(listings: list[NormalizedListing], observed_result_count: int | None = None) -> dict[str, Any]:
    prices = [v for x in listings if (v := x.price_usd if x.price_usd is not None else x.price) is not None]
    favorites = [x.favorites_count for x in listings if x.favorites_count is not None]
    digital = [x for x in listings if x.is_digital is True]
    bestseller = [x.is_bestseller for x in listings if x.is_bestseller is not None]
    top_rated = [x.is_top_rated for x in listings if x.is_top_rated is not None]
    shops = Counter(x.shop_name for x in listings if x.shop_name)
    tags = Counter(normalize_keyword(t) for x in listings for t in x.tags if t)
    categories = Counter(c for x in listings for c in x.categories if c)
    words = []
    for item in listings:
        words.extend(w for w in normalize_keyword(item.title or "").split() if len(w)>2 and w not in STOP)
    phrases = Counter(" ".join(words[i:i+2]) for i in range(max(0,len(words)-1)))
    bundles = []
    for item in listings:
        match = re.search(r"\b(\d{1,4})\s*(?:piece|pc|artwork|image|print)s?\b", item.title or "", re.I)
        if match: bundles.append(int(match.group(1)))
    dimension_counts = {dimension: Counter() for dimension in ("style", "color", "subject", "holiday", "occasion")}
    for item in listings:
        corpus = normalize_keyword(" ".join([item.title or "", *item.tags, *item.categories]))
        for dimension, counter in dimension_counts.items():
            for term in DIMENSIONS[dimension]:
                if term in corpus:
                    counter[term] += 1
    price_distribution = []
    for low, high in ((0,5),(5,10),(10,15),(15,25),(25,50),(50,None)):
        count = sum(value >= low and (high is None or value < high) for value in prices)
        price_distribution.append({"label":f"${low}+" if high is None else f"${low}-${high}","count":count})
    population = len(listings)
    normalized_titles = [normalize_keyword(x.title or "") for x in listings if x.title]
    exact_duplicate_titles = sum(count - 1 for count in Counter(normalized_titles).values() if count > 1)
    title_token_sets = [set(title.split()) for title in normalized_titles]
    near_duplicate_pairs = 0
    compared_pairs = 0
    for index, left in enumerate(title_token_sets):
        for right in title_token_sets[index + 1:]:
            compared_pairs += 1
            union = left | right
            if union and len(left & right) / len(union) >= 0.8:
                near_duplicate_pairs += 1
    fields = ["title","price","favorites_count","tags","categories","shop_name","is_digital","is_bestseller"]
    populated = sum(sum(getattr(x,f) not in (None,[],"") for f in fields) for x in listings)
    return {
        "observed_listings": population, "observed_result_count": observed_result_count,
        "confirmed_digital_count": sum(x.digital_classification_source.value=="ConfirmedProviderFlag" and x.is_digital is True for x in listings),
        "digital_count": len(digital), "digital_percentage": _pct(len(digital),population),
        "average_price": _mean(prices), "median_price": _median(prices), "minimum_price": min(prices) if prices else None, "maximum_price": max(prices) if prices else None,
        "average_favorites": _mean(favorites), "median_favorites": _median(favorites),
        "bestseller_percentage": _pct(sum(v is True for v in bestseller),len(bestseller)), "top_rated_percentage": _pct(sum(v is True for v in top_rated),len(top_rated)),
        "frequent_title_phrases": phrases.most_common(10), "frequent_tags": tags.most_common(15), "common_categories": categories.most_common(10),
        "dominant_shops": shops.most_common(10), "seller_concentration": round(max(shops.values())/population*100,1) if shops and population else None,
        "duplicate_title_percentage": _pct(exact_duplicate_titles, len(normalized_titles)),
        "near_duplicate_title_pair_percentage": _pct(near_duplicate_pairs, compared_pairs),
        "apparent_bundle_sizes": Counter(bundles).most_common(8), "detail_coverage": round(sum(x.detail_enriched for x in listings)/population*100,1) if population else 0,
        "price_distribution": price_distribution,
        "common_styles": dimension_counts["style"].most_common(10), "common_colors": dimension_counts["color"].most_common(10),
        "common_subjects": dimension_counts["subject"].most_common(10), "common_holidays": dimension_counts["holiday"].most_common(10),
        "common_occasions": dimension_counts["occasion"].most_common(10),
        "field_population_percentage": round(populated/(population*len(fields))*100,1) if population else 0,
        "source_consistency": 100 if len({x.source_provider for x in listings})<=1 else 70,
    }


class RuleBasedOpportunityScoringService(OpportunityScoringService):
    DEFAULT_WEIGHTS = {"buyer_demand":25,"demand_to_listing_ratio":20,"differentiation_potential":15,"price_attractiveness":10,"favorite_engagement":10,"low_seller_concentration":5,"bestseller_prevalence":5,"seasonality_adjustment":5,"evidence_quality":5}

    def score(self, metrics: dict, insight: dict | None, weights: dict | None = None) -> dict:
        evidence = self._evidence(metrics, insight)
        median_price = metrics.get("median_price")
        median_fav = metrics.get("median_favorites")
        concentration = metrics.get("seller_concentration")
        bestseller = metrics.get("bestseller_percentage")
        if insight:
            searches = insight["searches_last_30_days"]
            listings = insight["listings_last_30_days"]
            demand = _scale_log(searches, 10000)
            ratio = min(100, searches/max(listings,1)*250)
            label, warning = "Opportunity Score", None
        else:
            result_count = metrics.get("observed_result_count")
            demand = min(100, (median_fav or 0)*2 + (bestseller or 0)*0.8)
            ratio = 50 if result_count is None else max(0,100-_scale_log(result_count,200000))
            label, warning = "Provisional Opportunity Score", "This score does not include verified Etsy search volume."
        components = {
            "buyer_demand": round(demand,2), "demand_to_listing_ratio": round(ratio,2),
            "differentiation_potential": round(max(0,100-(metrics.get("duplicate_title_percentage") or 25)),2),
            "price_attractiveness": round(70 if median_price is None else max(0,100-abs(median_price-12)*4),2),
            "favorite_engagement": round(min(100,(median_fav or 0)*2),2),
            "low_seller_concentration": round(50 if concentration is None else max(0,100-concentration),2),
            "bestseller_prevalence": round(min(100,(bestseller or 0)*2),2),
            "seasonality_adjustment": 55, "evidence_quality": evidence,
        }
        used = dict(self.DEFAULT_WEIGHTS)
        if weights:
            for k,v in weights.items():
                if k in used and isinstance(v,(int,float)) and v>=0: used[k]=float(v)
        total = sum(used.values()) or 1
        calculation = [{"component":k,"value":components[k],"weight":used[k],"contribution":round(components[k]*used[k]/total,2)} for k in used]
        opportunity = round(sum(x["contribution"] for x in calculation),1)
        return {"evidence_score":evidence,"opportunity_score":opportunity,"score_label":label,"warning":warning,"components":components,"weights":used,"calculation":calculation}

    @staticmethod
    def _evidence(metrics: dict, insight: dict | None) -> float:
        sample = min(100,(metrics.get("observed_listings") or 0)/20*100)
        detail = metrics.get("detail_coverage") or 0
        fields = metrics.get("field_population_percentage") or 0
        consistency = metrics.get("source_consistency") or 0
        freshness = 100
        value = (25 if insight else 0)+sample*.20+detail*.20+fields*.15+freshness*.10+consistency*.10
        return round(min(100,value),1)


def cluster_niches(keywords: list[dict], listings: list[dict]) -> list[dict]:
    corpus = [(k["keyword"],"keyword",str(k.get("id",""))) for k in keywords]
    corpus += [(l.get("title") or "","listing",str(l.get("listing_id",""))) for l in listings]
    grouped = defaultdict(lambda:{"keywords":set(),"listing_ids":set(),"terms":Counter()})
    for text,kind,identifier in corpus:
        normalized=normalize_keyword(text)
        for dimension,terms in DIMENSIONS.items():
            for term in terms:
                if term in normalized:
                    key=(dimension,term)
                    if kind=="keyword": grouped[key]["keywords"].add(text)
                    else: grouped[key]["listing_ids"].add(identifier)
                    grouped[key]["terms"][term]+=1
    clusters=[]
    for (dimension,term),data in grouped.items():
        if len(data["keywords"])+len(data["listing_ids"])<1: continue
        clusters.append({"name":f"{term.title()} digital art opportunity","dimension":dimension,"keywords":sorted(data["keywords"]),"listing_ids":sorted(data["listing_ids"]),"traceable_terms":dict(data["terms"])})
    if not clusters and keywords:
        clusters=[{"name":f"{keywords[0]['keyword'].title()} opportunity","dimension":"keyword","keywords":[keywords[0]["keyword"]],"listing_ids":[str(l.get("listing_id")) for l in listings[:10]],"traceable_terms":{}}]
    return clusters[:12]


class DeterministicNicheRecommendationService(NicheRecommendationService):
    def recommend(self, cluster: dict, context: dict) -> dict:
        keywords=cluster.get("keywords") or [context.get("seed_keyword","digital wall art")]
        primary=keywords[0]
        metrics=context.get("metrics",{})
        score=context.get("score",{})
        style=cluster.get("name",primary).replace(" digital art opportunity","")
        bundle=100 if any(x in primary.lower() for x in ("frame tv","bundle","art")) else 12
        tags=_tags(primary,style)
        return {
            "niche_name":cluster["name"],"target_buyer":f"Shoppers seeking {style.lower()} downloadable decor","buyer_intent":"Decorate a compatible digital display or room with a coordinated collection",
            "recommended_digital_product":f"{bundle}-artwork {style} Frame TV art bundle","recommended_bundle_size":bundle,
            "suggested_styles_or_subcategories":[style,"coordinated neutrals","seasonal variations"],
            "suggested_price_range":"$8.99–$14.99" if bundle>=50 else "$4.99–$9.99","primary_keyword":primary,
            "supporting_keywords":keywords[1:8],"suggested_etsy_title":f"{bundle} {style} Frame TV Art Bundle, 4K Digital Download Collection"[:140],
            "suggested_etsy_tags":tags,"product_description_outline":["Buyer benefit","Exact files and dimensions","Download and display steps","License and AI disclosure"],
            "differentiation_strategy":"Use a tightly coordinated palette, truthful preview density, and clear 4K/16:9 specifications.",
            "competition_summary":f"Observed sample: {metrics.get('observed_listings',0)} listings; seller concentration: {metrics.get('seller_concentration')}%.",
            "demand_evidence":_demand_evidence(metrics,context.get("insight")),"risks":["Observed listing signals are not verified sales","Seasonal demand may vary"],
            "seasonality":"Review manually; no seasonality is inferred without dated demand data","confidence_level":"High" if score.get("evidence_score",0)>=70 else "Moderate" if score.get("evidence_score",0)>=40 else "Low",
            "evidence_score":score.get("evidence_score"),"opportunity_score":score.get("opportunity_score"),"score_label":score.get("score_label"),
            "source_keywords":keywords,"source_listing_ids":cluster.get("listing_ids",[]),"source_type":"Rule-based inference",
        }


def _tags(primary:str,style:str)->list[str]:
    raw=[primary,"frame tv art",f"{style} art","digital tv art","instant download","4k tv artwork","wall art bundle","digital wall art","art mode decor","tv art bundle","16x9 digital art","neutral home decor","downloadable art"]
    out=[]
    for value in raw:
        value=normalize_keyword(value)[:20].strip()
        if value and value not in out: out.append(value)
    while len(out)<13: out.append(f"digital art {len(out)+1}"[:20])
    return out[:13]


def _demand_evidence(metrics,insight):
    if insight: return f"Manual Etsy Marketplace Insights: {insight['searches_last_30_days']} searches and {insight['listings_last_30_days']} listings in the last 30 days."
    return f"Observed marketplace signals only: median favorites {metrics.get('median_favorites')}; bestseller prevalence {metrics.get('bestseller_percentage')}%. No verified Etsy search volume."


def _mean(v): return round(statistics.mean(v),2) if v else None
def _median(v): return round(statistics.median(v),2) if v else None
def _pct(n,d): return round(n/d*100,1) if d else None
def _scale_log(value,maximum): return min(100,math.log1p(max(value,0))/math.log1p(maximum)*100)
