"""
Enhanced Meeting Tools with proper ADK integration patterns
These tools are designed to work correctly with the ADK multi-agent framework
"""

from google.adk.tools.tool_context import ToolContext
from typing import Dict, Any


def prepare_meeting_brief_with_query(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Generate a meeting brief with explicit query parameter.
    This follows the ADK pattern where user input is passed as a parameter.
    """
    print(f"DEBUG: Enhanced meeting brief tool called with query: '{query}'")

    # Import the original tool function and call it with the query stored in state
    if hasattr(tool_context, 'state'):
        # Store the query in state for the original tool to access
        tool_context.state['_user_query'] = query
        print(f"DEBUG: Stored query in state: '{query}'")

    # Import and call the original tool
    from .meeting_brief_tool import prepare_meeting_brief_tool
    return prepare_meeting_brief_tool(tool_context)


def meetings_today_with_indexing(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Show today's meetings and create numbered index for selection.
    """
    print("DEBUG: Enhanced meetings today tool called")

    # Import and call the original tool
    from .meetings_today_tool import meetings_remaining_today_tool
    return meetings_remaining_today_tool(tool_context)


def search_meeting_by_number(meeting_number: int, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Search for a specific meeting by its numbered index.
    This tool helps route numbered meeting requests correctly.
    """
    print(f"DEBUG: Meeting search by number called for meeting #{meeting_number}")

    # Create a query that the meeting brief tool can understand
    query = f"brief for meeting {meeting_number}"

    # Store in state for tools to access
    if hasattr(tool_context, 'state'):
        tool_context.state['_user_query'] = query

    # Call the meeting brief tool
    from .meeting_brief_tool import prepare_meeting_brief_tool
    return prepare_meeting_brief_tool(tool_context)