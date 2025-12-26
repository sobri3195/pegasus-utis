# UTIS Architecture & Design

## Table of Contents
1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Module Design](#module-design)
4. [Design Decisions](#design-decisions)
5. [Data Flow](#data-flow)
6. [Security Model](#security-model)

---

## System Overview

UTIS is built on an **event sourcing** architecture with a **clean architecture** approach, separating:
- **Core domain logic** (event models, hash chains, storage abstraction)
- **Application services** (processors, query engines)
- **Infrastructure** (SQLite, JSONL implementations)
- **Modules** (location, email, WhatsApp, OSINT)
- **Interfaces** (FastAPI REST, CLI)

### Key Principles

1. **Immutability**: Events are write-once, creating an immutable audit trail
2. **Integrity**: SHA256 hash chains prevent tampering
3. **Modularity**: Each module is independent and pluggable
4. **Privacy**: Consent-based tracking, local-first storage
5. **Portability**: Abstract storage interface supports multiple backends

---

## Core Architecture

### 1. Event Model

```python
@dataclass
class Event:
    event_id: str          # UUID v4
    entity_id: str         # Subject of the event
    event_type: str        # Type identifier (e.g., "location_checkin")
    payload: Dict[str, Any]  # Event-specific data
    timestamp_utc: str     # ISO-8601 UTC timestamp
    source: str            # Origin (e.g., "location_web", "cli")
    hash: str              # SHA256(event_id + entity_id + ... + prev_hash)
    prev_hash: str         # Hash of previous event for this entity
```

**Hash Chain**:
- Each event's `hash` is computed from its content + `prev_hash`
- Forms a blockchain-like structure per entity
- Verification: recompute hashes in order, check `prev_hash` matches

**Benefits**:
- Detect tampering with historical events
- Prove data integrity without external authorities
- Support cryptographic verification

### 2. Entity Model

```python
@dataclass
class Entity:
    entity_id: str         # UUID v4 or user-specified
    entity_type: str       # "person", "device", "organization", etc.
    name: str              # Human-readable identifier
    metadata: Dict[str, Any]  # Flexible attributes
    created_at: str        # ISO-8601 UTC
    updated_at: str        # ISO-8601 UTC
```

**Purpose**:
- Represents the subject of events
- Enables grouping and querying by entity
- Supports foreign key constraints in SQL

### 3. Storage Engine Interface

```python
class StorageEngine(ABC):
    @abstractmethod
    def create_entity(self, entity: Entity) -> Entity: ...
    
    @abstractmethod
    def write_event(self, event: Event) -> Event: ...
    
    @abstractmethod
    def query_events(
        self, entity_id=None, event_type=None, 
        start_time=None, end_time=None, 
        limit=100, offset=0, sort_asc=False
    ) -> Tuple[List[Event], int]: ...
    
    @abstractmethod
    def write_audit(self, entry: AuditEntry) -> AuditEntry: ...
```

**Implementations**:
- **SQLiteStorageEngine**: Production-ready, thread-safe, indexed
- **JSONLStorageEngine**: Human-readable, portable, simple

### 4. Event Processor

```python
class EventProcessor:
    def create_event(
        self, entity_id, event_type, payload, 
        source="system", timestamp_utc=None
    ) -> Event:
        # 1. Get prev_hash from last event
        # 2. Create Event with prev_hash
        # 3. Compute hash
        # 4. Store event
        # 5. Log audit entry
```

**Responsibilities**:
- Maintain hash chain integrity
- Normalize timestamps to UTC
- Auto-create entities if missing (for SQLite)
- Audit every write

### 5. Query Engine

```python
class QueryEngine:
    def query_events(...) -> Tuple[List[Event], int]:
        # 1. Normalize time filters
        # 2. Query storage
        # 3. Log audit entry (who queried what)
        # 4. Return results + total count
```

**Features**:
- Pagination (limit/offset)
- Time range filtering
- Entity and event type filtering
- Sort order (ASC/DESC)
- Audit logging for all queries

---

## Module Design

### Module A: Location Check-in

**Components**:
- FastAPI app with REST endpoints
- HTML/JS page for browser geolocation
- Token-based check-in links

**Endpoints**:
- `GET /links` - Generate check-in link for entity
- `GET /c/{token}` - Serve consent page
- `POST /checkin/{token}` - Receive location data
- `GET /events` - Query events

**Data Flow**:
1. User generates link via API or CLI
2. Token stored in `checkin_links` table with entity_id
3. Recipient visits `/c/{token}`, browser requests permission
4. JS sends lat/lon/accuracy to API
5. API creates `location_checkin` event
6. Event stored with hash chain

**Privacy**:
- Consent required (browser prompt)
- Token can be single-use or expiring (future enhancement)
- IP and user-agent logged for audit

### Module B: Email Security Analyzer

**Components**:
- `.eml` parser (Python `email` library)
- Header analyzer (Received chain, auth results)
- URL extractor and risk scorer
- Allow/deny list loader

**Process**:
1. Load email file
2. Parse headers (From, Return-Path, Message-ID, etc.)
3. Extract Authentication-Results header (SPF/DKIM/DMARC)
4. Detect spoofing indicators (domain mismatches)
5. Extract URLs from body
6. Score URLs (IP addresses, punycode, suspicious TLDs, deny list)
7. Compute overall risk score (0-100)
8. Return structured report

**Heuristics**:
- **Spoofing**: From ≠ Return-Path domain, missing Message-ID
- **URL Risk**: Raw IPs (+25), punycode (+15), suspicious TLD (+10), deny list (+40)
- **Auth Failures**: SPF fail (+15), DKIM fail (+15), DMARC fail (+20)

**Limitations**:
- Does NOT perform DNS lookups (no live SPF/DKIM/DMARC validation)
- Relies on what's in the message (especially Authentication-Results header)
- Educational/analysis tool, not production email security

### Module C: WhatsApp Chat Analyzer

**Components**:
- Multi-format date parser (dateutil)
- Message extractor with continuation handling
- Statistics calculator
- Plot generator (matplotlib, optional)

**Parsing**:
- Supports multiple date formats (12/31/20 vs 31/12/20, AM/PM vs 24h)
- Auto-detects day-first vs month-first
- Handles multi-line messages

**Analytics**:
- Messages per day (time series)
- Active hours (histogram)
- Top words (frequency, excluding stopwords)
- Response time (average delta when sender changes)
- Anomaly detection (activity spikes)

**Export**:
- `report.json` - Full analysis
- CSV files for time series
- PNG plots (if matplotlib available)

### Module D: OSINT

**Components**:
- Provider interface (`Protocol`)
- Rate limiter (per-provider)
- Cache (SQLite or in-memory)
- Local JSONL provider
- GitHub API provider (optional)

**Provider Interface**:
```python
class Provider(Protocol):
    name: str
    def search(self, query: str) -> List[Evidence]: ...
```

**Evidence Model**:
```python
@dataclass
class Evidence:
    title: str
    summary: str
    source: str
    timestamp_utc: str
    link: Optional[str] = None
```

**Local Provider**:
- Reads JSONL file line by line
- Simple string matching (case-insensitive)
- No external dependencies

**GitHub Provider**:
- Uses official GitHub REST API
- Code search endpoint
- Rate-limited (1.2s per request)
- Requires `GITHUB_TOKEN` for higher limits

**Ethics**:
- Only public data sources
- Respects ToS
- Rate-limited to avoid abuse
- Cache results to minimize requests

---

## Design Decisions

### 1. Why Event Sourcing?

**Benefits**:
- Complete audit trail (who did what when)
- Time travel (query state at any point)
- Debugging (replay events)
- Compliance (GDPR right to access)

**Trade-offs**:
- Higher storage requirements
- Query complexity (need projections for aggregates)
- Learning curve

**Decision**: Benefits outweigh costs for a tracking/intelligence system where auditability is critical.

### 2. Why Hash Chains?

**Alternatives**:
- Merkle trees (more efficient verification)
- Digital signatures (stronger guarantees)

**Decision**: Hash chains are simpler, sufficient for single-entity integrity, and don't require key management.

### 3. Why SQLite + JSONL?

**Alternatives**:
- PostgreSQL (more features, harder to deploy)
- MongoDB (flexible schema, overkill)
- Pure files (no indexes, slow queries)

**Decision**: 
- SQLite for production (zero-config, fast, ACID)
- JSONL for portability (human-readable, easy to share)

### 4. Why FastAPI?

**Alternatives**:
- Flask (simpler but less modern)
- Django (full-stack, overkill)

**Decision**: FastAPI has automatic OpenAPI docs, type hints, async support, and modern patterns.

### 5. Why Click for CLI?

**Alternatives**:
- argparse (stdlib but verbose)
- typer (modern but newer)

**Decision**: Click is mature, widely used, and flexible.

### 6. Why Local-First Architecture?

**Alternatives**:
- Cloud-first (SaaS)
- Hybrid (local + cloud sync)

**Decision**: Privacy, control, and simplicity. Users own their data. No external dependencies.

### 7. Why Heuristic Email Analysis?

**Alternatives**:
- Full DNS validation (requires network, slow)
- API services (costs money, external dependency)

**Decision**: Heuristics are fast, local, and sufficient for educational purposes. Disclaimers clearly state limitations.

---

## Data Flow

### Location Check-in Flow

```
1. User → API: GET /links?name=Alice
2. API → Storage: Create entity (if new)
3. API → Storage: Create checkin_link
4. API → User: {token, checkin_url}

5. Recipient → Browser: Visit /c/{token}
6. Browser → API: GET /c/{token}
7. API → Browser: HTML with JS

8. Browser → JS: Request geolocation permission
9. JS → Browser: Geolocation granted
10. Browser → JS: {lat, lon, accuracy}
11. JS → API: POST /checkin/{token} {lat, lon, ...}

12. API → Storage: Get prev_hash
13. API → Storage: Create event with hash
14. API → Storage: Write audit entry
15. API → JS: {ok: true, event: {...}}
```

### Email Analysis Flow

```
1. User → CLI: utis email analyze msg.eml --entity user-123
2. CLI → EmailAnalyzer: analyze(msg.eml)
3. EmailAnalyzer → File: Read .eml
4. EmailAnalyzer → Parser: Parse headers/body
5. EmailAnalyzer → Lists: Load allow/deny lists
6. EmailAnalyzer → Heuristics: Score URLs, detect spoofing
7. EmailAnalyzer → CLI: EmailAnalysisResult

8. CLI → EventProcessor: create_event(user-123, email_analysis, result)
9. EventProcessor → Storage: write_event
10. Storage → DB: INSERT event
11. Storage → DB: INSERT audit_log
12. CLI → User: JSON report
```

### WhatsApp Analysis Flow

```
1. User → CLI: utis wa analyze chat.txt --entity user-123 --export out/
2. CLI → WhatsAppAnalyzer: analyze(chat.txt)
3. WhatsAppAnalyzer → Parser: Parse lines with regex
4. WhatsAppAnalyzer → Stats: Compute messages/day, hours, words
5. WhatsAppAnalyzer → Anomaly: Detect spikes
6. WhatsAppAnalyzer → CLI: WhatsAppAnalysisResult

7. CLI → WhatsAppAnalyzer: export(result, out/)
8. WhatsAppAnalyzer → Files: Write JSON, CSVs, PNGs

9. CLI → EventProcessor: create_event(user-123, whatsapp_analysis, result)
10. EventProcessor → Storage: write_event
11. CLI → User: Report
```

### OSINT Search Flow

```
1. User → CLI: utis osint search "email@x.com" --providers local,github
2. CLI → OSINTEngine: search(query, [LocalProvider, GithubProvider])

3. For each provider:
   a. Engine → Storage: Check cache
   b. If cached: Return cached result
   c. Else:
      i. Engine → Provider: search(query)
      ii. Provider → RateLimiter: wait()
      iii. Provider → External/File: Fetch data
      iv. Provider → Engine: List[Evidence]
      v. Engine → Storage: set_cache(key, result)

4. Engine → CLI: List[OSINTResult]
5. CLI → EventProcessor: create_event(entity, osint_footprint, results)
6. CLI → User: JSON report
```

---

## Security Model

### 1. Threat Model

**In Scope**:
- Data integrity (hash chains)
- Audit trail (who did what)
- Local data protection

**Out of Scope**:
- Network security (TLS is user's responsibility)
- Authentication (no built-in auth)
- Authorization (no RBAC)

### 2. Hash Chain Integrity

**Attack**: Modify historical event
**Defense**: 
- Hash chains detect tampering
- `verify_chain()` method checks integrity
- Any modification breaks the chain

**Attack**: Delete event
**Defense**:
- Next event's `prev_hash` won't match
- Chain verification fails
- Consider append-only storage mode (future)

### 3. Privacy

**Location Tracking**:
- Consent required (browser prompt)
- Token-based (no PII in URL)
- IP address logged for audit (can be anonymized)

**Email Analysis**:
- Local processing only
- No data sent to external services
- User controls output

**OSINT**:
- Only public data
- Cache stored locally
- User responsible for ethical use

### 4. Access Control

**Current**: None (single-user system)

**Future**:
- Add `actor` authentication
- Implement entity-level permissions
- Use JWT or API keys for multi-user

### 5. Compliance

**GDPR**:
- Right to access: Query events by entity_id
- Right to erasure: Delete entity events (add soft-delete)
- Right to portability: Export as JSON/CSV
- Audit trail: All actions logged

**Best Practices**:
- Store only necessary data
- Encrypt database at rest (use encrypted filesystem)
- Rotate check-in tokens
- Implement data retention policies

---

## Performance Considerations

### 1. Storage

**SQLite**:
- WAL mode for concurrent reads
- Indexes on (entity_id, timestamp_utc) and (event_type, timestamp_utc)
- PRAGMA foreign_keys for integrity
- Consider vacuuming for long-running systems

**JSONL**:
- Append-only for writes (O(1))
- Full scan for queries (O(n))
- Not suitable for >10k events per entity

### 2. Hash Chain Verification

**Cost**: O(n) where n = events per entity
**Optimization**: 
- Verify only on demand (not every read)
- Checkpoint hashes (verify from last checkpoint)
- Parallel verification (split by entity)

### 3. Query Performance

**Pagination**: Always use limit/offset
**Indexes**: Ensure entity_id + timestamp are indexed
**Time Filters**: Use normalized ISO-8601 for string comparison

### 4. Rate Limiting

**OSINT Providers**: 
- RateLimiter ensures min interval between requests
- Cache results to avoid repeated queries
- Consider exponential backoff on errors

---

## Future Enhancements

1. **Authentication & Authorization**
   - API key management
   - Role-based access control
   - OAuth2 integration

2. **Advanced Storage**
   - PostgreSQL backend
   - Encrypted storage engine
   - Cloud sync (S3, GCS)

3. **Real-Time Features**
   - WebSocket for live updates
   - Push notifications
   - Real-time dashboard

4. **Analytics**
   - Time-series aggregations
   - Anomaly detection ML models
   - Visualization dashboard

5. **Privacy Enhancements**
   - Differential privacy
   - Zero-knowledge proofs
   - Homomorphic encryption

6. **Scalability**
   - Sharding by entity_id
   - Read replicas
   - Event stream processing (Kafka)

---

## Testing Strategy

### Unit Tests
- Core models (hash computation)
- Storage engines (CRUD operations)
- Each module's analyzer logic

### Integration Tests
- Full workflows (entity → events → query)
- Module → storage → retrieval
- CLI commands end-to-end

### Performance Tests
- Large event volumes (1M+ events)
- Concurrent writes
- Query performance

### Security Tests
- Hash chain tampering detection
- SQL injection prevention
- Input validation

---

## Deployment

### Standalone (Single User)

```bash
# Install
pip install utis

# Run API
utis run-location-api --db /data/utis.db

# Use CLI
utis email analyze msg.eml --entity user1
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install .
CMD ["utis", "run-location-api", "--db", "/data/utis.db"]
```

### Systemd Service

```ini
[Unit]
Description=UTIS Location API
After=network.target

[Service]
Type=simple
User=utis
ExecStart=/usr/local/bin/utis run-location-api --db /var/lib/utis/utis.db
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Conclusion

UTIS is designed for:
- **Privacy**: Local-first, consent-based
- **Integrity**: Hash chains, audit logs
- **Modularity**: Pluggable storage, analyzers, providers
- **Simplicity**: Single-file deployment, minimal dependencies

The architecture supports evolution from single-user CLI to multi-user SaaS while maintaining core principles of data ownership and transparency.
