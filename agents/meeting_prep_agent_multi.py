"""
Multi-Agent Meeting Preparation System

This is the new multi-agent architecture that replaces the monolithic
meeting_prep_agent.py with specialized agents for different query types.
"""

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

# Load environment variables from .env file
load_dotenv()

print("Loading multi-agent meeting prep system...")

# Configure logging to reduce ALTS warnings
import logging
logging.getLogger('google.auth.transport.requests').setLevel(logging.WARNING)
logging.getLogger('google.auth._default').setLevel(logging.WARNING)
logging.getLogger('google.auth.credentials').setLevel(logging.WARNING)
logging.getLogger('grpc').setLevel(logging.WARNING)

# Import centralized settings
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import load_settings

settings = load_settings()
google_cloud_project = settings.google_cloud_project
google_cloud_location = settings.google_cloud_location
staging_bucket = settings.staging_bucket
auth_id = settings.auth_id
agent_display_name = settings.agent_display_name + "_Multi"  # Distinguish from single agent


def current_datetime(callback_context: CallbackContext):
    """Get current date time"""
    now = datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    callback_context.state["_time"] = formatted_time


def whoami(callback_context: CallbackContext, creds):
    """Get user info and timezone"""
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


def store_user_input(callback_context: CallbackContext):
    """Store user input in state for tools to access"""
    print("**** STORING USER INPUT ****")
    # Try multiple ways to capture the user input
    user_input = None

    # Check various possible attributes for user input
    if hasattr(callback_context, 'user_content') and callback_context.user_content:
        user_input = callback_context.user_content
        print(f"DEBUG: Found user_content: '{user_input}'")
    elif hasattr(callback_context, 'user_input') and callback_context.user_input:
        user_input = callback_context.user_input
        print(f"DEBUG: Found user_input: '{user_input}'")
    elif hasattr(callback_context, 'query') and callback_context.query:
        user_input = callback_context.query
        print(f"DEBUG: Found query: '{user_input}'")
    elif hasattr(callback_context, 'request') and callback_context.request:
        user_input = callback_context.request
        print(f"DEBUG: Found request: '{user_input}'")
    elif hasattr(callback_context, 'message') and callback_context.message:
        user_input = callback_context.message
        print(f"DEBUG: Found message: '{user_input}'")
    else:
        print("DEBUG: No user input found in callback_context")
        print(f"DEBUG: Available attributes: {[attr for attr in dir(callback_context) if not attr.startswith('_')]}")

    if user_input:
        callback_context.state['_user_query'] = user_input
        print(f"DEBUG: Stored user query in state: '{user_input}'")


def prereq_setup(callback_context: CallbackContext):
    """Prerequisites setup for all agents"""
    print("**** MULTI-AGENT PREREQ SETUP ****")
    access_token = callback_context.state[f"temp:{auth_id}"]
    creds = Credentials(token=access_token)
    current_datetime(callback_context)
    whoami(callback_context, creds)
    store_user_input(callback_context)


# Import specialized tools with proper ADK wrappers
from tools.meeting_brief_wrapper import prepare_meeting_brief, get_meetings_today
from tools.meeting_details_tool import prepare_meeting_details_tool
from tools.meeting_search_tools import search_meeting_by_time_tool, search_meeting_by_subject_tool, search_meeting_tool
from tools.export_tool import export_to_google_docs_tool


# ============================================================================
# SPECIALIZED AGENTS
# ============================================================================

