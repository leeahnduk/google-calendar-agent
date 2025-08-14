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
            model = GenerativeModel("gemini-2.0-flash-exp")
            
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
    
    def _research_with_gemini(meeting_title: str, description: str, attendees: List[str]) -> str:
        """Use Gemini to research meeting context and provide insights"""
        try:
            # Initialize Vertex AI and Gemini
            vertexai.init(project=google_cloud_project, location=google_cloud_location)
            model = GenerativeModel("gemini-2.0-flash-exp")
            
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
        
        # Get AI research and attachment analysis
        attendee_emails = [att.email for att in attendees if att.email]
        ai_insights = _research_with_gemini(event_context.summary, event_context.description or "", attendee_emails)
        attachment_analysis = _analyze_attachments_with_gemini(drive_files, event_context.summary)
        
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

## 📋 Attachment Analysis

{attachment_analysis}

## 🧠 AI Research & Insights

{ai_insights}

---
*📊 Brief generated automatically by Meeting Prep Agent with AI analysis*
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
