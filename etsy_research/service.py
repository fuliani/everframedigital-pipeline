from __future__ import annotations

import json
import uuid
from typing import Any

from .analysis import (
    DeterministicNicheRecommendationService, RuleBasedOpportunityScoringService,
    analyze_competitors, cluster_niches, dedupe_keywords, filter_listings, normalize_keyword,
)
from .config import Settings
from .database import ResearchRepository
from .models import KeywordSource, ResearchProgress, ResearchRequest
from .providers import (
    DeterministicKeywordSuggestionProvider, FixtureEtsyResearchProvider,
    ManualMarketplaceInsightsProvider, OmkarEtsyResearchProvider,
    OpenAiAnalysisProvider, merge_listing, normalize_listing,
)


class ResearchService:
    def __init__(self, settings: Settings, repository: ResearchRepository):
        self.settings=settings; self.repo=repository
        self.suggestions=DeterministicKeywordSuggestionProvider()
        self.insights=ManualMarketplaceInsightsProvider(repository)
        self.scoring=RuleBasedOpportunityScoringService()
        self.recommender=DeterministicNicheRecommendationService()

    def run(self, request: ResearchRequest) -> dict[str, Any]:
        run_id=str(uuid.uuid4())
        progress=ResearchProgress()
        self.repo.create_run(run_id,request.model_dump(),progress.model_dump())
        try:
            provider=self._provider(request)
            keyword_candidates=[]
            for seed in request.seed_keywords:
                keyword_candidates.append((seed,KeywordSource.SEED.value))
                if request.include_generated_keywords:
                    for suggestion in self.suggestions.suggest(seed,request.customer_or_style):
                        keyword_candidates.append((suggestion,KeywordSource.GENERATED.value))
                        self.repo.save_suggestion(run_id,seed,suggestion,KeywordSource.GENERATED.value)
            selected=dedupe_keywords(keyword_candidates)[:request.max_keywords]
            progress.keywords_total=len(selected)
            summaries=[]
            detail_limit={"search_only":0,"top_10":10,"top_20":20}[request.enrichment_mode]
            detail_limit=min(detail_limit,self.settings.max_details)
            remaining_detail_budget=detail_limit
            seen_details:dict[str,dict]={}
            all_listings=[]
            cancelled=False
            for keyword,source in selected:
                if self.repo.is_cancelled(run_id):
                    cancelled=True
                    progress.partial_results=True
                    progress.errors.append("Research run cancelled by user.")
                    break
                try:
                    search=provider.search(keyword,run_id)
                    progress.searches_completed+=1
                    result_count=_optional_int(search.get("result_count"))
                    keyword_id=self.repo.save_keyword(run_id,keyword,normalize_keyword(keyword),source,result_count)
                    raw_items=search.get("listings") or search.get("results") or []
                    if not isinstance(raw_items,list): raw_items=[]
                    normalized=[]
                    for rank,item in enumerate(raw_items[:request.listings_to_analyze],1):
                        if not isinstance(item,dict): continue
                        listing_id=str(item.get("listing_id") or item.get("id") or "")
                        detail={}
                        enriched=False
                        if listing_id and rank<=detail_limit:
                            if listing_id in seen_details: detail=seen_details[listing_id]
                            elif remaining_detail_budget > 0:
                                try:
                                    detail=provider.listing(listing_id,run_id); seen_details[listing_id]=detail
                                    progress.details_fetched+=1
                                    remaining_detail_budget-=1
                                except RuntimeError as exc:
                                    progress.errors.append(str(exc)); progress.partial_results=True
                            enriched=bool(detail)
                        model=normalize_listing(merge_listing(item,detail),keyword,provider.name,enriched)
                        if not model.listing_id: continue
                        normalized.append(model)
                    filtered=filter_listings(normalized,request.digital_only,request.min_price,request.max_price,request.negative_keywords)
                    metrics=analyze_competitors(filtered,result_count)
                    insight=self.insights.latest(keyword)
                    score=self.scoring.score(metrics,insight,request.score_weights)
                    metrics["marketplace_insight"]=insight
                    metrics["score_calculation"]=score["calculation"]
                    metrics["score_warning"]=score["warning"]
                    self.repo.update_keyword_metrics(keyword_id,metrics,score)
                    self.repo.save_score(run_id,keyword_id,score)
                    for rank,model in enumerate(filtered,1):
                        self.repo.save_listing(model); self.repo.associate_listing(run_id,keyword_id,model.listing_id,rank)
                        all_listings.append(model.model_dump())
                    summaries.append({"keyword_id":keyword_id,"keyword":keyword,"metrics":metrics,"score":score,"insight":insight})
                except RuntimeError as exc:
                    progress.errors.append(str(exc)); progress.partial_results=True
                finally:
                    progress.keywords_processed+=1
                    progress.api_calls_made=provider.stats["api_calls"]
                    progress.cache_hits=provider.stats["cache_hits"]
                    self.repo.update_run(run_id,status="running",progress=progress.model_dump())
            keyword_rows=self.repo.get_keywords(run_id)
            clusters=cluster_niches(keyword_rows,all_listings)
            for cluster in clusters:
                cluster_id=self.repo.save_cluster(run_id,cluster["name"],cluster["dimension"],cluster)
                matching=next((s for s in summaries if s["keyword"] in cluster.get("keywords",[])),summaries[0] if summaries else {})
                rec=self.recommender.recommend(cluster,{**matching,"seed_keyword":request.seed_keywords[0]})
                self.repo.save_recommendation(run_id,cluster_id,rec,"Rule-based inference")
            summary={
                "run_id":run_id,"provider":provider.name,"data_mode":"Mocked fixture" if request.use_mock or not self.settings.live_provider_configured else "Live Omkar data",
                "keywords_analyzed":len(summaries),"unique_listings":len({x['listing_id'] for x in all_listings}),
                "warnings":["Listing counts, favorites, and result counts are not Etsy search volume."],
                "best_opportunity":max(summaries,key=lambda x:x["score"]["opportunity_score"],default=None),
            }
            if self.settings.ai_configured and summaries:
                try:
                    ai = OpenAiAnalysisProvider(self.settings.openai_api_key).analyze({
                        "research_run": summary,
                        "keyword_evidence": summaries,
                        "clusters": clusters,
                        "instruction": "Analyze only supplied evidence. Label inferences, do not invent Etsy search volume, and return the required JSON schema.",
                    })
                    summary["ai_analysis"] = ai.model_dump()
                    for recommendation in ai.productRecommendations:
                        self.repo.save_recommendation(run_id,None,recommendation,"AI recommendation")
                except Exception as exc:
                    summary["ai_warning"] = f"Optional AI analysis was unavailable: {exc}"
            progress.api_calls_made=provider.stats["api_calls"];progress.cache_hits=provider.stats["cache_hits"]
            status="cancelled" if cancelled else "partial" if progress.partial_results else "completed"
            self.repo.update_run(run_id,status=status,progress=progress.model_dump(),summary=summary)
            return self.bundle(run_id)
        except Exception as exc:
            self.repo.update_run(run_id,status="failed",progress=progress.model_dump(),error=str(exc))
            raise

    def _provider(self, request):
        if request.use_mock or not self.settings.live_provider_configured:
            return FixtureEtsyResearchProvider()
        return OmkarEtsyResearchProvider(self.settings,self.repo)

    def bundle(self,run_id:str)->dict:
        run=self.repo.get_run(run_id)
        if not run: raise KeyError(run_id)
        return {"run":run,"keywords":self.repo.get_keywords(run_id),"listings":self.repo.get_listings(run_id),"clusters":self.repo.get_clusters(run_id),"recommendations":self.repo.get_recommendations(run_id)}


def _optional_int(value):
    try:return int(value) if value is not None else None
    except (TypeError,ValueError):return None
