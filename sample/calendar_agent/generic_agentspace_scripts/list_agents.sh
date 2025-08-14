#!/bin/bash

# --- Configuration Parameters ---

# Your Google Cloud Project ID
PROJECT_ID="" # export PROJECT_ID="your-gcp-project-id"

# The Google Cloud location (e.g., global, us-central1)
LOCATION="" # export LOCATION="global"

# The ID of your collection
COLLECTION_ID="" # export COLLECTION_ID="default_collection"

# The ID of your engine (e.g., gcal-agent_1747246671415)
ENGINE_ID="" # export ENGINE_ID="your_engine_id"

# The ID of your assistant
ASSISTANT_ID="" # export ASSISTANT_ID="default_assistant"

# These are less likely to change and are set directly
API_VERSION="v1alpha"
API_BASE_URL="https://discoveryengine.googleapis.com"

# --- Script Logic ---

# Get the access token
ACCESS_TOKEN=$(gcloud auth print-access-token)

# Construct the API endpoint URL
API_ENDPOINT="${API_BASE_URL}/${API_VERSION}/projects/${PROJECT_ID}/locations/${LOCATION}/collections/${COLLECTION_ID}/engines/${ENGINE_ID}/assistants/${ASSISTANT_ID}/agents"

# Make the cURL request
curl -X GET \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${API_ENDPOINT}"