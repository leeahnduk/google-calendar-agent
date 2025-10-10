# 🚀 Meeting Prep Agent: Complete Deployment Guide

This comprehensive guide provides step-by-step instructions to deploy the Google Calendar Meeting Prep Agent Multi-Agent System from scratch, including detailed Google Cloud setup, OAuth configuration, and deployment to AgentSpace.

## 📋 Prerequisites

Before you begin, ensure you have the following:

- **Google Cloud Account** with billing enabled
- **Google Workspace Account** (for Calendar, Drive, Gmail, Chat access)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated
- [Python 3.12+](https://www.python.org/downloads/) installed
- `git` installed on your local machine
- `jq` command-line JSON processor installed (for better script output formatting)
- Basic understanding of command line operations

## 🏗️ Step 1: Google Cloud Project Setup

### 1.1 Create or Select Project

1. **Create a new project** (or use an existing one):
   ```bash
   # Create new project
   gcloud projects create your-project-id --name="Meeting Prep Agent"

   # Set as active project
   gcloud config set project your-project-id
   ```

2. **Enable billing** for the project:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to **Billing** and link a billing account to your project

### 1.2 Enable Required APIs

Enable all necessary APIs for the multi-agent system:

```bash
gcloud services enable \
    calendar-json.googleapis.com \
    drive.googleapis.com \
    discoveryengine.googleapis.com \
    aiplatform.googleapis.com \
    oauth2.googleapis.com \
    gmail.googleapis.com \
    chat.googleapis.com \
    docs.googleapis.com \
    cloudresourcemanager.googleapis.com
```

### 1.3 Get Project Information

Collect project details needed for configuration:

```bash
# Get project ID (if you don't know it)
gcloud config get-value project

# Get project number
gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)"

# Note your preferred region (us-central1 recommended for Vertex AI)
echo "us-central1"
```

### 1.4 Create Storage Bucket

Create a bucket for agent staging:

```bash
# Replace 'your-unique-bucket-name' with a globally unique name
gsutil mb gs://your-unique-bucket-name-meeting-agent-staging

# Verify bucket creation
gsutil ls | grep meeting-agent-staging
```

## 🔐 Step 2: OAuth 2.0 Configuration

### 2.1 Configure OAuth Consent Screen

1. **Navigate to OAuth consent screen**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to **APIs & Services** → **OAuth consent screen**

2. **Select User Type**:
   - Choose **External** (unless you're in a Google Workspace organization)
   - Click **CREATE**

3. **Fill OAuth consent screen information**:
   ```
   App name: Meeting Prep Agent
   User support email: your-email@domain.com
   App logo: (optional)
   Application home page: (optional)
   Application privacy policy link: (optional)
   Application terms of service link: (optional)
   Authorized domains: (leave empty for development)
   Developer contact information: your-email@domain.com
   ```

4. **Add required scopes**:
   Click **ADD OR REMOVE SCOPES** and add:
   ```
   https://www.googleapis.com/auth/calendar.readonly
   https://www.googleapis.com/auth/drive.readonly
   https://www.googleapis.com/auth/userinfo.email
   https://www.googleapis.com/auth/chat.spaces.readonly
   https://www.googleapis.com/auth/chat.messages.readonly
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/documents
   ```

5. **Add test users**:
   - Add your Google account email as a test user
   - Add any other users who will test the agent

6. **Review and submit** for verification (or keep in testing mode)

### 2.2 Create OAuth 2.0 Client Credentials

1. **Navigate to Credentials**:
   - Go to **APIs & Services** → **Credentials**

2. **Create OAuth client ID**:
   - Click **+ CREATE CREDENTIALS** → **OAuth client ID**
   - Application type: **Web application**
   - Name: `Meeting Prep Agent Client`

3. **Configure authorized redirect URIs**:
   Add these URIs:
   ```
   https://vertexaisearch.cloud.google.com/oauth-redirect
   http://localhost:8080/
   ```

4. **Save and download credentials**:
   - Click **CREATE**
   - **Copy the Client ID and Client Secret** (you'll need these for .env file)
   - Optionally download the JSON file for backup

## 💻 Step 3: Local Development Environment Setup

### 3.1 Clone and Setup Repository

```bash
# Clone the repository
git clone https://github.com/leeahnduk/google-calendar-agent.git
cd google-calendar-agent

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3.2 Configure Environment Variables

1. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit .env file** with your project details:
   ```bash
   # Open in your preferred editor
   nano .env  # or vim .env or code .env
   ```

3. **Fill in the required values** (see next section for detailed explanation)

## ⚙️ Step 4: Environment Configuration (.env file)

Here's a complete `.env` file template with explanations:

```bash
# =============================================================================
# Google Cloud Configuration
# =============================================================================

# Your Google Cloud Project ID (from Step 1.3)
GOOGLE_CLOUD_PROJECT=your-project-id

# Your Google Cloud Project Number (from Step 1.3)
GOOGLE_CLOUD_PROJECT_NUMBER=123456789012

# Google Cloud region (us-central1 recommended for Vertex AI)
GOOGLE_CLOUD_LOCATION=us-central1

# Google Cloud Storage staging bucket (from Step 1.4)
STAGING_BUCKET=gs://your-unique-bucket-name-meeting-agent-staging

# =============================================================================
# Multi-Agent System Configuration
# =============================================================================

# Display name for the multi-agent system (will appear in AgentSpace)
AGENT_DISPLAY_NAME=Meeting_Prep_Agent_Multi

# OAuth authorization ID (create a unique identifier)
# ⚠️ CRITICAL: This value must match the fallback values in all tool files!
AUTH_ID=meeting-prep-multi

# =============================================================================
# OAuth 2.0 Credentials (from Step 2.2)
# =============================================================================

# Google OAuth 2.0 Client ID
CLIENT_ID=your-client-id.apps.googleusercontent.com

# Google OAuth 2.0 Client Secret
CLIENT_SECRET=your-client-secret

# OAuth 2.0 scopes (space-separated, required for AgentSpace authorization)
SCOPES="https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/chat.spaces.readonly https://www.googleapis.com/auth/chat.messages.readonly https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/documents"

# =============================================================================
# AgentSpace Configuration (will be filled after initial deployment)
# =============================================================================

# AgentSpace app/engine ID (leave empty initially)
AS_APP=

# Assistant ID within the AgentSpace app
ASSISTANT_ID=default_assistant

# Internal agent name (lowercase, hyphens, no spaces)
AGENT_NAME=meeting-prep-multi-agent

# Agent description for AgentSpace
AGENT_DESCRIPTION="Multi-agent system for comprehensive meeting preparation with smart routing"

# Tool description for AgentSpace
TOOL_DESCRIPTION="Specialized agents for meeting briefs, details, search, export, and scheduling"

# Reasoning engine resource name (set after deploying)
REASONING_ENGINE=

# =============================================================================
# AI Model Configuration
# =============================================================================

# Primary agent AI model
ROOT_AGENT_MODEL=gemini-2.5-flash

# Sub-agent AI model
SUB_AGENT_MODEL=gemini-2.5-flash

# =============================================================================
# Agent Behavior Settings
# =============================================================================

# Minutes before meeting start to prepare brief
BRIEF_LEAD_MINUTES=30

# Days to look back for historical meeting context
HISTORICAL_LOOKBACK_DAYS=90

# =============================================================================
# Chat Integration Settings
# =============================================================================

# Enable Google Chat integration
GOOGLE_CHAT_ENABLED=true

# Chat integration preference: "slack", "google_chat", or "both"
CHAT_INTEGRATION_PREFERENCE=both

# =============================================================================
# Optional: Slack Integration
# =============================================================================

# Slack bot token (optional, see Slack setup section)
SLACK_BOT_TOKEN=

# Slack signing secret (optional)
SLACK_SIGNING_SECRET=
```

## ✅ Pre-Deployment Verification

**🚨 CRITICAL**: Before deploying, run these commands to prevent common issues:

```bash
# 1. Verify AUTH_ID consistency (PREVENTS #1 FAILURE CAUSE)
echo "=== AUTH_ID Verification ==="
echo "AUTH_ID in .env file:"
grep "^AUTH_ID=" .env
echo "AUTH_ID in tool files:"
grep -r "AUTH_ID.*meeting-prep-multi" tools/ | wc -l
echo "Expected: Should find 5 tool files with meeting-prep-multi"
echo ""

# 2. Verify environment file completeness
echo "=== Environment File Check ==="
echo "Required variables present:"
grep -c "^GOOGLE_CLOUD_PROJECT=" .env && echo "✅ GOOGLE_CLOUD_PROJECT"
grep -c "^CLIENT_ID=" .env && echo "✅ CLIENT_ID"
grep -c "^CLIENT_SECRET=" .env && echo "✅ CLIENT_SECRET"
grep -c "^AUTH_ID=" .env && echo "✅ AUTH_ID"
echo ""

# 3. Test syntax before deployment
echo "=== Syntax Validation ==="
python -c "from agents.meeting_prep_agent_multi import root_agent; print('✅ Multi-agent syntax valid')"
```

**⚠️ If any checks fail, FIX THEM BEFORE deploying to avoid deployment failures!**

## 🚀 Step 5: Deploy Multi-Agent System

### 5.1 Deploy the Reasoning Engine

Deploy the multi-agent system to Google Cloud:

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Set Python path for imports
export PYTHONPATH=$(pwd):$PYTHONPATH

# Deploy the multi-agent system
python agents/meeting_prep_agent_multi.py
```

**Expected output:**
```
Creating multi-agent system...
Uploading reasoning engine...
✅ Multi-agent system created: projects/123456789012/locations/us-central1/reasoningEngines/987654321
```

### 5.2 Update Environment with Reasoning Engine

1. **Copy the reasoning engine resource name** from the output above

2. **Update your .env file**:
   ```bash
   # Add the reasoning engine resource name to your .env file
   echo "REASONING_ENGINE=projects/123456789012/locations/us-central1/reasoningEngines/987654321" >> .env
   ```

### 5.3 Verify Deployment

```bash
python -c "
import vertexai
from vertexai import agent_engines
from config.settings import load_settings

settings = load_settings()
vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)
agents = list(agent_engines.list(filter=f'display_name=\"{settings.agent_display_name}\"'))
print(f'✅ Found {len(agents)} agents')
if agents:
    print(f'📅 Last updated: {agents[0].update_time}')
    print(f'🚀 Resource: {agents[0].resource_name}')
"
```

## 🏢 Step 6: AgentSpace Registration

### 6.1 Create OAuth Authorization

Create the OAuth authorization in AgentSpace:

```bash
# Make script executable
chmod +x scripts/create_authorization.sh

# Create authorization (this will use your .env settings)
./scripts/create_authorization.sh
```

**Expected output:**
```
✅ Authorization created successfully: meeting-prep-multi-auth-v1
```

### 6.2 Register Agent in AgentSpace

Register the reasoning engine with AgentSpace:

```bash
# Make script executable
chmod +x scripts/create_agent.sh

# Register agent in AgentSpace
./scripts/create_agent.sh
```

**Expected output:**
```
✅ Agent registered successfully in AgentSpace
Agent ID: 1234567890123456789
```

### 6.3 Find Your Agent in AgentSpace

1. **Navigate to AgentSpace**:
   - Go to https://vertexaisearch.cloud.google.com/
   - Sign in with your Google account

2. **Locate your agent**:
   - Look for your agent under "From your organization"
   - Agent name: Meeting_Prep_Agent_Multi

## 🧪 Step 7: Testing and Verification

### 7.1 Test Multi-Agent Routing

Test different query types to verify agent routing:

1. **Brief queries**:
   ```
   "Give me a brief for my next meeting"
   "Quick summary of my 2pm meeting"
   ```

2. **Details queries**:
   ```
   "I need detailed analysis of my project review meeting"
   "Comprehensive insights for tomorrow's board meeting"
   ```

3. **Search queries**:
   ```
   "Meeting at 3pm today"
   "Meeting with subject 'Sprint Planning'"
   ```

4. **Export queries**:
   ```
   "Export details for meeting 2 to Google Docs"
   "Save brief for my next meeting to Drive"
   ```

### 7.2 Verify OAuth Permissions

During first use, you'll be prompted to grant permissions:

1. **Click "Authorize"** when prompted
2. **Select your Google account**
3. **Grant all requested permissions**:
   - Calendar (read-only)
   - Drive (read-only)
   - Gmail (read-only)
   - Chat (read-only)
   - Docs (create/edit)

### 7.3 Test Core Functionality

1. **Basic meeting brief**:
   ```
   Query: "Prepare brief for my next meeting"
   Expected: Meeting details with attachments and AI insights
   ```

2. **Numbered meeting selection**:
   ```
   Step 1: "How many meetings do I have today?"
   Step 2: "Brief for meeting 2"
   Expected: Brief for specific meeting
   ```

3. **Document export**:
   ```
   Query: "Export details for my next meeting to Google Docs"
   Expected: Google Doc created with comprehensive meeting details
   ```

## 🔧 Step 8: Optional Integrations

### 8.1 Slack Integration (Optional)

If you want Slack integration:

1. **Create Slack App**:
   - Visit https://api.slack.com/apps
   - Create new app "From scratch"
   - Name: "Meeting Prep Agent"

2. **Configure permissions**:
   - Go to "OAuth & Permissions"
   - Add Bot Token Scopes:
     ```
     channels:history
     channels:read
     users:read
     ```

3. **Install to workspace** and copy Bot User OAuth Token

4. **Update .env file**:
   ```bash
   SLACK_BOT_TOKEN=xoxb-your-token-here
   SLACK_SIGNING_SECRET=your-signing-secret
   ```

### 8.2 Advanced Configuration

For advanced users, you can customize:

- **Agent behavior settings** in .env file
- **AI model versions** (when new models are available)
- **Historical lookback period** for meeting context
- **Chat integration preferences**

## 🔍 Troubleshooting

### Common Issues and Solutions

#### Issue 1: "No access token available" (MOST COMMON)
**Symptom**: Agent says "No access token available. Please authenticate first"
**Root Cause**: AUTH_ID mismatch between `.env` file and tool files
**Solution**:
1. **FIRST**: Verify `AUTH_ID=meeting-prep-multi` in your `.env` file
2. **SECOND**: Ensure all tool files have matching AUTH_ID fallback values
3. **Check Command**: `grep -r "meeting-prep-multi" tools/` should show all tools using this value
4. **Never Change**: Unless you update ALL tool files, always use `meeting-prep-multi`
5. Re-authorize in AgentSpace if needed
6. Verify OAuth scopes in consent screen

**⚠️ CRITICAL**: This is the #1 cause of deployment failures. The AUTH_ID in `.env` must exactly match the default fallback values in all files under `tools/` directory.

#### Issue 2: "Agent not found in AgentSpace"
**Symptom**: Agent doesn't appear in UI
**Solution**:
1. Verify reasoning engine deployment
2. Check AgentSpace registration script output
3. Ensure AS_APP variable is set correctly

#### Issue 3: "Import errors during deployment"
**Symptom**: Python import failures
**Solution**:
```bash
# Ensure Python path is set
export PYTHONPATH=$(pwd):$PYTHONPATH

# Verify virtual environment
source venv/bin/activate
pip install -r requirements.txt
```

#### Issue 4: "Multi-agent routing issues"
**Symptom**: Wrong agent handles query
**Solution**:
1. Check query keywords in trace viewer
2. Verify routing logic in agent code
3. Test with explicit keywords

### Debug Commands

```bash
# FIRST: Verify AUTH_ID consistency (CRITICAL)
echo "Checking AUTH_ID in .env file:"
grep "^AUTH_ID=" .env
echo "Checking AUTH_ID in tool files:"
grep -r "meeting-prep-multi" tools/
echo "Expected: All tool files should contain 'meeting-prep-multi'"

# Verify environment configuration
python -c "from config.settings import load_settings; print(load_settings().__dict__)"

# Check agent deployment status
python -c "
import vertexai
from vertexai import agent_engines
from config.settings import load_settings
settings = load_settings()
vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)
agents = list(agent_engines.list())
for agent in agents:
    print(f'{agent.display_name}: {agent.update_time}')
"

# Test tool syntax
python -c "
import sys
sys.path.append('.')
from agents.meeting_prep_agent_multi import root_agent
print('✅ Multi-agent syntax validation passed')
"
```

### Getting Help

- **GitHub Issues**: [Report problems](https://github.com/leeahnduk/google-calendar-agent/issues)
- **Detailed Troubleshooting**: See [lessons.md](lessons.md)
- **Google Cloud Support**: For platform-specific issues

## 📋 Quick Reference

### Environment Variables Checklist
- [ ] GOOGLE_CLOUD_PROJECT
- [ ] GOOGLE_CLOUD_PROJECT_NUMBER
- [ ] GOOGLE_CLOUD_LOCATION
- [ ] STAGING_BUCKET
- [ ] CLIENT_ID
- [ ] CLIENT_SECRET
- [ ] AUTH_ID
- [ ] AGENT_DISPLAY_NAME

### Deployment Commands
```bash
# Complete deployment sequence
source venv/bin/activate
export PYTHONPATH=$(pwd):$PYTHONPATH
python agents/meeting_prep_agent_multi.py
./scripts/create_authorization.sh
./scripts/create_agent.sh
```

### Verification Commands
```bash
# Verify agent deployment
python -c "from config.settings import load_settings; from vertexai import agent_engines; import vertexai; s=load_settings(); vertexai.init(project=s.google_cloud_project, location=s.google_cloud_location); agents=list(agent_engines.list(filter=f'display_name=\"{s.agent_display_name}\"')); print(f'Found {len(agents)} agents'); [print(f'Updated: {a.update_time}') for a in agents]"
```

---

**🎯 Deployment Status**: Ready for Production
**📅 Last Updated**: October 10, 2025
**🏗️ Architecture**: Multi-Agent System with 5 specialized agents
**🔧 Compatibility**: Google Cloud AgentSpace, Python 3.12+, ADK Framework
**⚠️ CRITICAL FIX**: AUTH_ID consistency issues resolved (prevents "No access token available" errors)
**🔑 Standard AUTH_ID**: Use `meeting-prep-multi` for all deployments