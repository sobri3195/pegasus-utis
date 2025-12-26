#!/usr/bin/env python3
"""Example usage of UTIS modules."""

import json
import tempfile
from pathlib import Path

from utis.core import SQLiteStorageEngine, EventProcessor, Entity, QueryEngine
from utis.modules.email.analyzer import EmailAnalyzer
from utis.modules.whatsapp.analyzer import WhatsAppAnalyzer
from utis.modules.osint.engine import OSINTEngine, LocalJSONLProvider


def example_core_system():
    """Demonstrate core event sourcing with hash chains."""
    print("=== Example 1: Core Event System ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "example.db")
        storage = SQLiteStorageEngine(db_path)
        processor = EventProcessor(storage, actor="demo")

        entity = Entity(entity_id="alice", name="Alice", entity_type="person")
        storage.create_entity(entity)
        print(f"Created entity: {entity.name} ({entity.entity_id})")

        event1 = processor.create_event(
            entity_id="alice",
            event_type="user_signup",
            payload={"email": "alice@example.com", "plan": "free"},
            source="web",
        )
        print(f"\nEvent 1: {event1.event_type}")
        print(f"  Hash: {event1.hash[:16]}...")
        print(f"  Prev Hash: {event1.prev_hash or '(none)'}")

        event2 = processor.create_event(
            entity_id="alice",
            event_type="plan_upgrade",
            payload={"plan": "premium", "price": 9.99},
            source="web",
        )
        print(f"\nEvent 2: {event2.event_type}")
        print(f"  Hash: {event2.hash[:16]}...")
        print(f"  Prev Hash: {event2.prev_hash[:16]}...")

        event3 = processor.create_event(
            entity_id="alice",
            event_type="feature_used",
            payload={"feature": "export", "count": 1},
            source="api",
        )
        print(f"\nEvent 3: {event3.event_type}")

        print("\nVerifying hash chain integrity...")
        is_valid = processor.verify_chain("alice")
        print(f"  Chain valid: {is_valid}")

        query = QueryEngine(storage, actor="demo")
        events, total = query.query_events(entity_id="alice", limit=10)
        print(f"\nQueried {total} events (showing {len(events)}):")
        for e in events:
            print(f"  - {e.event_type} at {e.timestamp_utc}")


def example_email_analysis():
    """Demonstrate email security analysis."""
    print("\n\n=== Example 2: Email Analysis ===\n")

    sample_eml = """From: Support <support@paypal.com>
Return-Path: <bounce@evil-site.xyz>
Message-ID: <123@evil-site.xyz>
Authentication-Results: spf=fail dkim=fail dmarc=fail
Subject: Urgent: Verify your account

Please click here to verify: https://192.0.2.50/login
Or here: https://xn--paypa1-3ve.example/verify
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        eml_path = Path(tmpdir) / "suspicious.eml"
        eml_path.write_text(sample_eml, encoding="utf-8")

        analyzer = EmailAnalyzer()
        result = analyzer.analyze(str(eml_path))

        print(f"Analyzed: {result.input_path}")
        print(f"From: {result.headers.get('From')}")
        print(f"Return-Path: {result.headers.get('Return-Path')}")
        print(f"\nSpoofing Indicators ({len(result.spoofing_indicators)}):")
        for indicator in result.spoofing_indicators:
            print(f"  ⚠️  {indicator}")

        print(f"\nAuthentication Results:")
        for key, val in result.auth_results.items():
            print(f"  {key.upper()}: {val}")

        print(f"\nURL Risk Score: {result.url_risk['risk_score']}/60")
        for detail in result.url_risk["details"]:
            print(f"  {detail['url']}")
            print(f"    Score: {detail['score']}, Findings: {detail['findings']}")

        print(f"\n🔍 Overall Risk Score: {result.overall_risk_score}/100")


def example_whatsapp_analysis():
    """Demonstrate WhatsApp chat analysis."""
    print("\n\n=== Example 3: WhatsApp Chat Analysis ===\n")

    sample_chat = """12/31/23, 10:00 AM - Alice: Happy New Year Eve!
12/31/23, 10:05 AM - Bob: Same to you! Big plans tonight?
12/31/23, 10:10 AM - Alice: Just staying home. You?
12/31/23, 10:15 AM - Bob: Party at Mike's place
12/31/23, 10:20 AM - Alice: Have fun! 🎉
12/31/23, 11:00 PM - Bob: This party is amazing
12/31/23, 11:30 PM - Alice: Nice! Happy almost new year
1/1/24, 12:01 AM - Bob: HAPPY NEW YEAR!!!
1/1/24, 12:02 AM - Alice: Happy 2024!!! 🎊🎉
1/1/24, 9:00 AM - Alice: How's the hangover? 😂
1/1/24, 10:00 AM - Bob: Terrible lol
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        chat_path = Path(tmpdir) / "chat.txt"
        chat_path.write_text(sample_chat, encoding="utf-8")

        analyzer = WhatsAppAnalyzer()
        result = analyzer.analyze(str(chat_path))

        print(f"Parsed: {result.parsed_messages} messages")
        print(f"Participants: {', '.join(result.participants)}")

        print(f"\nMessages per day:")
        for day, count in sorted(result.messages_per_day.items()):
            print(f"  {day}: {count} messages")

        print(f"\nTop active hours:")
        top_hours = sorted(result.active_hours.items(), key=lambda x: x[1], reverse=True)[:5]
        for hour, count in top_hours:
            print(f"  {hour:02d}:00 - {count} messages")

        print(f"\nTop words:")
        for word, count in result.top_words[:10]:
            print(f"  {word}: {count}")

        if result.response_time_seconds_avg:
            print(f"\nAvg response time: {result.response_time_seconds_avg:.0f} seconds")

        if result.anomalies:
            print(f"\nAnomalies detected:")
            for anomaly in result.anomalies:
                print(f"  {anomaly['day']}: {anomaly['count']} messages ({anomaly['reason']})")


def example_osint_search():
    """Demonstrate OSINT search with local provider."""
    print("\n\n=== Example 4: OSINT Search ===\n")

    sample_data = [
        {"title": "LinkedIn profile", "summary": "Software engineer at Tech Co", "source": "linkedin", "link": "https://linkedin.com/in/alice"},
        {"title": "GitHub profile", "summary": "Open source contributor", "source": "github", "link": "https://github.com/alice"},
        {"title": "Company directory", "summary": "alice@company.com - Engineering team", "source": "company_hr"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = Path(tmpdir) / "data.jsonl"
        data_path.write_text("\n".join(json.dumps(d) for d in sample_data), encoding="utf-8")

        db_path = str(Path(tmpdir) / "osint.db")
        storage = SQLiteStorageEngine(db_path)
        engine = OSINTEngine(storage)

        provider = LocalJSONLProvider(str(data_path))

        query = "alice@company.com"
        print(f"Searching for: {query}")

        results = engine.search(query, [provider])

        for result in results:
            print(f"\nProvider: {result.provider}")
            print(f"Found {len(result.evidence)} results:")
            for evidence in result.evidence:
                print(f"  📄 {evidence.title}")
                print(f"     {evidence.summary}")
                if evidence.link:
                    print(f"     Link: {evidence.link}")


def main():
    """Run all examples."""
    example_core_system()
    example_email_analysis()
    example_whatsapp_analysis()
    example_osint_search()

    print("\n\n" + "=" * 60)
    print("✅ All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
