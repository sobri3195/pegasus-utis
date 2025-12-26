from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, List, Optional

from utis.core.models import EventRecord


class StorageEngine:
    def initialize(self) -> None:
        raise NotImplementedError

    def write_event(self, record: EventRecord) -> None:
        raise NotImplementedError

    def write_events(self, records: Iterable[EventRecord]) -> None:
        for record in records:
            self.write_event(record)

    def fetch_prev_hash(self) -> Optional[str]:
        raise NotImplementedError

    def insert_entity(self, entity_id: str, token: str) -> None:
        raise NotImplementedError

    def get_entity_by_token(self, token: str) -> Optional[str]:
        raise NotImplementedError


class SQLiteStorageEngine(StorageEngine):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                source TEXT NOT NULL,
                hash TEXT NOT NULL,
                prev_hash TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                details TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def write_event(self, record: EventRecord) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO events (
                    event_id, entity_id, event_type, payload,
                    timestamp_utc, source, hash, prev_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.event_id),
                    record.entity_id,
                    record.event_type,
                    json.dumps(record.payload, ensure_ascii=False),
                    record.timestamp_utc.isoformat(),
                    record.source,
                    record.hash,
                    record.prev_hash,
                ),
            )
            self._conn.commit()

    def write_events(self, records: Iterable[EventRecord]) -> None:
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO events (
                    event_id, entity_id, event_type, payload,
                    timestamp_utc, source, hash, prev_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(record.event_id),
                        record.entity_id,
                        record.event_type,
                        json.dumps(record.payload, ensure_ascii=False),
                        record.timestamp_utc.isoformat(),
                        record.source,
                        record.hash,
                        record.prev_hash,
                    )
                    for record in records
                ],
            )
            self._conn.commit()

    def fetch_prev_hash(self) -> Optional[str]:
        cursor = self._conn.execute(
            "SELECT hash FROM events ORDER BY timestamp_utc DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def insert_entity(self, entity_id: str, token: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO entities (entity_id, token, created_at) VALUES (?, ?, datetime('now'))",
                (entity_id, token),
            )
            self._conn.commit()

    def get_entity_by_token(self, token: str) -> Optional[str]:
        cursor = self._conn.execute(
            "SELECT entity_id FROM entities WHERE token = ?", (token,)
        )
        row = cursor.fetchone()
        return row[0] if row else None


class JSONLStorageEngine(StorageEngine):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.initialize()

    def initialize(self) -> None:
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def write_event(self, record: EventRecord) -> None:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record.model_dump(), default=str, ensure_ascii=False))
                handle.write("\n")

    def fetch_prev_hash(self) -> Optional[str]:
        if not self.path.exists():
            return None
        last_line = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_line = line
        if not last_line:
            return None
        data = json.loads(last_line)
        return data.get("hash")

    def insert_entity(self, entity_id: str, token: str) -> None:
        return None

    def get_entity_by_token(self, token: str) -> Optional[str]:
        return None
