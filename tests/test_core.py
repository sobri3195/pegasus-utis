"""Tests for core functionality."""

import tempfile
from pathlib import Path

from utis.core import SQLiteStorageEngine, EventProcessor, Entity, QueryEngine


def test_entity_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        storage = SQLiteStorageEngine(db_path)

        entity = Entity(entity_type="person", name="Alice")
        storage.create_entity(entity)

        fetched = storage.get_entity(entity.entity_id)
        assert fetched is not None
        assert fetched.name == "Alice"


def test_event_chain():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        storage = SQLiteStorageEngine(db_path)
        proc = EventProcessor(storage)

        entity = Entity(entity_id="ent1")
        storage.create_entity(entity)

        e1 = proc.create_event("ent1", "test", {"val": 1})
        assert e1.prev_hash == ""
        assert e1.hash != ""

        e2 = proc.create_event("ent1", "test", {"val": 2})
        assert e2.prev_hash == e1.hash

        e3 = proc.create_event("ent1", "test", {"val": 3})
        assert e3.prev_hash == e2.hash

        assert proc.verify_chain("ent1")


def test_query_events():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        storage = SQLiteStorageEngine(db_path)
        proc = EventProcessor(storage)
        query = QueryEngine(storage)

        entity = Entity(entity_id="ent1")
        storage.create_entity(entity)

        proc.create_event("ent1", "typeA", {"v": 1})
        proc.create_event("ent1", "typeB", {"v": 2})
        proc.create_event("ent1", "typeA", {"v": 3})

        events, total = query.query_events(entity_id="ent1", event_type="typeA")
        assert total == 2
        assert len(events) == 2
