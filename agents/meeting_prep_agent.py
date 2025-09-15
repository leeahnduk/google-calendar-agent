from __future__ import annotations

import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

import vertexai
from vertexai.preview import reasoning_engines
from vertexai import agent_engines

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Load environment variables from .env file (follow sample pattern)
load_dotenv()

print("loading .env")

# Import centralized settings
from config.settings import load_settings

settings = load_settings()
google_cloud_project = settings.google_cloud_project
google_cloud_location = settings.google_cloud_location
staging_bucket = settings.staging_bucket
auth_id = settings.auth_id
agent_display_name = settings.agent_display_name


def current_datetime(callback_context: CallbackContext):
    # get current date time
    now = datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    callback_context.state["_time"] = formatted_time


def whoami(callback_context: CallbackContext, creds):
    user_info_service = build('oauth2', 'v2', credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    user_email = user_info.get('email')
    callback_context.state['_user_email'] = user_email

    calendar_service = build('calendar', 'v3', credentials=creds)
    # Get the user's primary calendar to find their timezone
    calendar_list_entry = calendar_service.calendarList().get(
        calendarId='primary').execute()
    user_timezone = calendar_list_entry.get('timeZone')
    callback_context.state['_user_tz'] = user_timezone

    print(f"User's primary calendar timezone: {user_timezone}")


def prereq_setup(callback_context: CallbackContext):
    print("**** PREREQ SETUP ****")
    access_token = callback_context.state[f"temp:{auth_id}"]
    creds = Credentials(token=access_token)
    current_datetime(callback_context)
    whoami(callback_context, creds)


# Tool: prepare_meeting_brief (wraps our internal utilities)
def prepare_meeting_brief(tool_context: ToolContext):
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

    @dataclass
    class DriveDocument:
        id: str
        name: str
        link: str
        content: str = ""
        mime_type: str = ""
        source: str = "drive"  # "drive", "gmail", "attachment"
        relevance_score: float = 0.0
        last_modified: str = ""
        size: str = ""
        owner: str = ""

    @dataclass
    class GmailAttachment:
        filename: str
        mime_type: str
        size: int
        attachment_id: str
        message_id: str

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
                            content=""  # Will be filled later if needed
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

    def _search_gmail_attachments(gmail_service, meeting_title: str, attendee_emails: List[str], description: str = "") -> List[DriveDocument]:
        """Search Gmail for emails between attendees and extract attachments"""
        try:
            gmail_docs = []

            # Build search queries for Gmail
            search_queries = []

            # Search for emails between attendees
            if len(attendee_emails) >= 2:
                for i, email1 in enumerate(attendee_emails[:3]):  # Limit to avoid too many queries
                    for email2 in attendee_emails[i+1:4]:  # Limit combinations
                        if email1 and email2:
                            search_queries.append(f"from:{email1} to:{email2}")
                            search_queries.append(f"from:{email2} to:{email1}")

            # Search for emails with meeting title keywords
            if meeting_title:
                title_words = re.findall(r'\b\w+\b', meeting_title.lower())
                meaningful_words = [word for word in title_words if len(word) > 3]
                for word in meaningful_words[:3]:  # Limit keywords
                    search_queries.append(f'subject:"{word}"')
                    search_queries.append(f'"{word}"')

            # Search for emails with attachments
            search_queries.append("has:attachment")

            # Execute Gmail searches
            for query in search_queries[:8]:  # Limit total queries
                try:
                    # Search for messages
                    results = gmail_service.users().messages().list(
                        userId='me',
                        q=query,
                        maxResults=10
                    ).execute()

                    messages = results.get('messages', [])

                    for message in messages:
                        try:
                            # Get message details
                            msg = gmail_service.users().messages().get(
                                userId='me',
                                id=message['id'],
                                format='full'
                            ).execute()

                            # Extract attachments
                            payload = msg.get('payload', {})
                            attachments = []

                            def extract_attachments_from_payload(payload):
                                if 'parts' in payload:
                                    for part in payload['parts']:
                                        if part.get('filename'):
                                            attachment = GmailAttachment(
                                                filename=part.get('filename', ''),
                                                mime_type=part.get('mimeType', ''),
                                                size=part.get('body', {}).get('size', 0),
                                                attachment_id=part.get('body', {}).get('attachmentId', ''),
                                                message_id=message['id']
                                            )
                                            attachments.append(attachment)
                                        # Recursively check nested parts
                                        if 'parts' in part:
                                            extract_attachments_from_payload(part)
                                elif payload.get('filename'):
                                    attachment = GmailAttachment(
                                        filename=payload.get('filename', ''),
                                        mime_type=payload.get('mimeType', ''),
                                        size=payload.get('body', {}).get('size', 0),
                                        attachment_id=payload.get('body', {}).get('attachmentId', ''),
                                        message_id=message['id']
                                    )
                                    attachments.append(attachment)

                            extract_attachments_from_payload(payload)

                            # Convert Gmail attachments to DriveDocument format
                            for attachment in attachments:
                                if attachment.filename and attachment.size > 0:
                                    # Create a pseudo Drive link for Gmail attachments
                                    gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{message['id']}"

                                    doc = DriveDocument(
                                        id=f"gmail_{attachment.attachment_id}",
                                        name=attachment.filename,
                                        link=gmail_link,
                                        content="",  # Gmail attachments need special handling
                                        mime_type=attachment.mime_type,
                                        source="gmail",
                                        relevance_score=0.0,  # Will be calculated later
                                        last_modified=msg.get('internalDate', ''),
                                        size=str(attachment.size),
                                        owner="Gmail"
                                    )
                                    gmail_docs.append(doc)

                                    # Limit results
                                    if len(gmail_docs) >= 10:
                                        break

                            if len(gmail_docs) >= 10:
                                break

                        except Exception:
                            continue  # Skip problematic messages

                    if len(gmail_docs) >= 10:
                        break

                except Exception:
                    continue  # Skip failed queries

            return gmail_docs[:10]  # Return top 10 Gmail attachments

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

    def _build_comprehensive_document_table(documents: List[DriveDocument]) -> str:
        """Build a comprehensive table of relevant documents and resources"""
        if not documents:
            return "## 📋 Relevant Documents & Resources\n\nNo relevant documents found for this meeting."

        # Create a simpler, more presentation-friendly format
        content = "## 📋 Relevant Documents & Resources\n\n"
        
        for i, doc in enumerate(documents[:10], 1):  # Show top 10 most relevant documents
            # Format document name (truncate if too long)
            doc_name = doc.name[:60] + "..." if len(doc.name) > 60 else doc.name

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
                        last_modified = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                    else:
                        # Drive uses ISO format
                        last_modified = datetime.fromisoformat(doc.last_modified.replace('Z', '+00:00')).strftime("%Y-%m-%d")
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

            # Create document entry with better formatting
            content += f"### {i}. [{doc_name}]({doc.link})\n"
            content += f"**Type:** {file_type} | **Source:** {source_emoji} | **Relevance:** {relevance_stars} {relevance_text}\n"
            content += f"**Modified:** {last_modified} | **Size:** {size_display}\n\n"

        # Add summary statistics
        source_counts = {}
        for doc in documents:
            source_counts[doc.source] = source_counts.get(doc.source, 0) + 1

        summary = f"**📊 Summary:** {len(documents)} relevant documents found"
        if source_counts:
            summary += " ("
            summary_parts = []
            for source, count in source_counts.items():
                source_name = {"attachment": "Direct attachments", "gmail": "Gmail attachments", "drive": "Drive documents"}.get(source, source)
                summary_parts.append(f"{count} {source_name}")
            summary += ", ".join(summary_parts) + ")"

        return content + summary

    def _get_drive_document_content(drive_service, file_id: str) -> DriveDocument:
        """Get Drive document metadata and content"""
        try:
            # Get file metadata
            file_meta = drive_service.files().get(fileId=file_id, fields="id,name,mimeType,webViewLink").execute()

            doc = DriveDocument(
                id=file_id,
                name=file_meta.get("name", "Unknown"),
                link=file_meta.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view"),
                mime_type=file_meta.get("mimeType", "")
            )

            # Try to get content for various file types
            try:
                if "document" in doc.mime_type or "google-apps.document" in doc.mime_type:
                    # Google Docs
                    content = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
                    doc.content = content.decode('utf-8')[:3000]  # Increased limit for better analysis
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

            # Initialize Vertex AI and Gemini
            vertexai.init(project=google_cloud_project, location=google_cloud_location)
            model = GenerativeModel("gemini-2.5-flash")

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

            historical_summary = f"""
## 📚 Historical Context (Recurring Meeting)

**Previous Instance**: {recent_date}
**Previous Description**: {recent_description[:500]}{'...' if len(recent_description) > 500 else ''}

**Meeting History**: This meeting has occurred {len(past_instances)} time(s) in the last 60 days.

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
                return "## 📅 Calendar Context\n\n" + "\n".join(overview_sections) + "\n"
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

    def _parse_time_request(user_query: str) -> Optional[datetime]:
        """Parse user query to extract specific time request. Handles formats like 4:00p.m, 4:00 p.m, 4p.m, 4 p.m, 4 pm, 4 am."""
        import re
        from datetime import datetime, timedelta

        query = user_query.lower()

        # Patterns to detect time, with and without 'at'
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(a\.?.m\.?.|p\.?.m\.?)', # 4:00p.m, 4:00 p.m.
            r'(\d{1,2})\s*(a\.?.m\.?.|p\.?.m\.?)',       # 4p.m, 4 pm
        ]

        target_time = None
        for pattern in time_patterns:
            # Also check for 'at 2pm' style
            for prefix in [r'at\s+', '']:
                full_pattern = prefix + pattern
                match = re.search(full_pattern, query)
                if match:
                    groups = match.groups()
                    hour = int(groups[0])

                    if ':' in pattern:
                        minute = int(groups[1])
                        ampm_raw = groups[2]
                    else:
                        minute = 0
                        ampm_raw = groups[1]

                    # Normalize am/pm
                    ampm = 'pm' if ampm_raw.startswith('p') else 'am'

                    # Convert to 24-hour format
                    if ampm == 'pm' and hour != 12:
                        hour += 12
                    elif ampm == 'am' and hour == 12:
                        hour = 0

                    # Create naive datetime for today
                    today = datetime.now().date()
                    target_time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))

                    # Handle Singapore timezone (UTC+8) if specified
                    if 'sgt' in query or 'singapore' in query:
                        target_time = target_time - timedelta(hours=8)

                    # Found a match, exit loops
                    break
            if target_time:
                break

        return target_time

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

    # Initialize Gmail service for email and attachment search
    try:
        gmail_service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        gmail_service = None  # Gmail integration is optional

    # Parse user query to determine if they want a specific meeting
    user_query = tool_context.user_query.lower() if hasattr(tool_context, 'user_query') else ""
    
    # Check if user is asking for a specific meeting time
    target_event = None
    specific_time_requested = False
    
    # Look for time patterns in the query
    time_patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)',
        r'(\d{1,2})\s*(am|pm)',
        r'(\d{1,2}):(\d{2})',
        r'at\s+(\d{1,2}):(\d{2})',
        r'(\d{1,2}):(\d{2})\s*(am|pm)\s*meeting',
        r'meeting\s*at\s*(\d{1,2}):(\d{2})',
        r'(\d{1,2})\s*(am|pm)\s*meeting',
        r'meeting\s*(\d{1,2})\s*(am|pm)'
    ]
    
    import re
    target_time = None
    for pattern in time_patterns:
        match = re.search(pattern, user_query)
        if match:
            specific_time_requested = True
            groups = match.groups()
            if len(groups) >= 2:
                hour = int(groups[0])
                minute = int(groups[1]) if groups[1] else 0
                ampm = groups[2].lower() if len(groups) > 2 and groups[2] else None
                
                # Convert to 24-hour format
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                target_time = f"{hour:02d}:{minute:02d}"
                break
    
    # Get upcoming events - expanded to next 7 days for broader calendar insights
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=7)).isoformat()

    try:
        events_result = (
            calendar_service.events()
            .list(calendarId="primary", timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime", maxResults=50)
            .execute()
        )
        items = events_result.get("items", [])
        if not items:
            return {"panel_markdown": "## 📅 Calendar Overview\n\nNo upcoming meetings found in your calendar for the next 7 days.\n\n💡 **What I can help with:**\n- Schedule analysis and optimization\n- Meeting preparation for future events\n- Calendar management insights"}

        # Parse user query for specific time request
        user_query = tool_context.user_query.lower() if hasattr(tool_context, 'user_query') else ""
        target_time = _parse_time_request(user_query)

        target_event_item = None
        selection_note = ""

        if target_time:
            # User requested a specific time, try to find it
            for event in items:
                start_str = event.get("start", {}).get("dateTime", "")
                if start_str:
                    try:
                        event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)

                        # Make target_time aware of UTC for comparison
                        target_time_utc = target_time.replace(tzinfo=timezone.utc)

                        diff = abs((event_time - target_time_utc).total_seconds())
                        if diff <= 1800:  # Within a 30-minute window
                            target_event_item = event
                            break
                    except ValueError:
                        continue # Ignore events with invalid time format

            if target_event_item:
                start_str = target_event_item.get("start", {}).get("dateTime", "")
                event_time_utc = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)
                time_display = event_time_utc.strftime("%I:%M %p %Z")
                selection_note = f"\n> 💡 **Selected Meeting**: Found a meeting at {time_display} that matched your request.\n"
            else:
                selection_note = f"\n> ⚠️ **Note**: Could not find a meeting around the specified time. Showing the next upcoming meeting instead.\n"

        # If no specific time was requested or no match was found, default to the next meeting
        if not target_event_item:
            target_event_item = items[0]
            if not target_time: # Only add this note if no time was ever requested
                 selection_note = "\n> 💡 **Showing Next Meeting**: To see a brief for a different meeting, specify a time (e.g., 'brief for my 2pm meeting').\n"


        # Get the selected event with full details
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

        # Process comprehensive document search
        all_documents = []

        # 1. Process direct Drive attachments from meeting
        file_ids = _extract_drive_file_ids(ev)
        for file_id in file_ids:
            doc = _get_drive_document_content(drive_service, file_id)
            doc.source = "attachment"  # Mark as direct attachment
            all_documents.append(doc)

        # 2. Search for related documents in Google Drive
        attendee_emails = [att.email for att in attendees if att.email]
        related_drive_docs = _search_related_drive_documents(
            drive_service,
            event_context.summary,
            attendee_emails,
            event_context.description or ""
        )
        all_documents.extend(related_drive_docs)

        # 3. Search for Gmail attachments between attendees
        if gmail_service:
            gmail_docs = _search_gmail_attachments(
                gmail_service,
                event_context.summary,
                attendee_emails,
                event_context.description or ""
            )
            all_documents.extend(gmail_docs)

        # 4. Calculate relevance scores and sort documents
        all_documents = _calculate_document_relevance(
            all_documents,
            event_context.summary,
            event_context.description or "",
            attendee_emails
        )

        # 5. Get content for top documents (limit to avoid API limits)
        for doc in all_documents[:10]:  # Process top 10 most relevant documents
            if not doc.content and doc.source != "gmail":  # Skip Gmail docs (content extraction complex)
                try:
                    content_doc = _get_drive_document_content(drive_service, doc.id)
                    doc.content = content_doc.content
                except Exception:
                    pass  # Skip if content extraction fails

        # Get comprehensive analysis including historical and chat context
        attendee_emails = [att.email for att in attendees if att.email]
        ai_insights = _research_with_gemini(event_context.summary, event_context.description or "", attendee_emails)
        attachment_analysis = _analyze_attachments_with_gemini(all_documents[:5], event_context.summary)  # Analyze top 5 documents
        historical_context = _get_historical_context(calendar_service, event_context)
        chat_context = "## 💬 Chat Context\n\n*Chat analysis has been temporarily disabled to improve performance.*"

        # Build comprehensive document table
        document_table = _build_comprehensive_document_table(all_documents)

        # Build enhanced meeting brief with legacy attachments section for direct attachments only
        attachments_section = ""
        direct_attachments = [doc for doc in all_documents if doc.source == "attachment"]
        if direct_attachments:
            attachments_section = "\n## 📎 Direct Meeting Attachments\n\n"
            for i, doc in enumerate(direct_attachments, 1):
                attachments_section += f"### {i}. [{doc.name}]({doc.link})\n"
                attachments_section += f"**Type:** {doc.mime_type}\n"
                if doc.content and doc.content != "Content could not be extracted" and "Error accessing" not in doc.content:
                    # Show first few lines of content
                    content_preview = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                    attachments_section += f"**Preview:** {content_preview}\n\n"
                else:
                    attachments_section += "\n"

        # Add calendar overview section
        calendar_overview = _build_calendar_overview(items, now)

        markdown = f"""# 📅 Meeting Brief{selection_note}

## {event_context.summary}

**🕐 Time:** {event_context.start_iso}
**⏱️ Duration:** Until {event_context.end_iso}

**📝 Description:** {event_context.description or 'No description provided'}

**👥 Attendees:**
{chr(10).join([f"- {att.email} ({att.response_status or 'No response'})" for att in event_context.attendees]) if event_context.attendees else 'No attendees listed'}

**📍 Location:** {event_context.location or 'No location specified'}

**🔗 Meeting Link:** [{event_context.html_link}]({event_context.html_link})
{attachments_section}

{calendar_overview}

{historical_context}

{chat_context}

{document_table}

## 📋 Document Analysis

{attachment_analysis}

## 🧠 AI Research & Insights

{ai_insights}

---
*📊 Brief generated automatically by Enhanced Meeting Prep Agent with comprehensive document search, Gmail integration, and AI analysis*"""

        return {"panel_markdown": markdown}

    except Exception as e:
        return {"panel_markdown": f"Error accessing calendar: {str(e)}"}


# Define sub-agent that owns the tool (follow sample pattern)
prepare_brief = LlmAgent(
    name="prepare_brief",
    model=settings.sub_agent_model,
    description="Gathers Calendar/Drive/Slack context and prepares a concise meeting brief.",
    instruction="""
You specialize in preparing meeting briefs. Always use the provided tool to gather
and compose the brief. Do not greet. Keep the output concise and actionable.
    """,
    tools=[prepare_meeting_brief],
    before_agent_callback=prereq_setup,
)


# Root agent delegates to the sub-agent (follow sample pattern)
root_agent = LlmAgent(
    model=settings.root_agent_model,
    name="root_agent",
    instruction="""
You are a comprehensive meeting preparation and calendar management assistant. You help users with a wide range of calendar and meeting-related tasks.

If the user greets you, you should greet them back, introduce yourself and your capabilities, and then wait for their query. Your capabilities are:
- **Meeting Preparation**: Generate detailed briefs with attachments, chat context, and AI insights
- **Calendar Management**: Show upcoming meetings, schedule analysis, and time management
- **Meeting Discovery**: Find specific meetings by date, attendee, or topic
- **Document Analysis**: Analyze meeting attachments and related documents
- **Chat Integration**: Search Google Chat and Slack conversations for meeting context
- **Schedule Insights**: Provide patterns, conflicts, and optimization suggestions

After the initial greeting, for any subsequent calendar or meeting question, always use the \"prepare_brief\" sub-agent to get comprehensive calendar data, then provide the specific information requested.

**Types of questions to handle with prepare_brief tool:**
- Today's/tomorrow's schedule
- Weekly meeting overview
- Meeting patterns and analysis
- Schedule conflicts and busy periods
- Meeting attendee information
- Document and attachment summaries
- Time management suggestions
- **Specific meeting requests by time**

**Example responses for common questions:**

*"What meetings do I have today?"*
→ ALWAYS use prepare_brief tool and extract today's meetings from the calendar context

*"How many meetings do I have today?"*
→ ALWAYS use prepare_brief tool and count today's meetings

*"Show my schedule this week"*
→ ALWAYS use prepare_brief tool and provide a week overview based on calendar data

*"What's my next meeting about?"*
→ ALWAYS use prepare_brief tool to get details about the upcoming meeting

*"Generate meeting brief for my 2pm meeting"*
→ ALWAYS use prepare_brief tool to get details about the specific 2pm meeting

*"Prepare brief for the meeting at 5:30pm"*
→ ALWAYS use prepare_brief tool to get details about the specific 5:30pm meeting

*"Find meetings with [person]"*
→ ALWAYS use prepare_brief tool and analyze attendee information

*"Do I have any conflicts tomorrow?"*
→ ALWAYS use prepare_brief tool and analyze the schedule for conflicts

**Special Handling for Specific Meeting Requests:**
- When users mention specific times (e.g., "2pm meeting", "meeting at 5:30pm"), the agent will automatically find and brief that specific meeting
- The agent supports various time formats: "2pm", "2:30pm", "14:30", "meeting at 2pm", etc.
- If no exact match is found, it will find the closest meeting within 30 minutes

**Always be proactive**: If someone asks a simple calendar question, offer to prepare a meeting brief or provide additional helpful context.

Do not greet the user if you have already greeted them. Always provide actionable, specific information.
    """,
    sub_agents=[prepare_brief],
)


def deploy_agent_engine_app():
    app = reasoning_engines.AdkApp(
        agent=root_agent,
        enable_tracing=True,
    )

    vertexai.init(
        project=google_cloud_project,  # Your project ID.
        location=google_cloud_location,  # Your cloud region.
        staging_bucket=staging_bucket,  # Your staging bucket.
    )

    agent_config = {
        "agent_engine": app,
        "display_name": agent_display_name,
        "requirements": "requirements.txt",
        # "extra_packages": [".env"]
    }

    existing_agents = list(
        agent_engines.list(filter=f'display_name="{agent_display_name}"'))

    if existing_agents:
        print(f"Number of existing agents found for {agent_display_name}:" + str(
            len(list(existing_agents))))
        print(existing_agents[0].resource_name)

    if existing_agents:
        # update the existing agent
        remote_app = agent_engines.update(
            resource_name=existing_agents[0].resource_name, **agent_config)
    else:
        # create a new agent
        remote_app = agent_engines.create(**agent_config)

    return None


if __name__ == "__main__":
    deploy_agent_engine_app()
