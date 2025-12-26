import hashlib
import json
from typing import Any, Dict


def canonical_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_event_hash(
    event_id: str,
    entity_id: str,
    event_type: str,
    payload: Dict[str, Any],
    timestamp_utc: str,
    source: str,
    prev_hash: str | None,
) -> str:
    base = "|".join(
        [
            event_id,
            entity_id,
            event_type,
            canonical_payload(payload),
            timestamp_utc,
            source,
            prev_hash or "",
        ]
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
