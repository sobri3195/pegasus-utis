from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional

from utis.core.hashing import compute_event_hash
from utis.core.models import Event, EventRecord, normalize_utc
from utis.core.storage import StorageEngine


class EventProcessor:
    def __init__(self, storage: StorageEngine) -> None:
        self.storage = storage

    def _record_from_event(self, event: Event, prev_hash: Optional[str]) -> EventRecord:
        timestamp = normalize_utc(event.timestamp_utc)
        event_hash = compute_event_hash(
            str(event.event_id),
            event.entity_id,
            event.event_type,
            event.payload,
            timestamp.isoformat(),
            event.source,
            prev_hash,
        )
        return EventRecord(
            event_id=event.event_id,
            entity_id=event.entity_id,
            event_type=event.event_type,
            payload=event.payload,
            timestamp_utc=timestamp,
            source=event.source,
            hash=event_hash,
            prev_hash=prev_hash,
        )

    def emit(self, event: Event) -> EventRecord:
        prev_hash = self.storage.fetch_prev_hash()
        record = self._record_from_event(event, prev_hash)
        self.storage.write_event(record)
        return record

    def emit_batch(self, events: Iterable[Event]) -> List[EventRecord]:
        prev_hash = self.storage.fetch_prev_hash()
        records = []
        for event in events:
            record = self._record_from_event(event, prev_hash)
            prev_hash = record.hash
            records.append(record)
        self.storage.write_events(records)
        return records
