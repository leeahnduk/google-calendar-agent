import os.path
from datetime import datetime
from typing import Dict
from typing import List
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
from google.adk.tools.google_api_tool import calendar_tool_set
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

"""
This agent works with agent-engine using the Dev UI and handles it's own oauth. 
The other agent (agent.py) is designed to work with Agentspace directly
"""

# Load environment variables from .env file
load_dotenv()

# Access the variable
oauth_client_id = os.getenv("OAUTH_CLIENT_ID")
oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET")
google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION")
staging_bucket = os.getenv("STAGING_BUCKET")

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly",
          "https://www.googleapis.com/auth/userinfo.email",

]

calendar_tool_set.configure_auth(
    client_id=oauth_client_id, client_secret=oauth_client_secret
)

vertexai.init(
    project=google_cloud_project,          # Your project ID.
    location=google_cloud_location,         # Your cloud region.
    staging_bucket=staging_bucket,  # Your staging bucket.
)


def current_datetime(callback_context: CallbackContext):
  callback_context.state['_tz'] = time.tzname[time.daylight]
  print("*** Server Timezone: "+time.tzname[time.daylight])
# get current date time
  now = datetime.now()
  formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
  callback_context.state["_time"] = formatted_time


def whoami(callback_context: CallbackContext):
  # creds = auth_user(tool_context)
  if "calendar_tool_tokens" in callback_context.state:
    creds = Credentials.from_authorized_user_info(
        callback_context.state["calendar_tool_tokens"], SCOPES
    )
    user_info_service = build('oauth2', 'v2', credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    user_email = user_info.get('email')
    # return user_email
    callback_context.state['my_email'] = user_email


def prereq_setup(callback_context: CallbackContext):
  current_datetime(callback_context)
  whoami(callback_context)


def auth_user(tool_context: ToolContext):
  creds = None
  # Check if the tokes were already in the session state, which means the user
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
      # Oauth response is just passed back.
      auth_response = tool_context.get_auth_response(
          AuthConfig(
              auth_scheme=auth_scheme, raw_auth_credential=auth_credential
          )
      )
      if auth_response:
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
      else:
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
        # to LLM to generate a user friendly message. e.g. LLM will tell user:
        # "I need your authorization to access your calendar. Please authorize
        # me so I can check your meetings for today."
        return "Need User Authorization to access their calendar. " \
               "Please allow pop-ups and go through the authorization process"

    # We store the access token and refresh token in the session state for the
    # next runs. This is just an example. On production, a tool should store
    # those credentials in some secure store or properly encrypt it before store
    # it in the session state.
    tool_context.state["calendar_tool_tokens"] = json.loads(creds.to_json())


def check_free_busy(attendeeEmails: List[str],
    startTime: str,
    endTime: str,
    tool_context: ToolContext,
):

  try:
    formatted_attendee_emails: List[Dict[str, str]] = []
    if not isinstance(attendeeEmails, list):
      raise TypeError("Input must be a list.")
    for email in attendeeEmails:
      if not isinstance(email, str):
        raise TypeError("Each element in the input list must be a string.")
      formatted_attendee_emails.append({"id": email})

    if "calendar_tool_tokens" in tool_context.state:
      creds = Credentials.from_authorized_user_info(
          tool_context.state["calendar_tool_tokens"], SCOPES
      )

    service = build('calendar', 'v3', credentials=creds)
    freebusy_request_body = {
        'timeMin': startTime,
        'timeMax': endTime,
        # 'timeZone': 'America/New_York',
        'items': formatted_attendee_emails
    }
    freebusy_result = service.freebusy().query(body=freebusy_request_body).execute()

    print(freebusy_result)
    return freebusy_result

  except Exception as e:
    print(f'An error occurred: {e}')
    return None

check_availability = LlmAgent(
    name="check_availability",
    model="gemini-2.5-flash-preview-04-17",
    description="Handles calendar scheduling",
    # flow="auto",
    instruction="""
        You are specialized in google calendar scheduling to find available timeslots for all attendees. 
        Assumptions:
         - Their working hours are 9AM-5PM in their timezone on weekdays (no weekends) and they only want to schedule during those times unless explicitly told otherwise. 
         Do not check weekends for availability. You accept both single dates and date ranges.
         - The timezone is {_tz}
         - The current datetime is {_time}
         - My email is {my_email} and you should add it to attendeeEmails by default
         - You can use date ranges and relative dates, no need for exact dates
        Follow these guidelines:
        - Do not greet user, Do not welcome user as you already did.
        1. Check calendar availability
            - Gather User Information:
                - Check if you have all of the attendeeEmails including from the conversation context.
                - If not, politely ask for their attendeeEmails.
                - Check if you have the date and time for this meeting in the conversation context
                - If not, politely ask them for a date or time range. 
                - Whatever format they provide, use ISO8601 format internally
                - Confirm if they want to proceed with scheduling a meeting. If yes, move to the next step.
            - Check Attendee Availability
                - If you have the attendeeEmails use the checkFreeBusy tool to get busy timeslots. Make sure date and time are ISO8601
                - Once you have the busy timeslots, identify the free timeslots. We are looking for overlapping free timeslots that apply to ALL attendees√√√
                - If there are no overlapping free timeslots for all attendees during the provided timeframe, tell the user and suggest alternative times using the same dates when they are all free
                - Inform User:
                    - Present up to 5 overlapping free timeslots as a bulleted list formatted in their timezone. 
                    - Ask "Is there anything else I can help you with?"
        If you are unable to assist the user or none of your tools are suitable for their request, transfer to other child agents.

    """,
    tools=[check_free_busy],
    before_agent_callback=prereq_setup,

)

root_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="root_agent",
    instruction="""
        You are a helpful virtual assistant for Google to help users by 
        checking and suggesting Google Calendar availability.
        Greet the user by welcoming the user to the Google Calendar Helper, let 
        the user know you'll need to authenticate to begin and authenticate the user 
        using auth_user. If user asks you to check calendar availability, please
        always use "check_availability" to check and propose an available 
        timeslots. Never greet user again if you already did previously.""",
    sub_agents=[check_availability],
    tools=[auth_user],
    # flow="auto",
)


app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)

