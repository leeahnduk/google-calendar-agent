#!/bin/bash

# --- Variables ---
PROJECT_ID="" # Your Google Cloud Project ID
PROJECT_NUMBER="" # Your Google Cloud Project Number
DISCOVERY_ENGINE_PROD_API_ENDPOINT="https://discoveryengine.googleapis.com"
LOCATION="" # The location of your resources, e.g., "us-central1"
AS_APP="" # The application identifier, e.g., "gcal-agent_1747246671415"
AGENT_DISPLAY_NAME="" # The display name for the agent, e.g., "Google Calendar Agent"
REASONING_ENGINE="" # The full resource name of the reasoning engine, e.g., "projects/<PROJECT_NUMBER>/locations/<LOCATION>/reasoningEngines/<REASONING_ENGINE_ID>"
AGENT_DESCRIPTION="" # A description of what the agent does, e.g., "The agent lets you find free calendar slots between multiple attendees using their Google Calendar availability. Feel free to use natural language."
AGENT_ID="" # A unique ID for the agent, e.g., "google_calendar_agent"
AUTH_ID="" # The authorization ID, e.g., "gcal-agent-auth"
ICON_URI="" # The URI for the agent's icon, e.g., "https://ssl.gstatic.com/calendar/images/dynamiclogo_2020q4/calendar_20_2x.png"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)

curl -X PATCH \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  "${DISCOVERY_ENGINE_PROD_API_ENDPOINT}/v1alpha/projects/${PROJECT_NUMBER}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/default_assistant?updateMask=agent_configs" \
  -d '{
    "name": "projects/'"${PROJECT_NUMBER}"'/locations/'"${LOCATION}"'/collections/default_collection/engines/'"${AS_APP}"'/assistants/default_assistant",
    "displayName": "Default Assistant",
    "agentConfigs": [{
      "displayName": "'"${AGENT_DISPLAY_NAME}"'",
      "vertexAiSdkAgentConnectionInfo": {
        "reasoningEngine": "'"${REASONING_ENGINE}"'"
      },
      "toolDescription": "'"${AGENT_DESCRIPTION}"'",
      "icon": {
        "uri": "'"${ICON_URI}"'"
      },
      "id": "'"${AGENT_ID}"'",
      "authorizations": [
        "projects/'"${PROJECT_NUMBER}"'/locations/global/authorizations/'"${AUTH_ID}"'"
      ]
    }]
  }'