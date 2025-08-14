#!/bin/bash

# =============================================================================
# VALIDATE MEETING PREP AGENT SETUP
# =============================================================================
# This script validates your environment configuration and setup

set -e

echo "🔍 Validating Meeting Prep Agent Setup..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    echo "   Copy .env.example to .env and configure it:"
    echo "   cp .env.example .env"
    exit 1
fi

echo "✅ .env file found"

# Load environment variables
source .env

# Validate critical environment variables
required_vars=("GOOGLE_CLOUD_PROJECT" "STAGING_BUCKET" "CLIENT_ID" "CLIENT_SECRET")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" = "your-project-id" ] || [ "${!var}" = "your-staging-bucket" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing or unconfigured environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo "   Please update your .env file with actual values"
    exit 1
fi

echo "✅ Required environment variables configured"

# Check Google Cloud authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null 2>&1; then
    echo "❌ Google Cloud authentication not found"
    echo "   Run: gcloud auth login"
    exit 1
fi

echo "✅ Google Cloud authentication active"

# Check if project exists and is accessible
if ! gcloud projects describe "$GOOGLE_CLOUD_PROJECT" > /dev/null 2>&1; then
    echo "❌ Cannot access Google Cloud project: $GOOGLE_CLOUD_PROJECT"
    echo "   Verify project ID and permissions"
    exit 1
fi

echo "✅ Google Cloud project accessible: $GOOGLE_CLOUD_PROJECT"

# Check required APIs
required_apis=("calendar-json.googleapis.com" "drive.googleapis.com" "discoveryengine.googleapis.com" "aiplatform.googleapis.com")
missing_apis=()

for api in "${required_apis[@]}"; do
    if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
        missing_apis+=("$api")
    fi
done

if [ ${#missing_apis[@]} -ne 0 ]; then
    echo "❌ Missing required APIs:"
    for api in "${missing_apis[@]}"; do
        echo "   - $api"
    done
    echo "   Enable them with:"
    echo "   gcloud services enable ${missing_apis[*]}"
    exit 1
fi

echo "✅ Required APIs enabled"

# Check staging bucket
if ! gsutil ls "gs://$STAGING_BUCKET" > /dev/null 2>&1; then
    echo "❌ Cannot access staging bucket: $STAGING_BUCKET"
    echo "   Create it with: gsutil mb gs://$STAGING_BUCKET"
    exit 1
fi

echo "✅ Staging bucket accessible: $STAGING_BUCKET"

# Test Python dependencies
if ! python3 -c "from config.settings import load_settings; load_settings()" > /dev/null 2>&1; then
    echo "❌ Python configuration test failed"
    echo "   Install dependencies: pip install -r requirements.txt"
    exit 1
fi

echo "✅ Python configuration working"

# Test ADK imports
if ! python3 -c "from google.adk.agents import LlmAgent; from vertexai.preview import reasoning_engines" > /dev/null 2>&1; then
    echo "❌ ADK dependencies not properly installed"
    echo "   Install dependencies: pip install -r requirements.txt"
    exit 1
fi

echo "✅ ADK dependencies available"

echo ""
echo "🎉 Setup validation complete!"
echo ""
echo "Next steps:"
echo "1. Deploy agent: python agents/meeting_prep_agent.py"
echo "2. Create authorization: ./scripts/create_authorization.sh"
echo "3. Create agent: ./scripts/create_agent.sh"
echo "4. Test in AgentSpace web interface"
echo ""
echo "📖 See Testplan.md for detailed testing instructions"