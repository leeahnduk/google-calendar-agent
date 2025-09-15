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
        
        # Create the table header
        table_header = """## 📋 Relevant Documents & Resources

| Document Name | Type | Source | Relevance | Last Modified | Size | Link |
|---------------|------|--------|-----------|---------------|------|------|"""
        
        table_rows = []
        
        for doc in documents[:15]:  # Show top 15 most relevant documents
            # Format document name (truncate if too long)
            doc_name = doc.name[:50] + "..." if len(doc.name) > 50 else doc.name
            
            # Format file type
            file_type = "Unknown"
            if "document" in doc.mime_type:
                file_type = "📄 Document"
            elif "spreadsheet" in doc.mime_type:
                file_type = "📊 Spreadsheet"
            elif "presentation" in doc.mime_type:
                file_type = "📽️ Presentation"
            elif "pdf" in doc.mime_type:
                file_type = "📕 PDF"
            elif "image" in doc.mime_type:
                file_type = "🖼️ Image"
            elif "text" in doc.mime_type:
                file_type = "📝 Text"
            else:
                file_type = f"📎 {doc.mime_type.split('/')[-1].upper()}"
            
            # Format source
            source_emoji = {
                "attachment": "📎 Direct",
                "gmail": "📧 Gmail",
                "drive": "💾 Drive"
            }.get(doc.source, "❓ Unknown")
            
            # Format relevance score
            relevance_stars = "⭐" * min(5, int(doc.relevance_score))
            if doc.relevance_score >= 4:
                relevance_display = f"{relevance_stars} High"
            elif doc.relevance_score >= 2:
                relevance_display = f"{relevance_stars} Medium"
            else:
                relevance_display = f"{relevance_stars} Low"
            
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
            
            # Create table row
            row = f"| {doc_name} | {file_type} | {source_emoji} | {relevance_display} | {last_modified} | {size_display} | [Open]({doc.link}) |"
            table_rows.append(row)
        
        # Combine header and rows
        table_content = table_header + "\n" + "\n".join(table_rows)
        
        # Add summary statistics
        source_counts = {}
        for doc in documents:
            source_counts[doc.source] = source_counts.get(doc.source, 0) + 1
        
        summary = f"\n\n**📊 Summary:** {len(documents)} relevant documents found"
        if source_counts:
            summary += " ("
            summary_parts = []
            for source, count in source_counts.items():
                source_name = {"attachment": "Direct attachments", "gmail": "Gmail attachments", "drive": "Drive documents"}.get(source, source)
                summary_parts.append(f"{count} {source_name}")
            summary += ", ".join(summary_parts) + ")"
        
        return table_content + summary
    
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

