from __future__ import annotations

import json
from datetime import datetime
from typing import List

from utis.core.models import EventRecord, QueryFilters


class QueryEngine:
    def __init__(self, connection) -> None:
        self._conn = connection

    def query_events(self, filters: QueryFilters) -> List[EventRecord]:
        clauses = []
        params = []
        if filters.entity_id:
            clauses.append("entity_id = ?")
            params.append(filters.entity_id)
        if filters.event_type:
            clauses.append("event_type = ?")
            params.append(filters.event_type)
        if filters.start_time:
            clauses.append("timestamp_utc >= ?")
            params.append(filters.start_time.isoformat())
        if filters.end_time:
            clauses.append("timestamp_utc <= ?")
            params.append(filters.end_time.isoformat())

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "ASC" if filters.sort_asc else "DESC"
        sql = (
            "SELECT event_id, entity_id, event_type, payload, timestamp_utc, source, hash, prev_hash "
            "FROM events "
            f"{where_clause} ORDER BY timestamp_utc {order} LIMIT ? OFFSET ?"
        )
        params.extend([filters.limit, filters.offset])
        cursor = self._conn.execute(sql, params)
        records = []
        for row in cursor.fetchall():
            records.append(
                EventRecord(
                    event_id=row[0],
                    entity_id=row[1],
                    event_type=row[2],
                    payload=json.loads(row[3]),
                    timestamp_utc=datetime.fromisoformat(row[4]),
                    source=row[5],
                    hash=row[6],
                    prev_hash=row[7],
                )
            )
        return records
