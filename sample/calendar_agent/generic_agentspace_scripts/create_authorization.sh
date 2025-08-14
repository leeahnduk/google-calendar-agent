#!/bin/bash

# --- Variables ---
PROJECT_ID="" # Your Google Cloud Project ID
AUTHORIZATION_ID="" # A unique ID for the authorization, e.g., "gcal-agent-auth"
CLIENT_ID="" # The OAuth 2.0 Client ID from your Google Cloud project
CLIENT_SECRET="" # The OAuth 2.0 Client Secret from your Google Cloud project
SCOPES="" # A space-separated list of OAuth scopes, e.g., "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/userinfo.email"
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com/v1alpha"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)

# Construct the authorizationUri separately and URL-encode the scopes
# Using printf %s to avoid issues with newline in variable expansion
ENCODED_SCOPES=$(printf %s "${SCOPES}" | sed 's/ /+/g') # More robust way to replace spaces with +

AUTHORIZATION_URI="https://accounts.google.com/o/oauth2/v2/auth?&scope=${ENCODED_SCOPES}&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent"

# Create the JSON payload
JSON_PAYLOAD=$(cat <<EOF
{
  "name": "projects/${PROJECT_ID}/locations/global/authorizations/${AUTHORIZATION_ID}",
  "serverSideOauth2": {
    "clientId": "${CLIENT_ID}",
    "clientSecret": "${CLIENT_SECRET}",
    "authorizationUri": "${AUTHORIZATION_URI}",
    "tokenUri": "https://oauth2.googleapis.com/token"
  }
}
EOF
)

curl -X POST \
     -H "Authorization: Bearer ${AUTH_TOKEN}" \
     -H "Content-Type: application/json" \
     -H "X-Goog-User-Project: ${PROJECT_ID}" \
     "${DISCOVERY_ENGINE_API_BASE_URL}/projects/${PROJECT_ID}/locations/global/authorizations?authorizationId=${AUTHORIZATION_ID}" \
     -d "${JSON_PAYLOAD}"