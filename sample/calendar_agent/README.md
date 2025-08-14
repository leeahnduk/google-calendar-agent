# Google Calendar Availability Agent

This repository contains a Google Calendar Agent built using the Google Agent Development Kit (ADK) that helps users find available time slots for meetings by checking attendees' Google Calendars.

<img src="images/google_calendar_agent_video.gif" alt="Google Calendar Agent" width="500">

## Features

* **Finds Available Time Slots:** Determines overlapping free time slots for multiple attendees based on their Google Calendar availability.
* **Handles User Input:** Gathers necessary information (attendee emails, desired date/time, timezone) from the user.
* **OAuth2 Integration:** Securely authenticates with Google Calendar API using OAuth2 for user authorization.
* **Timezone Awareness:** Considers the user's and server's timezone for accurate scheduling.
* **User Email Integration:** Automatically identifies the user's email to include them in meeting availability checks.
* **Intelligent Suggestions:** If no overlapping free slots are found, the agent suggests alternative times.

---

## Getting Started

### Prerequisites

Before running this agent, ensure you have the following:

* **Google Cloud Project:** A Google Cloud project with the **Calendar API** and **OAuth2 API** enabled.
* **OAuth 2.0 Client ID and Client Secret:** Created credentials for a **Desktop application** in your Google Cloud Project.
* **Google Agent Development Kit (ADK):** Installed and configured.
* **Python 3.9+:** The recommended Python version.
* **Environment Variables:** These variables are required for the agent to function. For local development, they should be in a `.env` file. When deploying to Cloud Run or the Agent Engine, you will configure them directly in the service settings or during the deployment script.
    * `OAUTH_CLIENT_ID`: Your Google OAuth 2.0 Client ID.
    * `OAUTH_CLIENT_SECRET`: Your Google OAuth 2.0 Client Secret.
    * `GOOGLE_CLOUD_PROJECT`: Your Google Cloud Project ID.
    * `GOOGLE_CLOUD_LOCATION`: The Google Cloud region where your project is located (e.g., `us-central1`).
    * `STAGING_BUCKET`: A Google Cloud Storage bucket for staging (e.g., `gs://your-bucket-name`).
    * `AUTH_ID`: A unique identifier for your authentication flow (e.g., `google_oauth`).
    * `AGENT_DISPLAY_NAME`: A display name for your deployed Agent Engine (e.g., `CalendarAgent`).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd google-calendar-agent
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    (You'll need a `requirements.txt` file containing entries like `google-cloud-vertexai`, `python-dotenv`, `google-auth-oauthlib`, `google-api-python-client`, `fastapi`, etc., based on your project's dependencies.)
3.  **Create a `.env` file (for local development):**
    Create a file named `.env` in the root directory of your project and add the required environment variables for local testing:
    ```
    OAUTH_CLIENT_ID="YOUR_OAUTH_CLIENT_ID"
    OAUTH_CLIENT_SECRET="YOUR_OAUTH_CLIENT_SECRET"
    GOOGLE_CLOUD_PROJECT="YOUR_GOOGLE_CLOUD_PROJECT_ID"
    GOOGLE_CLOUD_LOCATION="YOUR_GOOGLE_CLOUD_LOCATION"
    STAGING_BUCKET="gs://YOUR_STAGING_BUCKET"
    AUTH_ID="google_oauth" # Or your chosen auth ID
    AGENT_DISPLAY_NAME="CalendarAgent" # Or your chosen display name
    ```

---

## Running the Agent Locally

To run the Google Calendar Agent locally using the ADK web server:

```bash
adk web
```

This command will start a local web server, and you can interact with the agent through your web browser, typically at `http://localhost:8000`.

---

## Deploying to Cloud Run

To deploy the Google Calendar Agent to Google Cloud Run:

1.  **Build and Deploy with ADK:**

    ```bash
    adk deploy cloud_run \
      --project=YOUR_GOOGLE_CLOUD_PROJECT_ID \
      --service_name=YOUR_SERVICE_NAME \
      --region=YOUR_CLOUD_REGION \
      --with_ui \
      .
    ```

    Replace the placeholders with your specific values:

    * `YOUR_GOOGLE_CLOUD_PROJECT_ID`: Your Google Cloud Project ID.
    * `YOUR_SERVICE_NAME`: A desired name for your Cloud Run service (e.g., `gcal-agent`).
    * `YOUR_CLOUD_REGION`: The Google Cloud region where you want to deploy your service (e.g., `us-central1`).

    The `--with_ui` flag will deploy the agent along with a basic user interface for interaction.

