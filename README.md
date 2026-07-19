# AIWallArt / EverframeDigital

Python automation and research tools for producing, packaging, researching, and preparing digital Frame TV artwork for Etsy.

## Etsy opportunity research workspace

The repository includes a local FastAPI + SQLite workspace for keyword research, competitor analysis, manual Etsy Marketplace Insights validation, transparent opportunity scoring, niche clustering, evidence-linked product recommendations, and CSV export.

### Architecture

- **Runtime:** Python 3.11
- **Web API:** FastAPI
- **UI:** responsive HTML/CSS/JavaScript served by FastAPI
- **Persistence/cache:** SQLite with versioned SQL migration
- **Live data:** optional Omkar Etsy Scraper API, server-side only
- **AI:** optional OpenAI structured analysis provider; deterministic analysis remains the default
- **Tests:** pytest + FastAPI TestClient with saved Omkar-compatible fixtures

The research module is isolated in `etsy_research/`; existing generation and Etsy-publishing scripts are unchanged.

### Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env  # only when .env does not already exist
```

Configure `.env` as needed:

```env
OMKAR_API_KEY=
OMKAR_API_BASE_URL=https://etsy-scraper.omkar.cloud
AI_PROVIDER=
OPENAI_API_KEY=
ETSY_RESEARCH_CACHE_HOURS=24
ETSY_MAX_DETAIL_REQUESTS_PER_RESEARCH=20
ETSY_REQUEST_TIMEOUT_SECONDS=30
```

No key is required for fixture mode. API keys remain server-side and are never returned by status endpoints.

### Run locally

```powershell
.\.venv\Scripts\python.exe -m uvicorn etsy_research.app:app --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>.

### Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Example workflow

1. Select a preset or enter one or more seed keywords.
2. Choose search-only, top-10, or top-20 enrichment.
3. Use fixture mode for a zero-cost demonstration or configure `OMKAR_API_KEY` for live data.
4. Review observed competitor metrics and provisional scores.
5. Manually enter or import Etsy Marketplace Insights values to produce a full Opportunity Score.
6. Inspect traceable clusters and recommendations, then export keywords to CSV.

### Data limitations

- Omkar result counts, listing samples, favorites, and badges are marketplace observations—not search volume or verified sales.
- Marketplace Insights values are accepted only through manual entry or CSV import and are labeled accordingly.
- A score without Marketplace Insights is explicitly named **Provisional Opportunity Score**.
- Seller concentration is treated as a supply/concentration signal, not demand.
- AI analysis is optional and cannot supply missing marketplace measurements.

See [architecture](docs/etsy-research-architecture.md), [scoring](docs/opportunity-scoring.md), and [Marketplace Insights import](docs/marketplace-insights-import.md).

### Optional Nexscope skills

The application does not require globally installed skills. If desired, install the relevant MIT-licensed analysis instruction packages separately:

```powershell
npx skills add nexscope-ai/eCommerce-Skills --skill etsy-seo -g
npx skills add nexscope-ai/eCommerce-Skills --skill ecommerce-keyword-research -g
npx skills add nexscope-ai/eCommerce-Skills --skill market-gap-analysis -g
npx skills add nexscope-ai/eCommerce-Skills --skill ecommerce-competitor-analysis -g
npx skills add nexscope-ai/eCommerce-Skills --skill product-description-generator -g
```

No Nexscope source code is copied into this repository.

### Troubleshooting

- **Missing API key:** enable fixture mode or add `OMKAR_API_KEY` to `.env`.
- **401:** verify the Omkar key without printing it.
- **429:** reduce searched keywords/detail enrichment; cached requests do not consume new calls.
- **Provider schema issue:** run fixture tests and inspect the provider request log in SQLite.
- **Port in use:** select another local port with `--port`.