Format your response in clear markdown sections. Be specific and actionable in your analysis.
"""
            
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
                if (item.get("recurringEventId") == event_context.recurring_event_id and 
                    item.get("id") != event_context.id):
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

*Note: For detailed notes from previous sessions, check your meeting notes repository or shared documents.*
"""
            return historical_summary
            
        except Exception as e:
            return f"Historical context unavailable: {str(e)}"
    
    def _get_chat_context(meeting_title: str, attendee_emails: List[str], creds: Credentials) -> str:
        """Get chat context from Slack and/or Google Chat based on meeting title and attendees"""
        chat_sections = []
        
        # Load settings directly with environment variables (AgentSpace compatible)
        import os
        
        def _get_env(name: str, default: str = "") -> str:
            return os.getenv(name, default)
        
        # Get chat integration settings - Default to enabling Google Chat
        google_chat_enabled = _get_env("GOOGLE_CHAT_ENABLED", "true").lower() == "true"
        chat_integration_preference = _get_env("CHAT_INTEGRATION_PREFERENCE", "both")
        
        # Slack Integration
        if chat_integration_preference in ["slack", "both"]:
            try:
                # Inline Slack integration (AgentSpace compatible)
                slack_bot_token = _get_env("SLACK_BOT_TOKEN", "")
                
                slack_messages = []
                if slack_bot_token:
                    try:
                        from slack_sdk import WebClient
                        from slack_sdk.errors import SlackApiError
                        
                        client = WebClient(token=slack_bot_token)
                        channel_cand = f"#{meeting_title.lower().replace(' ', '-')}"
                        
                        # Get channels
                        res = client.conversations_list(limit=1000)
                        channels = res.get("channels", [])
                        
                        # Find matching channel
                        channel_id = None
                        for ch in channels:
                            if ch.get("name", "").lower() == channel_cand.strip("#"):
                                channel_id = ch.get("id")
                                break
                        
                        # Get messages if channel found
                        if channel_id:
                            res = client.conversations_history(channel=channel_id, limit=20)
                            for m in res.get("messages", []):
                                slack_messages.append({
                                    'ts': m.get("ts", ""),
                                    'user': m.get("user", ""),
                                    'text': m.get("text", ""),
                                    'channel': channel_cand,
                                    'permalink': f"https://slack.com/app_redirect?channel={channel_id}&message_ts={m.get('ts','')}"
                                })
                                
                    except Exception:
                        pass  # Slack integration is optional
                
                if slack_messages:
                    # Analyze messages with AI for relevance
                    vertexai.init(project=google_cloud_project, location=google_cloud_location)
                    model = GenerativeModel("gemini-2.5-flash")
                    
                    messages_text = ""
                    for msg in slack_messages[:10]:  # Limit to most recent 10 messages
                        messages_text += f"**@{msg['user']}**: {msg['text']}\n"
                    
                    slack_analysis_prompt = f"""
Analyze these recent Slack messages from the channel related to the meeting "{meeting_title}":

{messages_text}

Please provide:
1. **Key Discussion Points**: Main topics being discussed
2. **Recent Updates**: Any important updates or decisions
3. **Action Items**: Tasks or follow-ups mentioned
4. **Relevance**: How these discussions relate to the upcoming meeting

Keep the response concise and focused on meeting preparation.
"""
                    
                    response = model.generate_content(slack_analysis_prompt)
                    
                    slack_section = f"""
## 💬 Slack Context

**Channel**: {slack_messages[0]['channel'] if slack_messages else "Unknown"}
**Recent Messages**: {len(slack_messages)} messages in the last 7 days

{response.text}

**Direct Links**:
{chr(10).join([f"- [Message from @{msg['user']}]({msg['permalink']})" for msg in slack_messages[:3]])}
"""
                    chat_sections.append(slack_section)
                else:
                    # Try to infer channel name from meeting title
                    potential_channels = []
                    title_words = meeting_title.lower().split()
                    
                    # Common patterns for channel naming
                    for word in title_words:
                        if len(word) > 3:  # Skip short words
                            potential_channels.append(f"#{word}")
                            potential_channels.append(f"#{word.replace(' ', '-')}")
                    
                    slack_section = f"""
## 💬 Slack Context

No recent messages found in channels related to "{meeting_title}".

**Suggested channels to check manually:**
{chr(10).join([f"- {channel}" for channel in potential_channels[:3]])}

*Note: Slack integration requires proper bot token configuration.*
"""
                    chat_sections.append(slack_section)
                    
            except Exception as e:
                slack_section = f"""
## 💬 Slack Context

Unable to fetch Slack context: {str(e)}

*Note: Slack integration requires:*
- Valid SLACK_BOT_TOKEN in environment variables
- Bot permissions to read channels
- Channel naming that matches meeting title patterns
"""
                chat_sections.append(slack_section)
        
        # Google Chat Integration
        if chat_integration_preference in ["google_chat", "both"] and google_chat_enabled:
            try:
                # Inline Google Chat integration (AgentSpace compatible)
                from datetime import datetime, timedelta
                
                def _fetch_google_chat_messages():
                    """Inline Google Chat fetching"""
                    try:
                        from googleapiclient.discovery import build
                        from googleapiclient.errors import HttpError
                        
                        service = build('chat', 'v1', credentials=creds)
                        
                        # Get all spaces
                        spaces_result = service.spaces().list().execute()
                        spaces_data = spaces_result.get('spaces', [])
                        
                        all_messages = []
                        cutoff_time = datetime.now() - timedelta(days=7)
                        
                        # Find relevant spaces and get messages
                        title_words = set(word.lower().strip() for word in meeting_title.split() if len(word) > 2)
                        
                        for space_data in spaces_data:
                            space_name = space_data.get('name', '')
                            space_display_name = space_data.get('displayName', '')
                            space_type = space_data.get('type', '')
                            
                            # Check if space is relevant
                            is_relevant = False
                            if space_type == 'DM':
                                is_relevant = True  # Check all DMs
                            else:
                                # Check if space name contains meeting keywords
                                space_words = set(word.lower().strip() for word in space_display_name.split())
                                if title_words.intersection(space_words):
                                    is_relevant = True
                            
                            if is_relevant:
                                try:
                                    # Get messages from this space
                                    messages_result = service.spaces().messages().list(
                                        parent=space_name,
                                        pageSize=20,
                                        orderBy='createTime desc'
                                    ).execute()
                                    
                                    messages_data = messages_result.get('messages', [])
                                    
                                    for msg_data in messages_data:
                                        # Parse message creation time
                                        create_time_str = msg_data.get('createTime', '')
                                        try:
                                            create_time = datetime.fromisoformat(create_time_str.replace('Z', '+00:00'))
                                            if create_time < cutoff_time:
                                                continue  # Skip old messages
                                        except ValueError:
                                            continue
                                        
                                        # Extract message details
                                        sender_info = msg_data.get('sender', {})
                                        sender_name = (
                                            sender_info.get('displayName', '') or 
                                            sender_info.get('name', '').split('/')[-1] or 
                                            'Unknown'
                                        )
                                        
                                        message_text = msg_data.get('text', '')
                                        
                                        # Basic relevance check
                                        message_words = set(word.lower().strip() for word in message_text.split())
                                        if title_words.intersection(message_words) or len(message_text.strip()) > 10:
                                            all_messages.append({
                                                'sender': sender_name,
                                                'text': message_text,
                                                'create_time': create_time_str,
                                                'space': space_display_name
                                            })
                                        
                                except HttpError:
                                    continue  # Skip spaces we can't access
                        
                        # Sort by creation time and limit results
                        all_messages.sort(key=lambda m: m['create_time'], reverse=True)
                        return all_messages[:20]
                        
                    except Exception:
                        return []
                
                # Get messages from Google Chat
                chat_messages = _fetch_google_chat_messages()
                
                if chat_messages:
                    # Analyze messages with AI for relevance
                    vertexai.init(project=google_cloud_project, location=google_cloud_location)
                    model = GenerativeModel("gemini-2.5-flash")
                    
                    messages_text = ""
                    spaces_mentioned = set()
                    for msg in chat_messages[:10]:  # Limit to most recent 10 messages
                        messages_text += f"**{msg['sender']}** (in {msg['space']}): {msg['text']}\n"
                        spaces_mentioned.add(msg['space'])
                    
                    chat_analysis_prompt = f"""
Analyze these recent Google Chat messages related to the meeting "{meeting_title}":

{messages_text}

Please provide:
1. **Key Discussion Points**: Main topics being discussed
2. **Recent Updates**: Any important updates or decisions
3. **Action Items**: Tasks or follow-ups mentioned
4. **Relevance**: How these discussions relate to the upcoming meeting

Keep the response concise and focused on meeting preparation.
"""
                    
                    response = model.generate_content(chat_analysis_prompt)
                    
                    chat_section = f"""
## 💬 Google Chat Context

**Spaces involved**: {', '.join(list(spaces_mentioned)[:3])}
**Recent Messages**: {len(chat_messages)} messages in the last 7 days

{response.text}

**Message Timeline**:
{chr(10).join([f"- **{msg['sender']}**: {msg['text'][:100]}{'...' if len(msg['text']) > 100 else ''} _(in {msg['space']})_" for msg in chat_messages[:3]])}
"""
                    chat_sections.append(chat_section)
                else:
                    chat_section = f"""
## 💬 Google Chat Context

No recent Google Chat messages found related to "{meeting_title}" with the meeting attendees.

*Note: This searches through:*
- Direct messages with attendees
- Group chats involving attendees
- Conversations mentioning meeting topics
"""
                    chat_sections.append(chat_section)
                    
            except Exception as e:
                error_details = str(e)
                chat_section = f"""
## 💬 Google Chat Context

❌ **Error:** Unable to fetch Google Chat context

**Error Details:** {error_details}

**Troubleshooting:**
- If error mentions "403" or "insufficient permissions": OAuth needs Google Chat scopes
- If error mentions "API not enabled": Enable Google Chat API in Cloud Console
- If error mentions "credentials": Check OAuth authorization status

**Required for Google Chat:**
- OAuth2 credentials with Chat API access
- Scopes: `chat.spaces.readonly` and `chat.messages.readonly`
- Google Chat API enabled in Cloud Console
- GOOGLE_CHAT_ENABLED=true in environment

**Next Steps:** Reauthenticate with Google Chat permissions
"""
                chat_sections.append(chat_section)
        
        # If no integrations are configured or add debug info
        if not chat_sections:
            debug_info = f"""
## 💬 Chat Context

No chat integrations are currently enabled.

**Debug Information:**
- GOOGLE_CHAT_ENABLED: {google_chat_enabled}
- CHAT_INTEGRATION_PREFERENCE: {chat_integration_preference}
- Slack token configured: {bool(_get_env("SLACK_BOT_TOKEN", ""))}

**Available integrations:**
- Slack: Set SLACK_BOT_TOKEN and CHAT_INTEGRATION_PREFERENCE
- Google Chat: Set GOOGLE_CHAT_ENABLED=true and CHAT_INTEGRATION_PREFERENCE

*Current preference: {chat_integration_preference}*
"""
            chat_sections.append(debug_info)
        
        # Always add debug section when Google Chat is enabled but no messages found
        if google_chat_enabled and chat_integration_preference in ["google_chat", "both"]:
            if not any("Google Chat Context" in section for section in chat_sections):
                debug_section = f"""
## 💬 Google Chat Debug

**Configuration Status:** ✅ Google Chat is enabled
- GOOGLE_CHAT_ENABLED: {google_chat_enabled}
- CHAT_INTEGRATION_PREFERENCE: {chat_integration_preference}
- Meeting Title: "{meeting_title}"
- Attendees: {len(attendee_emails)} attendee(s)

**Possible Issues:**
- OAuth permissions for Google Chat API not granted
- No Google Chat conversations found related to this meeting
- Google Chat API access denied
"""
                chat_sections.append(debug_section)
        
        return "\n".join(chat_sections)
    
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

