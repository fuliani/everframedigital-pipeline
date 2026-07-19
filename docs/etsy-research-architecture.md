# Etsy research architecture

## Detected repository architecture

The existing project is Python 3.11 automation with JSON configuration, `requests`-based provider adapters, image-generation utilities, and Etsy API publishing scripts. It previously had no web framework, database, route layer, component library, state manager, or project test suite.

The research workspace therefore extends the Python stack rather than adding ASP.NET/React:

```text
Browser UI
  → FastAPI routes
    → ResearchService
      → EtsyResearchProvider (Omkar or saved fixture)
      → KeywordSuggestionProvider
      → MarketplaceInsightsProvider
      → OpportunityScoringService
      → NicheRecommendationService
      → optional AiAnalysisProvider
    → ResearchRepository (SQLite + provider cache)
```

Third-party communication is server-side. Users cannot provide an arbitrary provider URL, preventing SSRF through this feature. Responses are cached by request path/parameters, and provider request logs store status/error metadata without keys.

## Persistence

`001_initial.sql` creates the required run, keyword, suggestion, listing, association, insight, cluster, score, recommendation, request-log, and cache records. Listing details are de-duplicated by listing ID while run associations retain evidence traceability.

## Sources and labels

- Observed fact: Omkar response or fixture with the same contract
- Calculated metric: deterministic aggregation
- Rule-based inference: cluster/recommendation logic
- Manual Etsy Marketplace Insights entry: validated manual or CSV data
- AI recommendation: optional structured output only

## Rate limits and failures

Search/detail requests use cache-first lookup, capped retries, explicit timeouts, and special HTTP 429 handling. A failed detail request leaves search results available and marks the run partial.
