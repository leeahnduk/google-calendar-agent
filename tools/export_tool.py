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
        auth_id = os.getenv("AUTH_ID", "meeting-prep-multi")

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

        # The export agent calls prepare_meeting_brief or prepare_meeting_details in sequence before calling this export tool
        # We need to detect which content was generated and use that for export
        content_to_export = "No content available to export."

        # Check conversation context for fresh content from the export agent's workflow
        print("DEBUG: Checking for fresh content from export agent workflow...")

        # The export agent should have just called prepare_meeting_details or prepare_meeting_brief
        # Let's check various possible locations for the fresh content
        if hasattr(tool_context, 'state'):
            try:
                # Try multiple approaches to find the fresh content
                # Priority order: wrapper-stored content first, then other sources
                possible_keys = [
                    '_export_content',      # From export wrapper - highest priority
                    '_fresh_content',       # From any recent tool call
                    '_last_tool_response',  # From general tool responses
                    '_recent_content',      # From recent operations
                    'latest_response'       # From latest operations
                ]

                for key in possible_keys:
                    try:
                        if hasattr(tool_context.state, 'get'):
                            content = tool_context.state.get(key)
                        else:
                            content = getattr(tool_context.state, key, None)

                        if content:
                            if isinstance(content, dict) and 'panel_markdown' in content:
                                content_to_export = content['panel_markdown']
                                print(f"DEBUG: Found fresh content via key '{key}'")
                                break
                            elif isinstance(content, str) and len(content) > 100:
                                content_to_export = content
                                print(f"DEBUG: Found fresh content string via key '{key}'")
                                break
                    except Exception:
                        continue

                # If we still don't have content, check if there's any state that looks like fresh content
                if content_to_export == "No content available to export.":
                    try:
                        if hasattr(tool_context.state, 'keys'):
                            all_keys = list(tool_context.state.keys())
                            print(f"DEBUG: Available state keys: {all_keys}")

                            # Look for any key that might contain fresh meeting content
                            for key in all_keys:
                                if 'meeting' in key.lower() or 'content' in key.lower() or 'response' in key.lower():
                                    try:
                                        potential_content = tool_context.state.get(key)
                                        if isinstance(potential_content, dict) and 'panel_markdown' in potential_content:
                                            panel_content = potential_content['panel_markdown']
                                            if isinstance(panel_content, str) and len(panel_content) > 200:
                                                content_to_export = panel_content
                                                print(f"DEBUG: Found fresh content in state key '{key}'")
                                                break
                                    except Exception:
                                        continue
                    except Exception as e:
                        print(f"DEBUG: Error checking state keys: {e}")

            except Exception as e:
                print(f"DEBUG: Error accessing tool context state: {e}")

        # If still no fresh content found, generate new content based on user's export request
        if content_to_export == "No content available to export.":
            print("DEBUG: No fresh content found, generating new content for export")

            # Try to parse the user query to determine what type of content to generate
            user_query = ""
            if hasattr(tool_context, 'state'):
                try:
                    if hasattr(tool_context.state, 'get'):
                        user_query = tool_context.state.get('_user_query', '') or ""
                    else:
                        user_query = getattr(tool_context.state, '_user_query', '') or ""
                except Exception:
                    pass

            print(f"DEBUG: User query for content generation: '{user_query}'")

            # Determine if user wants details or brief based on the export request
            wants_details = any(keyword in user_query.lower() for keyword in [
                'details', 'detail', 'comprehensive', 'full analysis', 'in-depth',
                'thorough', 'deep dive', 'breakdown', 'elaborate', 'expanded'
            ]) if user_query else False

            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

            if wants_details:
                print("DEBUG: Generating fresh meeting details for export")
                from tools.meeting_details_tool import prepare_meeting_details_tool
                details_result = prepare_meeting_details_tool(user_query, tool_context)
                content_to_export = details_result.get("panel_markdown", "No content available to export.")
            else:
                print("DEBUG: Generating fresh meeting brief for export")
                from tools.meeting_brief_tool import prepare_meeting_brief_tool
                brief_result = prepare_meeting_brief_tool(user_query, tool_context)
                content_to_export = brief_result.get("panel_markdown", "No content available to export.")

        # Enhanced content handling for different response types
        print(f"DEBUG: Export content type: {type(content_to_export)}")
        print(f"DEBUG: Export content length: {len(str(content_to_export)) if content_to_export else 'None'}")
        print(f"DEBUG: Export content preview: {str(content_to_export)[:200]}...")

        # Check if this is Content object from Gemini/ADK
        if hasattr(content_to_export, '__class__') and 'Content' in str(type(content_to_export)):
            print("DEBUG: Detected Content object, extracting text...")

        if isinstance(content_to_export, dict):
            # It's a dictionary response from a tool
            clean_content = content_to_export.get("panel_markdown", str(content_to_export))
        elif hasattr(content_to_export, 'text'):
            # It's a Content object, extract the text
            clean_content = str(content_to_export.text)
        elif hasattr(content_to_export, 'parts') and content_to_export.parts:
            # It's a Content object with parts
            text_parts = []
            for part in content_to_export.parts:
                if hasattr(part, 'text'):
                    text_parts.append(part.text)
            clean_content = '\n'.join(text_parts) if text_parts else str(content_to_export)
        elif isinstance(content_to_export, str):
            # It's already a string
            clean_content = content_to_export
        elif hasattr(content_to_export, '__str__'):
            # Convert to string if it's not already
            clean_content = str(content_to_export)
        else:
            clean_content = "Content could not be extracted for export."

        print(f"DEBUG: Clean content type: {type(clean_content)}")
        print(f"DEBUG: Clean content length: {len(clean_content)}")
        print(f"DEBUG: Clean content preview: {clean_content[:200]}...")

        # Clean up markdown for Google Docs (remove markdown formatting)
        import re
        clean_content = re.sub(r'[*#`]', '', clean_content)
        clean_content = re.sub(r'\\n', '\n', clean_content)

        # Determine document type and create appropriate title
        doc_type = "Brief"  # Default

        # First check if wrapper provided content type
        if hasattr(tool_context, 'state'):
            try:
                if hasattr(tool_context.state, 'get'):
                    wrapper_content_type = tool_context.state.get('_export_content_type')
                else:
                    wrapper_content_type = getattr(tool_context.state, '_export_content_type', None)

                if wrapper_content_type:
                    doc_type = wrapper_content_type.title()  # "details" -> "Details", "brief" -> "Brief"
                    print(f"DEBUG: Using wrapper-provided content type: {doc_type}")
            except Exception as e:
                print(f"DEBUG: Error accessing wrapper content type: {e}")

        # Fallback: detect from content
        if doc_type == "Brief" and ("Meeting Details:" in clean_content or "📅 Meeting Details:" in clean_content):
            doc_type = "Details"

        print(f"DEBUG: Detected document type: {doc_type}")
        print(f"DEBUG: Content contains 'Meeting Details:': {'Meeting Details:' in clean_content}")
        print(f"DEBUG: Content contains '📅 Meeting Details:': {'📅 Meeting Details:' in clean_content}")

        # Extract meeting name from content
        meeting_name = "Unknown Meeting"
        try:
            # Try to extract meeting name from content
            import re
            # Try multiple patterns to extract meeting name
            patterns = [
                r'📅 Meeting (?:Brief|Details):\s*([^\n]+)',
                r'Meeting (?:Brief|Details):\s*([^\n]+)',
                r'# 📅 Meeting (?:Brief|Details):\s*([^\n]+)',
                r'Meeting:\s*"([^"]+)"'
            ]

            for pattern in patterns:
                match = re.search(pattern, clean_content)
                if match:
                    meeting_name = match.group(1).strip()
                    print(f"DEBUG: Extracted meeting name with pattern '{pattern}': '{meeting_name}'")
                    break

            if meeting_name != "Unknown Meeting":
                # Clean up the meeting name
                meeting_name = re.sub(r'[^\w\s-]', '', meeting_name)
                meeting_name = meeting_name[:50]  # Limit length
                print(f"DEBUG: Cleaned meeting name: '{meeting_name}'")
        except Exception as e:
            print(f"DEBUG: Error extracting meeting name: {e}")

        # Create document with descriptive title using Singapore time
        # Format: Meeting [Brief/Details] Notes - [Meeting Name] - [Date Time SGT]
        from datetime import timedelta, timezone
        singapore_tz = timezone(timedelta(hours=8))
        now_sgt = datetime.now(singapore_tz)
        document_title = f'Meeting {doc_type} Notes - {meeting_name} - {now_sgt.strftime("%Y-%m-%d %H:%M")}'
        print(f"DEBUG: Final document title: '{document_title}'")
        document = docs_service.documents().create(body={
            'title': document_title
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