from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from utis.core.events import EventProcessor
from utis.core.models import Event
from utis.modules.osint.providers import Evidence, Provider


class CacheStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (query TEXT PRIMARY KEY, payload TEXT, timestamp REAL)"
        )
        self._conn.commit()

    def get(self, query: str) -> Dict | None:
        cursor = self._conn.execute(
            "SELECT payload FROM cache WHERE query = ?", (query,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

    def set(self, query: str, payload: Dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (query, payload, timestamp) VALUES (?, ?, ?)",
            (query, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        self._conn.commit()


class RateLimiter:
    def __init__(self, min_interval: float = 1.0) -> None:
        self.min_interval = min_interval
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()


class OSINTService:
    def __init__(
        self,
        providers: List[Provider],
        cache: CacheStore,
        rate_limiter: RateLimiter,
        processor: EventProcessor,
    ) -> None:
        self.providers = providers
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.processor = processor

    def search(self, query: str, entity_id: str) -> Dict[str, object]:
        cached = self.cache.get(query)
        if cached:
            return cached
        evidence: List[Evidence] = []
        for provider in self.providers:
            self.rate_limiter.wait()
            evidence.extend(provider.search(query))
        report = {
            "query": query,
            "results": [
                {
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "timestamp": item.timestamp.isoformat(),
                }
                for item in evidence
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }
        event = Event(
            entity_id=entity_id,
            event_type="osint_footprint",
            payload=report,
            source="osint_cli",
        )
        self.processor.emit(event)
        self.cache.set(query, report)
        return report
