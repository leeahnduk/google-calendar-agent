#!/bin/bash

# --- Variables ---
PROJECT_ID="" # Your Google Cloud Project ID
AS_APP="" # The application identifier, e.g., "gcal-agent_1747246671415"
ASSISTANT_ID="" # The assistant ID, usually "default_assistant"
AGENT_TO_DELETE_ID="" # The specific agent ID to be deleted, e.g., "4450334824673066089"
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)

curl -X DELETE \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${DISCOVERY_ENGINE_API_BASE_URL}/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/${ASSISTANT_ID}/agents/${AGENT_TO_DELETE_ID}"