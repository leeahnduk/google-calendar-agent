import os.path
from datetime import datetime, timedelta
from typing import Dict, List
import time

from dotenv import load_dotenv

import vertexai
from vertexai.preview import reasoning_engines

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.google_api_tool import calendar_tool_set

"""
Meeting Prep Agent with real calendar and drive data using ADK's built-in OAuth
"""

# Load environment variables
load_dotenv()
print("loading .env")

# Environment variables
google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION") 
staging_bucket = os.getenv("STAGING_BUCKET")
oauth_client_id = os.getenv("CLIENT_ID")
oauth_client_secret = os.getenv("CLIENT_SECRET")

# Import settings
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config.settings import load_settings
settings = load_settings()

# Configure ADK's built-in calendar tool with OAuth
calendar_tool_set.configure_auth(
    client_id=oauth_client_id, 
    client_secret=oauth_client_secret
)

vertexai.init(
    project=google_cloud_project,
    location=google_cloud_location,
    staging_bucket=staging_bucket,
)


def current_datetime(callback_context: CallbackContext):
    callback_context.state['_tz'] = time.tzname[time.daylight]
    now = datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    callback_context.state["_time"] = formatted_time


def prereq_setup(callback_context: CallbackContext):
    print("**** PREREQ SETUP ****")
    current_datetime(callback_context)
    # Set user context - will be populated by OAuth
    callback_context.state['_user_email'] = "user@example.com"
    callback_context.state['_user_tz'] = "America/Los_Angeles"


def get_upcoming_meetings(tool_context: ToolContext):
    """Get upcoming meetings from user's calendar"""
    try:
        # Use ADK's calendar tool to get events
        now = datetime.now()
        time_min = now.isoformat() + 'Z'
        time_max = (now + timedelta(days=7)).isoformat() + 'Z'
        
        # This will trigger OAuth if needed - using calendar_events_list
        events_result = calendar_tool_set.calendar_events_list(
            tool_context=tool_context,
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        )
        
        return events_result
        
    except Exception as e:
        print(f"Error getting calendar events: {e}")
        return None


def prepare_meeting_brief_real(tool_context: ToolContext):
    """
    Prepare a real meeting brief using actual calendar data
    """
    try:
        # Get upcoming meetings
        events = get_upcoming_meetings(tool_context)
        
        if not events or not events.get('items'):
            return {"panel_markdown": "No upcoming meetings found in your calendar."}
        
        # Get the next meeting
        next_event = events['items'][0]
        event_summary = next_event.get('summary', 'Untitled Meeting')
        event_start = next_event.get('start', {}).get('dateTime', 'No time specified')
        event_description = next_event.get('description', 'No description provided')
        attendees = next_event.get('attendees', [])
        
        # Build the brief
        brief_content = f"""# Meeting Brief: {event_summary}

**Time:** {event_start}
**Description:** {event_description}"""

        if attendees:
            brief_content += f"\n**Attendees:** {len(attendees)} people"
            attendee_list = []
            for attendee in attendees[:5]:  # Show first 5 attendees
                email = attendee.get('email', 'Unknown')
                attendee_list.append(email)
            if attendee_list:
                brief_content += f"\n- {', '.join(attendee_list)}"

        brief_content += """

## Meeting Materials
- No preparatory materials could be found for this meeting
- *Note: Drive search is not available in this version*

## Notes
✅ **Real data from your Google Calendar!**

This brief was generated using:
1. **Your actual calendar events** - Found "{}" 
2. **Live OAuth authentication** - Using ADK's built-in calendar tools
3. **Real attendee information** - Showing actual meeting participants

The Meeting Prep Agent is successfully accessing your real calendar data! 🎉

**Next Steps:**
- Drive document search will be added in future versions
- Slack integration available in full deployment
""".format(event_summary)

        return {"panel_markdown": brief_content.strip()}
        
    except Exception as e:
        error_msg = f"""# Meeting Brief Error

There was an issue accessing your calendar data:

**Error:** {str(e)}

This might be because:
1. You need to complete the OAuth authentication flow
2. The required Calendar permissions haven't been granted
3. There's a temporary API issue

Please try authenticating again or contact support if the issue persists.

**Available Calendar Tools:** {', '.join([tool for tool in dir(calendar_tool_set) if 'calendar_events' in tool])}
"""
        print(f"Error in prepare_meeting_brief_real: {e}")
        return {"panel_markdown": error_msg}


# Sub-agent with real data capabilities
prepare_brief = LlmAgent(
    name="prepare_brief",
    model=settings.sub_agent_model,
    description="Gathers real Calendar data and prepares a meeting brief using live OAuth authentication.",
    instruction="""
You specialize in preparing meeting briefs using real data from Google Calendar.
Always use the provided tool to gather and compose the brief. Do not greet. 
Keep the output concise and actionable.

The timezone is {_tz}
The current datetime is {_time}
The user's email is {_user_email}
The user's timezone is {_user_tz}
    """,
    tools=[prepare_meeting_brief_real],
    before_agent_callback=prereq_setup,
)


# Root agent
root_agent = LlmAgent(
    model=settings.root_agent_model,
    name="root_agent", 
    instruction="""
You are a Meeting Prep Assistant that helps users prepare for meetings using real data from their Google Calendar and Drive.

Welcome the user and explain that you can help them prepare for meetings by:
- Finding their upcoming calendar events
- Showing meeting details, attendees, and descriptions
- Compiling everything into a comprehensive brief

When they ask to prepare a meeting brief, use the "prepare_brief" sub-agent to access their real calendar data.

Note: This will require OAuth authentication to access their Google services.

Never greet the user again if you already did previously.
    """,
    sub_agents=[prepare_brief],
)


# For ADK web compatibility
agent = root_agent

app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)