from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_utc(ts: Optional[datetime]) -> datetime:
    if ts is None:
        return utc_now()
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@dataclass
class Event:
    entity_id: str
    event_type: str
    payload: Dict[str, Any]
    source: str
    timestamp_utc: datetime = field(default_factory=utc_now)
    event_id: UUID = field(default_factory=uuid4)
    prev_hash: Optional[str] = None
    hash: Optional[str] = None


class EventRecord(BaseModel):
    event_id: UUID
    entity_id: str
    event_type: str
    payload: Dict[str, Any]
    timestamp_utc: datetime
    source: str
    hash: str
    prev_hash: Optional[str] = None


class QueryFilters(BaseModel):
    entity_id: Optional[str] = None
    event_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_asc: bool = True
