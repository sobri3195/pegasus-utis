"""Storage engine implementations for UTIS."""
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import Event, Entity, AuditEntry
from .timeutils import utc_now_iso


class StorageEngine(ABC):
    """Abstract storage interface."""

    @abstractmethod
    def init_schema(self) -> None:
        """Initialize database schema."""
        pass

    @abstractmethod
    def create_entity(self, entity: Entity) -> Entity:
        """Create new entity."""
        pass

    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        pass

    @abstractmethod
    def write_event(self, event: Event) -> Event:
        """Write single event."""
        pass

    @abstractmethod
    def get_last_event_hash(self, entity_id: str) -> str:
        """Get hash of last event for entity."""
        pass

    @abstractmethod
    def query_events(
        self,
        entity_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_asc: bool = False,
    ) -> Tuple[List[Event], int]:
        """Query events with filters."""
        pass

    @abstractmethod
    def write_audit(self, entry: AuditEntry) -> AuditEntry:
        """Write audit log entry."""
        pass


class SQLiteStorageEngine(StorageEngine):
    """SQLite storage implementation."""

    def __init__(self, db_path: str = "utis.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_schema(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS entities (
                        entity_id TEXT PRIMARY KEY,
                        entity_type TEXT NOT NULL,
                        name TEXT,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS events (
                        event_id TEXT PRIMARY KEY,
                        entity_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        timestamp_utc TEXT NOT NULL,
                        source TEXT NOT NULL,
                        hash TEXT NOT NULL,
                        prev_hash TEXT,
                        FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_events_entity_time ON events(entity_id, timestamp_utc);
                    CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, timestamp_utc);

                    CREATE TABLE IF NOT EXISTS audit_log (
                        audit_id TEXT PRIMARY KEY,
                        timestamp_utc TEXT NOT NULL,
                        action TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        resource_type TEXT,
                        resource_id TEXT,
                        details TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp_utc);

                    CREATE TABLE IF NOT EXISTS checkin_links (
                        token TEXT PRIMARY KEY,
                        entity_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        used_count INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
                    );

                    CREATE TABLE IF NOT EXISTS osint_cache (
                        cache_key TEXT PRIMARY KEY,
                        provider TEXT NOT NULL,
                        query TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def create_entity(self, entity: Entity) -> Entity:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO entities (entity_id, entity_type, name, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        entity.entity_id,
                        entity.entity_type,
                        entity.name,
                        json.dumps(entity.metadata),
                        entity.created_at,
                        entity.updated_at,
                    ),
                )
                conn.commit()
                return entity
            finally:
                conn.close()

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
                if not row:
                    return None
                return Entity.from_dict(
                    {
                        "entity_id": row["entity_id"],
                        "entity_type": row["entity_type"],
                        "name": row["name"] or "",
                        "metadata": json.loads(row["metadata"] or "{}"),
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )
            finally:
                conn.close()

    def write_event(self, event: Event) -> Event:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO events (event_id, entity_id, event_type, payload, timestamp_utc, source, hash, prev_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        event.event_id,
                        event.entity_id,
                        event.event_type,
                        json.dumps(event.payload),
                        event.timestamp_utc,
                        event.source,
                        event.hash,
                        event.prev_hash,
                    ),
                )
                conn.commit()
                return event
            finally:
                conn.close()

    def get_last_event_hash(self, entity_id: str) -> str:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT hash FROM events WHERE entity_id = ? ORDER BY timestamp_utc DESC LIMIT 1",
                    (entity_id,),
                ).fetchone()
                return row["hash"] if row else ""
            finally:
                conn.close()

    def query_events(
        self,
        entity_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_asc: bool = False,
    ) -> Tuple[List[Event], int]:
        with self._lock:
            conn = self._get_conn()
            try:
                where = []
                params: List[Any] = []

                if entity_id:
                    where.append("entity_id = ?")
                    params.append(entity_id)
                if event_type:
                    where.append("event_type = ?")
                    params.append(event_type)
                if start_time:
                    where.append("timestamp_utc >= ?")
                    params.append(start_time)
                if end_time:
                    where.append("timestamp_utc <= ?")
                    params.append(end_time)

                where_sql = "WHERE " + " AND ".join(where) if where else ""
                order = "ASC" if sort_asc else "DESC"

                count_row = conn.execute(f"SELECT COUNT(*) as cnt FROM events {where_sql}", params).fetchone()
                total = int(count_row["cnt"]) if count_row else 0

                rows = conn.execute(
                    f"SELECT * FROM events {where_sql} ORDER BY timestamp_utc {order} LIMIT ? OFFSET ?",
                    params + [limit, offset],
                ).fetchall()

                events = []
                for row in rows:
                    events.append(
                        Event.from_dict(
                            {
                                "event_id": row["event_id"],
                                "entity_id": row["entity_id"],
                                "event_type": row["event_type"],
                                "payload": json.loads(row["payload"]),
                                "timestamp_utc": row["timestamp_utc"],
                                "source": row["source"],
                                "hash": row["hash"],
                                "prev_hash": row["prev_hash"] or "",
                            }
                        )
                    )
                return events, total
            finally:
                conn.close()

    def write_audit(self, entry: AuditEntry) -> AuditEntry:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO audit_log (audit_id, timestamp_utc, action, actor, resource_type, resource_id, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry.audit_id,
                        entry.timestamp_utc,
                        entry.action,
                        entry.actor,
                        entry.resource_type,
                        entry.resource_id,
                        json.dumps(entry.details),
                    ),
                )
                conn.commit()
                return entry
            finally:
                conn.close()

    # Location link helpers
    def create_checkin_link(self, token: str, entity_id: str, expires_at: Optional[str] = None) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO checkin_links (token, entity_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (token, entity_id, utc_now_iso(), expires_at),
                )
                conn.commit()
            finally:
                conn.close()

    def get_checkin_link(self, token: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM checkin_links WHERE token = ?", (token,)).fetchone()
                if not row:
                    return None
                return {
                    "token": row["token"],
                    "entity_id": row["entity_id"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                    "used_count": row["used_count"],
                }
            finally:
                conn.close()

    def increment_checkin_link_use(self, token: str) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("UPDATE checkin_links SET used_count = used_count + 1 WHERE token = ?", (token,))
                conn.commit()
            finally:
                conn.close()

    # OSINT cache helpers
    def get_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM osint_cache WHERE cache_key = ?", (cache_key,)).fetchone()
                if not row:
                    return None
                return {
                    "cache_key": row["cache_key"],
                    "provider": row["provider"],
                    "query": row["query"],
                    "response": json.loads(row["response_json"]),
                    "created_at": row["created_at"],
                }
            finally:
                conn.close()

    def set_cache(self, cache_key: str, provider: str, query: str, response: Any) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO osint_cache (cache_key, provider, query, response_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (cache_key, provider, query, json.dumps(response), utc_now_iso()),
                )
                conn.commit()
            finally:
                conn.close()
