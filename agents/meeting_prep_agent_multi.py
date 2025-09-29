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
from tools.meeting_details_wrapper import prepare_meeting_details
from tools.meeting_search_wrapper import search_meeting_tool, search_meeting_by_time_tool, search_meeting_by_subject_tool
from tools.export_wrapper import export_to_google_docs_tool_wrapper


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

IMPORTANT: Always use the prepare_meeting_details tool and pass the user's complete request as the user_request parameter. For example:
- For "details for meeting 2" -> use prepare_meeting_details with user_request="details for meeting 2"
- For "comprehensive analysis" -> use prepare_meeting_details with user_request="comprehensive analysis"
Provide thorough, in-depth information for users who need complete details.

TRIGGER KEYWORDS: "details", "deep dive", "full analysis", "insights", "comprehensive", "in-depth", "thorough", "full", "expanded", "elaborate", "breakdown"
    """,
    tools=[prepare_meeting_details],
    before_agent_callback=prereq_setup,
)

# Meeting Search Agent
meeting_search_agent = LlmAgent(
    name="meeting_search_agent",
    model=settings.sub_agent_model,
    description="Searches for specific meetings by time or subject and provides appropriate briefs",
    instruction="""
You are the meeting search specialist. Your job is to find specific meetings by time or subject and provide the appropriate brief or details.

🚨 **CRITICAL WORKFLOW**:
1. **GET USER QUERY**: Retrieve the user's request from the conversation context
2. **CALL SEARCH TOOL**: Immediately call search_meeting_tool with the complete user request
3. **RETURN RESULTS**: Provide the meeting brief/details from the search results
4. **NEVER TRANSFER**: Do not transfer to other agents - you handle the complete response

**How to get the user query:**
- The user's complete request is stored in the session state as '_user_query'
- Access it from the tool context and pass it to your search tool
- Use the exact query the user provided (e.g., "meeting brief for my meeting starting at 5:00pm today")

**Tool Usage:**
- IMMEDIATELY call: search_meeting_tool(user_request="[user's complete request]")
- The user_request parameter must contain the user's exact query
- The tool will find the specific meeting and provide brief or details format based on the user's request
- Do not modify or interpret the user's request - pass it exactly as received

**Examples:**
- User query: "generate a meeting brief for my meeting starting at 5:00pm today"
  → Call: search_meeting_tool(user_request="generate a meeting brief for my meeting starting at 5:00pm today")

- User query: "meeting details with subject 'Budget Planning'"
  → Call: search_meeting_tool(user_request="meeting details with subject 'Budget Planning'")

🚫 **NEVER**: Transfer to meeting_brief_agent, meeting_details_agent, or any other agent
✅ **ALWAYS**: Use search_meeting_tool with the complete user request to find and provide meeting information

The search tool will handle both finding the specific meeting and providing the appropriate format (brief or details) based on what the user requested.
    """,
    tools=[search_meeting_tool, search_meeting_by_time_tool, search_meeting_by_subject_tool],
    before_agent_callback=prereq_setup,
)

# Export Agent
export_agent = LlmAgent(
    name="export_agent",
    model=settings.sub_agent_model,
    description="Exports meeting briefs and analysis to Google Docs with sequential workflow support",
    instruction="""
You export meeting briefs and analysis to Google Docs in the user's Google Drive.

Your capabilities:
- Export previous meeting briefs to Google Docs
- Export detailed meeting analysis to Google Docs
- Generate fresh content for specific numbered meetings before export
- Create properly formatted documents with timestamps
- Provide direct links to created documents

🔄 **SEQUENTIAL EXPORT WORKFLOW**:

**For numbered meeting exports** (e.g., "export details for meeting 4 to Google Docs"):
1. **Parse the request**: Identify if user wants "brief" or "details" and which meeting number
2. **Generate content**: Call prepare_meeting_brief or prepare_meeting_details to get fresh content for that specific meeting
3. **Store content**: After getting the result, remember the content for the export tool
4. **Export content**: Use export_to_google_docs_tool to export the generated content
5. **Return link**: Provide the user with the Google Docs link

**For general exports** (e.g., "export to Google Docs"):
- Use previous response or generate new content as needed
- Export using export_to_google_docs_tool

**SEQUENTIAL EXPORT WORKFLOW**:
The export tool wrapper now handles the complete sequential workflow automatically:

