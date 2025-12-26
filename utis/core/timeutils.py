"""Time normalization utilities."""

from datetime import datetime, timezone
from typing import Optional

try:
    from dateutil import parser as dtparser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


def utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_to_utc_iso(value: Optional[str]) -> Optional[str]:
    """Normalize a timestamp string to UTC ISO-8601 format.
    
    Requires python-dateutil for flexible parsing.
    Falls back to datetime.fromisoformat for ISO-8601 strings if dateutil unavailable.
    """
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None

    if HAS_DATEUTIL:
        dt = dtparser.parse(v)
    else:
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return v

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat().replace("+00:00", "Z")
