from __future__ import annotations

from pathlib import Path

from utis.core.storage import JSONLStorageEngine, SQLiteStorageEngine, StorageEngine


def default_sqlite_path() -> Path:
    return Path("data") / "utis.db"


def build_storage(engine: str = "sqlite", path: str | None = None) -> StorageEngine:
    if engine == "jsonl":
        target = Path(path or "data/events.jsonl")
        return JSONLStorageEngine(target)
    target = Path(path) if path else default_sqlite_path()
    return SQLiteStorageEngine(target)
