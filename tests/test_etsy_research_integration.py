from dataclasses import replace

from fastapi.testclient import TestClient

from etsy_research.app import create_app
from etsy_research.config import Settings
from etsy_research.database import ResearchRepository


def client(tmp_path):
    settings=replace(Settings(),database_path=tmp_path/"research.sqlite3",omkar_api_key="")
    return TestClient(create_app(settings,ResearchRepository(settings.database_path)))


def test_seed_to_mock_results_scoring_recommendation_and_export(tmp_path):
    with client(tmp_path) as c:
        response=c.post("/api/etsy-research/runs",json={"seed_keywords":["japandi frame tv art"],"use_mock":True,"max_keywords":1,"enrichment_mode":"top_10","digital_only":True})
        assert response.status_code==200,response.text
        data=response.json();run_id=data["run"]["id"]
        assert data["run"]["status"]=="completed"
        assert data["keywords"][0]["score_label"]=="Provisional Opportunity Score"
        assert data["listings"] and all(x["is_digital"] is True for x in data["listings"])
        assert len(data["recommendations"][0]["suggested_etsy_tags"])==13
        exported=c.get(f"/api/etsy-research/export/{run_id}")
        assert exported.status_code==200 and "keyword,source" in exported.text


def test_marketplace_csv_partial_import(tmp_path):
    with client(tmp_path) as c:
        csv_text="Keyword,SearchesLast30Days,ListingsLast30Days,TrendDirection,CapturedAt,Notes\nvalid keyword,10,5,Up,2026-07-18,ok\nbad keyword,-2,4,Down,2026-07-18,bad\n"
        response=c.post("/api/etsy-research/marketplace-insights/import",content=csv_text,headers={"Content-Type":"text/csv"})
        data=response.json();assert data["imported"]==1 and len(data["errors"])==1


def test_provider_status_does_not_expose_key(tmp_path):
    with client(tmp_path) as c:
        text=c.get("/api/etsy-research/provider-status").text
        assert "api_key" not in text.lower()


def test_frontend_critical_workspace_assets_load(tmp_path):
    with client(tmp_path) as c:
        page=c.get("/")
        script=c.get("/static/app.js")
        assert page.status_code==200 and "Run research" in page.text
        assert "Marketplace Insights validation" in page.text
        assert script.status_code==200 and "renderRecommendations" in script.text


def test_cancel_endpoint_handles_missing_and_existing_runs(tmp_path):
    with client(tmp_path) as c:
        assert c.post("/api/etsy-research/runs/missing/cancel").status_code==404
        response=c.post("/api/etsy-research/runs",json={"seed_keywords":["frame tv art"],"use_mock":True,"max_keywords":1})
        run_id=response.json()["run"]["id"]
        cancelled=c.post(f"/api/etsy-research/runs/{run_id}/cancel")
        assert cancelled.status_code==200 and cancelled.json()["status"]=="completed"