Keep the response concise but informative, formatted in markdown.
"""
            
            response = model.generate_content(research_prompt)
            return response.text
            
        except Exception as e:
            return f"AI research unavailable: {str(e)}"
    
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

        # Get the first upcoming event with full details
        event_id = items[0]["id"]
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
        chat_context = _get_chat_context(event_context.summary, attendee_emails, creds)
        
        # Build comprehensive document table
        document_table = _build_comprehensive_document_table(all_documents)
        
        # Build enhanced meeting brief with legacy attachments section for direct attachments only
        attachments_section = ""
        direct_attachments = [doc for doc in all_documents if doc.source == "attachment"]
        if direct_attachments:
            attachments_section = "\n## 📎 Direct Meeting Attachments\n"
            for doc in direct_attachments:
                attachments_section += f"\n### [{doc.name}]({doc.link})\n"
                attachments_section += f"**Type:** {doc.mime_type}\n"
                if doc.content and doc.content != "Content could not be extracted":
                    # Show first few lines of content
                    content_preview = doc.content[:300] + "..." if len(doc.content) > 300 else doc.content
                    attachments_section += f"**Preview:** {content_preview}\n"
        
        # Add calendar overview section
        calendar_overview = _build_calendar_overview(items, now)
        
        markdown = f"""# 📅 Meeting Brief

