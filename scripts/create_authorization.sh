#!/bin/bash

# =============================================================================
# CREATE AGENTSPACE AUTHORIZATION
# =============================================================================
# This script creates an OAuth 2.0 authorization for the Meeting Prep Agent
# Run this FIRST before creating the agent

set -e  # Exit on any error

# Load environment variables
if [ -f .env ]; then
    source .env
    echo "✅ Loaded .env file"
else
    echo "❌ Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Validate required variables
required_vars=("GOOGLE_CLOUD_PROJECT" "AUTH_ID" "CLIENT_ID" "CLIENT_SECRET" "SCOPES")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: Required environment variable $var is not set in .env"
        exit 1
    fi
done

echo "🚀 Creating AgentSpace Authorization..."
echo "   Project: $GOOGLE_CLOUD_PROJECT"
echo "   Auth ID: $AUTH_ID"
echo "   Scopes: $SCOPES"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com/v1alpha"

# Construct the authorizationUri separately and URL-encode the scopes
ENCODED_SCOPES=$(printf %s "${SCOPES}" | sed 's/ /+/g')
AUTHORIZATION_URI="https://accounts.google.com/o/oauth2/v2/auth?&scope=${ENCODED_SCOPES}&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent"

# Create the JSON payload
JSON_PAYLOAD=$(cat <<EOF
{
  "name": "projects/${GOOGLE_CLOUD_PROJECT}/locations/global/authorizations/${AUTH_ID}",
  "serverSideOauth2": {
    "clientId": "${CLIENT_ID}",
    "clientSecret": "${CLIENT_SECRET}",
    "authorizationUri": "${AUTHORIZATION_URI}",
    "tokenUri": "https://oauth2.googleapis.com/token"
  }
}
EOF
)

echo "📡 Making API request..."
response=$(curl -s -w "\n%{http_code}" -X POST \
     -H "Authorization: Bearer ${AUTH_TOKEN}" \
     -H "Content-Type: application/json" \
     -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
     "${DISCOVERY_ENGINE_API_BASE_URL}/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/authorizations?authorizationId=${AUTH_ID}" \
     -d "${JSON_PAYLOAD}")

# Extract response body and status code
http_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | sed '$d')

echo "📋 Response:"
echo "$response_body" | jq . 2>/dev/null || echo "$response_body"

if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
    echo "✅ Authorization created successfully!"
    echo "   Auth ID: $AUTH_ID"
    echo "   Next step: Run 'scripts/create_agent.sh' to create the agent"
else
    echo "❌ Failed to create authorization (HTTP $http_code)"
    echo "   Check your configuration and try again"
    exit 1
fi