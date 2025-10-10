"""
Meeting Details Tool - Provides comprehensive meeting analysis and detailed insights.
"""

from google.adk.tools.tool_context import ToolContext


def prepare_meeting_details_tool(meeting_query: str = "", tool_context: ToolContext = None):
    """
    Generate comprehensive meeting details and analysis.
    Handles: details, deep dive, full analysis, insights queries

    Args:
        meeting_query: The user's request/query for the meeting details
        tool_context: Tool context containing authentication state
    """
    print("DEBUG: ========== MEETING DETAILS TOOL STARTED ==========")
    print(f"DEBUG: Received meeting_query parameter: '{meeting_query}'")
    # Enhanced implementation with comprehensive attachment processing and Gemini research
    from datetime import datetime, timedelta, timezone
    from dataclasses import dataclass
    from typing import List, Optional, Dict, Any
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    import re
    import vertexai
    from vertexai.generative_models import GenerativeModel

    @dataclass
    class EventAttendee:
        email: str
        response_status: Optional[str] = None

    @dataclass
    class EventContext:
        id: str
        summary: str
        description: str
        start_iso: str
        end_iso: str
        attendees: List[EventAttendee]
        recurring_event_id: Optional[str] = None
        html_link: Optional[str] = None
        location: Optional[str] = None
        attachments: List[Dict] = None

    @dataclass
    class DriveDocument:
        id: str
        name: str
        link: str
        content: str = ""
        mime_type: str = ""
        source: str = "drive"
        relevance_score: float = 0.0
        last_modified: str = ""
        size: str = ""
        owner: str = ""

    def _to_iso(dt_str: str) -> str:
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return dt_str

    def _extract_drive_file_ids(event_data: Dict) -> List[str]:
        """Extract Google Drive file IDs from event attachments and description"""
        file_ids = []

        # From attachments
        attachments = event_data.get("attachments", [])
        for att in attachments:
            file_id = att.get("fileId")
            if file_id:
                file_ids.append(file_id)
            # Also try to extract from fileUrl
            file_url = att.get("fileUrl", "")
            if file_url:
                match = re.search(r"/file/d/([a-zA-Z0-9-_]+)", file_url)
                if match:
                    file_ids.append(match.group(1))

        # From description URLs
        description = event_data.get("description", "") or ""
        drive_urls = re.findall(r"https://drive\.google\.com/[^\s]+", description)
        for url in drive_urls:
            match = re.search(r"/file/d/([a-zA-Z0-9-_]+)", url)
            if match:
                file_ids.append(match.group(1))

        return list(set(file_ids))  # Remove duplicates

    def _get_drive_document_content(drive_service, file_id: str) -> DriveDocument:
        """Get Drive document metadata and content"""
        try:
            # Get file metadata
            file_meta = drive_service.files().get(fileId=file_id, fields="id,name,mimeType,webViewLink,modifiedTime,size,owners").execute()

            doc = DriveDocument(
                id=file_id,
                name=file_meta.get("name", "Unknown"),
                link=file_meta.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view"),
                mime_type=file_meta.get("mimeType", ""),
                last_modified=file_meta.get("modifiedTime", ""),
                size=str(file_meta.get("size", "")),
                owner=file_meta.get("owners", [{}])[0].get("displayName", "Unknown") if file_meta.get("owners") else "Unknown"
            )

            # Try to get content for various file types
            try:
                if "document" in doc.mime_type or "google-apps.document" in doc.mime_type:
                    # Google Docs
                    content = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
                    doc.content = content.decode('utf-8')[:3000]  # Increased limit for detailed analysis
                elif "spreadsheet" in doc.mime_type or "google-apps.spreadsheet" in doc.mime_type:
                    # Google Sheets
                    content = drive_service.files().export(fileId=file_id, mimeType="text/csv").execute()
                    doc.content = content.decode('utf-8')[:3000]
                elif "presentation" in doc.mime_type or "google-apps.presentation" in doc.mime_type:
                    # Google Slides
                    content = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
                    doc.content = content.decode('utf-8')[:3000]
                elif "text" in doc.mime_type:
                    # Plain text files
                    content = drive_service.files().get_media(fileId=file_id).execute()
                    doc.content = content.decode('utf-8')[:3000]
                elif "pdf" in doc.mime_type:
                    # For PDFs, we can't extract content via Drive API easily
                    doc.content = "PDF file - Content extraction not available via Drive API. Please review the document directly."
                else:
                    doc.content = f"File type '{doc.mime_type}' - Content preview not available"
            except Exception as e:
                doc.content = f"Content could not be extracted: {str(e)}"

            return doc

        except Exception as e:
            return DriveDocument(
                id=file_id,
                name="Unknown Document",
                link=f"https://drive.google.com/file/d/{file_id}/view",
                content=f"Error accessing document: {str(e)}"
            )

    def _analyze_attachments_with_gemini(attachments: List[DriveDocument], meeting_title: str) -> str:
        """Use Gemini to analyze meeting attachments and provide insights"""
        try:
            if not attachments:
                return "No attachments to analyze."

            # Initialize Vertex AI and Gemini only if we have the required config
            if google_cloud_project:
                vertexai.init(project=google_cloud_project, location=google_cloud_location)
                model = GenerativeModel("gemini-2.5-flash")
            else:
                return "AI analysis unavailable - missing project configuration."

            # Prepare attachment content for analysis
            attachment_info = ""
            for doc in attachments:
                attachment_info += f"\n**Document: {doc.name}**\n"
                attachment_info += f"Type: {doc.mime_type}\n"
                if doc.content and "Content extraction not available" not in doc.content and "Error accessing" not in doc.content:
                    attachment_info += f"Content Preview:\n{doc.content}\n"
                else:
                    attachment_info += f"Content: {doc.content}\n"
                attachment_info += "---\n"

            analysis_prompt = f"""
Analyze these meeting attachments for the upcoming meeting "{meeting_title}":

{attachment_info}

Please provide a comprehensive analysis including:

1. **Document Summary**: Brief summary of what each document contains
2. **Key Points**: Most important information from the attachments
3. **Meeting Relevance**: How these documents relate to the meeting agenda
4. **Action Items**: Any tasks or decisions that seem to be needed based on the content
5. **Preparation Insights**: What attendees should focus on or prepare based on these documents
6. **Questions to Consider**: Relevant questions that might arise from reviewing these materials

Format your response in clear markdown sections. Be specific and actionable in your analysis."""

            response = model.generate_content(analysis_prompt)
            return response.text

        except Exception as e:
            return f"Attachment analysis unavailable: {str(e)}"

    def _build_comprehensive_document_table(documents: List[DriveDocument]) -> str:
        """Build a comprehensive table of relevant documents and resources"""
        if not documents:
            return "## 📋 Relevant Documents & Resources\\n\\nNo relevant documents found for this meeting."

        # Create a detailed, comprehensive format
        content = "## 📋 Relevant Documents & Resources\\n\\n"

        for i, doc in enumerate(documents[:15], 1):  # Show top 15 most relevant documents
            # Format document name (truncate if too long)
            doc_name = doc.name[:80] + "..." if len(doc.name) > 80 else doc.name

            # Format file type with emoji
            file_type = "📄 Document"
            if "spreadsheet" in doc.mime_type:
                file_type = "📊 Spreadsheet"
            elif "presentation" in doc.mime_type:
                file_type = "📽️ Presentation"
            elif "pdf" in doc.mime_type:
                file_type = "📕 PDF"
            elif "image" in doc.mime_type:
                file_type = "🖼️ Image"
            elif "text" in doc.mime_type:
                file_type = "📝 Text"
            elif "folder" in doc.mime_type:
                file_type = "📁 Folder"
            else:
                file_type = f"📎 {doc.mime_type.split('/')[-1].upper()}" if doc.mime_type else "📎 File"

            # Format source
            source_emoji = {
                "attachment": "📎 Direct",
                "gmail": "📧 Gmail",
                "drive": "💾 Drive"
            }.get(doc.source, "❓ Unknown")

            # Format relevance score
            relevance_stars = "⭐" * min(5, int(doc.relevance_score))
            relevance_text = "High" if doc.relevance_score >= 4 else "Medium" if doc.relevance_score >= 2 else "Low"

            # Format last modified
            last_modified = "Unknown"
            if doc.last_modified:
                try:
                    if doc.source == "gmail":
                        # Gmail uses internal date format
                        import time
                        timestamp = int(doc.last_modified) / 1000
                        last_modified = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
                    else:
                        # Drive uses ISO format
                        last_modified = datetime.fromisoformat(doc.last_modified.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                except:
                    last_modified = "Unknown"

            # Format size
            size_display = "Unknown"
            if doc.size:
                try:
                    size_bytes = int(doc.size)
                    if size_bytes < 1024:
                        size_display = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_display = f"{size_bytes // 1024} KB"
                    else:
                        size_display = f"{size_bytes // (1024 * 1024)} MB"
                except:
                    size_display = doc.size

            # Create comprehensive document entry
            content += f"### {i}. [{doc_name}]({doc.link})\\n"
            content += f"**Type:** {file_type} | **Source:** {source_emoji} | **Relevance:** {relevance_stars} {relevance_text}\\n"
            content += f"**Modified:** {last_modified} | **Size:** {size_display} | **Owner:** {doc.owner}\\n"

            # Add content preview for detailed analysis
            if doc.content and len(doc.content) > 50 and "Error accessing" not in doc.content:
                preview = doc.content[:300] + "..." if len(doc.content) > 300 else doc.content
                content += f"**Content Preview:** {preview}\\n\\n"
            else:
                content += "\\n"

        return content

    try:
        # Get environment variables directly
        import os
        auth_id = os.getenv("AUTH_ID", "meeting-prep-multi")
        google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

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
        calendar_service = build("calendar", "v3", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # Parse user query to determine if they want a specific meeting
        print(f"DEBUG: tool_context attributes: {dir(tool_context)}")
        print(f"DEBUG: tool_context.state: {getattr(tool_context, 'state', 'No state')}")

        # Get user query from parameter first, then fallback to tool context state
        user_query = meeting_query
        print(f"DEBUG: Received meeting_query parameter: '{meeting_query}'")

        if not user_query and tool_context and hasattr(tool_context, 'state'):
            try:
                if hasattr(tool_context.state, 'get'):
                    if tool_context.state.get('_user_query'):
                        user_query = tool_context.state.get('_user_query')
                        print(f"DEBUG: Found user_query via tool_context.state.get('_user_query'): '{user_query}'")
                    elif tool_context.state.get('user_input'):
                        user_query = tool_context.state.get('user_input')
                        print(f"DEBUG: Found user_query via tool_context.state.get('user_input'): '{user_query}'")
                    else:
                        print(f"DEBUG: No user_query found in tool_context state")
                else:
                    # Fallback to direct attribute access
                    user_query = getattr(tool_context.state, '_user_query', None) or getattr(tool_context.state, 'user_input', None)
                    if user_query:
                        print(f"DEBUG: Found user_query via getattr: '{user_query}'")
                    else:
                        print(f"DEBUG: No user_query found in tool_context state via getattr")
            except Exception as e:
                print(f"DEBUG: Error accessing user_query from state: {e}")
        elif not user_query:
            print(f"DEBUG: No tool_context or state available")

        print(f"DEBUG: Final user_query: '{user_query}'")

        # Get events from today onwards - including past events from today
        now = datetime.now(timezone.utc)
        # Start from beginning of today in Singapore timezone, then convert to UTC
        singapore_tz = timezone(timedelta(hours=8))
        today_sg = datetime.now(singapore_tz).date()
        start_of_today_sg = datetime.combine(today_sg, datetime.min.time()).replace(tzinfo=singapore_tz)
        start_of_today_utc = start_of_today_sg.astimezone(timezone.utc)

        time_min = start_of_today_utc.isoformat()
        time_max = (now + timedelta(days=7)).isoformat()

        events_result = (
            calendar_service.events()
            .list(calendarId="primary", timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime", maxResults=50)
            .execute()
        )
        items = events_result.get("items", [])
        if not items:
            return {"panel_markdown": "## 📅 Calendar Overview\\n\\nNo upcoming meetings found in your calendar for the next 7 days."}

        # Check for numbered meeting selection
        target_event_item = items[0]  # Default to first meeting
        selection_note = ""

        # Check if search tool has already selected a specific meeting
        selected_meeting_data = None
        if hasattr(tool_context, 'state'):
            try:
                if hasattr(tool_context.state, 'get'):
                    selected_meeting_data = tool_context.state.get('_selected_meeting_data')
                else:
                    selected_meeting_data = getattr(tool_context.state, '_selected_meeting_data', None)

                if selected_meeting_data:
                    print(f"DEBUG: Using meeting selected by search tool: {selected_meeting_data.get('summary', '')}")
                    target_event_item = selected_meeting_data
                    selection_note = "\\n> 🔍 **Selected Meeting**: Using meeting found by search.\\n"
                else:
                    print("DEBUG: No pre-selected meeting found, using default logic")
            except Exception as e:
                print(f"DEBUG: Error accessing selected meeting data: {e}")

        # Check for numbered meeting selection patterns
        number_patterns = [
            r'details for meeting (\d+)',
            r'meeting (\d+)',
            r'number (\d+)',
            r'(\d+)'  # Just a number
        ]

        meeting_number = None
        for pattern in number_patterns:
            match = re.search(pattern, user_query, re.IGNORECASE)
            if match:
                meeting_number = int(match.group(1))
                break

        if meeting_number:
            print(f"DEBUG: Looking for meeting number {meeting_number} for details")

            # Try to get saved meeting index from meetings_today_agent output
            saved_meeting_index = None
            print(f"DEBUG: tool_context has state: {hasattr(tool_context, 'state')}")
            if hasattr(tool_context, 'state'):
                try:
                    # Try to access state keys safely
                    if hasattr(tool_context.state, 'keys'):
                        print(f"DEBUG: tool_context.state keys: {list(tool_context.state.keys())}")
                    else:
                        print(f"DEBUG: tool_context.state type: {type(tool_context.state)}")
                except Exception as e:
                    print(f"DEBUG: Error accessing state keys: {e}")

                # Try to get meeting_index from state
                try:
                    if hasattr(tool_context.state, 'get'):
                        saved_meeting_index = tool_context.state.get('meeting_index')
                    else:
                        # Fallback to direct access
                        saved_meeting_index = getattr(tool_context.state, 'meeting_index', None)

                    if saved_meeting_index:
                        print(f"DEBUG: Found saved meeting index with {len(saved_meeting_index)} meetings")
                        print(f"DEBUG: First meeting in index: {saved_meeting_index[0] if saved_meeting_index else 'None'}")
                    else:
                        print("DEBUG: 'meeting_index' not found in tool_context.state")
                except Exception as e:
                    print(f"DEBUG: Error accessing meeting_index: {e}")
                    saved_meeting_index = None
            else:
                print("DEBUG: tool_context has no state attribute")
                saved_meeting_index = None

            if saved_meeting_index:
                # Use the saved meeting index
                selected_meeting_data = None
                for meeting_data in saved_meeting_index:
                    if meeting_data.get('number') == meeting_number:
                        selected_meeting_data = meeting_data
                        break

                if selected_meeting_data:
                    # Find the corresponding event by ID
                    meeting_id = selected_meeting_data.get('id')
                    for event in items:
                        if event.get('id') == meeting_id:
                            target_event_item = event
                            status = selected_meeting_data.get('status', 'unknown')
                            status_emoji = {"past": "✅", "current": "🟢", "upcoming": "🟡"}.get(status, "❓")
                            time_display = selected_meeting_data.get('start_time_display', 'Unknown time')
                            selection_note = f"\\n> 🔢 **Detailed Analysis for Meeting #{meeting_number}**: {status_emoji} {target_event_item.get('summary', '')} at {time_display}.\\n"
                            print(f"DEBUG: Found meeting #{meeting_number} from saved index: {target_event_item.get('summary', '')}")
                            break
                    else:
                        selection_note = f"\\n> ⚠️ **Note**: Meeting #{meeting_number} found in index but not in current calendar results. Showing first meeting instead.\\n"
                else:
                    selection_note = f"\\n> ⚠️ **Note**: Meeting #{meeting_number} not found in saved index. Showing first meeting instead.\\n"
            else:
                # Fallback: No saved index available, inform user to run meetings list first
                selection_note = f"\\n> 💡 **Tip**: To use numbered meeting selection, first ask 'how many meetings do I have left today?' to generate the meeting index.\\n"
        event_id = target_event_item["id"]
        ev = calendar_service.events().get(calendarId="primary", eventId=event_id).execute()

        attendees_raw = ev.get("attendees", [])
        attendees = [
            EventAttendee(email=a.get("email", ""), response_status=a.get("responseStatus")) for a in attendees_raw
        ]
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or ""
        end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date") or ""

        event_context = EventContext(
            id=ev.get("id", ""),
            summary=ev.get("summary", ""),
            description=ev.get("description", ""),
            start_iso=_to_iso(start),
            end_iso=_to_iso(end),
            attendees=attendees,
            recurring_event_id=ev.get("recurringEventId"),
            html_link=ev.get("htmlLink"),
            location=ev.get("location"),
            attachments=ev.get("attachments", [])
        )

        # Process comprehensive document search for detailed analysis
        all_documents = []

        def _search_related_drive_documents(drive_service, meeting_title: str, attendee_emails: List[str], description: str = "") -> List[DriveDocument]:
            """Search Google Drive for documents related to the meeting"""
            try:
                related_docs = []

                # Extract keywords from meeting title and description
                keywords = []
                if meeting_title:
                    # Split title into meaningful words
                    title_words = re.findall(r'\\b\\w+\\b', meeting_title.lower())
                    keywords.extend([word for word in title_words if len(word) > 3])

                if description:
                    desc_words = re.findall(r'\\b\\w+\\b', description.lower())
                    keywords.extend([word for word in desc_words if len(word) > 3])

                # Remove common words and duplicates
                common_words = {'meeting', 'call', 'sync', 'review', 'discussion', 'update', 'status', 'weekly', 'daily', 'monthly', 'team', 'project', 'with', 'for', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from', 'by', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'}
                keywords = list(set([kw for kw in keywords if kw not in common_words]))

                # Search queries to try
                search_queries = []

                # Add meeting title as search query
                if meeting_title:
                    search_queries.append(f"name contains '{meeting_title}'")

                # Add keyword-based searches
                for keyword in keywords[:5]:  # Limit to top 5 keywords
                    search_queries.append(f"name contains '{keyword}'")
                    search_queries.append(f"fullText contains '{keyword}'")

                # Add attendee-based searches (if we have attendee emails)
                for email in attendee_emails[:3]:  # Limit to top 3 attendees
                    if email:
                        # Extract name from email for search
                        name_part = email.split('@')[0].replace('.', ' ').replace('_', ' ')
                        if name_part:
                            search_queries.append(f"fullText contains '{name_part}'")

                # Execute searches
                for query in search_queries[:10]:  # Limit total queries
                    try:
                        results = drive_service.files().list(
                            q=query,
                            pageSize=10,
                            fields="files(id,name,mimeType,webViewLink,modifiedTime,size,owners)",
                            orderBy="modifiedTime desc"
                        ).execute()

                        for file_data in results.get('files', []):
                            # Skip if we already have this file
                            if any(doc.id == file_data['id'] for doc in related_docs):
                                continue

                            doc = DriveDocument(
                                id=file_data['id'],
                                name=file_data.get('name', 'Unknown'),
                                link=file_data.get('webViewLink', f"https://drive.google.com/file/d/{file_data['id']}/view"),
                                mime_type=file_data.get('mimeType', ''),
                                content="",  # Will be filled later if needed
                                source="drive",
                                last_modified=file_data.get('modifiedTime', ''),
                                size=str(file_data.get('size', '')),
                                owner=file_data.get('owners', [{}])[0].get('displayName', 'Unknown') if file_data.get('owners') else 'Unknown'
                            )
                            related_docs.append(doc)

                            # Limit total results
                            if len(related_docs) >= 15:
                                break

                        if len(related_docs) >= 15:
                            break

                    except Exception:
                        continue  # Skip failed queries

                return related_docs[:15]  # Return top 15 results

            except Exception as e:
                return []

        def _calculate_document_relevance(docs: List[DriveDocument], meeting_title: str, meeting_description: str, attendee_emails: List[str]) -> List[DriveDocument]:
            """Calculate relevance scores for documents based on meeting context"""
            try:
                # Extract keywords from meeting context
                meeting_text = f"{meeting_title} {meeting_description}".lower()
                meeting_words = set(re.findall(r'\\b\\w+\\b', meeting_text))

                # Remove common words
                common_words = {'meeting', 'call', 'sync', 'review', 'discussion', 'update', 'status', 'weekly', 'daily', 'monthly', 'team', 'project', 'with', 'for', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from', 'by', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'}
                meeting_words = meeting_words - common_words

                # Calculate relevance for each document
                for doc in docs:
                    score = 0.0

                    # Title matching
                    doc_title_words = set(re.findall(r'\\b\\w+\\b', doc.name.lower()))
                    title_overlap = len(meeting_words.intersection(doc_title_words))
                    score += title_overlap * 2.0  # Higher weight for title matches

                    # Content matching (if available)
                    if doc.content:
                        doc_content_words = set(re.findall(r'\\b\\w+\\b', doc.content.lower()))
                        content_overlap = len(meeting_words.intersection(doc_content_words))
                        score += content_overlap * 1.0

                    # Source preference
                    if doc.source == "attachment":
                        score += 3.0  # Highest priority for direct attachments
                    elif doc.source == "gmail":
                        score += 2.0  # High priority for Gmail attachments
                    elif doc.source == "drive":
                        score += 1.0  # Standard priority for Drive search

                    # File type preference
                    if "document" in doc.mime_type or "presentation" in doc.mime_type:
                        score += 1.5
                    elif "spreadsheet" in doc.mime_type:
                        score += 1.0
                    elif "pdf" in doc.mime_type:
                        score += 0.5

                    # Attendee relevance (if document name contains attendee names)
                    for email in attendee_emails:
                        if email:
                            name_part = email.split('@')[0].replace('.', ' ').replace('_', ' ')
                            if name_part.lower() in doc.name.lower():
                                score += 1.0

                    doc.relevance_score = score

                # Sort by relevance score
                docs.sort(key=lambda x: x.relevance_score, reverse=True)
                return docs

            except Exception:
                return docs  # Return original list if scoring fails

        # 1. Process direct Drive attachments from meeting
        file_ids = _extract_drive_file_ids(ev)
        for file_id in file_ids:
            doc = _get_drive_document_content(drive_service, file_id)
            doc.source = "attachment"  # Mark as direct attachment
            doc.relevance_score = 5.0  # Highest relevance for direct attachments
            all_documents.append(doc)

        # 2. Search for related documents in Google Drive
        attendee_emails = [att.email for att in event_context.attendees if att.email]
        related_drive_docs = _search_related_drive_documents(
            drive_service,
            event_context.summary,
            attendee_emails,
            event_context.description or ""
        )
        all_documents.extend(related_drive_docs)

        # 3. Calculate relevance scores and sort documents
        all_documents = _calculate_document_relevance(
            all_documents,
            event_context.summary,
            event_context.description or "",
            attendee_emails
        )

        # Build comprehensive document table for detailed analysis
        document_table = _build_comprehensive_document_table(all_documents)

        # Get comprehensive analysis with AI
        attachment_analysis = _analyze_attachments_with_gemini(all_documents, event_context.summary)

        # Format attendees with detailed status
        attendees_section = ""
        if event_context.attendees:
            attendees_section = "**👥 Attendees:**\\n"
            for att in event_context.attendees:
                status_emoji = {
                    "accepted": "✅",
                    "declined": "❌",
                    "tentative": "❓",
                    "needsAction": "⏳"
                }.get(att.response_status, "❔")
                attendees_section += f"- {att.email} {status_emoji} ({att.response_status or 'No response'})\\n"
        else:
            attendees_section = "**👥 Attendees:** No attendees listed\\n"

        # Format detailed time information in Singapore timezone
        try:
            start_dt = datetime.fromisoformat(event_context.start_iso.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(event_context.end_iso.replace("Z", "+00:00"))

            # Convert to Singapore timezone (UTC+8)
            singapore_tz = timezone(timedelta(hours=8))
            start_dt_sg = start_dt.astimezone(singapore_tz)
            end_dt_sg = end_dt.astimezone(singapore_tz)
            duration = end_dt_sg - start_dt_sg

            detailed_time = f"""**🕐 Time:** {start_dt_sg.strftime("%A, %B %d, %Y at %I:%M %p")} (SGT)
**⏱️ Duration:** {duration} (until {end_dt_sg.strftime("%I:%M %p")})
**🌍 Timezone:** Singapore Time (SGT)"""
        except:
            detailed_time = f"""**🕐 Time:** {event_context.start_iso}
**⏱️ Duration:** Until {event_context.end_iso}"""

        # Get additional comprehensive sections that match the original agent output

        # Get historical context
        def _get_historical_context(calendar_service, event_context: EventContext) -> str:
            """Get historical context for recurring meetings"""
            try:
                if not event_context.recurring_event_id:
                    return "This is not a recurring meeting - no historical context available."

                # Search for past instances of this recurring meeting
                from datetime import datetime, timedelta, timezone

                # Look back 60 days for previous instances
                now = datetime.now(timezone.utc)
                time_min = (now - timedelta(days=60)).isoformat()
                time_max = now.isoformat()

                events_result = calendar_service.events().list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime"
                ).execute()

                # Find previous instances of this recurring meeting
                past_instances = []
                for item in events_result.get("items", []):
                    if (
                        item.get("recurringEventId") == event_context.recurring_event_id and
                        item.get("id") != event_context.id
                    ):
                        past_instances.append(item)

                if not past_instances:
                    return "No previous instances of this recurring meeting found in the last 60 days."

                # Get the most recent instance
                most_recent = past_instances[-1] if past_instances else None
                if not most_recent:
                    return "No previous instances found."

                recent_date = most_recent.get("start", {}).get("dateTime", "Unknown date")
                recent_description = most_recent.get("description", "No description available")

                historical_summary = f"""**Previous Instance:** {recent_date}
**Previous Description:** {recent_description[:500]}{'...' if len(recent_description) > 500 else ''}

**Meeting History:** This meeting has occurred {len(past_instances)} time(s) in the last 60 days.

*Note: For detailed notes from previous sessions, check your meeting notes repository or shared documents.*"""
                return historical_summary

            except Exception as e:
                return f"Historical context unavailable: {str(e)}"

        def _build_calendar_overview(all_events: List[Dict], current_time: datetime) -> str:
            """Build a calendar overview showing upcoming meetings"""
            try:
                if len(all_events) <= 1:
                    return ""

                # Categorize events by timeframe
                today_events = []
                tomorrow_events = []
                week_events = []

                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow_start = today_start + timedelta(days=1)
                week_end = today_start + timedelta(days=7)

                for event in all_events[1:]:  # Skip first event (main meeting)
                    start_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                    if not start_str:
                        continue

                    try:
                        event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

                        if today_start <= event_time < tomorrow_start:
                            today_events.append(event)
                        elif tomorrow_start <= event_time < tomorrow_start + timedelta(days=1):
                            tomorrow_events.append(event)
                        elif event_time < week_end:
                            week_events.append(event)
                    except:
                        continue

                overview_sections = []

                # Today's remaining meetings
                if today_events:
                    overview_sections.append(f"**📅 Today ({current_time.strftime('%A, %B %d')})** - {len(today_events)} more meeting(s):")
                    for event in today_events[:3]:  # Show up to 3
                        start_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                        summary = event.get("summary", "No title")
                        try:
                            event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            time_str = event_time.strftime("%I:%M %p")
                        except:
                            time_str = "Time TBD"
                        overview_sections.append(f"  - {time_str}: {summary}")

                # Tomorrow's meetings
                if tomorrow_events:
                    tomorrow_date = (current_time + timedelta(days=1)).strftime('%A, %B %d')
                    overview_sections.append(f"**📅 Tomorrow ({tomorrow_date})** - {len(tomorrow_events)} meeting(s):")
                    for event in tomorrow_events[:3]:  # Show up to 3
                        start_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                        summary = event.get("summary", "No title")
                        try:
                            event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            time_str = event_time.strftime("%I:%M %p")
                        except:
                            time_str = "Time TBD"
                        overview_sections.append(f"  - {time_str}: {summary}")

                # Week summary
                total_week_meetings = len(today_events) + len(tomorrow_events) + len(week_events) + 1  # +1 for current meeting
                if total_week_meetings > 1:
                    overview_sections.append(f"**📊 This Week Summary:** {total_week_meetings} total meetings")

                if overview_sections:
                    return "\\n".join(overview_sections)
                else:
                    return ""

            except Exception:
                return ""

        def _research_with_gemini(meeting_title: str, description: str, attendees: List[str]) -> str:
            """Use Gemini to research meeting context and provide insights"""
            try:
                # Initialize Vertex AI and Gemini
                vertexai.init(project=google_cloud_project, location=google_cloud_location)
                model = GenerativeModel("gemini-2.5-flash")

                research_prompt = f"""
Analyze this upcoming meeting and provide helpful context and insights:

Meeting: {meeting_title}
Description: {description}
Attendees: {', '.join(attendees)}

Please provide:
1. Key topics likely to be discussed based on the meeting title and description
2. Potential preparation points for attendees
3. Relevant background context if you recognize any technical terms or project names
4. Suggested questions or discussion points
5. Any notable patterns or insights about this type of meeting

Keep the response concise but informative, formatted in markdown."""

                response = model.generate_content(research_prompt)
                return response.text

            except Exception as e:
                return f"AI research unavailable: {str(e)}"

        # Get all the comprehensive sections
        now = datetime.now(timezone.utc)
        historical_context = _get_historical_context(calendar_service, event_context)

        # Get calendar overview (need to fetch more events for this)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=7)).isoformat()
        events_result = calendar_service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=50
        ).execute()
        all_events = events_result.get("items", [])
        calendar_overview = _build_calendar_overview(all_events, now)

        # Get AI research
        attendee_emails = [att.email for att in event_context.attendees if att.email]
        ai_insights = _research_with_gemini(event_context.summary, event_context.description or "", attendee_emails)

        # Build legacy attachments section for direct attachments only
        attachments_section = ""
        direct_attachments = [doc for doc in all_documents if doc.source == "attachment"]
        if direct_attachments:
            attachments_section = "\\n## 📎 Direct Meeting Attachments\\n\\n"
            for i, doc in enumerate(direct_attachments, 1):
                attachments_section += f"### {i}. {doc.name}\\n"
                attachments_section += f"**Type:** {doc.mime_type}\\n"
                if doc.content and doc.content != "Content could not be extracted" and "Error accessing" not in doc.content:
                    # Show first few lines of content
                    content_preview = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                    attachments_section += f"**Preview:** {content_preview}\\n\\n"
                else:
                    attachments_section += "\\n"

        # Chat context sections (matching original format)
        slack_context = """**📱 Slack Context**
*Slack analysis has been temporarily disabled to improve performance.*"""

        google_chat_context = """**💬 Google Chat Context**
*Google Chat analysis has been temporarily disabled to improve performance.*"""

        # Build comprehensive meeting details matching original format exactly
        markdown = f"""# 📅 Meeting Details: {event_context.summary}

{detailed_time}

**📝 Description:** {event_context.description or 'No description provided'}

{attendees_section}

**📍 Location:** {event_context.location or 'No location specified'}

**🔗 Meeting Link:** [{event_context.html_link}]({event_context.html_link})
{attachments_section}

-----

## 📅 Calendar Context

{calendar_overview}

-----

## 📚 Historical Context (Recurring Meeting)

{historical_context}

-----

## 💬 Slack Context

{slack_context}

-----

## 💬 Google Chat Context

{google_chat_context}

-----

{document_table}

-----

## 📋 Document Analysis

{attachment_analysis}

-----

## 🧠 AI Research & Insights

{ai_insights}

---
*📊 Detailed analysis generated by Enhanced Meeting Prep Agent with comprehensive document analysis and AI insights*{selection_note}"""

        return {"panel_markdown": markdown}

    except Exception as e:
        return {"panel_markdown": f"Error generating comprehensive meeting details: {str(e)}"}