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
        ```
    -   Add your email to the list of **Test users**.

2.  **Create OAuth 2.0 Client ID**:
    -   Navigate to **APIs & Services -> Credentials**.
    -   Click **+ CREATE CREDENTIALS** and select **OAuth client ID**.
    -   Select **Web application** for the application type.
    -   Under **Authorized redirect URIs**, add the following:
        -   `https://developers.google.com/oauthplayground`
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

1.  **Run the Deployment Script**:
    This command activates the environment, sets the correct Python path, and runs the deployment.
    ```bash
    source venv/bin/activate && \
    export PYTHONPATH=$(pwd):$PYTHONPATH && \
    python agents/meeting_prep_agent.py
    ```
    This process may take 2-5 minutes.

2.  **Update `.env` with Reasoning Engine Name**:
    After the script finishes, it will output the `Resource name` of the agent engine. Copy this value.
    -   **Example output**: `Agent Engine updated. Resource name: projects/12345/locations/us-central1/reasoningEngines/67890`
    -   Open your `.env` file and paste this value into the `REASONING_ENGINE` variable.

## Step 6: Register with AgentSpace

Now, register your OAuth credentials and agent engine with the AgentSpace platform.

1.  **Create AgentSpace Authorization**:
    This is a critical step. After creating credentials in the Google Cloud Console (Step 2), you must register them with AgentSpace. This script links your OAuth Client ID to the AgentSpace platform, which allows the agent to request user permissions correctly.

    It reads the `CLIENT_ID`, `CLIENT_SECRET`, and `SCOPES` from your `.env` file to create the authorization profile.
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

-   **OAuth Errors**: If you see permission errors, ensure all required scopes are added to your OAuth consent screen and that your test user is added. You may need to re-run the `./scripts/create_authorization.sh` script if you change scopes.
-   **Deployment Timeouts**: The `python agents/meeting_prep_agent.py` command can sometimes appear to time out. This is often normal. Use the verification script in Step 7 to check if the deployment succeeded.
-   **Agent Not Found in UI**: If the agent doesn't appear in AgentSpace, ensure that both `create_authorization.sh` and `create_agent.sh` ran successfully and that all variables in your `.env` file are correct.