1. **Single Tool Call**: Use export_to_google_docs_tool_wrapper with the complete user request
2. **Automatic Content Generation**: The wrapper automatically determines if user wants brief or details
3. **Fresh Content**: The wrapper generates fresh content for the specific meeting requested
4. **Document Creation**: The wrapper creates the Google Doc with the correct content and naming

**Examples:**
- "export details for meeting 4 to Google Docs" → Call export_to_google_docs_tool_wrapper("export details for meeting 4 to Google Docs")
- "export brief for meeting 2 to Google Docs" → Call export_to_google_docs_tool_wrapper("export brief for meeting 2 to Google Docs")

**IMPORTANT CHANGES**:
- **Single tool call only**: Do NOT call prepare_meeting_details or prepare_meeting_brief separately
- **Pass complete user request**: Always pass the user's full export request to the wrapper
- **Automatic workflow**: The wrapper handles content generation, storage, and export automatically
- **Proper content**: The wrapper ensures the correct content type (brief vs details) is exported
    """,
    tools=[export_to_google_docs_tool_wrapper, prepare_meeting_brief, prepare_meeting_details],
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
   - Time triggers: "meeting at 2pm", "10:30 meeting", "yesterday meeting", "19:00 SGT", "starting at", "at 5:00pm"
   - Subject triggers: "subject:", "titled", "called", "named", "meeting with subject"
   - Use when: User specifies a particular meeting time or subject, even if they also want a brief/details
   - PRIORITY: If user mentions both time AND brief/details, route here (search agent can provide appropriate format)

🔸 **meetings_today_agent**: For showing all remaining meetings today with numbered index
   - Triggers: "how many meetings", "meetings left", "remaining meetings", "meetings today", "what meetings", "meetings remaining", "schedule today", "today's schedule", "calendar today"
   - Format: Numbered list with status (current/upcoming/past), times, locations, attendees
   - Use when: User wants to see their full schedule or remaining meetings for today

🔸 **export_agent**: For saving responses to Google Docs
   - Triggers: "export", "save", "google doc", "document", "save to drive"
   - Creates: Formatted Google Doc in user's Drive with sharing link
   - Use when: User wants to save or share the meeting preparation

🚨🚨🚨 **CRITICAL ROUTING RULES - MANDATORY COMPLIANCE** 🚨🚨🚨

**HIGHEST PRIORITY RULE #1**: If query contains ANY TIME words → IMMEDIATELY route to meeting_search_agent
   TIME KEYWORDS: "at 5:00pm", "starting at", "Starting at", "happening at", "happening around", "happening after", "5pm", "2:30", "19:00", "meeting at", "yesterday", "tomorrow", "5:00pm", "6pm", "7:00pm", "4:30", "17:00"
   ✅ EXAMPLE: "brief for my meeting starting at 5:00pm" → meeting_search_agent
   ✅ EXAMPLE: "generate meeting brief for meeting at 6pm" → meeting_search_agent

**HIGHEST PRIORITY RULE #2**: If query contains ANY SUBJECT words → IMMEDIATELY route to meeting_search_agent
   SUBJECT KEYWORDS: "subject:", "titled", "called", "named", "with subject", "starting with", "Starting with", "contain", "Containing", "meeting about", "about"
   ✅ EXAMPLE: "meeting with subject Budget" → meeting_search_agent

**RULE #3**: If query contains numbered selection ("brief for meeting 2", "details for meeting 3") → route to brief_agent or details_agent
**RULE #4**: If query contains meeting count ("how many meetings", "meetings today", "remaining meetings") → route to meetings_today_agent
**RULE #5**: If query contains export ("export", "save", "google doc") → route to export_agent
**RULE #6**: For general queries without above keywords → route to meeting_brief_agent or meeting_details_agent

🛑 **CRITICAL**: ALWAYS prioritize TIME and SUBJECT detection over "brief" or "details" keywords
🛑 **NEVER route time-based queries to meeting_details_agent or meeting_brief_agent**
🛑 **The search agent handles ALL time and subject queries regardless of brief/details format requested**

**Examples:**
- "generate a meeting brief for my meeting starting at 5:00pm today" → meeting_search_agent (TIME detected)
- "meeting details for subject 'Planning'" → meeting_search_agent (SUBJECT detected)
- "brief for meeting 2" → meeting_brief_agent (NUMBERED selection)
- "how many meetings today" → meetings_today_agent (COUNT query)

CRITICAL: Always pass the complete user query to the selected agent.

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