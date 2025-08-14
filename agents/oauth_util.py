from google.oauth2.credentials import Credentials
from typing import Any


def get_google_creds_from_tool_context(tool_context: Any, auth_id: str) -> Credentials:
    """
    Retrieve a short-lived access token that AgentSpace places in the tool context state
    under key f"temp:{auth_id}" and wrap it in google.oauth2 Credentials for use with
    googleapiclient discovery build().
    """
    if not hasattr(tool_context, "state"):
        raise RuntimeError("tool_context is missing 'state' attribute")
    token_key = f"temp:{auth_id}"
    access_token = tool_context.state.get(token_key)
    if not access_token:
        raise RuntimeError(
            f"Missing access token in tool_context.state['{token_key}']; ensure AgentSpace OAuth is configured."
        )
    return Credentials(token=access_token)
