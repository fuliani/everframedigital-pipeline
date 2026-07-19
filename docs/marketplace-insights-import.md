# Marketplace Insights manual import

The application does not log into or scrape authenticated Etsy Marketplace Insights pages.

Download the CSV template from the workspace or use:

`etsy_research/fixtures/marketplace-insights-template.csv`

Required columns:

```text
Keyword,SearchesLast30Days,ListingsLast30Days,TrendDirection,CapturedAt,Notes
```

Rules:

- Searches and listings must be nonnegative integers.
- `CapturedAt` must be an ISO date or datetime.
- Keyword + capture-date duplicates are rejected.
- Invalid rows are returned with their row number; valid rows still import.
- Values remain separate from scraped listing data.
- The UI labels them `Manual Etsy Marketplace Insights entry`.
