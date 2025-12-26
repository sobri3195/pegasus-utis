"""Event processor with hash chain integrity."""
from typing import Dict, Any, Optional

from .models import Event
from .storage import StorageEngine
from .timeutils import utc_now_iso


class EventProcessor:
    """Process and write events with integrity checks."""

    def __init__(self, storage: StorageEngine, actor: str = "system"):
        self.storage = storage
        self.actor = actor

    def create_event(
        self,
        entity_id: str,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "system",
        timestamp_utc: Optional[str] = None,
    ) -> Event:
        """Create and store event with hash chain and audit logging."""
        if not timestamp_utc:
            timestamp_utc = utc_now_iso()

        # Ensure entity exists to satisfy FK constraints.
        try:
            if hasattr(self.storage, "get_entity") and hasattr(self.storage, "create_entity"):
                ent = self.storage.get_entity(entity_id)
                if ent is None:
                    from .models import Entity

                    self.storage.create_entity(Entity(entity_id=entity_id, name=entity_id))
        except Exception:
            # Some storage engines might not support entities.
            pass

        prev_hash = self.storage.get_last_event_hash(entity_id)

        event = Event(
            entity_id=entity_id,
            event_type=event_type,
            payload=payload,
            timestamp_utc=timestamp_utc,
            source=source,
            prev_hash=prev_hash,
        )

        event.hash = event.compute_hash()
        stored = self.storage.write_event(event)

        # Audit
        try:
            from .models import AuditEntry

            self.storage.write_audit(
                AuditEntry(
                    action="write_event",
                    actor=self.actor,
                    resource_type="event",
                    resource_id=stored.event_id,
                    details={
                        "entity_id": stored.entity_id,
                        "event_type": stored.event_type,
                        "source": stored.source,
                    },
                )
            )
        except Exception:
            pass

        return stored

    def verify_chain(self, entity_id: str) -> bool:
        """Verify hash chain integrity for entity."""
        events, _ = self.storage.query_events(
            entity_id=entity_id,
            limit=10000,
            sort_asc=True
        )
        
        expected_prev_hash = ""
        for event in events:
            if event.prev_hash != expected_prev_hash:
                return False
            
            computed = event.compute_hash()
            if computed != event.hash:
                return False
            
            expected_prev_hash = event.hash
        
        return True
