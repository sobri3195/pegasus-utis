"""Integration tests for the full UTIS system."""

import tempfile
from pathlib import Path

from utis.core import SQLiteStorageEngine, EventProcessor, Entity, QueryEngine
from utis.modules.email.analyzer import EmailAnalyzer
from utis.modules.whatsapp.analyzer import WhatsAppAnalyzer
from utis.modules.osint.engine import OSINTEngine, LocalJSONLProvider


def test_full_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        storage = SQLiteStorageEngine(db_path)
        proc = EventProcessor(storage)

        entity = Entity(entity_id="test-entity", name="Test User")
        storage.create_entity(entity)

        event1 = proc.create_event(
            entity_id=entity.entity_id,
            event_type="test_event",
            payload={"test": "data"},
            source="test",
        )

        assert event1.hash != ""
        assert event1.prev_hash == ""

        event2 = proc.create_event(
            entity_id=entity.entity_id,
            event_type="test_event",
            payload={"test": "data2"},
            source="test",
        )

        assert event2.prev_hash == event1.hash

        query = QueryEngine(storage)
        events, total = query.query_events(entity_id=entity.entity_id)

        assert total == 2
        assert len(events) == 2

        assert proc.verify_chain(entity.entity_id)


def test_email_to_event():
    eml = """From: test@example.com
Subject: Test

Body
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        eml_path = Path(tmpdir) / "test.eml"
        eml_path.write_text(eml, encoding="utf-8")

        analyzer = EmailAnalyzer()
        result = analyzer.analyze(str(eml_path))

        assert result.headers["From"]

        db_path = str(Path(tmpdir) / "test.db")
        storage = SQLiteStorageEngine(db_path)
        proc = EventProcessor(storage)

        event = proc.create_event(
            entity_id="email-user",
            event_type="email_analysis",
            payload=result.to_dict(),
            source="test",
        )

        assert event.event_type == "email_analysis"


def test_whatsapp_to_event():
    chat = """1/1/21, 10:00 AM - Alice: Hello
1/1/21, 10:01 AM - Bob: Hi
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        chat_path = Path(tmpdir) / "chat.txt"
        chat_path.write_text(chat, encoding="utf-8")

        analyzer = WhatsAppAnalyzer()
        result = analyzer.analyze(str(chat_path))

        assert result.parsed_messages == 2

        db_path = str(Path(tmpdir) / "test.db")
        storage = SQLiteStorageEngine(db_path)
        proc = EventProcessor(storage)

        event = proc.create_event(
            entity_id="wa-user",
            event_type="whatsapp_analysis",
            payload=result.to_dict(),
            source="test",
        )

        assert event.event_type == "whatsapp_analysis"


def test_osint_to_event():
    data = '{"title":"Test","summary":"Test summary","source":"test"}\n'

    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = Path(tmpdir) / "data.jsonl"
        data_path.write_text(data, encoding="utf-8")

        db_path = str(Path(tmpdir) / "test.db")
        storage = SQLiteStorageEngine(db_path)
        engine = OSINTEngine(storage)

        provider = LocalJSONLProvider(str(data_path))
        results = engine.search("Test", [provider])

        assert len(results) == 1
        assert len(results[0].evidence) > 0

        proc = EventProcessor(storage)
        event = proc.create_event(
            entity_id="osint-user",
            event_type="osint_search",
            payload=results[0].to_dict(),
            source="test",
        )

        assert event.event_type == "osint_search"
