"""ToS-friendly OSINT framework.

Providers must only use public datasets or official APIs.
This module includes local dataset providers and an optional GitHub provider
(using official GitHub REST API).
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol

from utis.core.storage import SQLiteStorageEngine
from utis.core.timeutils import utc_now_iso


@dataclass
class Evidence:
    title: str
    summary: str
    source: str
    timestamp_utc: str
    link: Optional[str] = None


@dataclass
class OSINTResult:
    query: str
    provider: str
    evidence: List[Evidence]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "provider": self.provider,
            "evidence": [e.__dict__ for e in self.evidence],
        }


class Provider(Protocol):
    name: str

    def search(self, query: str) -> List[Evidence]:
        ...


class RateLimiter:
    def __init__(self, min_interval_seconds: float = 1.0):
        self.min_interval_seconds = min_interval_seconds
        self._last_ts = 0.0

    def wait(self):
        now = time.time()
        elapsed = now - self._last_ts
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_ts = time.time()


class LocalJSONLProvider:
    name = "local_jsonl"

    def __init__(self, path: str):
        self.path = Path(path)

    def search(self, query: str) -> List[Evidence]:
        q = query.lower()
        out: List[Evidence] = []
        if not self.path.exists():
            return out

        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            hay = json.dumps(obj, ensure_ascii=False).lower()
            if q in hay:
                out.append(
                    Evidence(
                        title=str(obj.get("title") or obj.get("source") or "match"),
                        summary=str(obj.get("summary") or obj.get("text") or "matched local dataset"),
                        source=str(obj.get("source") or self.path.name),
                        link=obj.get("link"),
                        timestamp_utc=utc_now_iso(),
                    )
                )

        return out


class GithubProvider:
    """Official GitHub REST API provider (rate-limited).

    Requires internet access and may require GITHUB_TOKEN to avoid low limits.
    """

    name = "github"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.rate = RateLimiter(min_interval_seconds=1.2)

    def search(self, query: str) -> List[Evidence]:
        self.rate.wait()
        try:
            import httpx
        except Exception:
            return []

        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # Use code search as a general public footprint source.
        url = "https://api.github.com/search/code"
        params = {"q": query, "per_page": 5}
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                return []
            data = r.json()

        items = data.get("items") or []
        out: List[Evidence] = []
        for it in items:
            html_url = it.get("html_url")
            repo = (it.get("repository") or {}).get("full_name")
            path = it.get("path")
            out.append(
                Evidence(
                    title=f"GitHub code match in {repo}:{path}",
                    summary="Query found in GitHub code search (public).",
                    source="github_api",
                    link=html_url,
                    timestamp_utc=utc_now_iso(),
                )
            )
        return out


class OSINTEngine:
    def __init__(self, storage: SQLiteStorageEngine, cache_ttl_seconds: int = 3600):
        self.storage = storage
        self.cache_ttl_seconds = cache_ttl_seconds

    def _cache_key(self, provider: str, query: str) -> str:
        s = f"{provider}:{query}".encode("utf-8")
        return hashlib.sha256(s).hexdigest()

    def search(self, query: str, providers: Iterable[Provider], use_cache: bool = True) -> List[OSINTResult]:
        results: List[OSINTResult] = []
        for p in providers:
            key = self._cache_key(p.name, query)
            if use_cache:
                cached = self.storage.get_cache(key)
                if cached:
                    evidence = [Evidence(**e) for e in cached["response"]["evidence"]]
                    results.append(OSINTResult(query=query, provider=p.name, evidence=evidence))
                    continue

            evidence = p.search(query)
            res = OSINTResult(query=query, provider=p.name, evidence=evidence)
            if use_cache:
                self.storage.set_cache(key, p.name, query, res.to_dict())
            results.append(res)

        return results
