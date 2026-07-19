from __future__ import annotations

import csv
import io
import json
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .config import Settings
from .database import ResearchRepository
from .models import MarketplaceInsightInput, ResearchRequest
from .service import ResearchService

STATIC=Path(__file__).parent/"static"
PRESETS=["Samsung Frame TV art","digital wall art bundle","neutral landscape TV art","seasonal Frame TV art","Christmas Frame TV art","coastal Frame TV art","vintage landscape digital download","Japandi wall art","Southwestern wall art","gallery wall printable set"]


def create_app(settings: Settings | None = None, repository: ResearchRepository | None = None) -> FastAPI:
    settings=settings or Settings()
    repo=repository or ResearchRepository(settings.database_path)
    service=ResearchService(settings,repo)
    app=FastAPI(title="EverframeDigital Etsy Research",version="1.0.0")
    app.state.settings=settings;app.state.repository=repo;app.state.service=service
    app.add_middleware(CORSMiddleware,allow_origins=["http://127.0.0.1:8765","http://localhost:8765"],allow_methods=["GET","POST"],allow_headers=["Content-Type"])
    app.mount("/static",StaticFiles(directory=STATIC),name="static")
    request_windows: dict[str, deque[float]] = defaultdict(deque)
    request_lock = threading.Lock()

    @app.middleware("http")
    async def internal_rate_limit(request: Request, call_next):
        if request.url.path.startswith("/api/etsy-research"):
            key = request.client.host if request.client else "local"
            now = time.monotonic()
            with request_lock:
                window = request_windows[key]
                while window and now - window[0] > 60:
                    window.popleft()
                if len(window) >= 120:
                    return JSONResponse({"detail":"Local API rate limit exceeded; retry in one minute."},status_code=429)
                window.append(now)
        return await call_next(request)

    @app.get("/",response_class=HTMLResponse)
    def index(): return FileResponse(STATIC/"index.html")

    @app.get("/api/etsy-research/provider-status")
    def provider_status():
        return {"live_configured":settings.live_provider_configured,"provider":"Omkar Etsy Scraper API","base_url":settings.omkar_base_url,"cache_hours":settings.cache_hours,"max_details":settings.max_details,"ai_configured":settings.ai_configured,"presets":PRESETS,"mock_available":True}

    @app.post("/api/etsy-research/runs")
    def create_run(payload:ResearchRequest):
        try:return service.run(payload)
        except Exception as exc: raise HTTPException(502,str(exc)) from exc

    @app.get("/api/etsy-research/runs/{run_id}")
    def run(run_id:str):
        try:return service.bundle(run_id)
        except KeyError:raise HTTPException(404,"Research run not found")

    @app.post("/api/etsy-research/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        if not repo.cancel_run(run_id):
            raise HTTPException(404,"Research run not found")
        run = repo.get_run(run_id)
        return {"run_id":run_id,"status":run["status"],"cancelled":run["status"]=="cancelled"}

    @app.get("/api/etsy-research/runs/{run_id}/keywords")
    def keywords(run_id:str):return repo.get_keywords(run_id)

    @app.get("/api/etsy-research/runs/{run_id}/listings")
    def listings(run_id:str):return repo.get_listings(run_id)

    @app.get("/api/etsy-research/runs/{run_id}/clusters")
    def clusters(run_id:str):return repo.get_clusters(run_id)

    @app.get("/api/etsy-research/runs/{run_id}/recommendations")
    def recommendations(run_id:str):return repo.get_recommendations(run_id)

    @app.post("/api/etsy-research/marketplace-insights")
    def add_insight(payload:MarketplaceInsightInput):
        try:return {"id":repo.add_insight(payload),"source":"Manual Etsy Marketplace Insights entry"}
        except Exception as exc:
            if "UNIQUE" in str(exc):raise HTTPException(409,"A record already exists for this keyword and capture date")
            raise

    @app.post("/api/etsy-research/marketplace-insights/import")
    async def import_insights(request:Request):
        text=(await request.body()).decode("utf-8-sig")
        reader=csv.DictReader(io.StringIO(text));imported=[];errors=[]
        required={"Keyword","SearchesLast30Days","ListingsLast30Days","CapturedAt"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise HTTPException(400,f"CSV must include: {', '.join(sorted(required))}")
        for line,row in enumerate(reader,2):
            try:
                model=MarketplaceInsightInput(keyword=row["Keyword"],searches_last_30_days=row["SearchesLast30Days"],listings_last_30_days=row["ListingsLast30Days"],trend_direction=row.get("TrendDirection") or None,captured_at=row["CapturedAt"],notes=row.get("Notes") or None)
                imported.append(repo.add_insight(model))
            except Exception as exc:errors.append({"row":line,"error":str(exc)})
        return {"imported":len(imported),"errors":errors,"source":"Manual Etsy Marketplace Insights entry"}

    @app.get("/api/etsy-research/export/{run_id}")
    def export(run_id:str):
        rows=repo.get_keywords(run_id)
        if not repo.get_run(run_id):raise HTTPException(404,"Research run not found")
        out=io.StringIO();fields=["keyword","source","observed_result_count","digital_percentage","median_price","median_favorites","bestseller_percentage","marketplace_searches","marketplace_listings","evidence_score","opportunity_score","score_label","created_at"]
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        for row in rows:
            m=row.get("metrics",{});ins=m.get("marketplace_insight") or {}
            writer.writerow({"keyword":row["keyword"],"source":row["source"],"observed_result_count":row.get("observed_result_count"),"digital_percentage":m.get("digital_percentage"),"median_price":m.get("median_price"),"median_favorites":m.get("median_favorites"),"bestseller_percentage":m.get("bestseller_percentage"),"marketplace_searches":ins.get("searches_last_30_days"),"marketplace_listings":ins.get("listings_last_30_days"),"evidence_score":row.get("evidence_score"),"opportunity_score":row.get("opportunity_score"),"score_label":row.get("score_label"),"created_at":row.get("created_at")})
        return StreamingResponse(iter([out.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="etsy-research-{run_id}.csv"'})

    @app.get("/api/etsy-research/marketplace-insights/template")
    def template():
        path=Path(__file__).parent/"fixtures"/"marketplace-insights-template.csv"
        return FileResponse(path,media_type="text/csv",filename=path.name)

    return app


app=create_app()


if __name__=="__main__":
    import uvicorn
    uvicorn.run("etsy_research.app:app",host="127.0.0.1",port=8765,reload=False)
