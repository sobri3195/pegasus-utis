"""Optional JSONL storage engine.

This engine is intended for lightweight, file-based storage and portability.
It is not optimized for large datasets.
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import AuditEntry, Entity, Event
from .storage import StorageEngine
from .timeutils import utc_now_iso


class JSONLStorageEngine(StorageEngine):
    def __init__(self, base_path: str = "utis_jsonl"):
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)
        self.events_path = self.base / "events.jsonl"
        self.entities_path = self.base / "entities.json"
        self.audit_path = self.base / "audit.jsonl"
        self._lock = threading.RLock()
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            if not self.entities_path.exists():
                self.entities_path.write_text("{}", encoding="utf-8")
            if not self.events_path.exists():
                self.events_path.write_text("", encoding="utf-8")
            if not self.audit_path.exists():
                self.audit_path.write_text("", encoding="utf-8")

    def _load_entities(self) -> Dict[str, Any]:
        return json.loads(self.entities_path.read_text(encoding="utf-8") or "{}")

    def _save_entities(self, data: Dict[str, Any]) -> None:
        self.entities_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_entity(self, entity: Entity) -> Entity:
        with self._lock:
            ents = self._load_entities()
            ents[entity.entity_id] = entity.to_dict()
            self._save_entities(ents)
            return entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        with self._lock:
            ents = self._load_entities()
            if entity_id not in ents:
                return None
            return Entity.from_dict(ents[entity_id])

    def write_event(self, event: Event) -> Event:
        with self._lock:
            with self.events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
            return event

    def get_last_event_hash(self, entity_id: str) -> str:
        with self._lock:
            if not self.events_path.exists():
                return ""
            last_hash = ""
            for line in self.events_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("entity_id") == entity_id:
                    last_hash = obj.get("hash") or ""
            return last_hash

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
        with self._lock:
            events: List[Event] = []
            if self.events_path.exists():
                for line in self.events_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        obj = json.loads(line)
                        e = Event.from_dict(obj)
                    except Exception:
                        continue

                    if entity_id and e.entity_id != entity_id:
                        continue
                    if event_type and e.event_type != event_type:
                        continue
                    if start_time and e.timestamp_utc < start_time:
                        continue
                    if end_time and e.timestamp_utc > end_time:
                        continue
                    events.append(e)

            events.sort(key=lambda x: x.timestamp_utc, reverse=not sort_asc)
            total = len(events)
            return events[offset : offset + limit], total

    def write_audit(self, entry: AuditEntry) -> AuditEntry:
        with self._lock:
            with self.audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            return entry