# Meeting Brief Agent
meeting_brief_agent = LlmAgent(
    name="meeting_brief_agent",
    model=settings.sub_agent_model,
    description="Generates concise meeting briefs and summaries following the specified format",
    instruction="""
You generate concise meeting briefs using the specified format exactly as shown:

📅**Meeting:** "Title" **Time:** YYYY-MM-DD, HH:MM - HH:MM

* **Attendees:** attendee1@example.com, attendee2@example.com
* **Location:** Location or "Not specified"
* **Meeting Link:** [Join Meeting](URL)

📚**Context:** Brief 1-2 sentence description of what this meeting is about and why it's important.

💬**Key Challenge to Discuss:** One-line key challenge or discussion point for the meeting.

📎**Related Documents:**
Top 3 most relevant documents with brief descriptions.

📋**Potential Talking Points:**
1. First talking point
2. Second talking point
3. Third talking point

If you'd like to dig deeper, I have more details ready. Just ask for the full document analysis, a list of questions to consider for the meeting, or insights into the project's history.

IMPORTANT: Always use the prepare_meeting_brief tool and pass the user's complete request as the user_request parameter. For example:
- For "brief for meeting 2" -> use prepare_meeting_brief with user_request="brief for meeting 2"
- For "quick summary" -> use prepare_meeting_brief with user_request="quick summary"

Keep responses concise and actionable.

TRIGGER KEYWORDS: "brief", "summary", "quick", "overview", "information", "info", "recap", "short", "condensed", "key points", "outline", "abstract", "fast", "a glance", "rapid", "instant", "takeaways", "highlights"
    """,
    tools=[prepare_meeting_brief],
    before_agent_callback=prereq_setup,
)

# Meeting Details Agent
meeting_details_agent = LlmAgent(
    name="meeting_details_agent",
    model=settings.sub_agent_model,
    description="Provides comprehensive meeting analysis and detailed insights",
    instruction="""
You provide detailed, comprehensive meeting analysis including:
- Full meeting context and background
- Complete document analysis with content previews
- Historical meeting patterns (if recurring)
- Detailed AI insights and recommendations
- Comprehensive attendee information
- Full document search results with relevance scoring

Use the comprehensive detailed format that includes:
- Meeting overview with full details
- Direct meeting attachments section
- Complete document analysis
- AI research & insights
- Historical context when available

IMPORTANT: Always use the prepare_meeting_details_tool to generate the comprehensive analysis.
Provide thorough, in-depth information for users who need complete details.

TRIGGER KEYWORDS: "details", "deep dive", "full analysis", "insights", "comprehensive", "in-depth", "thorough", "full", "expanded", "elaborate", "breakdown"
    """,
    tools=[prepare_meeting_details_tool],
    before_agent_callback=prereq_setup,
)

# Meeting Search Agent
meeting_search_agent = LlmAgent(
    name="meeting_search_agent",
    model=settings.sub_agent_model,
    description="Searches for specific meetings by time or subject and provides appropriate briefs",
    instruction="""
You search for specific meetings based on:
- Time queries: "meeting at 2pm", "2:30 meeting today", "meeting at 19:00 SGT", "yesterday meeting"
- Subject queries: "meeting with subject: 'Title'", "meeting titled 'Planning'"

Your process:
1. Parse the user's query to identify time or subject criteria
2. Search for the matching meeting
3. Determine if user wants brief or detailed response based on their query
4. Provide the appropriate format (brief by default, details if requested)

Time formats supported:
- 2:00p.m, 2:00 p.m, 2p.m, 2 p.m
- 2pm, 2:30pm, 14:30, 19:00 SGT
- today, tomorrow, yesterday
- "at 2pm", "meeting at 10:30"

Subject formats supported:
- "subject: 'Meeting Title'"
- "titled 'Planning Session'"
- "called 'Sprint Review'"

IMPORTANT: Use search_meeting_tool for unified search that handles both time and subject queries automatically.
If the user query contains specific time or subject patterns, route to the appropriate specialized tool.
    """,
    tools=[search_meeting_tool, search_meeting_by_time_tool, search_meeting_by_subject_tool],
    before_agent_callback=prereq_setup,
)

