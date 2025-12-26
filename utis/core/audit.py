from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from utis.core.models import normalize_utc


class AuditLogger:
    def __init__(self, connection) -> None:
        self._conn = connection

    def log(self, action: str, actor: str, details: Dict[str, Any]) -> None:
        timestamp = normalize_utc(datetime.utcnow())
        self._conn.execute(
            "INSERT INTO audit_log (action, actor, timestamp_utc, details) VALUES (?, ?, ?, ?)",
            (action, actor, timestamp.isoformat(), json.dumps(details, ensure_ascii=False)),
        )
        self._conn.commit()
