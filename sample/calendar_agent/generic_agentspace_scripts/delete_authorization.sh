#!/bin/bash

# --- Variables ---
PROJECT_ID="" # Your Google Cloud Project ID
AUTHORIZATION_ID="" # The ID of the authorization to delete, e.g., "gcal-agent-auth"
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com/v1alpha"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)

curl -X DELETE \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${DISCOVERY_ENGINE_API_BASE_URL}/projects/${PROJECT_ID}/locations/global/authorizations/${AUTHORIZATION_ID}"