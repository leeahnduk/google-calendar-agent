from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from googleapiclient.discovery import build

from config.settings import load_settings
from agents.oauth_util import get_google_creds_from_tool_context


@dataclass
class EventAttendee:
    email: str
    response_status: Optional[str] = None


@dataclass
class EventContext:
    id: str
    summary: str
    description: str
    start_iso: str
    end_iso: str
    attendees: List[EventAttendee]
    recurring_event_id: Optional[str] = None
    html_link: Optional[str] = None
    location: Optional[str] = None


def _to_iso(dt_str: str) -> str:
    # Accept either dateTime or date; normalize to ISO8601
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except Exception:
        return dt_str


def get_next_event(tool_context: Any) -> Optional[EventContext]:
    settings = load_settings()
    creds = get_google_creds_from_tool_context(tool_context, settings.auth_id)
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=1)).isoformat()

    events_result = (
        service.events()
        .list(calendarId="primary", timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime")
        .execute()
    )
    items = events_result.get("items", [])
    if not items:
        return None

    # Pick the first upcoming event in the window
    ev = items[0]
    attendees_raw = ev.get("attendees", [])
    attendees = [
        EventAttendee(email=a.get("email", ""), response_status=a.get("responseStatus")) for a in attendees_raw
    ]
    start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or ""
    end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date") or ""

    return EventContext(
        id=ev.get("id", ""),
        summary=ev.get("summary", ""),
        description=ev.get("description", ""),
        start_iso=_to_iso(start),
        end_iso=_to_iso(end),
        attendees=attendees,
        recurring_event_id=ev.get("recurringEventId"),
        html_link=ev.get("htmlLink"),
        location=ev.get("location"),
    )
