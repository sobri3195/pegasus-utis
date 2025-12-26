# UTIS - Unified Tracking & Intelligence System

A comprehensive toolkit for consent-based location tracking, email security analysis, WhatsApp chat analytics, and OSINT research with clean architecture, event sourcing, and hash chain integrity.

## Features

### 🗺️ Module A - Consent Location Check-in
FastAPI-based location tracking with web interface:
- Token-based check-in links
- Browser geolocation API integration
- Event storage with hash chain integrity
- REST API for managing entities and querying events

### ✉️ Module B - Email Security & Deliverability Analyzer
Analyze email headers and content for security signals:
- Parse `.eml` files or raw headers
- Extract `Received` chain, authentication results
- Detect spoofing indicators (heuristic-based)
- URL risk scoring with allow/deny lists
- Note: Does NOT perform live DNS validation (SPF/DKIM/DMARC)

### 💬 Module C - WhatsApp Chat Export Analyzer
Parse and analyze WhatsApp chat exports:
- Multi-locale date parsing
- Statistics: messages/day, active hours, top words
- Response time analysis
- Anomaly detection (activity spikes)
- Export to JSON/CSV with plots

### 🔍 Module D - OSINT Public Footprint Checker
ToS-friendly OSINT framework:
- Modular provider interface
- Local JSONL dataset provider
- Optional GitHub API provider (requires token)
- Rate limiting and caching

### 🏗️ Core System - Clean Architecture
- Event sourcing with SHA256 hash chains
- Pluggable storage engines (SQLite, JSONL)
- Query engine with pagination
- Comprehensive audit logging
- Thread-safe operations

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd utis

# Install with pip
pip install -e .

# With optional dependencies for plotting
pip install -e ".[plot]"

# For development
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Location Check-in API

Start the FastAPI server:

```bash
utis run-location-api --host 0.0.0.0 --port 8000 --db data/utis.db
```

Generate a check-in link:

```bash
curl "http://localhost:8000/links?name=Alice&entity_type=person"
```

Response:
```json
{
  "entity_id": "abc-123",
  "token": "def456",
  "checkin_url": "/c/def456"
}
```

Visit `http://localhost:8000/c/def456` to share location via browser.

Query events:

```bash
curl "http://localhost:8000/events?entity_id=abc-123&limit=10"
```

### 2. Email Security Analysis

Analyze an email file:

```bash
utis email analyze samples/email/sample_suspicious.eml --out report.json
```

Output (partial):
```json
{
  "input_path": "samples/email/sample_suspicious.eml",
  "headers": {
    "From": "Payroll <payroll@company.com>",
    "Return-Path": "<bounce@evil-payroll.xyz>"
  },
  "spoofing_indicators": [
    "From domain differs from Return-Path domain",
    "Authentication-Results indicates SPF fail"
  ],
  "overall_risk_score": 75,
  "url_risk": {
    "risk_score": 40,
    "details": [...]
  }
}
```

Attach to entity:

```bash
utis email analyze samples/email/sample_suspicious.eml --entity user-123 --db data/utis.db
```

### 3. WhatsApp Chat Analysis

Analyze a WhatsApp export:

```bash
utis wa analyze samples/whatsapp/sample_chat.txt --entity user-123 --export output/wa_analysis/
```

Output:
```json
{
  "parsed_messages": 13,
  "participants": ["Alice", "Bob"],
  "messages_per_day": {
    "2020-12-31": 7,
    "2021-01-01": 4,
    "2021-01-02": 2
  },
  "active_hours": {...},
  "top_words": [...],
  "response_time_seconds_avg": 180.5,
  "anomalies": []
}
```

Exports include:
- `report.json` - Full analysis
- `messages_per_day.csv` - Time series
- `active_hours.csv` - Hourly distribution
- `messages_per_day.png` - Plot (if matplotlib installed)

### 4. OSINT Search

Search local dataset:

```bash
utis osint search "email@example.com" --providers local --local-dataset samples/osint/osint_data.jsonl
```

