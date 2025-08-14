from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from config.settings import load_settings
from agents.oauth_util import get_google_creds_from_tool_context


def whoami(tool_context: Any) -> dict:
    """
    Returns user email and primary calendar timezone using AgentSpace-managed token.
    """
    settings = load_settings()
    creds: Credentials = get_google_creds_from_tool_context(tool_context, settings.auth_id)

    user_info_service = build("oauth2", "v2", credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    email = user_info.get("email")

    calendar_service = build("calendar", "v3", credentials=creds)
    calendar_list_entry = calendar_service.calendarList().get(calendarId="primary").execute()
    user_timezone = calendar_list_entry.get("timeZone")

    return {"email": email, "timezone": user_timezone}
