"""
Meeting Brief Tool - Generates concise meeting briefs following the exact format specified.
"""

from google.adk.tools.tool_context import ToolContext


def prepare_meeting_brief_tool(meeting_query: str = "", tool_context: ToolContext = None):
    """
    Generate a concise meeting brief following the specified format.
    Handles: brief, summary, quick overview queries

    Args:
        meeting_request: The user's request/query for the meeting brief
        tool_context: Tool context containing authentication state
    """
    print("DEBUG: ========== MEETING BRIEF TOOL STARTED ==========")
    # Enhanced implementation with attachment processing and Gemini research
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

    def _to_iso(dt_str: str) -> str:
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return dt_str

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

        # Check for numbered meeting selection using saved meeting index
        target_event_item = items[0]  # Default to first meeting

        # Check if search tool has already selected a specific meeting
        selected_meeting_data = None
        selection_note = ""
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
            r'brief for meeting (\d+)',
            r'meeting (\d+)',
            r'number (\d+)',
            r'(\d+)'  # Just a number
        ]

        meeting_number = None
        print(f"DEBUG: Testing patterns against user_query: '{user_query}'")
        for pattern in number_patterns:
            match = re.search(pattern, user_query, re.IGNORECASE)
            print(f"DEBUG: Pattern '{pattern}' match result: {match}")
            if match:
                meeting_number = int(match.group(1))
                print(f"DEBUG: Extracted meeting_number: {meeting_number}")
                break

        if meeting_number:
            print(f"DEBUG: Looking for meeting number {meeting_number} for brief")

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
                            selection_note = f"\\n> 🔢 **Selected Meeting #{meeting_number}**: {status_emoji} {target_event_item.get('summary', '')} at {time_display}.\\n"
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

        # Format attendees
        attendees_list = ", ".join([att.email for att in event_context.attendees]) if event_context.attendees else "No attendees listed"

        # Format time in Singapore timezone for user display
        try:
            from datetime import timedelta, timezone
            singapore_tz = timezone(timedelta(hours=8))

            start_dt = datetime.fromisoformat(event_context.start_iso.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(event_context.end_iso.replace("Z", "+00:00"))

            # Convert to Singapore timezone
            start_dt_sg = start_dt.astimezone(singapore_tz)
            end_dt_sg = end_dt.astimezone(singapore_tz)

            start_time = start_dt_sg.strftime("%Y-%m-%d, %H:%M")
            end_time = end_dt_sg.strftime("%H:%M")
        except:
            start_time = event_context.start_iso
            end_time = event_context.end_iso

        # Enhanced AI analysis for meeting context
        def _analyze_meeting_with_gemini(meeting_title: str, description: str, location: str, attendees: List[str]) -> Dict[str, str]:
            """Use Gemini to analyze meeting and provide enhanced context"""
            try:
                import os
                google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
                google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

                if google_cloud_project:
                    vertexai.init(project=google_cloud_project, location=google_cloud_location)
                    model = GenerativeModel("gemini-2.5-flash")

                    analysis_prompt = f"""
Analyze this upcoming meeting and provide a comprehensive brief:

Meeting Title: {meeting_title}
Description: {description or "No description provided"}
Location: {location or "No location specified"}
Attendees: {', '.join(attendees)}

Please provide:

1. **Context Analysis** (2-3 paragraphs): What is this meeting likely about? What's the business context and importance? What type of meeting is this (planning, review, decision-making, etc.)?

2. **Key Challenges** (1-2 sentences): What are the main challenges or decisions that need to be discussed based on the meeting title and context?

3. **Preparation Insights** (3-4 concise talking points): What should attendees prepare or focus on? What are the likely discussion topics and outcomes expected?

Format your response as:
CONTEXT: [context analysis]
CHALLENGES: [key challenges]
TALKING_POINTS: [numbered list of 3-4 points]

Be specific and actionable based on the meeting details provided."""

                    response = model.generate_content(analysis_prompt)
                    ai_response = response.text

                    # Parse the structured response
                    context_match = re.search(r'CONTEXT:\s*(.*?)(?=CHALLENGES:|$)', ai_response, re.DOTALL)
                    challenges_match = re.search(r'CHALLENGES:\s*(.*?)(?=TALKING_POINTS:|$)', ai_response, re.DOTALL)
                    talking_points_match = re.search(r'TALKING_POINTS:\s*(.*?)$', ai_response, re.DOTALL)

                    return {
                        "context": context_match.group(1).strip() if context_match else f"Meeting about {meeting_title}",
                        "challenges": challenges_match.group(1).strip() if challenges_match else "Review agenda and prepare talking points for effective discussion.",
                        "talking_points": talking_points_match.group(1).strip() if talking_points_match else "1. Review meeting objectives\n2. Prepare questions and concerns\n3. Share relevant updates"
                    }
                else:
                    # Fallback when no AI available
                    return {
                        "context": f"Meeting about {meeting_title}" + (f": {description[:100]}..." if description else ""),
                        "challenges": "Review agenda and prepare talking points for effective discussion.",
                        "talking_points": "1. Review meeting objectives and expected outcomes\n2. Prepare any questions or concerns to discuss\n3. Share relevant updates from your work"
                    }
            except Exception as e:
                print(f"AI analysis error: {e}")
                return {
                    "context": f"Meeting about {meeting_title}" + (f": {description[:100]}..." if description else ""),
                    "challenges": "Review agenda and prepare talking points for effective discussion.",
                    "talking_points": "1. Review meeting objectives and expected outcomes\n2. Prepare any questions or concerns to discuss\n3. Share relevant updates from your work"
                }

        # Get enhanced AI analysis
        attendee_emails = [att.email for att in event_context.attendees if att.email]
        ai_analysis = _analyze_meeting_with_gemini(
            event_context.summary,
            event_context.description or "",
            event_context.location or "",
            attendee_emails
        )

        key_context = ai_analysis["context"]
        key_challenge = ai_analysis["challenges"]
        talking_points = ai_analysis["talking_points"]

        # Enhanced Google Drive document search with relevance scoring
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

        def _search_related_drive_documents(drive_service, meeting_title: str, attendee_emails: List[str], description: str = "") -> List[DriveDocument]:
            """Search Google Drive for documents related to the meeting"""
            try:
                related_docs = []

                # Extract keywords from meeting title and description
                keywords = []
                if meeting_title:
                    # Split title into meaningful words
                    title_words = re.findall(r'\b\w+\b', meeting_title.lower())
                    keywords.extend([word for word in title_words if len(word) > 3])

                if description:
                    desc_words = re.findall(r'\b\w+\b', description.lower())
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
                                size=str(file_data.get('size', ''))
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
                meeting_words = set(re.findall(r'\b\w+\b', meeting_text))

                # Remove common words
                common_words = {'meeting', 'call', 'sync', 'review', 'discussion', 'update', 'status', 'weekly', 'daily', 'monthly', 'team', 'project', 'with', 'for', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from', 'by', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'}
                meeting_words = meeting_words - common_words

                # Calculate relevance for each document
                for doc in docs:
                    score = 0.0

                    # Title matching
                    doc_title_words = set(re.findall(r'\b\w+\b', doc.name.lower()))
                    title_overlap = len(meeting_words.intersection(doc_title_words))
                    score += title_overlap * 2.0  # Higher weight for title matches

                    # Content matching (if available)
                    if doc.content:
                        doc_content_words = set(re.findall(r'\b\w+\b', doc.content.lower()))
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

        def _search_drive_for_relevant_documents(drive_service, meeting_title: str, event_data: dict) -> str:
            """Search Google Drive for documents relevant to the meeting topic using sophisticated relevance scoring"""
            try:
                # Extract attendee emails
                attendees = event_data.get("attendees", [])
                attendee_emails = [att.get("email", "") for att in attendees if att.get("email")]
                meeting_description = event_data.get("description", "") or ""

                # Search for related documents
                related_docs = _search_related_drive_documents(drive_service, meeting_title, attendee_emails, meeting_description)

                if not related_docs:
                    return "No relevant documents found in Google Drive for this meeting topic."

                # Calculate relevance scores
                scored_docs = _calculate_document_relevance(related_docs, meeting_title, meeting_description, attendee_emails)

                # Filter for high relevance (score >= 4) and get top 2
                high_relevance_docs = [doc for doc in scored_docs if doc.relevance_score >= 4.0][:2]

                if not high_relevance_docs:
                    # If no high relevance docs, show top 2 overall
                    high_relevance_docs = scored_docs[:2]

                # Format the results
                result = f"Found {len(high_relevance_docs)} relevant document(s) in Google Drive:\n\n"
                for i, doc in enumerate(high_relevance_docs, 1):
                    # Create document description based on type
                    doc_description = ""
                    if "document" in doc.mime_type or "google-apps.document" in doc.mime_type:
                        doc_description = "Document with meeting-related content and analysis"
                    elif "spreadsheet" in doc.mime_type:
                        doc_description = "Spreadsheet with data and metrics relevant to the discussion"
                    elif "presentation" in doc.mime_type:
                        doc_description = "Presentation slides with key information and updates"
                    elif "pdf" in doc.mime_type:
                        doc_description = "PDF document with formal documentation or reports"
                    else:
                        doc_description = "File containing relevant meeting information"

                    # Include relevance score in the description
                    relevance_text = f"(Relevance: {doc.relevance_score:.1f})"
                    result += f"{i}. **[{doc.name}]({doc.link})** - {doc_description} {relevance_text}\n"

                return result

            except Exception as e:
                print(f"DEBUG: Error searching Google Drive: {e}")
                return "Unable to search Google Drive for relevant documents at this time."

        # Process documents for brief format
        def _process_documents_for_brief(drive_service, event_data, meeting_title: str) -> str:
            """Process and analyze documents for brief format"""
            try:
                import re

                # Extract file IDs from attachments
                file_ids = []
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

                # Extract from description URLs
                description = event_data.get("description", "") or ""
                drive_urls = re.findall(r"https://drive\.google\.com/[^\s]+", description)
                for url in drive_urls:
                    match = re.search(r"/file/d/([a-zA-Z0-9-_]+)", url)
                    if match:
                        file_ids.append(match.group(1))

                file_ids = list(set(file_ids))  # Remove duplicates

                if not file_ids:
                    # No direct attachments, search Google Drive for relevant documents
                    print("DEBUG: No direct attachments found, searching Google Drive for relevant documents")
                    return _search_drive_for_relevant_documents(drive_service, meeting_title, event_data)

                documents = []
                for file_id in file_ids[:5]:  # Limit to 5 docs for brief
                    try:
                        # Get file metadata
                        file_meta = drive_service.files().get(
                            fileId=file_id,
                            fields="id,name,mimeType,webViewLink"
                        ).execute()

                        doc_name = file_meta.get("name", "Unknown Document")
                        doc_link = file_meta.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
                        mime_type = file_meta.get("mimeType", "")

                        # Try to get content summary
                        content_summary = ""
                        try:
                            if "document" in mime_type or "google-apps.document" in mime_type:
                                content = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
                                text_content = content.decode('utf-8')[:500]  # First 500 chars
                                content_summary = f"Document content preview: {text_content}..."
                            elif "spreadsheet" in mime_type:
                                content_summary = "Spreadsheet with data and analysis"
                            elif "presentation" in mime_type:
                                content_summary = "Presentation with slides and content"
                            elif "pdf" in mime_type:
                                content_summary = "PDF document - view directly for content"
                            else:
                                content_summary = f"{mime_type.split('/')[-1].upper()} file"
                        except:
                            content_summary = "Document available for review"

                        documents.append({
                            'name': doc_name,
                            'link': doc_link,
                            'summary': content_summary
                        })

                    except Exception as e:
                        print(f"Error processing document {file_id}: {e}")
                        continue

                if not documents:
                    return "Documents attached but could not be processed - please review before meeting."

                # Format document list with summaries
                result = ""
                for i, doc in enumerate(documents, 1):
                    result += f"{i}. **[{doc['name']}]({doc['link']})** - {doc['summary']}\n"

                return result

            except Exception as e:
                print(f"Error processing documents: {e}")
                return "Documents attached - please review before meeting."

        # Get enhanced document analysis
        docs_section = _process_documents_for_brief(drive_service, ev, event_context.summary)

        brief = f"""📅**Meeting:** "{event_context.summary}" **Time:** {start_time} - {end_time}

* **Attendees:** {attendees_list}
* **Location:** {event_context.location or "Not specified"}
* **Meeting Link:** [Join Meeting]({event_context.html_link})

📚**Context:** {key_context}

💬**Key Challenge to Discuss:** {key_challenge}

📎**Related Documents:**
{docs_section}

📋**Potential Talking Points:**
{talking_points}

If you'd like to dig deeper, I have more details ready. Just ask for the full document analysis, a list of questions to consider for the meeting, or insights into the project's history.{selection_note}"""

        return {"panel_markdown": brief}

    except Exception as e:
        return {"panel_markdown": f"Error generating meeting brief: {str(e)}"}