With GitHub provider (requires `GITHUB_TOKEN` env var):

```bash
export GITHUB_TOKEN=ghp_xxxxx
utis osint search "user@company.com" --providers local,github --entity user-123
```

Output:
```json
[
  {
    "query": "email@example.com",
    "provider": "local",
    "evidence": [
      {
        "title": "Company directory",
        "summary": "Employee record: email@example.com, department IT.",
        "source": "local_dataset",
        "link": "file://local/hr",
        "timestamp_utc": "2024-01-01T10:00:00Z"
      }
    ]
  }
]
```

---

## Architecture Overview

### Event Sourcing & Hash Chain

Every event has:
- `event_id` (UUID)
- `entity_id` (subject of the event)
- `event_type` (e.g., `location_checkin`, `email_analysis`)
- `payload` (event-specific data)
- `timestamp_utc` (ISO-8601)
- `source` (origin of the event)
- `hash` (SHA256 of event content)
- `prev_hash` (hash of previous event for same entity)

This creates an immutable, verifiable chain.

### Storage Engines

**SQLiteStorageEngine** (default):
- Thread-safe with WAL mode
- Foreign key constraints
- Indexed queries
- Suitable for production

**JSONLStorageEngine** (optional):
- File-based, human-readable
- Easy portability
- Not optimized for large datasets

### Query & Audit

All queries are logged to `audit_log` table/file with:
- Actor (who queried)
- Action (what was done)
- Resource type/ID
- Filters and result counts

---

## Project Structure

```
utis/
├── core/
│   ├── models.py           # Event, Entity, AuditEntry dataclasses
│   ├── storage.py          # StorageEngine interface & SQLite impl
│   ├── storage_jsonl.py    # JSONL storage engine
│   ├── processor.py        # EventProcessor (hash chain)
│   ├── query.py            # QueryEngine (with audit)
│   └── timeutils.py        # UTC time normalization
├── modules/
│   ├── location/
│   │   └── api.py          # FastAPI location check-in
│   ├── email/
│   │   ├── analyzer.py     # Email security analyzer
│   │   └── lists/          # Allow/deny lists
│   ├── whatsapp/
│   │   └── analyzer.py     # WhatsApp export parser
│   └── osint/
│       └── engine.py       # OSINT provider framework
├── cli.py                  # Click CLI entry point
└── web/                    # Static web assets (if any)

tests/
├── test_core.py            # Core system tests
├── test_email.py           # Email analyzer tests
└── test_whatsapp.py        # WhatsApp analyzer tests

samples/
├── email/                  # Sample .eml files
├── whatsapp/               # Sample chat exports
└── osint/                  # Sample JSONL datasets
```

---

## Design Decisions

### 1. Hash Chain Integrity
- Each event is cryptographically linked to its predecessor
- Allows verification of data integrity
- Prevents tampering with historical events

### 2. Entity-Event Model
- Entities represent subjects (person, device, etc.)
- Events represent things that happen to entities
- Clean separation of identity and activity

### 3. Thread-Safe Storage
- RLock for all storage operations
- SQLite WAL mode for concurrent reads
- Safe for multi-threaded API server

### 4. ToS-Friendly OSINT
- Only public data sources or official APIs
- No scraping or terms violations
- Local datasets for user-provided data
- GitHub uses official REST API (rate-limited)

### 5. Heuristic Email Analysis
- Does NOT claim to validate SPF/DKIM/DMARC via DNS
- Analyzes what's present in headers (Authentication-Results)
- URL risk based on local lists + heuristics
- Designed for educational/analysis purposes

### 6. Privacy by Design
- Consent-based location tracking
- No data leaves the system without explicit export
- Audit logging for all queries and writes
- User controls their data via entity IDs

---

## Example Outputs

