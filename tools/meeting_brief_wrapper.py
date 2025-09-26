"""
Meeting Brief Tool Wrapper - Properly integrates with ADK framework
This wrapper ensures the user query is passed correctly to the meeting brief tool
"""

from google.adk.tools.tool_context import ToolContext
from typing import Dict, Any


async def prepare_meeting_brief(user_request: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Generate a meeting brief based on user request.

    Args:
        user_request: The user's request for the meeting brief (e.g., "brief for meeting 2")
        tool_context: Tool context containing authentication and state
    """
    print(f"DEBUG: Meeting brief wrapper called with user_request: '{user_request}'")

    # Store the user request in tool context state for the underlying tool to access
    if hasattr(tool_context, 'state'):
        tool_context.state['_user_query'] = user_request
        print(f"DEBUG: Stored user_request in tool_context.state: '{user_request}'")

    # Import and call the original meeting brief tool
    from .meeting_brief_tool import prepare_meeting_brief_tool

    # Call the tool with the user request as parameter
    result = prepare_meeting_brief_tool(user_request, tool_context)

    print(f"DEBUG: Meeting brief tool returned: {type(result)}")
    return result


async def get_meetings_today(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Get today's meetings with numbered index.
    """
    print("DEBUG: Meetings today wrapper called")

    # Import and call the original meetings today tool
    from .meetings_today_tool import meetings_remaining_today_tool

    result = meetings_remaining_today_tool(tool_context)

    print(f"DEBUG: Meetings today tool returned: {type(result)}")
    return result