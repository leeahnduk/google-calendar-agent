# 🚀 Meeting Prep Agent: Deployment Guide

This guide provides step-by-step instructions to deploy the Google Calendar Meeting Prep Agent from scratch, including project setup, authentication, and deployment to Google Cloud AgentSpace.

## 📋 Prerequisites

Before you begin, ensure you have the following:

- A Google Cloud Project with billing enabled.
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated.
- [Python 3.12+](https://www.python.org/downloads/) installed.
- `git` installed on your local machine.
- `jq` command-line JSON processor installed (for better script output formatting).

## Step 1: Google Cloud Project Setup

1.  **Select Your Project**:
    Set your active Google Cloud project.
    ```bash
    gcloud config set project YOUR_PROJECT_ID
    ```

2.  **Enable Required APIs**:
    Enable all necessary APIs for the agent to function.
    ```bash
    gcloud services enable \
        calendar-json.googleapis.com \
        drive.googleapis.com \
        discoveryengine.googleapis.com \
        aiplatform.googleapis.com \
        oauth2.googleapis.com \
        gmail.googleapis.com \
        chat.googleapis.com
    ```

## Step 2: OAuth 2.0 Configuration

The agent requires OAuth 2.0 credentials to access Google services on behalf of the user.

1.  **Configure OAuth Consent Screen**:
    -   In the Google Cloud Console, navigate to **APIs & Services -> OAuth consent screen**.
    -   Choose **External** and create a new consent screen.
    -   Add the following scopes:
        ```
        https://www.googleapis.com/auth/calendar.readonly
        https://www.googleapis.com/auth/drive.readonly
        https://www.googleapis.com/auth/userinfo.email
        https://www.googleapis.com/auth/chat.spaces.readonly
        https://www.googleapis.com/auth/chat.messages.readonly
        https://www.googleapis.com/auth/gmail.readonly
        https://www.googleapis.com/auth/documents
        ```
    -   Add your email to the list of **Test users**.

2.  **Create OAuth 2.0 Client ID**:
    -   Navigate to **APIs & Services -> Credentials**.
    -   Click **+ CREATE CREDENTIALS** and select **OAuth client ID**.
    -   Select **Web application** for the application type.
    -   Under **Authorized redirect URIs**, add the following:
        -   `https://vertexaisearch.cloud.google.com/oauth-redirect`
        -   `http://localhost:8080/` (for local testing with `adk web`)
    -   Click **Create**.
    -   Copy the **Client ID** and **Client Secret**. You will need them for the `.env` file.

## Step 3: Local Environment Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/leeahnduk/google-calendar-agent.git
    cd google-calendar-agent
    ```

2.  **Create and Activate Virtual Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Step 4: Configuration File (`.env`)

1.  **Create `.env` file**:
    Copy the example file to create your own configuration.
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`**:
    Open the `.env` file and fill in the values based on your Google Cloud project and the OAuth credentials you just created.

    ```dotenv
    # Google Cloud Configuration
    GOOGLE_CLOUD_PROJECT="your-project-id"
    GOOGLE_CLOUD_PROJECT_NUMBER="your-project-number"
    GOOGLE_CLOUD_LOCATION="us-central1"
    STAGING_BUCKET="gs://your-gcs-staging-bucket" # Create a new GCS bucket if you don't have one

    # OAuth Credentials
    CLIENT_ID="your-oauth-client-id.apps.googleusercontent.com"
    CLIENT_SECRET="your-oauth-client-secret"
    SCOPES="https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/chat.spaces.readonly https://www.googleapis.com/auth/chat.messages.readonly https://www.googleapis.com/auth/gmail.readonly"

    # Agent Configuration
    AGENT_DISPLAY_NAME="Meeting_Prep_Agent"
    AUTH_ID="meeting-prep-auth-v1" # A unique ID for your authorization

    # AgentSpace Configuration (if deploying to AgentSpace)
    AS_APP="your-agentspace-app-id"
    ASSISTANT_ID="default_assistant"
    AGENT_NAME="meeting-prep-agent-v1" # A unique name for your agent in AgentSpace
    AGENT_DESCRIPTION="A smart agent that prepares you for meetings."
    TOOL_DESCRIPTION="Prepares a comprehensive meeting brief by analyzing calendar events, attachments, and related documents."

    # This will be filled in after the first deployment
    REASONING_ENGINE=""
    ```

## Step 5: Deploy the Agent to Agent Engine

This step packages your agent code and deploys it as a "Reasoning Engine" in Vertex AI.

### Option A: Deploy the Original Monolithic Agent

1.  **Run the Deployment Script**:
    This command activates the environment, sets the correct Python path, and runs the deployment.
    ```bash
    source venv/bin/activate && \
    export PYTHONPATH=$(pwd):$PYTHONPATH && \
    python agents/meeting_prep_agent.py
    ```
    This process may take 2-5 minutes.

### Option B: Deploy the Multi-Agent System (Recommended)

1.  **Deploy the Multi-Agent System**:
    This command deploys the new multi-agent architecture with specialized agents for different query types.
    ```bash
    source venv/bin/activate && \
    export PYTHONPATH=$(pwd):$PYTHONPATH && \
    python agents/meeting_prep_agent_multi.py
    ```
    This process may take 2-5 minutes.

    **Multi-Agent Benefits:**
    - **Smart Query Routing**: Automatically routes requests to specialized agents
    - **Brief Agent**: Quick summaries and overviews
    - **Details Agent**: Comprehensive analysis and insights
    - **Search Agent**: Find specific meetings by time or subject
    - **Export Agent**: Save briefs to Google Docs
    - **Enhanced Keywords**: Better intent recognition and response matching

2.  **Update `.env` with Reasoning Engine Name**:
    After the script finishes, it will output the `Resource name` of the agent engine. Copy this value.
    -   **Example output**: `✅ Multi-agent system created: projects/12345/locations/us-central1/reasoningEngines/67890`
    -   Open your `.env` file and paste this value into the `REASONING_ENGINE` variable.

3.  **Update Agent Display Name**:
    If deploying the multi-agent system, consider updating your `.env` file:
    ```bash
    AGENT_DISPLAY_NAME="Meeting_Prep_Agent_Multi"
    AUTH_ID="meeting-prep-multi-auth"
    ```

## Step 6: Deploy to AgentSpace

Now, register the deployed agent engine with AgentSpace.

1.  **Create AgentSpace Authorization**:
    This script uses your OAuth credentials from the `.env` file to create an authorization profile in AgentSpace.
    ```bash
    ./scripts/create_authorization.sh
    ```
    On success, it will confirm that the authorization was created.

2.  **Create AgentSpace Agent**:
    This final script links your reasoning engine to AgentSpace, making it available in the web UI.
    ```bash
    ./scripts/create_agent.sh
    ```
    On success, it will confirm that the agent was created.

## Step 7: Verification and Testing

1.  **Verify with the Script**:
    Run the verification script to confirm the agent is deployed and the timestamp is recent.
    ```bash
    source venv/bin/activate && \
    python -c "
    from dotenv import load_dotenv
    from config.settings import load_settings
    import vertexai
    from vertexai import agent_engines

    load_dotenv()
    settings = load_settings()

    vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)
    agents = list(agent_engines.list(filter=f'display_name=\"{settings.agent_display_name}\"'))
    print(f'Found {len(agents)} agents with display name \"{settings.agent_display_name}\"')
    for agent in agents:
        print(f'Agent: {agent.display_name}')
        print(f'Updated: {agent.update_time}')
    "
    ```

2.  **Test in AgentSpace UI**:
    -   Navigate to the AgentSpace web interface for your project.
    -   Find your newly deployed agent ("Meeting_Prep_Agent").
    -   Initiate a chat and grant the necessary permissions when the OAuth flow begins.
    -   Test with a query like: `Prepare a brief for my next meeting.`

## Troubleshooting

### Common Deployment Issues

-   **OAuth Errors**: If you see permission errors, ensure all required scopes are added to your OAuth consent screen and that your test user is added. You may need to re-run the `./scripts/create_authorization.sh` script if you change scopes.
-   **Deployment Timeouts**: The `python agents/meeting_prep_agent.py` command can sometimes appear to time out. This is often normal. Use the verification script in Step 7 to check if the deployment succeeded.
-   **Agent Not Found in UI**: If the agent doesn't appear in AgentSpace, ensure that both `create_authorization.sh` and `create_agent.sh` ran successfully and that all variables in your `.env` file are correct.

### Multi-Agent System Specific Issues

#### 1. **State Access Errors**
**Symptom**: `'State' object has no attribute 'keys'` during tool execution
**Solution**: Fixed in the latest version with defensive state access patterns. Ensure you're using the latest code:
```bash
git pull origin main  # Get latest fixes
python agents/meeting_prep_agent_multi.py  # Redeploy
```

#### 2. **User Query Not Passed to Tools**
**Symptom**: Agent always returns brief for "next meeting" instead of specific requested meeting
**Solution**: Fixed with proper tool wrapper implementation. Verify in trace viewer:
- Check `gcp.vertex.agent.tool_call_args` should show: `{"user_request": "your query"}`
- If empty `{}`, redeploy the latest version

#### 3. **Debug Output Not Visible**
**Symptom**: Can't see debug logs in Google Cloud Trace viewer
**Solution**: Fixed with logging configuration to suppress ALTS warnings. Latest version includes proper debug output.

#### 4. **Numbered Meeting Selection Not Working**
**Symptom**: "brief for meeting 2" doesn't work correctly
**Solution**:
1. First ask: "how many meetings do I have left today?" to generate the meeting index
2. Then use: "brief for meeting 2" to get the specific meeting

### Advanced Troubleshooting

#### 1. **Syntax Validation Before Deployment**
```bash
# Validate multi-agent syntax
python -c "
import sys
import os
sys.path.append('.')
from agents.meeting_prep_agent_multi import root_agent
print('✅ Multi-agent syntax validation passed')
"
```

#### 2. **Import Path Issues**
If you see module import errors:
```bash
# Ensure proper Python path
export PYTHONPATH=$(pwd):$PYTHONPATH
python agents/meeting_prep_agent_multi.py
```

#### 3. **State Access Debugging**
Add to tools for debugging state issues:
```python
print(f"DEBUG: tool_context.state type: {type(tool_context.state)}")
print(f"DEBUG: Available state methods: {[m for m in dir(tool_context.state) if not m.startswith('_')]}")
```

#### 4. **Callback Context Analysis**
Debug callback context in setup functions:
```python
print(f"DEBUG: callback_context attributes: {[attr for attr in dir(callback_context) if not attr.startswith('_')]}")
```

### Testing Multi-Agent Features

#### 1. **Basic Functionality Test**
```
Query: "Give me a brief for my next meeting"
Expected: Quick, formatted meeting brief
```

#### 2. **Numbered Selection Test**
```
Step 1: "How many meetings do I have left today?"
Step 2: "Brief for meeting 2"
Expected: Brief for the second meeting in the list
```

#### 3. **Time-Based Search Test**
```
Query: "Meeting at 3:00pm today"
Expected: Brief for meeting starting at 3:00pm
```

#### 4. **Subject-Based Search Test**
```
Query: "Meeting with subject 'Budget Planning'"
Expected: Brief for meeting matching that subject
```

### Performance Optimization

#### 1. **Deployment Speed**
- Multi-agent deployment typically takes 2-5 minutes
- Use verification script to confirm completion
- No need to wait for UI refresh - verification script is authoritative

#### 2. **Response Time**
- Brief agent: 3-8 seconds for quick summaries
- Details agent: 8-15 seconds for comprehensive analysis
- Search agent: 2-5 seconds for meeting lookup

#### 3. **Memory Management**
- Large documents are processed with content limits
- Attachment processing is optimized for performance
- Pagination used for large meeting lists

### Quick Fix Commands

```bash
# Full redeploy with all fixes
source venv/bin/activate
export PYTHONPATH=$(pwd):$PYTHONPATH
python agents/meeting_prep_agent_multi.py

# Verify deployment success
python -c "
import vertexai
from vertexai import agent_engines
from config.settings import load_settings
settings = load_settings()
vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)
agents = list(agent_engines.list(filter=f'display_name=\"{settings.agent_display_name}\"'))
print(f'Found {len(agents)} agents')
if agents:
    print(f'Last updated: {agents[0].update_time}')
    print(f'Resource name: {agents[0].resource_name}')
"
```

### Getting Additional Help

- **Comprehensive Debugging Guide**: See [lessons.md](lessons.md) for detailed troubleshooting patterns
- **GitHub Issues**: [Report issues](https://github.com/leeahnduk/google-calendar-agent/issues)
- **Multi-Agent Architecture**: See [MultiAgent_Revamp_Plan.md](MultiAgent_Revamp_Plan.md)
- **Security Guidelines**: See [SECURITY.md](SECURITY.md)
