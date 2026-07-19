PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    progress_json TEXT NOT NULL,
    summary_json TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS research_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_result_count INTEGER,
    metrics_json TEXT,
    evidence_score REAL,
    opportunity_score REAL,
    score_label TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, normalized_keyword)
);

CREATE TABLE IF NOT EXISTS keyword_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    seed_keyword TEXT NOT NULL,
    keyword TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etsy_listings (
    listing_id TEXT PRIMARY KEY,
    listing_json TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    source_provider TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listing_keyword_associations (
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES research_keywords(id) ON DELETE CASCADE,
    listing_id TEXT NOT NULL REFERENCES etsy_listings(listing_id),
    rank INTEGER,
    PRIMARY KEY(run_id, keyword_id, listing_id)
);

CREATE TABLE IF NOT EXISTS marketplace_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    searches_last_30_days INTEGER NOT NULL,
    listings_last_30_days INTEGER NOT NULL,
    trend_direction TEXT,
    captured_at TEXT NOT NULL,
    notes TEXT,
    source TEXT NOT NULL DEFAULT 'Manual Etsy Marketplace Insights entry',
    created_at TEXT NOT NULL,
    UNIQUE(normalized_keyword, captured_at)
);

CREATE TABLE IF NOT EXISTS niche_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    dimension TEXT NOT NULL,
    cluster_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES research_keywords(id) ON DELETE CASCADE,
    scoring_version TEXT NOT NULL,
    score_type TEXT NOT NULL,
    evidence_score REAL NOT NULL,
    opportunity_score REAL NOT NULL,
    components_json TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    cluster_id INTEGER REFERENCES niche_clusters(id) ON DELETE SET NULL,
    recommendation_json TEXT NOT NULL,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    cache_key TEXT,
    status_code INTEGER,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    requested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_cache (
    cache_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_keywords_run ON research_keywords(run_id);
CREATE INDEX IF NOT EXISTS idx_assoc_run ON listing_keyword_associations(run_id);
CREATE INDEX IF NOT EXISTS idx_insights_keyword ON marketplace_insights(normalized_keyword);
