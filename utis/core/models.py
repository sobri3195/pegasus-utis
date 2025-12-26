"""Core data models for the UTIS event system."""
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
from uuid import uuid4

from .timeutils import utc_now_iso


@dataclass
class Event:
    """Core event model with hash chain integrity."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    entity_id: str = ""
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=utc_now_iso)
    source: str = "system"
    hash: str = ""
    prev_hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return asdict(self)
    
    def compute_hash(self) -> str:
        """Compute SHA256 hash of event content (excluding hash field)."""
        data = {
            "event_id": self.event_id,
            "entity_id": self.entity_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp_utc": self.timestamp_utc,
            "source": self.source,
            "prev_hash": self.prev_hash
        }
        # Ensure consistent ordering
        json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        return cls(**data)


@dataclass
class Entity:
    """Entity model representing a tracked subject."""
    entity_id: str = field(default_factory=lambda: str(uuid4()))
    entity_type: str = "generic"
    name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Entity':
        """Create entity from dictionary."""
        return cls(**data)


@dataclass
class AuditEntry:
    """Audit log entry."""
    audit_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp_utc: str = field(default_factory=utc_now_iso)
    action: str = ""
    actor: str = "system"
    resource_type: str = ""
    resource_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit entry to dictionary."""
        return asdict(self)
