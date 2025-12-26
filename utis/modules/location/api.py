from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from utis.core.events import EventProcessor
from utis.core.models import Event, QueryFilters, normalize_utc
from utis.core.query import QueryEngine
from utis.core.runtime import build_storage


class CheckInPayload(BaseModel):
    lat: float
    lon: float
    accuracy: Optional[float] = None
    timestamp_client: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="Pegasus-UTIS Location Check-in")
_storage = build_storage()
_processor = EventProcessor(_storage)
_query = QueryEngine(_storage._conn)


@app.get("/links")
def generate_link(entity_id: Optional[str] = Query(default=None)) -> Dict[str, str]:
    entity = entity_id or str(uuid4())
    token = uuid4().hex
    _storage.insert_entity(entity, token)
    return {"entity_id": entity, "token": token, "url": f"/c/{token}"}


@app.get("/c/{token}", response_class=HTMLResponse)
def checkin_page(token: str) -> str:
    return f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Pegasus-UTIS Check-in</title>
</head>
<body>
  <h1>Consent Location Check-in</h1>
  <p id=\"status\">Menunggu izin lokasi...</p>
  <button id=\"checkin\">Check-in</button>
  <script>
    const statusEl = document.getElementById('status');
    document.getElementById('checkin').addEventListener('click', () => {
      if (!navigator.geolocation) {
        statusEl.textContent = 'Geolocation tidak didukung.';
        return;
      }
      statusEl.textContent = 'Meminta izin lokasi...';
      navigator.geolocation.getCurrentPosition(async (pos) => {
        const payload = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          timestamp_client: new Date().toISOString(),
          metadata: { user_agent: navigator.userAgent }
        };
        const resp = await fetch('/checkin/{token}', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (resp.ok) {
          statusEl.textContent = 'Check-in tersimpan.';
        } else {
          statusEl.textContent = 'Gagal menyimpan check-in.';
        }
      }, (err) => {
        statusEl.textContent = 'Izin lokasi ditolak: ' + err.message;
      });
    });
  </script>
</body>
</html>
"""


@app.post("/checkin/{token}")
def checkin(token: str, payload: CheckInPayload) -> Dict[str, Any]:
    entity_id = _storage.get_entity_by_token(token)
    if not entity_id:
        raise HTTPException(status_code=404, detail="Token tidak ditemukan")
    event = Event(
        entity_id=entity_id,
        event_type="location_checkin",
        payload={
            "lat": payload.lat,
            "lon": payload.lon,
            "accuracy": payload.accuracy,
            "timestamp_client": payload.timestamp_client.isoformat()
            if payload.timestamp_client
            else None,
            "metadata": payload.metadata,
        },
        source="location_web",
        timestamp_utc=normalize_utc(datetime.utcnow()),
    )
    record = _processor.emit(event)
    return {"event_id": str(record.event_id), "hash": record.hash}


@app.get("/events")
def get_events(
    entity_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    filters = QueryFilters(
        entity_id=entity_id,
        event_type="location_checkin",
        start_time=start,
        end_time=end,
        limit=limit,
        offset=offset,
    )
    records = _query.query_events(filters)
    return {"count": len(records), "events": [record.model_dump() for record in records]}
