from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Protocol

from .models import MarketplaceInsightInput, NormalizedListing, utc_now


class ResearchRepositoryInterface(Protocol):
    """Persistence contract used by research services and provider adapters."""

    def create_run(self, run_id: str, request: dict[str, Any], progress: dict[str, Any]) -> None: ...
    def get_run(self, run_id: str) -> dict[str, Any] | None: ...
    def cache_get(self, key: str) -> dict | None: ...
    def cache_set(self, key: str, provider: str, data: dict, hours: int) -> None: ...


class ResearchRepository:
    """SQLite persistence and provider cache; thread-safe per operation."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        migration = Path(__file__).parent / "migrations" / "001_initial.sql"
        with self._lock, self.connect() as conn:
            conn.executescript(migration.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)",
                (utc_now(),),
            )

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self._lock, self.connect() as conn:
            cur = conn.execute(sql, params)
            return int(cur.lastrowid or 0)

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def create_run(self, run_id: str, request: dict[str, Any], progress: dict[str, Any]) -> None:
        now = utc_now()
        self.execute(
            "INSERT INTO research_runs VALUES(?,?,?,?,?,?,?,?)",
            (run_id, now, now, "running", json.dumps(request), json.dumps(progress), None, None),
        )

    def update_run(self, run_id: str, *, status: str, progress: dict, summary: dict | None = None, error: str | None = None) -> None:
        self.execute(
            "UPDATE research_runs SET updated_at=?, status=?, progress_json=?, summary_json=?, error=? WHERE id=?",
            (utc_now(), status, json.dumps(progress), json.dumps(summary) if summary else None, error, run_id),
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        rows = self.query("SELECT * FROM research_runs WHERE id=?", (run_id,))
        if not rows:
            return None
        row = rows[0]
        for key in ("request_json", "progress_json", "summary_json"):
            row[key.removesuffix("_json")] = json.loads(row[key]) if row.get(key) else None
            row.pop(key, None)
        return row

    def cancel_run(self, run_id: str) -> bool:
        if not self.get_run(run_id):
            return False
        self.execute(
            "UPDATE research_runs SET updated_at=?, status=? WHERE id=? AND status='running'",
            (utc_now(), "cancelled", run_id),
        )
        return True

    def is_cancelled(self, run_id: str) -> bool:
        rows = self.query("SELECT status FROM research_runs WHERE id=?", (run_id,))
        return bool(rows and rows[0]["status"] == "cancelled")

    def save_keyword(self, run_id: str, keyword: str, normalized: str, source: str, result_count: int | None) -> int:
        return self.execute(
            "INSERT INTO research_keywords(run_id,keyword,normalized_keyword,source,observed_result_count,created_at) VALUES(?,?,?,?,?,?)",
            (run_id, keyword, normalized, source, result_count, utc_now()),
        )

    def update_keyword_metrics(self, keyword_id: int, metrics: dict, score: dict) -> None:
        self.execute(
            "UPDATE research_keywords SET metrics_json=?, evidence_score=?, opportunity_score=?, score_label=? WHERE id=?",
            (json.dumps(metrics), score["evidence_score"], score["opportunity_score"], score["score_label"], keyword_id),
        )

    def save_suggestion(self, run_id: str, seed: str, keyword: str, source: str) -> None:
        self.execute(
            "INSERT INTO keyword_suggestions(run_id,seed_keyword,keyword,source,created_at) VALUES(?,?,?,?,?)",
            (run_id, seed, keyword, source, utc_now()),
        )

    def save_listing(self, listing: NormalizedListing) -> None:
        self.execute(
            "INSERT INTO etsy_listings VALUES(?,?,?,?) ON CONFLICT(listing_id) DO UPDATE SET listing_json=excluded.listing_json,retrieved_at=excluded.retrieved_at,source_provider=excluded.source_provider",
            (listing.listing_id, listing.model_dump_json(), listing.retrieved_at, listing.source_provider),
        )

    def associate_listing(self, run_id: str, keyword_id: int, listing_id: str, rank: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO listing_keyword_associations VALUES(?,?,?,?)",
            (run_id, keyword_id, listing_id, rank),
        )

    def get_keywords(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM research_keywords WHERE run_id=? ORDER BY opportunity_score DESC, id", (run_id,))
        for row in rows:
            row["metrics"] = json.loads(row.pop("metrics_json")) if row.get("metrics_json") else {}
        return rows

    def get_listings(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.query(
            "SELECT e.listing_json,a.rank,k.keyword source_keyword FROM listing_keyword_associations a JOIN etsy_listings e ON e.listing_id=a.listing_id JOIN research_keywords k ON k.id=a.keyword_id WHERE a.run_id=? ORDER BY k.id,a.rank",
            (run_id,),
        )
        result = []
        for row in rows:
            item = json.loads(row["listing_json"])
            item["rank"] = row["rank"]
            item["source_keyword"] = row["source_keyword"]
            result.append(item)
        return result

    def save_score(self, run_id: str, keyword_id: int, score: dict) -> None:
        self.execute(
            "INSERT INTO opportunity_scores(run_id,keyword_id,scoring_version,score_type,evidence_score,opportunity_score,components_json,weights_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (run_id, keyword_id, "1.0", score["score_label"], score["evidence_score"], score["opportunity_score"], json.dumps(score["components"]), json.dumps(score["weights"]), utc_now()),
        )

    def save_cluster(self, run_id: str, name: str, dimension: str, cluster: dict) -> int:
        return self.execute(
            "INSERT INTO niche_clusters(run_id,name,dimension,cluster_json,created_at) VALUES(?,?,?,?,?)",
            (run_id, name, dimension, json.dumps(cluster), utc_now()),
        )

    def get_clusters(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM niche_clusters WHERE run_id=? ORDER BY id", (run_id,))
        for row in rows:
            row.update(json.loads(row.pop("cluster_json")))
        return rows

    def save_recommendation(self, run_id: str, cluster_id: int | None, recommendation: dict, source_type: str) -> int:
        return self.execute(
            "INSERT INTO product_recommendations(run_id,cluster_id,recommendation_json,source_type,created_at) VALUES(?,?,?,?,?)",
            (run_id, cluster_id, json.dumps(recommendation), source_type, utc_now()),
        )

    def get_recommendations(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM product_recommendations WHERE run_id=? ORDER BY id", (run_id,))
        for row in rows:
            row.update(json.loads(row.pop("recommendation_json")))
        return rows

    def add_insight(self, insight: MarketplaceInsightInput) -> int:
        normalized = " ".join(insight.keyword.lower().split())
        return self.execute(
            "INSERT INTO marketplace_insights(keyword,normalized_keyword,searches_last_30_days,listings_last_30_days,trend_direction,captured_at,notes,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (insight.keyword, normalized, insight.searches_last_30_days, insight.listings_last_30_days, insight.trend_direction, insight.captured_at, insight.notes, utc_now()),
        )

    def get_latest_insight(self, keyword: str) -> dict[str, Any] | None:
        normalized = " ".join(keyword.lower().split())
        rows = self.query("SELECT * FROM marketplace_insights WHERE normalized_keyword=? ORDER BY captured_at DESC LIMIT 1", (normalized,))
        return rows[0] if rows else None

    def cache_get(self, key: str) -> dict | None:
        rows = self.query("SELECT response_json,expires_at FROM provider_cache WHERE cache_key=?", (key,))
        if not rows:
            return None
        expires = datetime.fromisoformat(rows[0]["expires_at"])
        if expires < datetime.now(timezone.utc):
            self.execute("DELETE FROM provider_cache WHERE cache_key=?", (key,))
            return None
        return json.loads(rows[0]["response_json"])

    def cache_set(self, key: str, provider: str, data: dict, hours: int) -> None:
        now = datetime.now(timezone.utc)
        self.execute(
            "INSERT INTO provider_cache VALUES(?,?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET response_json=excluded.response_json,created_at=excluded.created_at,expires_at=excluded.expires_at",
            (key, provider, json.dumps(data), now.isoformat(), (now + timedelta(hours=hours)).isoformat()),
        )

    def log_request(self, run_id: str | None, provider: str, endpoint: str, cache_key: str, status: int | None, hit: bool, error: str | None = None) -> None:
        self.execute(
            "INSERT INTO provider_request_logs(run_id,provider,endpoint,cache_key,status_code,cache_hit,error,requested_at) VALUES(?,?,?,?,?,?,?,?)",
            (run_id, provider, endpoint, cache_key, status, int(hit), error, utc_now()),
        )
