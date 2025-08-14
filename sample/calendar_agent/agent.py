import os.path
from datetime import datetime
from typing import Dict
from typing import List
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

print("loading .env")

google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION")
staging_bucket = os.getenv("STAGING_BUCKET")
auth_id = os.getenv("AUTH_ID")
agent_display_name = os.getenv("AGENT_DISPLAY_NAME")


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


def check_free_busy(attendee_emails: List[str],
                    start_time: str,
                    end_time: str,
                    tool_context: ToolContext,
                    ):

  print("check_free_busy in progress...")

  try:
    formatted_attendee_emails: List[Dict[str, str]] = []
    if not isinstance(attendee_emails, list):
      raise TypeError("Input must be a list.")
    for email in attendee_emails:
      if not isinstance(email, str):
        raise TypeError("Each element in the input list must be a string.")
      formatted_attendee_emails.append({"id": email})
      print("Email: " + email)

    service = None

    try:
      # Attempt to build the service
      access_token = tool_context.state[f"temp:{auth_id}"]
      creds = Credentials(token=access_token)
      service = build('calendar', 'v3', credentials=creds)

      print("Google Calendar API service built successfully.")

    except Exception as e:
      # Catch any other unexpected errors during the build process
      print(f"An unexpected error occurred: {e}")

    # service = build('calendar', 'v3')
    free_busy_request_body = {
        'timeMin': start_time,
        'timeMax': end_time,
        'items': formatted_attendee_emails
    }
    print(f"Request Body: {free_busy_request_body}")

    freebusy_result = service.freebusy().query(
        body=free_busy_request_body).execute()

    print(f"Response Body: {freebusy_result}")
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
         - You can use date ranges and relative dates, no need for exact dates
        Follow these guidelines:
        - Do not greet user, Do not welcome user as you already did.
        1. Check calendar availability
            - Gather User Information:
                - Check if you have all of the attendeeEmails including from the conversation context.
                - If not, politely ask for their attendeeEmails.
                - The timezone is {_user_tz}
                - The current datetime is {_time}
                - My email is {_user_email} and you should add it to attendeeEmails by default
                - Check if you have the date and time for this meeting in the conversation context
                - If not, politely ask them for a date or time range. 
                - Whatever format they provide, use ISO8601 format internally
                - Confirm if they want to proceed with scheduling a meeting. If yes, move to the next step.
            - Check Attendee Availability
                - If you have the attendeeEmails use the check_free_busy tool to get busy timeslots. Make sure date and time are ISO8601
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
        checking and suggesting Google Calendar availability. If user asks you 
        to check calendar availability, please always use "check_availability" 
        to check and propose an available timeslots. Never greet user 
        again if you already did previously.""",
    sub_agents=[check_availability]
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
