import os.path
from datetime import datetime
from typing import Dict, List
import time
import json

from dotenv import load_dotenv

import vertexai
from vertexai.preview import reasoning_engines

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

"""
Simplified Meeting Prep Agent for ADK Web testing
This version focuses on core functionality without complex OAuth flows
"""

# Load environment variables from .env file
load_dotenv()

print("loading .env")

# Access the environment variables
google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION")
staging_bucket = os.getenv("STAGING_BUCKET")

# Import centralized settings for non-OAuth configs
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config.settings import load_settings
settings = load_settings()

vertexai.init(
    project=google_cloud_project,
    location=google_cloud_location,
    staging_bucket=staging_bucket,
)


def current_datetime(callback_context: CallbackContext):
    callback_context.state['_tz'] = time.tzname[time.daylight]
    print("*** Server Timezone: " + time.tzname[time.daylight])
    # get current date time
    now = datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    callback_context.state["_time"] = formatted_time


def setup_defaults(callback_context: CallbackContext):
    # Set default values for testing
    callback_context.state['_user_email'] = "test@example.com"
    callback_context.state['_user_tz'] = "America/Los_Angeles"
    print("Default user context set")


def prereq_setup(callback_context: CallbackContext):
    print("**** PREREQ SETUP ****")
    current_datetime(callback_context)
    setup_defaults(callback_context)


# Tool: prepare_meeting_brief (simplified for testing)
def prepare_meeting_brief(tool_context: ToolContext):
    """
    Simplified meeting brief tool for testing
    """
    try:
        # Mock meeting data for testing
        mock_meeting = {
            "summary": "Project Phoenix Weekly Sync",
            "start": "2025-08-15T14:30:00-07:00",
            "description": "Weekly sync meeting for Project Phoenix team to discuss progress and blockers"
        }
        
        # Mock response
        brief_content = f"""
# Meeting Brief: {mock_meeting['summary']}

**Time:** {mock_meeting['start']}
**Description:** {mock_meeting['description']}

## Meeting Materials
- No preparatory materials could be found for this meeting

## Notes
This is a test response from the Meeting Prep Agent. In a full implementation, this would:
1. Search your calendar for upcoming meetings
2. Find related documents in Google Drive
3. Check Slack for relevant conversations
4. Compile everything into a comprehensive brief

The agent is working correctly! 🎉
        """
        
        return {"panel_markdown": brief_content.strip()}
        
    except Exception as e:
        error_msg = f"Error generating meeting brief: {str(e)}"
        print(error_msg)
        return {"panel_markdown": error_msg}


# Define sub-agent that owns the tool
prepare_brief = LlmAgent(
    name="prepare_brief", 
    model=settings.sub_agent_model,
    description="Gathers Calendar/Drive/Slack context and prepares a concise meeting brief.",
    instruction="""
You specialize in preparing meeting briefs. Always use the provided tool to gather
and compose the brief. Do not greet. Keep the output concise and actionable.
The timezone is {_tz}
The current datetime is {_time}
The user's email is {_user_email}
The user's timezone is {_user_tz}
    """,
    tools=[prepare_meeting_brief],
    before_agent_callback=prereq_setup,
)


# Root agent delegates to the sub-agent
root_agent = LlmAgent(
    model=settings.root_agent_model,
    name="root_agent",
    instruction="""
You are a helpful meeting preparation assistant that helps users get ready for their upcoming meetings.

Welcome the user to the Meeting Prep Assistant and let them know you're ready to help.

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


# For ADK web compatibility
agent = root_agent

app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)