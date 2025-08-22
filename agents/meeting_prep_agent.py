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

    # Get next event
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=1)).isoformat()

    try:
        events_result = (
            calendar_service.events()
            .list(calendarId="primary", timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime")
            .execute()
        )
        items = events_result.get("items", [])
        if not items:
            return {"panel_markdown": "No upcoming meetings found in your calendar."}

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
        
        # Process Drive attachments
        drive_files = []
        file_ids = _extract_drive_file_ids(ev)
        for file_id in file_ids:
            doc = _get_drive_document_content(drive_service, file_id)
            drive_files.append(doc)
        
        # Get comprehensive analysis including historical and chat context
        attendee_emails = [att.email for att in attendees if att.email]
        ai_insights = _research_with_gemini(event_context.summary, event_context.description or "", attendee_emails)
        attachment_analysis = _analyze_attachments_with_gemini(drive_files, event_context.summary)
        historical_context = _get_historical_context(calendar_service, event_context)
        chat_context = _get_chat_context(event_context.summary, attendee_emails, creds)
        
        # Build enhanced meeting brief
        attachments_section = ""
        if drive_files:
            attachments_section = "\n## 📎 Attachments\n"
            for doc in drive_files:
                attachments_section += f"\n### [{doc.name}]({doc.link})\n"
                attachments_section += f"**Type:** {doc.mime_type}\n"
                if doc.content and doc.content != "Content could not be extracted":
                    # Show first few lines of content
                    content_preview = doc.content[:300] + "..." if len(doc.content) > 300 else doc.content
                    attachments_section += f"**Preview:** {content_preview}\n"
        
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

{historical_context}

{chat_context}

## 📋 Attachment Analysis

{attachment_analysis}

## 🧠 AI Research & Insights

{ai_insights}

---
*📊 Brief generated automatically by Meeting Prep Agent with comprehensive AI analysis*
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
You are a helpful meeting preparation assistant that helps users get ready for their upcoming meetings.

If the user asks to prepare a meeting brief, prepare for a meeting, or get meeting preparation materials, 
always use the "prepare_brief" sub-agent to gather and compose the brief.

You can help with:
- Generating meeting briefs for upcoming meetings
- Gathering relevant documents and context
- Summarizing previous meeting notes and discussions
- Finding related Slack conversations

Never greet the user again if you already did previously.
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
