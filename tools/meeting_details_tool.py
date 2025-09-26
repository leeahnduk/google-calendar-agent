"""
Meeting Details Tool - Provides comprehensive meeting analysis and detailed insights.
"""

from google.adk.tools.tool_context import ToolContext


def prepare_meeting_details_tool(tool_context: ToolContext):
    """
    Generate comprehensive meeting details and analysis.
    Handles: details, deep dive, full analysis, insights queries
    """
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
        auth_id = os.getenv("AUTH_ID", "grab_meeting_multi")
        google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

        # Get OAuth credentials from tool context
        if not hasattr(tool_context, "state"):
            return {"panel_markdown": "Error: No authentication state available."}

        token_key = f"temp:{auth_id}"
        access_token = tool_context.state.get(token_key)
        if not access_token:
            return {"panel_markdown": "Error: No access token available. Please authenticate first."}

        creds = Credentials(token=access_token)
        calendar_service = build("calendar", "v3", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # Parse user query to determine if they want a specific meeting
        user_query = tool_context.user_query if hasattr(tool_context, 'user_query') else ""

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
            if hasattr(tool_context, 'state') and 'meeting_index' in tool_context.state:
                saved_meeting_index = tool_context.state['meeting_index']
                print(f"DEBUG: Found saved meeting index with {len(saved_meeting_index)} meetings")

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

        # 1. Process direct Drive attachments from meeting
        file_ids = _extract_drive_file_ids(ev)
        for file_id in file_ids:
            doc = _get_drive_document_content(drive_service, file_id)
            doc.source = "attachment"  # Mark as direct attachment
            doc.relevance_score = 5.0  # Highest relevance for direct attachments
            all_documents.append(doc)

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

        # Format detailed time information
        try:
            start_dt = datetime.fromisoformat(event_context.start_iso.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(event_context.end_iso.replace("Z", "+00:00"))
            duration = end_dt - start_dt

            detailed_time = f"""**🕐 Time:** {start_dt.strftime("%A, %B %d, %Y at %I:%M %p")}
**⏱️ Duration:** {duration} (until {end_dt.strftime("%I:%M %p")})
**🌍 Timezone:** {start_dt.strftime("%Z")}"""
        except:
            detailed_time = f"""**🕐 Time:** {event_context.start_iso}
**⏱️ Duration:** Until {event_context.end_iso}"""

        # Build comprehensive meeting details
        markdown = f"""# 📋 Comprehensive Meeting Analysis

## {event_context.summary}

{detailed_time}

**📝 Description:** {event_context.description or 'No description provided'}

{attendees_section}

**📍 Location:** {event_context.location or 'No location specified'}

**🔗 Meeting Link:** [{event_context.html_link}]({event_context.html_link})

{document_table}

## 📋 Comprehensive Document Analysis

{attachment_analysis}

## 🎯 Meeting Preparation Recommendations

### Pre-Meeting Actions:
1. **Review all attached documents** - Pay special attention to any action items or decisions required
2. **Prepare your updates** - Think about what progress or blockers you need to share
3. **List your questions** - Write down any clarifications needed from other attendees
4. **Check technical requirements** - Ensure your setup works for screen sharing if needed

### Discussion Focus Areas:
- Key decisions that need to be made during this meeting
- Progress updates from all attendees on relevant work streams
- Any blockers or challenges that need group problem-solving
- Next steps and accountability assignments

### Post-Meeting Follow-up:
- Document key decisions and action items
- Share meeting notes with all attendees
- Schedule follow-up meetings if needed
- Update project tracking systems with new information

---
*📊 Detailed analysis generated by Enhanced Meeting Prep Agent with comprehensive document analysis and AI insights*{selection_note}"""

        return {"panel_markdown": markdown}

    except Exception as e:
        return {"panel_markdown": f"Error generating comprehensive meeting details: {str(e)}"}