2.  **Configure Environment Variables in Cloud Run:**
    After the deployment is complete, you will need to manually set the environment variables in the Cloud Run service settings within the Google Cloud Console.

    * Navigate to the Cloud Run service you just deployed.
    * Go to the **"Revisions"** tab, then click on the **"Edit & Deploy new revision"** button.
    * Expand the **"Container, Networking, Security"** section.
    * Under **"Environment variables"**, add the following key-value pairs:
        * `OAUTH_CLIENT_ID`: `YOUR_OAUTH_CLIENT_ID`
        * `OAUTH_CLIENT_SECRET`: `YOUR_OAUTH_CLIENT_SECRET`
        * `GOOGLE_CLOUD_PROJECT`: `YOUR_GOOGLE_CLOUD_PROJECT_ID`
        * `GOOGLE_CLOUD_LOCATION`: `YOUR_CLOUD_REGION`
        * `STAGING_BUCKET`: `gs://YOUR_STAGING_BUCKET`
        * `AUTH_ID`: `google_oauth` (or your chosen auth ID)
        * `AGENT_DISPLAY_NAME`: `CalendarAgent` (or your chosen display name)
    * Click **"Deploy"** to apply the changes.

---

## Deploying the Agent Engine

This agent utilizes the Google Agent Engine for persistent deployment and management within your Google Cloud project. To deploy or update your agent engine:

1.  **Ensure Environment Variables are Set:** Make sure your `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `STAGING_BUCKET`, `AUTH_ID`, and `AGENT_DISPLAY_NAME` environment variables are correctly set (either in your `.env` file or as system environment variables).
2.  **Run the Deployment Script:** Execute the main script to deploy or update the agent engine. This script will check for an existing agent with the specified `AGENT_DISPLAY_NAME` and either update it or create a new one.

    ```bash
    python your_main_agent_file.py
    ```
    (Replace `your_main_agent_file.py` with the actual name of your Python file containing the `deploy_agent_engine_app` function and agent definitions.)

    Upon successful execution, the script will print the resource name of the deployed agent, which you can use to interact with it via the Agent Engine API.

---

## How it Works

The agent leverages the Google Agent Development Kit (ADK) to create `LlmAgent`s (Language Model Agents) that interact with users and utilize tools and callbacks to fulfill requests.

* **`root_agent`**: The main agent that acts as a helpful virtual assistant. It greets the user and then delegates calendar-related requests to the `check_availability` sub-agent.
* **`check_availability` Agent**: This specialized agent handles calendar scheduling.
    * **Instruction-driven:** It follows a detailed set of instructions to gather user information (attendee emails, date, time, timezone).
    * **`before_agent_callback` (`prereq_setup`):** Before the agent processes a request, the `prereq_setup` callback runs. This callback in turn:
        * Calls `current_datetime` to determine the server's current time, storing it in the agent's state (`_time`).
        * Calls `whoami` to retrieve the authenticated user's email and primary calendar timezone, storing them in the agent's state (`_user_email`, `_user_tz`). This email is then used by the agent as a default attendee.
    * **Tool Usage:** It utilizes the `check_free_busy` tool:
        * **Credential Handling:** It retrieves the previously authenticated credentials from `tool_context.state[f"temp:{AUTH_ID}"]` where `AUTH_ID` is your unique authentication identifier.
        * **Calendar API Integration:** It uses the `googleapiclient` library to query the Google Calendar API's `freebusy` endpoint, checking the availability of specified attendees within a given time range.
        * **Result Processing:** It processes the `freebusy` results to identify overlapping free time slots for all attendees.
    * **User Interaction:** It politely asks for missing information, confirms scheduling intent, presents available time slots, and suggests alternatives if no overlapping slots are found.
---

## Customization

You can customize the agent's behavior by modifying the following:

* **`instruction` within `LlmAgent`:** Adjust the instructions for `check_availability` to refine its conversational flow, assumptions (e.g., working hours, year), and how it presents information.
* **`model` within `LlmAgent`:** Change the language model used by the agents (e.g., `gemini-2.5-flash-preview-04-17`, `gemini-2.0-flash`).
* **`SCOPES`:** If you need to access more Google Calendar functionalities, modify the `SCOPES` variable to include the necessary permissions. Remember to update the `scopes` in the `auth_user` function as well.
* **`check_free_busy` tool:** Extend or modify this function to add more complex calendar interactions (e.g., creating events, updating events).
* **`prereq_setup` callback:** Add or modify the logic within this callback to prepare other necessary information in the agent's state before the main agent execution.

---

## Troubleshooting

* **OAuth Flow Issues:** Ensure your `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` are correct and that your OAuth consent screen is properly configured in your Google Cloud Project. Always **re-authorize** the application if you change the requested `SCOPES`.
* **API Permissions:** Verify that both the **Google Calendar API** and **Google OAuth2 API** are enabled in your Google Cloud Project.
* **Environment Variables:** For local development, ensure all required environment variables are set correctly in your `.env` file. For Cloud Run and Agent Engine deployments, verify that the environment variables are correctly configured in the service settings or passed during deployment.
* **Error Messages:** Review the console output for any error messages from the Google Calendar API or the ADK. Pay close attention to messages from `print(f'An error occurred: {e}')` in your `check_free_busy` function.

---

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for any improvements or bug fixes.

---