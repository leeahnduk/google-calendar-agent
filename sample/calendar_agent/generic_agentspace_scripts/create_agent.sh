#!/bin/bash

# --- Variables ---
PROJECT_ID="" # Your Google Cloud Project ID
PROJECT_NUMBER="" # Your Google Cloud Project Number
LOCATION="" # The location of your resources, e.g., "us-central1"
AS_APP="" # The application identifier, e.g., "gcal-agent_1747246671415"
ASSISTANT_ID="" # The assistant ID, e.g., "default_assistant"
AGENT_NAME="" # A unique name for the agent, e.g., "gcal-agent-2"
AGENT_DISPLAY_NAME="" # The display name for the agent, e.g., "Google Calendar Agent"
AGENT_DESCRIPTION="" # A brief description of what the agent does
TOOL_DESCRIPTION="" # A description of the tool used by the agent
REASONING_ENGINE="" # The full resource name of the reasoning engine, e.g., "projects/<PROJECT_NUMBER>/locations/<LOCATION>/reasoningEngines/<REASONING_ENGINE_ID>"
AUTH_ID="" # The authorization ID, e.g., "gcal-agent-auth"
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)

curl -X POST \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${DISCOVERY_ENGINE_API_BASE_URL}/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/${ASSISTANT_ID}/agents" \
  -d '{
    "name": "projects/'"${PROJECT_NUMBER}"'/locations/'"${LOCATION}"'/collections/default_collection/engines/'"${AS_APP}"'/assistants/'"${ASSISTANT_ID}"'/agents/'"${AGENT_NAME}"'",
    "displayName": "'"${AGENT_DISPLAY_NAME}"'",
    "description": "'"${AGENT_DESCRIPTION}"'",
    "adk_agent_definition": {
      "tool_settings": {
        "tool_description": "'"${TOOL_DESCRIPTION}"'"
      },
      "provisioned_reasoning_engine": {
        "reasoning_engine": "'"${REASONING_ENGINE}"'"
      },
      "authorizations": [
        "projects/'"${PROJECT_NUMBER}"'/locations/global/authorizations/'"${AUTH_ID}"'"
      ]
    }
  }'