from __future__ import annotations

from typing import Any, Optional

from config.settings import load_settings
from tools.calendar_fetcher import get_next_event, EventContext
from agents.scheduler import should_generate


def on_demand_next_event(tool_context: Any) -> Optional[EventContext]:
    """
    Fetch the user's next event (within ~24h window). Caller can force brief preparation.
    """
    return get_next_event(tool_context)


def should_prepare_now(tool_context: Any) -> bool:
    """
    Returns True if we are within the lead window for the next event.
    """
    settings = load_settings()
    ev = get_next_event(tool_context)
    if not ev:
        return False
    return should_generate(ev.start_iso, settings.brief_lead_minutes)