## {event_context.summary}

**🕐 Time:** {event_context.start_iso}  
**⏱️ Duration:** Until {event_context.end_iso}

**📝 Description:** {event_context.description or 'No description provided'}

**👥 Attendees:**
{chr(10).join([f"- {att.email} ({att.response_status or 'No response'})" for att in event_context.attendees]) if event_context.attendees else 'No attendees listed'}

**📍 Location:** {event_context.location or 'No location specified'}

**🔗 Meeting Link:** [Join Meeting]({event_context.html_link})
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
*📊 Brief generated automatically by Enhanced Meeting Prep Agent with comprehensive document search, Gmail integration, and AI analysis*
"""
        
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

**Core Capabilities:**
- **Meeting Preparation**: Generate detailed briefs with attachments, chat context, and AI insights
- **Calendar Management**: Show upcoming meetings, schedule analysis, and time management
- **Meeting Discovery**: Find specific meetings by date, attendee, or topic
- **Document Analysis**: Analyze meeting attachments and related documents
- **Chat Integration**: Search Google Chat and Slack conversations for meeting context
- **Schedule Insights**: Provide patterns, conflicts, and optimization suggestions

**For ANY calendar or meeting question**, always use the "prepare_brief" sub-agent to get comprehensive calendar data, then provide the specific information requested.

**Types of questions to handle with prepare_brief tool:**
- Today's/tomorrow's schedule
- Weekly meeting overview
- Meeting patterns and analysis
- Schedule conflicts and busy periods
- Meeting attendee information
- Document and attachment summaries
- Time management suggestions

**Example responses for common questions:**

*"What meetings do I have today?"*
→ ALWAYS use prepare_brief tool and extract today's meetings from the calendar context

*"How many meetings do I have today?"*
→ ALWAYS use prepare_brief tool and count today's meetings

*"Show my schedule this week"*
→ ALWAYS use prepare_brief tool and provide a week overview based on calendar data

*"What's my next meeting about?"*
→ ALWAYS use prepare_brief tool to get details about the upcoming meeting

*"Find meetings with [person]"*
→ ALWAYS use prepare_brief tool and analyze attendee information

*"Do I have any conflicts tomorrow?"*
→ ALWAYS use prepare_brief tool and analyze the schedule for conflicts

**Always be proactive**: If someone asks a simple calendar question, offer to prepare a meeting brief or provide additional helpful context.

Never greet the user again if you already did previously. Always provide actionable, specific information.
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
