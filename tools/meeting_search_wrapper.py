"""
Meeting Search Tool Wrappers - ADK-compatible wrappers for meeting search tools
"""

from typing import Dict, Any
from google.adk.tools.tool_context import ToolContext


async def search_meeting_tool(user_request: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    ADK-compatible wrapper for the unified meeting search tool.

    Args:
        user_request: The user's request (e.g., "meeting at 5:00pm today", "meeting with subject 'Planning'")
        tool_context: Tool context containing authentication and state

    Returns:
        Dict containing the panel_markdown with meeting search results
    """
    print(f"DEBUG: Meeting search wrapper called with user_request: '{user_request}'")

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
    from .meeting_search_tools import search_meeting_tool as search_tool
    return search_tool(user_request, tool_context)


async def search_meeting_by_time_tool(user_request: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    ADK-compatible wrapper for meeting search by time.

    Args:
        user_request: The user's request (e.g., "meeting at 5:00pm today")
        tool_context: Tool context containing authentication and state

    Returns:
        Dict containing the panel_markdown with meeting search results
    """
    print(f"DEBUG: Meeting search by time wrapper called with user_request: '{user_request}'")
    return await search_meeting_tool(user_request, tool_context)


async def search_meeting_by_subject_tool(user_request: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    ADK-compatible wrapper for meeting search by subject.

    Args:
        user_request: The user's request (e.g., "meeting with subject 'Planning'")
        tool_context: Tool context containing authentication and state

    Returns:
        Dict containing the panel_markdown with meeting search results
    """
    print(f"DEBUG: Meeting search by subject wrapper called with user_request: '{user_request}'")
    return await search_meeting_tool(user_request, tool_context)