# Export Agent
export_agent = LlmAgent(
    name="export_agent",
    model=settings.sub_agent_model,
    description="Exports meeting briefs and analysis to Google Docs",
    instruction="""
You export meeting briefs and analysis to Google Docs in the user's Google Drive.

Your capabilities:
- Export previous meeting briefs to Google Docs
- Export detailed meeting analysis to Google Docs
- Generate fresh content if needed before export
- Create properly formatted documents with timestamps
- Provide direct links to created documents

Process:
1. Determine what content to export (previous response or generate new)
2. Create a new Google Doc with appropriate title
3. Format the content for Google Docs (convert markdown to readable text)
4. Provide the user with the document link

IMPORTANT: Always use export_to_google_docs_tool to handle the export process.
Ensure users get a working link to their exported document.
    """,
    tools=[export_to_google_docs_tool],
    before_agent_callback=prereq_setup,
)

# Meetings Today Agent - Shows remaining meetings with numbered index
meetings_today_agent = LlmAgent(
    model=settings.sub_agent_model,
    name="meetings_today_agent",
    instruction="""
You specialize in showing users their remaining meetings for today with a numbered index
that can be used for easy selection.

Your responsibilities:
- Display all meetings remaining for today with numbers (1, 2, 3...)
- Show current meetings that are in progress
- Provide meeting status: upcoming, current, or past
- Show meeting times in Singapore timezone
- Include duration, location, and attendee information
- Create a searchable index for numbered selection
- Suggest quick actions for meeting selection

Format:
📅 Today's Meetings (as of current time)

🟢 Currently In Progress:
1. Meeting Title (time - time, duration)

⏳ Remaining Meetings Today: X
🟡 2. Meeting Title (time - time, duration)
   📍 Location
   👥 X attendees

✅ Completed Today: X meetings

💡 Quick Actions:
• To get a brief for any meeting, say: "brief for meeting 2"

IMPORTANT: Always use get_meetings_today to fetch and display the meetings.
Store the meeting index for future numbered selections.

TRIGGER KEYWORDS: "how many meetings", "meetings left", "remaining meetings", "meetings today", "what meetings", "meetings remaining", "schedule today", "today's schedule", "calendar today"
    """,
    tools=[get_meetings_today],
    before_agent_callback=prereq_setup
)

# ============================================================================
# ROOT AGENT WITH MULTI-AGENT COORDINATION
# ============================================================================

def root_agent_setup(callback_context: CallbackContext):
    """Setup for root agent - capture user input at the highest level"""
    print("**** ROOT AGENT SETUP ****")
    store_user_input(callback_context)


