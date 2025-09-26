"""
Export Tool - Exports meeting briefs and analysis to Google Docs.
"""

from google.adk.tools.tool_context import ToolContext


def export_to_google_docs_tool(tool_context: ToolContext):
    """
    Export meeting briefs and analysis to Google Docs.
    Creates a new document in user's Google Drive.
    """
    from datetime import datetime
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    import re

    try:
        # Get auth_id from environment or use default
        import os
        auth_id = os.getenv("AUTH_ID", "grab_meeting_multi")

        # Get OAuth credentials from tool context
        if not hasattr(tool_context, "state"):
            return {"panel_markdown": "Error: No authentication state available."}

        token_key = f"temp:{auth_id}"
        try:
            if hasattr(tool_context.state, 'get'):
                access_token = tool_context.state.get(token_key)
            else:
                access_token = getattr(tool_context.state, token_key, None)
        except Exception as e:
            print(f"DEBUG: Error accessing access token: {e}")
            return {"panel_markdown": f"Error: Unable to access authentication state: {str(e)}"}

        if not access_token:
            return {"panel_markdown": "Error: No access token available. Please authenticate first."}

        creds = Credentials(token=access_token)

        # Create Google Docs and Drive services
        docs_service = build('docs', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        # For this implementation, we'll generate a fresh meeting brief using the current tools
        # Import the meeting brief tool directly
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        from tools.meeting_brief_tool import prepare_meeting_brief_tool

        # Get the meeting brief content using the same approach as the multi-agent system
        brief_result = prepare_meeting_brief_tool("", tool_context)
        content_to_export = brief_result.get("panel_markdown", "No content available to export.")

        # Clean up markdown for Google Docs (remove markdown formatting)
        clean_content = re.sub(r'[*#`]', '', content_to_export)
        clean_content = re.sub(r'\\n', '\n', clean_content)

        # Create new document
        document = docs_service.documents().create(body={
            'title': f'Meeting Brief - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        }).execute()

        doc_id = document['documentId']

        # Insert content
        requests = [{
            'insertText': {
                'location': {'index': 1},
                'text': clean_content
            }
        }]

        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        # Get document URL
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        return {"panel_markdown": f"✅ Successfully exported to Google Docs: [View Document]({doc_url})"}

    except Exception as e:
        return {"panel_markdown": f"Error exporting to Google Docs: {str(e)}"}