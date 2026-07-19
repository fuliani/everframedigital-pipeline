# Opportunity scoring

The workspace displays two independent 0–100 scores.

## Evidence Score

Evidence measures reliability and coverage:

- Marketplace Insights available: 25 points
- Listing sample sufficiency: 20 points
- Detail coverage: 20 points
- Field population: 15 points
- Freshness: 10 points
- Source consistency: 10 points

Missing values remain missing and are not silently converted to zero.

## Opportunity Score

Default weights:

| Component | Weight |
|---|---:|
| Buyer demand | 25% |
| Demand-to-listing ratio | 20% |
| Differentiation potential | 15% |
| Price attractiveness | 10% |
| Favorite engagement | 10% |
| Low seller concentration | 5% |
| Bestseller prevalence | 5% |
| Seasonality adjustment | 5% |
| Evidence quality | 5% |

Each UI row exposes component values, weights, and contributions. When manual Marketplace Insights is unavailable, the result is called **Provisional Opportunity Score** and warns that it does not include verified Etsy search volume. Observed favorites and badges are marketplace engagement signals, never sales estimates.

Custom nonnegative weights can be submitted in the research request. They are normalized by their total.
