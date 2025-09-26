"""
Core shared functions and data classes for the meeting preparation agent.

This module contains reusable components extracted from the monolithic
prepare_meeting_brief function to enable the multi-agent architecture.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re


@dataclass
class EventAttendee:
    """Represents a meeting attendee"""
    email: str
    response_status: Optional[str] = None


@dataclass
class EventContext:
    """Represents a calendar event/meeting with all relevant context"""
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
    """Represents a Google Drive document with metadata and content"""
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
    """Represents a Gmail attachment"""
    filename: str
    mime_type: str
    size: int
    attachment_id: str
    message_id: str


@dataclass
class MeetingContext:
    """Complete context for a meeting including all related data"""
    event: EventContext
    drive_documents: List[DriveDocument]
    slack_context: Optional[Dict] = None
    google_chat_context: Optional[Dict] = None
    gmail_attachments: List[GmailAttachment] = None
    historical_context: Optional[Dict] = None


def get_user_credentials(tool_context):
    """Extract user credentials from tool context - follows exact sample pattern"""
    # Import settings here to avoid circular imports
    from config.settings import load_settings
    settings = load_settings()

    # Follow exact pattern from sample/meeting_prep_agent.py
    if not hasattr(tool_context, "state"):
        return None, {"panel_markdown": "Error: No authentication state available."}

    token_key = f"temp:{settings.auth_id}"
    access_token = tool_context.state.get(token_key)
    if not access_token:
        return None, {"panel_markdown": "Error: No access token available. Please authenticate first."}

    creds = Credentials(token=access_token)
    return creds, None


def to_iso(dt_str: str) -> str:
    """Convert datetime string to ISO format"""
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except Exception:
        return dt_str


def extract_drive_file_ids(event_data: Dict) -> List[str]:
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


def find_next_meeting(calendar_service, user_timezone: str = None) -> EventContext:
    """Find the next upcoming meeting"""
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=7)).isoformat()

    events_result = (
        calendar_service.events()
        .list(calendarId="primary", timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime", maxResults=50)
        .execute()
    )
    items = events_result.get("items", [])

    if not items:
        raise ValueError("No upcoming meetings found in your calendar for the next 7 days")

    # Get the first event with full details
    event_item = items[0]
    event_id = event_item["id"]
    ev = calendar_service.events().get(calendarId="primary", eventId=event_id).execute()

    return _create_event_context_from_api_response(ev)


def find_meeting_by_time(calendar_service, time_query: str, user_timezone: str = None) -> EventContext:
    """Find meeting by specific time"""
    target_time = parse_time_request(time_query)
    if not target_time:
        raise ValueError(f"Could not parse time from query: {time_query}")

    # Search in a reasonable window around the target time
    search_start = target_time - timedelta(hours=12)
    search_end = target_time + timedelta(hours=12)

    events_result = (
        calendar_service.events()
        .list(
            calendarId="primary",
            timeMin=search_start.isoformat(),
            timeMax=search_end.isoformat(),
            singleEvents=True,
            orderBy="startTime"
        )
        .execute()
    )
    items = events_result.get("items", [])

    # Find the closest meeting within 30 minutes
    for event in items:
        start_str = event.get("start", {}).get("dateTime", "")
        if start_str:
            try:
                event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)
                diff = abs((event_time - target_time).total_seconds())
                if diff <= 1800:  # Within 30 minutes
                    event_id = event["id"]
                    ev = calendar_service.events().get(calendarId="primary", eventId=event_id).execute()
                    return _create_event_context_from_api_response(ev)
            except ValueError:
                continue

    raise ValueError(f"No meeting found around {target_time.strftime('%I:%M %p')} within 30 minutes")


def find_meeting_by_subject(calendar_service, subject_query: str) -> EventContext:
    """Find meeting by subject/title"""
    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=7)).isoformat()  # Look back 7 days
    time_max = (now + timedelta(days=30)).isoformat()  # Look ahead 30 days

    events_result = (
        calendar_service.events()
        .list(calendarId="primary", timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime")
        .execute()
    )
    items = events_result.get("items", [])

    # Find matching event by title (case insensitive)
    subject_lower = subject_query.lower()
    for event in items:
        summary = event.get("summary", "").lower()
        if subject_lower in summary:
            event_id = event["id"]
            ev = calendar_service.events().get(calendarId="primary", eventId=event_id).execute()
            return _create_event_context_from_api_response(ev)

    raise ValueError(f"No meeting found with subject containing: {subject_query}")


def parse_time_request(user_query: str) -> Optional[datetime]:
    """Parse time from user query string"""
    if not user_query:
        return None

    user_query = user_query.lower()
    now = datetime.now(timezone.utc)

    # Time patterns with various formats (ordered by specificity)
    time_patterns = [
        r"(\d{1,2}):(\d{2})\s*(p\.?m\.?)",     # 2:30p.m, 2:30 p.m, 2:30pm
        r"(\d{1,2}):(\d{2})\s*(a\.?m\.?)",     # 2:30a.m, 2:30 a.m, 2:30am
        r"(\d{1,2})\s*(p\.?m\.?)",             # 2p.m, 2 p.m, 2pm
        r"(\d{1,2})\s*(a\.?m\.?)",             # 2a.m, 2 a.m, 2am
        r"(\d{1,2}):(\d{2})\s*(am|pm)",        # 2:30 PM, 2:30 AM
        r"(\d{1,2})\s*(am|pm)",                # 2 PM, 2 AM
        r"(\d{1,2}):(\d{2})\s*([A-Z]{3})",     # 19:00 SGT, 14:30 EST
        r"(\d{1,2}):(\d{2})",                  # 14:30 (24-hour)
        r"at\s+(\d{1,2}):(\d{2})",             # at 14:30
    ]

    for pattern in time_patterns:
        match = re.search(pattern, user_query, re.IGNORECASE)
        if match:
            groups = match.groups()
            hour = int(groups[0])

            # Handle minute and AM/PM/timezone
            minute = 0
            ampm = None
            timezone_str = None

            # Determine minute, AM/PM, and timezone based on group count and content
            if len(groups) >= 3 and groups[1] and groups[2]:
                # Pattern with hour:minute and AM/PM/timezone
                if groups[1].isdigit():
                    minute = int(groups[1])
                    ampm_or_tz = groups[2].lower()
                    if 'p.m' in ampm_or_tz or 'pm' in ampm_or_tz:
                        ampm = 'pm'
                    elif 'a.m' in ampm_or_tz or 'am' in ampm_or_tz:
                        ampm = 'am'
                    elif len(groups[2]) == 3:
                        timezone_str = groups[2]
            elif len(groups) >= 2 and groups[1]:
                # Pattern with hour and AM/PM or just minute
                if groups[1].isdigit():
                    minute = int(groups[1])
                else:
                    ampm_str = groups[1].lower()
                    if 'p.m' in ampm_str or 'pm' in ampm_str:
                        ampm = 'pm'
                    elif 'a.m' in ampm_str or 'am' in ampm_str:
                        ampm = 'am'

            # Handle AM/PM conversion
            if ampm:
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0

            # Create target time for today, adjust if needed
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If the time has passed today, assume it's for tomorrow
            if target_time < now:
                target_time = target_time + timedelta(days=1)

            return target_time

    # Handle relative time expressions
    if "today" in user_query:
        return now.replace(hour=9, minute=0, second=0, microsecond=0)  # Default to 9 AM today
    elif "tomorrow" in user_query:
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)  # Default to 9 AM tomorrow
    elif "yesterday" in user_query:
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=9, minute=0, second=0, microsecond=0)  # Default to 9 AM yesterday
    elif "next" in user_query:
        return now  # Return current time for "next meeting"

    return None


def _create_event_context_from_api_response(ev: Dict) -> EventContext:
    """Create EventContext from Google Calendar API response"""
    attendees_raw = ev.get("attendees", [])
    attendees = [
        EventAttendee(email=a.get("email", ""), response_status=a.get("responseStatus"))
        for a in attendees_raw
    ]

    start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or ""
    end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date") or ""

    return EventContext(
        id=ev.get("id", ""),
        summary=ev.get("summary", ""),
        description=ev.get("description", ""),
        start_iso=to_iso(start),
        end_iso=to_iso(end),
        attendees=attendees,
        recurring_event_id=ev.get("recurringEventId"),
        html_link=ev.get("htmlLink"),
        location=ev.get("location"),
        attachments=ev.get("attachments", [])
    )


def get_drive_document_content(drive_service, file_id: str) -> DriveDocument:
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
                doc.content = content.decode('utf-8')[:3000]  # Limit for performance
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


def process_drive_documents(drive_service, event: EventContext) -> List[DriveDocument]:
    """Process Drive documents related to a meeting"""
    all_documents = []

    # Process direct attachments
    if hasattr(event, 'attachments') and event.attachments:
        # Convert to dict format for compatibility
        event_dict = {
            'attachments': event.attachments,
            'description': event.description
        }
        file_ids = extract_drive_file_ids(event_dict)

        for file_id in file_ids:
            doc = get_drive_document_content(drive_service, file_id)
            doc.source = "attachment"
            all_documents.append(doc)

    return all_documents


def search_related_drive_documents(drive_service, meeting_title: str, attendee_emails: List[str], description: str = "") -> List[DriveDocument]:
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
                        last_modified=file_data.get('modifiedTime', ''),
                        size=file_data.get('size', ''),
                        owner=file_data.get('owners', [{}])[0].get('displayName', '') if file_data.get('owners') else ''
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


def search_gmail_attachments(gmail_service, meeting_title: str, attendee_emails: List[str], description: str = "") -> List[DriveDocument]:
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

                        # Extract subject for relevance
                        headers = msg.get('payload', {}).get('headers', [])
                        subject = ""
                        for header in headers:
                            if header.get('name') == 'Subject':
                                subject = header.get('value', '')
                                break

                        # Create a DriveDocument entry for Gmail attachments
                        # (simplified representation for now)
                        if 'attachment' in query or any(keyword in subject.lower() for keyword in [meeting_title.lower()] if meeting_title):
                            doc = DriveDocument(
                                id=message['id'],
                                name=f"Gmail: {subject[:50]}..." if len(subject) > 50 else f"Gmail: {subject}",
                                link=f"https://mail.google.com/mail/u/0/#inbox/{message['id']}",
                                content=f"Gmail message with potential attachments: {subject}",
                                mime_type="message/gmail",
                                source="gmail",
                                last_modified=msg.get('internalDate', '')
                            )
                            gmail_docs.append(doc)

                            if len(gmail_docs) >= 5:  # Limit Gmail results
                                break

                    except Exception:
                        continue  # Skip failed message processing

                if len(gmail_docs) >= 5:
                    break

            except Exception:
                continue  # Skip failed queries

        return gmail_docs[:5]  # Return top 5 Gmail results

    except Exception:
        return []


def calculate_document_relevance(docs: List[DriveDocument], meeting_title: str, meeting_description: str, attendee_emails: List[str]) -> List[DriveDocument]:
    """Calculate relevance scores for documents based on meeting context"""
    try:
        meeting_keywords = set()

        # Extract keywords from meeting title
        if meeting_title:
            title_words = re.findall(r'\b\w+\b', meeting_title.lower())
            meeting_keywords.update([word for word in title_words if len(word) > 3])

        # Extract keywords from description
        if meeting_description:
            desc_words = re.findall(r'\b\w+\b', meeting_description.lower())
            meeting_keywords.update([word for word in desc_words if len(word) > 3])

        # Extract names from attendee emails
        attendee_keywords = set()
        for email in attendee_emails:
            if email:
                name_part = email.split('@')[0].replace('.', ' ').replace('_', ' ')
                attendee_keywords.update(name_part.split())

        for doc in docs:
            score = 0.0

            # Score based on document name
            doc_name_lower = doc.name.lower()
            for keyword in meeting_keywords:
                if keyword in doc_name_lower:
                    score += 2.0

            # Score based on attendee names in document
            for keyword in attendee_keywords:
                if keyword.lower() in doc_name_lower:
                    score += 1.0

            # Score based on document content (if available)
            if doc.content:
                doc_content_lower = doc.content.lower()
                for keyword in meeting_keywords:
                    if keyword in doc_content_lower:
                        score += 1.0
                for keyword in attendee_keywords:
                    if keyword.lower() in doc_content_lower:
                        score += 0.5

            # Bonus for direct attachments
            if doc.source == "attachment":
                score += 5.0

            # Bonus for recent documents
            if doc.last_modified:
                try:
                    import time
                    if doc.source == "gmail":
                        # Gmail uses internal date format
                        timestamp = int(doc.last_modified) / 1000
                        modified_date = datetime.fromtimestamp(timestamp)
                    else:
                        # Drive uses ISO format
                        modified_date = datetime.fromisoformat(doc.last_modified.replace('Z', '+00:00'))

                    days_old = (datetime.now(timezone.utc) - modified_date.replace(tzinfo=timezone.utc)).days
                    if days_old < 7:
                        score += 2.0
                    elif days_old < 30:
                        score += 1.0
                except:
                    pass  # Skip date processing if it fails

            doc.relevance_score = score

        # Sort by relevance score
        docs.sort(key=lambda x: x.relevance_score, reverse=True)
        return docs

    except Exception:
        return docs  # Return original list if scoring fails


def build_comprehensive_document_table(documents: List[DriveDocument]) -> str:
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
        elif "gmail" in doc.mime_type:
            file_type = "📧 Email"
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


def analyze_with_gemini(context: MeetingContext, analysis_type: str) -> str:
    """Analyze meeting context using Gemini AI"""
    try:
        # Import here to avoid circular dependencies
        import vertexai
        from vertexai.generative_models import GenerativeModel
        from config.settings import load_settings

        settings = load_settings()

        # Initialize Vertex AI and Gemini
        vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)
        model = GenerativeModel("gemini-2.5-flash")

        if analysis_type == "insights":
            prompt = f"""
            Analyze this meeting and provide comprehensive insights:

            Meeting: {context.event.summary}
            Description: {context.event.description}
            Attendees: {[att.email for att in context.event.attendees]}

            Please provide:
            1. Meeting purpose and objectives
            2. Key topics likely to be discussed
            3. Potential challenges or blockers
            4. Recommended preparation steps
            5. Expected outcomes

            Be specific and actionable in your analysis.
            """
        elif analysis_type == "attachments":
            if not context.drive_documents:
                return "No attachments to analyze."

            attachment_info = ""
            for doc in context.drive_documents[:5]:  # Limit to top 5
                attachment_info += f"\n**Document: {doc.name}**\n"
                attachment_info += f"Type: {doc.mime_type}\n"
                if doc.content and "Content extraction not available" not in doc.content and "Error accessing" not in doc.content:
                    attachment_info += f"Content Preview:\n{doc.content}\n"
                else:
                    attachment_info += f"Content: {doc.content}\n"
                attachment_info += "---\n"

            prompt = f"""
            Analyze these meeting attachments for "{context.event.summary}":

            {attachment_info}

            Provide:
            1. Document Summary: Brief summary of each document
            2. Key Points: Most important information
            3. Meeting Relevance: How documents relate to the agenda
            4. Action Items: Tasks or decisions needed
            5. Preparation Insights: What attendees should focus on
            6. Questions to Consider: Relevant questions that might arise

            Format as clear markdown sections.
            """
        else:
            prompt = f"Analyze this meeting: {context.event.summary} - {context.event.description}"

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"AI analysis unavailable: {str(e)}"