"""
Export Tool Wrapper - ADK-compatible wrapper for export functionality with sequential workflow
"""

from typing import Dict, Any
from google.adk.tools.tool_context import ToolContext


def export_to_google_docs_tool_wrapper(user_request: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    ADK-compatible wrapper for the export tool with enhanced sequential workflow.

    This wrapper implements the sequential export workflow:
    1. Parse user request to determine if they want brief or details
    2. Call the appropriate content generation tool
    3. Store the fresh content for export
    4. Call the export tool

    Args:
        user_request: The user's export request (e.g., "export details for meeting 4 to Google Docs")
        tool_context: Tool context containing authentication and state

    Returns:
        Dict containing the panel_markdown with export results
    """
    print(f"DEBUG: Export wrapper called with user_request: '{user_request}'")

    # Store user request in state
    if hasattr(tool_context, 'state'):
        try:
            if hasattr(tool_context.state, '__setitem__'):
                tool_context.state['_user_query'] = user_request
            else:
                setattr(tool_context.state, '_user_query', user_request)
            print(f"DEBUG: Stored user_request in state: '{user_request}'")
        except Exception as e:
            print(f"DEBUG: Error storing user_request in state: {e}")

    # Determine if user wants details or brief
    wants_details = any(keyword in user_request.lower() for keyword in [
        'details', 'detail', 'comprehensive', 'full analysis', 'in-depth',
        'thorough', 'deep dive', 'breakdown', 'elaborate', 'expanded'
    ])

    print(f"DEBUG: Export workflow - wants_details: {wants_details}")

    # Step 1: Generate fresh content based on user request
    fresh_content = None
    content_type = "details" if wants_details else "brief"

    try:
        if wants_details:
            print("DEBUG: Generating fresh meeting details for export")
            from .meeting_details_tool import prepare_meeting_details_tool
            result = prepare_meeting_details_tool(user_request, tool_context)
        else:
            print("DEBUG: Generating fresh meeting brief for export")
            from .meeting_brief_tool import prepare_meeting_brief_tool
            result = prepare_meeting_brief_tool(user_request, tool_context)

        if isinstance(result, dict) and 'panel_markdown' in result:
            fresh_content = result['panel_markdown']
            print(f"DEBUG: Generated fresh {content_type} content ({len(fresh_content)} chars)")
        else:
            print(f"DEBUG: Unexpected result format from {content_type} tool: {type(result)}")

    except Exception as e:
        print(f"DEBUG: Error generating fresh content: {e}")
        fresh_content = None

    # Step 2: Store the fresh content in state for the export tool to access
    if fresh_content and hasattr(tool_context, 'state'):
        try:
            if hasattr(tool_context.state, '__setitem__'):
                tool_context.state['_export_content'] = fresh_content
                tool_context.state['_export_content_type'] = content_type
            else:
                setattr(tool_context.state, '_export_content', fresh_content)
                setattr(tool_context.state, '_export_content_type', content_type)
            print(f"DEBUG: Stored fresh {content_type} content for export ({len(fresh_content)} chars)")
        except Exception as e:
            print(f"DEBUG: Error storing fresh content: {e}")

    # Step 3: Call the actual export tool
    from .export_tool import export_to_google_docs_tool
    return export_to_google_docs_tool(tool_context)


# Legacy function name for backward compatibility
def export_to_google_docs_tool(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Legacy wrapper - calls the new wrapper with user request from state
    """
    user_request = ""
    if hasattr(tool_context, 'state'):
        try:
            if hasattr(tool_context.state, 'get'):
                user_request = tool_context.state.get('_user_query', '')
            else:
                user_request = getattr(tool_context.state, '_user_query', '')
        except Exception:
            pass

    return export_to_google_docs_tool_wrapper(user_request, tool_context)