### Location Check-in Event

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "entity_id": "user-alice",
  "event_type": "location_checkin",
  "timestamp_utc": "2024-01-01T14:30:00Z",
  "source": "location_web",
  "payload": {
    "lat": -6.2088,
    "lon": 106.8456,
    "accuracy": 20.0,
    "timestamp_client": "2024-01-01T14:29:58Z",
    "metadata": {
      "userAgent": "Mozilla/5.0...",
      "platform": "MacIntel"
    },
    "request": {
      "ip": "192.0.2.100",
      "user_agent": "Mozilla/5.0..."
    },
    "server_received_utc": "2024-01-01T14:30:00Z"
  },
  "hash": "abc123...",
  "prev_hash": "def456..."
}
```

### Email Analysis Event

```json
{
  "event_type": "email_analysis",
  "payload": {
    "input_path": "suspicious.eml",
    "spoofing_indicators": [
      "From domain differs from Return-Path domain",
      "Authentication-Results indicates DMARC fail"
    ],
    "overall_risk_score": 75,
    "url_risk": {
      "risk_score": 40,
      "details": [
        {
          "url": "https://192.0.2.10/login",
          "host": "192.0.2.10",
          "score": 25,
          "findings": ["URL uses raw IPv4 address"]
        }
      ]
    }
  }
}
```

### WhatsApp Analysis Event

```json
{
  "event_type": "whatsapp_export_analysis",
  "payload": {
    "parsed_messages": 150,
    "participants": ["Alice", "Bob", "Charlie"],
    "messages_per_day": {
      "2024-01-01": 45,
      "2024-01-02": 60,
      "2024-01-03": 45
    },
    "top_words": [
      {"word": "meeting", "count": 12},
      {"word": "project", "count": 10}
    ],
    "anomalies": [
      {
        "day": "2024-01-02",
        "count": 60,
        "reason": "activity_spike"
      }
    ]
  }
}
```

### OSINT Search Event

```json
{
  "event_type": "osint_footprint",
  "payload": {
    "query": "email@example.com",
    "results": [
      {
        "provider": "local",
        "evidence": [
          {
            "title": "Public paste",
            "summary": "Email found in paste",
            "source": "local_dataset",
            "link": "file://paste1",
            "timestamp_utc": "2024-01-01T10:00:00Z"
          }
        ]
      }
    ]
  }
}
```

---

## Testing

Run tests with pytest:

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=utis --cov-report=html
```

---

## Development

### Adding a New Module

1. Create module directory: `utis/modules/mymodule/`
2. Implement analyzer/engine
3. Add CLI commands in `utis/cli.py`
4. Write tests in `tests/test_mymodule.py`
5. Update README with examples

### Adding a New Storage Engine

1. Subclass `StorageEngine` in `utis/core/storage.py`
2. Implement all abstract methods
3. Add option to CLI for selecting storage backend

### Adding a New OSINT Provider

1. Create class implementing `Provider` protocol
2. Implement `search(query: str) -> List[Evidence]`
3. Add to `OSINTEngine` provider options
4. Document API requirements and rate limits

---

## Security Considerations

⚠️ **Email Analyzer Disclaimer**:
This tool analyzes email headers but does NOT perform live DNS lookups. SPF/DKIM/DMARC status is extracted from the `Authentication-Results` header if present. Do not use this as sole verification for email authenticity.

⚠️ **OSINT Ethics**:
Only use providers that respect terms of service. Do not use this tool for harassment, stalking, or illegal activities. Always obtain consent before researching individuals.

⚠️ **Location Privacy**:
Location tracking requires explicit user consent via browser geolocation API. Store data securely and comply with privacy regulations (GDPR, etc.).

---

## License

MIT License - See LICENSE file

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

---

## Support

For issues, questions, or feature requests, please open a GitHub issue.

---

## Changelog

### v0.1.0 (Initial Release)
- Core event sourcing system with hash chain
- SQLite and JSONL storage engines
- Location check-in module (FastAPI + Web)
- Email security analyzer (CLI)
- WhatsApp chat analyzer (CLI)
- OSINT framework with local + GitHub providers
- Comprehensive CLI interface
- Full test coverage
