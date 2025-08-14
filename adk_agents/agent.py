import os.path
from datetime import datetime
from typing import Dict, List
import time
import json

from dotenv import load_dotenv
from fastapi.openapi.models import OAuth2
from fastapi.openapi.models import OAuthFlowAuthorizationCode
from fastapi.openapi.models import OAuthFlows

import vertexai
from vertexai.preview import reasoning_engines

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.auth import AuthConfig
from google.adk.auth import AuthCredential
from google.adk.auth import AuthCredentialTypes
from google.adk.auth import OAuth2Auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

"""
This agent works with agent-engine using the Dev UI and handles its own oauth. 
The other agent (meeting_prep_agent.py) is designed to work with Agentspace directly
"""

# Load environment variables from .env file
load_dotenv()

print("loading .env")

# Access the environment variables
oauth_client_id = os.getenv("CLIENT_ID")
oauth_client_secret = os.getenv("CLIENT_SECRET")
google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION")
staging_bucket = os.getenv("STAGING_BUCKET")

# Import centralized settings for non-OAuth configs
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config.settings import load_settings
settings = load_settings()

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.readonly"
]

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


def whoami(callback_context: CallbackContext):
    if "calendar_tool_tokens" in callback_context.state:
        try:
            creds = Credentials.from_authorized_user_info(
                callback_context.state["calendar_tool_tokens"], SCOPES
            )
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
        except Exception as e:
            print(f"Error getting user info: {e}")
            # Set default values if authentication fails
            callback_context.state['_user_email'] = "user@example.com"
            callback_context.state['_user_tz'] = "UTC"
    else:
        print("No calendar_tool_tokens found in state")
        # Set default values if no tokens
        callback_context.state['_user_email'] = "user@example.com" 
        callback_context.state['_user_tz'] = "UTC"


def prereq_setup(callback_context: CallbackContext):
    print("**** PREREQ SETUP ****")
    current_datetime(callback_context)
    whoami(callback_context)


def auth_user(tool_context: ToolContext):
    creds = None
    # Check if the tokens were already in the session state, which means the user
    # has already gone through the OAuth flow and successfully authenticated and
    # authorized the tool to access their calendar.
    if "calendar_tool_tokens" in tool_context.state:
        creds = Credentials.from_authorized_user_info(
            tool_context.state["calendar_tool_tokens"], SCOPES
        )

    if not creds or not creds.valid:
        # If the access token is expired, refresh it with the refresh token.
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            auth_scheme = OAuth2(
                flows=OAuthFlows(
                    authorizationCode=OAuthFlowAuthorizationCode(
                        authorizationUrl="https://accounts.google.com/o/oauth2/auth",
                        tokenUrl="https://oauth2.googleapis.com/token",
                        scopes={
                            "https://www.googleapis.com/auth/calendar.readonly": (
                                "See and download any calendar you can access "
                                "using your Google Calendar"
                            ),
                            "https://www.googleapis.com/auth/userinfo.email": (
                                "View your email address"
                            ),
                            "https://www.googleapis.com/auth/drive.readonly": (
                                "See and download all your Google Drive files"
                            )
                        },
                    )
                )
            )
            auth_credential = AuthCredential(
                auth_type=AuthCredentialTypes.OAUTH2,
                oauth2=OAuth2Auth(
                    client_id=oauth_client_id, client_secret=oauth_client_secret
                ),
            )
            # If the user has not gone through the OAuth flow before, or the refresh
            # token also expired, we need to ask users to go through the OAuth flow.
            # First we check whether the user has just gone through the OAuth flow and
            # OAuth response is just passed back.
            auth_response = tool_context.get_auth_response(
                AuthConfig(
                    auth_scheme=auth_scheme, raw_auth_credential=auth_credential
                )
            )
            print(f"Auth response received: {auth_response is not None}")
            
            if auth_response:
                print("Processing auth response...")
                # ADK exchanged the access token already for us
                access_token = auth_response.oauth2.access_token
                refresh_token = auth_response.oauth2.refresh_token

                creds = Credentials(
                    token=access_token,
                    refresh_token=refresh_token,
                    token_uri=auth_scheme.flows.authorizationCode.tokenUrl,
                    client_id=oauth_client_id,
                    client_secret=oauth_client_secret,
                    scopes=list(auth_scheme.flows.authorizationCode.scopes.keys()),
                )
                print("Credentials created successfully")
            else:
                print("No auth response, requesting credentials...")
                # If there are no auth response which means the user has not gone
                # through the OAuth flow yet, we need to ask users to go through the
                # OAuth flow.
                tool_context.request_credential(
                    AuthConfig(
                        auth_scheme=auth_scheme,
                        raw_auth_credential=auth_credential,
                    )
                )
                # The return value is optional and could be any dict object. It will be
                # wrapped in a dict with key as 'result' and value as the return value
                # if the object returned is not a dict. This response will be passed
                # to LLM to generate a user friendly message.
                return "Need User Authorization to access your calendar and drive. " \
                       "Please allow pop-ups and go through the authorization process"

        # We store the access token and refresh token in the session state for the
        # next runs. This is just an example. On production, a tool should store
        # those credentials in some secure store or properly encrypt it before store
        # it in the session state.
        tool_context.state["calendar_tool_tokens"] = json.loads(creds.to_json())
        print("Authentication successful! Tokens stored.")
        return "Authentication successful! You can now ask me to prepare meeting briefs."


# Tool: prepare_meeting_brief (adapted for dev UI)
def prepare_meeting_brief(tool_context: ToolContext):
    # Lazy import internal tools
    from agents.trigger import on_demand_next_event
    from tools.attachment_ingest import ingest_event_attachments
    from tools.drive_search import search_drive
    from tools.slack_fetcher import fetch_slack_messages
    from agents.delivery import build_panel_markdown

    # Check if user is authenticated
    if "calendar_tool_tokens" not in tool_context.state:
        return {"panel_markdown": "Please authenticate first to access your calendar and documents."}

    ev = on_demand_next_event(tool_context)
    if not ev:
        return {"panel_markdown": "No upcoming meetings found."}

    # Attachment ingest + drive search
    # Note: ingest requires raw event dict; tool_context may not carry it, so search by title keywords as well
    raw_event = {"id": ev.id, "description": ev.description or "", "attachments": []}
    docs_att = ingest_event_attachments(tool_context, raw_event)
    docs_search = search_drive(tool_context, [ev.summary])
    docs = (docs_att or []) + (docs_search or [])

    # Slack
    slack_msgs = fetch_slack_messages(ev.summary)

    # Render
    md = build_panel_markdown(event=ev, key_docs=docs, slack_msgs=slack_msgs, historical=None)
    return {"panel_markdown": md}


# Define sub-agent that owns the tool (follow sample pattern)
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


# Root agent delegates to the sub-agent (follow sample pattern)
root_agent = LlmAgent(
    model=settings.root_agent_model,
    name="root_agent",
    instruction="""
You are a helpful meeting preparation assistant that helps users get ready for their upcoming meetings.

Greet the user by welcoming them to the Meeting Prep Assistant, let them know you'll need to 
authenticate to begin and authenticate the user using auth_user.

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
    tools=[auth_user],
)


# For ADK web compatibility
agent = root_agent

app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)