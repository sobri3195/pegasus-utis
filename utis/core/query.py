"""Query engine with audit logging."""
from typing import Optional, Tuple, List

from .models import AuditEntry, Event
from .storage import StorageEngine
from .timeutils import normalize_to_utc_iso


class QueryEngine:
    """Query events with audit logging."""

    def __init__(self, storage: StorageEngine, actor: str = "system"):
        self.storage = storage
        self.actor = actor

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
        """Query events and log audit."""
        start_norm = normalize_to_utc_iso(start_time)
        end_norm = normalize_to_utc_iso(end_time)

        events, total = self.storage.query_events(
            entity_id=entity_id,
            event_type=event_type,
            start_time=start_norm,
            end_time=end_norm,
            limit=limit,
            offset=offset,
            sort_asc=sort_asc,
        )

        self.storage.write_audit(
            AuditEntry(
                action="query_events",
                actor=self.actor,
                resource_type="events",
                resource_id=entity_id or "*",
                details={
                    "filters": {
                        "entity_id": entity_id,
                        "event_type": event_type,
                        "start_time": start_norm,
                        "end_time": end_norm,
                    },
                    "limit": limit,
                    "offset": offset,
                    "returned": len(events),
                    "total": total,
                },
            )
        )

        return events, total