root_agent = LlmAgent(
    model=settings.root_agent_model,
    name="root_agent",
    instruction="""
You are an intelligent meeting preparation assistant that coordinates multiple specialist agents
to provide the best possible meeting preparation experience.

Your workflow:
1. Analyze the user's request to understand their specific needs
2. Store the complete user query in the session state for tools to access
3. Route the request to the most appropriate specialist agent
4. Coordinate the response to ensure users get exactly what they need

IMPORTANT: Always ensure the user's complete request is preserved and passed to the selected agent.

Available Specialist Agents:

🔸 **meeting_brief_agent**: For concise summaries and quick overviews
   - Triggers: "brief", "summary", "quick", "overview", "information", "info", "recap", "short", "condensed", "key points", "outline", "abstract", "fast", "a glance", "rapid", "instant", "takeaways", "highlights"
   - Numbered selection: "brief for meeting 2", "brief for meeting 4", etc.
   - Format: Structured brief with key points, top 3 documents, talking points
   - Use when: User wants fast, actionable information or requests brief for a specific numbered meeting

🔸 **meeting_details_agent**: For comprehensive analysis and deep insights
   - Triggers: "details", "deep dive", "full analysis", "insights", "comprehensive", "in-depth", "thorough", "full", "expanded", "elaborate", "breakdown"
   - Numbered selection: "details for meeting 3", "full analysis for meeting 1", etc.
   - Format: Complete analysis with full document review, AI insights, historical context
   - Use when: User needs in-depth preparation and complete information or requests details for a specific numbered meeting

🔸 **meeting_search_agent**: For finding specific meetings by time or subject
   - Time triggers: "meeting at 2pm", "10:30 meeting", "yesterday meeting", "19:00 SGT"
   - Subject triggers: "subject:", "titled", "called", "named", "meeting with subject"
   - Use when: User specifies a particular meeting rather than "next meeting"

🔸 **meetings_today_agent**: For showing all remaining meetings today with numbered index
   - Triggers: "how many meetings", "meetings left", "remaining meetings", "meetings today", "what meetings", "meetings remaining", "schedule today", "today's schedule", "calendar today"
   - Format: Numbered list with status (current/upcoming/past), times, locations, attendees
   - Use when: User wants to see their full schedule or remaining meetings for today

🔸 **export_agent**: For saving responses to Google Docs
   - Triggers: "export", "save", "google doc", "document", "save to drive"
   - Creates: Formatted Google Doc in user's Drive with sharing link
   - Use when: User wants to save or share the meeting preparation

Routing Guidelines:
- Default to meeting_brief_agent for general meeting preparation requests
- Use meeting_details_agent when user explicitly asks for comprehensive information
- Use meeting_search_agent when specific time or subject criteria are mentioned
- Use export_agent when user wants to save or export previous responses
- **NUMBERED MEETING SELECTION**: For queries like "brief for meeting 2", "details for meeting 4", route to the appropriate agent (brief/details) based on the action word, NOT to search agent
- Always pass the complete user query to the selected agent
- Be proactive in suggesting other agents if the initial response doesn't fully meet the user's needs

Special Handling:
- If user greets you, greet back and explain your capabilities, then wait for their request
- For ambiguous queries, default to brief format but mention detailed options are available
- If a user asks follow-up questions after an initial response, consider if a different agent would be more appropriate

Remember: Your goal is to ensure every user gets the most appropriate type of meeting preparation
for their specific needs and context.
    """,
    before_agent_callback=root_agent_setup,
    sub_agents=[
        meeting_brief_agent,
        meeting_details_agent,
        meeting_search_agent,
        meetings_today_agent,
        export_agent
    ],
)


# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

def deploy_multi_agent_system():
    """Deploy the multi-agent meeting preparation system"""
    app = reasoning_engines.AdkApp(
        agent=root_agent,
        enable_tracing=True,
    )

    vertexai.init(
        project=google_cloud_project,
        location=google_cloud_location,
        staging_bucket=staging_bucket,
    )

    agent_config = {
        "agent_engine": app,
        "display_name": agent_display_name,
        "requirements": "requirements.txt",
        "extra_packages": ["tools", "config"]
    }

    # Check for existing agents with the multi-agent name
    existing_agents = list(
        agent_engines.list(filter=f'display_name="{agent_display_name}"'))

    if existing_agents:
        print(f"Number of existing multi-agents found for {agent_display_name}: " + str(
            len(list(existing_agents))))
        print(f"Existing agent resource name: {existing_agents[0].resource_name}")

    if existing_agents:
        # Update the existing multi-agent
        print("Updating existing multi-agent system...")
        remote_app = agent_engines.update(
            resource_name=existing_agents[0].resource_name, **agent_config)
        print(f"✅ Multi-agent system updated: {remote_app.resource_name}")
    else:
        # Create a new multi-agent system
        print("Creating new multi-agent system...")
        remote_app = agent_engines.create(**agent_config)
        print(f"✅ Multi-agent system created: {remote_app.resource_name}")

    return remote_app


def deploy_agent_engine_app():
    """Deploy the multi-agent system (compatibility wrapper)"""
    return deploy_multi_agent_system()


if __name__ == "__main__":
    print("🚀 Deploying Multi-Agent Meeting Preparation System...")
    deploy_multi_agent_system()
    print("🎉 Multi-agent deployment complete!")