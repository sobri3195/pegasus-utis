"""FastAPI app for consent-based location check-in."""
import os
import secrets
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from utis.core import SQLiteStorageEngine, EventProcessor, Entity, QueryEngine, utc_now_iso


class CheckinPayload(BaseModel):
    lat: float
    lon: float
    accuracy: Optional[float] = None
    timestamp_client: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _location_page_html(token: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>UTIS Location Check-in</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 16px; }}
    code {{ background: #f5f5f5; padding: 2px 4px; border-radius: 4px; }}
    pre {{ background: #f5f5f5; padding: 12px; border-radius: 8px; overflow-x: auto; }}
    .ok {{ color: #0a7; }}
    .err {{ color: #c00; }}
  </style>
</head>
<body>
  <h1>Location Check-in</h1>
  <p>Token: <code>{token}</code></p>
  <button id="btn">Share my location</button>
  <p id="status">Idle</p>
  <pre id="out"></pre>

<script>
const token = {token!r};
const statusEl = document.getElementById('status');
const outEl = document.getElementById('out');

function setStatus(text, ok=true) {{
  statusEl.textContent = text;
  statusEl.className = ok ? 'ok' : 'err';
}}

async function sendLocation(pos) {{
  const payload = {{
    lat: pos.coords.latitude,
    lon: pos.coords.longitude,
    accuracy: pos.coords.accuracy,
    timestamp_client: new Date(pos.timestamp).toISOString(),
    metadata: {{
      userAgent: navigator.userAgent,
      platform: navigator.platform
    }}
  }};

  const res = await fetch(`/checkin/${token}`, {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(payload)
  }});

  const data = await res.json();
  if (!res.ok) {{
    setStatus('Failed: ' + (data.detail || res.statusText), false);
  }} else {{
    setStatus('Check-in OK');
  }}
  outEl.textContent = JSON.stringify(data, null, 2);
}}

function doCheckin() {{
  if (!navigator.geolocation) {{
    setStatus('Geolocation not supported', false);
    return;
  }}

  setStatus('Requesting permission...');
  navigator.geolocation.getCurrentPosition(
    (pos) => {{
      setStatus('Got location. Sending...');
      sendLocation(pos).catch(err => setStatus('Error sending: ' + err, false));
    }},
    (err) => setStatus('Geolocation error: ' + err.message, false),
    {{ enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }}
  );
}

document.getElementById('btn').addEventListener('click', doCheckin);
</script>
</body>
</html>"""


def create_app(db_path: Optional[str] = None) -> FastAPI:
    db_path = db_path or os.getenv("UTIS_DB_PATH", "utis.db")
    storage = SQLiteStorageEngine(db_path)
    processor = EventProcessor(storage, actor="api")

    app = FastAPI(title="UTIS Location Check-in")

    @app.get("/")
    def root():
        return {"ok": True, "service": "utis-location"}

    @app.get("/links")
    def generate_link(entity_id: Optional[str] = None, name: Optional[str] = None, entity_type: str = "person"):
        if not entity_id:
            entity = Entity(entity_type=entity_type, name=name or "")
            storage.create_entity(entity)
            entity_id = entity.entity_id
        else:
            ent = storage.get_entity(entity_id)
            if not ent:
                entity = Entity(entity_id=entity_id, entity_type=entity_type, name=name or "")
                storage.create_entity(entity)

        token = secrets.token_urlsafe(16)
        storage.create_checkin_link(token=token, entity_id=entity_id)
        try:
            from utis.core.models import AuditEntry

            storage.write_audit(
                AuditEntry(
                    action="create_checkin_link",
                    actor="api",
                    resource_type="checkin_link",
                    resource_id=token,
                    details={"entity_id": entity_id},
                )
            )
        except Exception:
            pass

        return {
            "entity_id": entity_id,
            "token": token,
            "checkin_url": f"/c/{token}",
        }

    @app.get("/c/{token}", response_class=HTMLResponse)
    def checkin_page(token: str):
        link = storage.get_checkin_link(token)
        if not link:
            raise HTTPException(status_code=404, detail="Invalid token")
        return _location_page_html(token)

    @app.post("/checkin/{token}")
    async def checkin(token: str, payload: CheckinPayload, request: Request):
        link = storage.get_checkin_link(token)
        if not link:
            raise HTTPException(status_code=404, detail="Invalid token")

        entity_id = link["entity_id"]
        storage.increment_checkin_link_use(token)

        meta = {
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        event_payload = {
            **payload.model_dump(),
            "request": meta,
            "server_received_utc": utc_now_iso(),
        }

        event = processor.create_event(
            entity_id=entity_id,
            event_type="location_checkin",
            payload=event_payload,
            source="location_web",
        )

        return {"ok": True, "event": event.to_dict()}

    @app.get("/events")
    def list_events(
        entity_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_asc: bool = False,
    ):
        q = QueryEngine(storage, actor="api")
        events, total = q.query_events(
            entity_id=entity_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
            sort_asc=sort_asc,
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "events": [e.to_dict() for e in events],
        }

    return app


app = create_app()
