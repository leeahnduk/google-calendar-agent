"""
Meeting Details Tool Wrapper - ADK-compatible wrapper for the meeting details tool
"""

from typing import Dict, Any
from google.adk.tools.tool_context import ToolContext


async def prepare_meeting_details(user_request: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    ADK-compatible wrapper for the meeting details tool.

    Args:
        user_request: The user's request (e.g., "details for meeting 2", "comprehensive analysis")
        tool_context: Tool context containing authentication and state

    Returns:
        Dict containing the panel_markdown with meeting details
    """
    print(f"DEBUG: Meeting details wrapper called with user_request: '{user_request}'")

    # Store user request in state for the underlying tool to access
    if hasattr(tool_context, 'state'):
        try:
            # Use defensive state access
            if hasattr(tool_context.state, '__setitem__'):
                tool_context.state['_user_query'] = user_request
            else:
                setattr(tool_context.state, '_user_query', user_request)
            print(f"DEBUG: Stored user_request in state: '{user_request}'")
        except Exception as e:
            print(f"DEBUG: Error storing user_request in state: {e}")

    # Import and call the actual implementation
    from .meeting_details_tool import prepare_meeting_details_tool
    return prepare_meeting_details_tool(user_request, tool_context)