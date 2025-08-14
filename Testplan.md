# Meeting Prep Agent - End-to-End Test Plan

## Overview

This document provides a comprehensive test plan for the Meeting Prep Agent, including setup instructions, test scenarios, and validation steps for end-to-end testing using ADK Web interface and AgentSpace deployment.

## Prerequisites

### 1. Google Cloud Setup
- Google Cloud Project with billing enabled
- Enable required APIs:
  ```bash
  gcloud services enable calendar-json.googleapis.com
  gcloud services enable drive.googleapis.com
  gcloud services enable discoveryengine.googleapis.com
  gcloud services enable aiplatform.googleapis.com
  ```

### 2. OAuth 2.0 Setup
- Create OAuth 2.0 credentials in Google Cloud Console
  - Go to APIs & Services > Credentials
  - Create OAuth 2.0 Client ID (Web application)
  - Note down CLIENT_ID and CLIENT_SECRET

### 3. AgentSpace Setup
- Access to AgentSpace web interface
- AgentSpace application configured

## Setup Instructions

### Step 1: Environment Configuration

1. **Copy and configure environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Update `.env` with your values:**
   ```bash
   # Required - Get from Google Cloud Console
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_CLOUD_PROJECT_NUMBER=123456789012
   GOOGLE_CLOUD_LOCATION=us-central1
   STAGING_BUCKET=your-staging-bucket
   
   # Required - OAuth credentials
   CLIENT_ID=your-oauth-client-id.googleusercontent.com
   CLIENT_SECRET=your-oauth-client-secret
   
   # Required - AgentSpace configuration
   AS_APP=your-agentspace-app-id
   ASSISTANT_ID=default_assistant
   AGENT_NAME=meeting-prep-agent
   
   # Required - Agent configuration
   AUTH_ID=meeting-prep-auth
   AGENT_DISPLAY_NAME=Meeting Prep Agent
   
   # Optional - AI Model configuration
   ROOT_AGENT_MODEL=gemini-2.5-flash
   SUB_AGENT_MODEL=gemini-2.5-flash
   
   # Optional - Behavior settings
   BRIEF_LEAD_MINUTES=30
   HISTORICAL_LOOKBACK_DAYS=90
   
   # Optional - Slack integration (if needed)
   SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
   SLACK_SIGNING_SECRET=your-slack-signing-secret
   ```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Deploy Reasoning Engine

1. **Deploy the ADK agent:**
   ```bash
   python agents/meeting_prep_agent.py
   ```

2. **Note the reasoning engine resource name** and update `.env`:
   ```bash
   REASONING_ENGINE=projects/PROJECT_NUMBER/locations/LOCATION/reasoningEngines/ENGINE_ID
   ```

### Step 4: Create AgentSpace Authorization

```bash
./scripts/create_authorization.sh
```

**Expected Output:**
- HTTP 200/201 response
- Authorization created with specified AUTH_ID

### Step 5: Create AgentSpace Agent

```bash
./scripts/create_agent.sh
```

**Expected Output:**
- HTTP 200/201 response
- Agent created and linked to reasoning engine

### Step 6: Local Testing with ADK Web (Alternative)

For local development and testing, you can also use ADK Web:

1. **Start ADK Web locally:**
   ```bash
   # Install ADK Web if not already installed
   pip install google-adk-web
   
   # Start the web interface
   adk web --agent agents/meeting_prep_agent.py
   ```

2. **Access the local interface:**
   - Open browser to `http://localhost:8080`
   - Follow OAuth flow to authenticate
   - Test agent interactions directly

## Test Scenarios

### PRD Acceptance Criteria Validation

The following test scenarios are based on the acceptance criteria defined in the Meeting Prep Agent PRD. Each scenario validates specific requirements from the product specification.

### Test Scenario 1: Recurring Meeting with Historical Context (AC-1)

**PRD Acceptance Criteria:** GIVEN my 4:30 PM meeting is a recurring "Project Phoenix Weekly Sync," WHEN the agent prepares the brief, THEN it must also include a link to last week's meeting notes/transcript and a summary from previous sessions.

**Objective:** Verify the agent can generate a brief for recurring meetings with historical context

**Preconditions:**
- Agent deployed and accessible via ADK Web or AgentSpace
- User has a recurring calendar event titled "Project Phoenix Weekly Sync" at 4:30 PM
- Previous meeting notes/transcripts exist in Google Drive
- User has authorized Calendar and Drive access

**Test Steps:**
1. Access agent interface (ADK Web or AgentSpace)
2. Send message: "Prepare a meeting brief for my Project Phoenix Weekly Sync"
3. Wait for response

**Expected Results:**
- Agent responds with a structured meeting brief
- Brief includes current meeting details (title, time, attendees)
- Brief includes links to previous meeting notes/transcripts
- Brief includes summary from previous sessions
- Response time < 30 seconds

**Validation Checkpoints:**
- ✅ Agent finds the recurring meeting
- ✅ Brief contains current meeting information
- ✅ Links to previous meeting materials are included
- ✅ Historical summary is provided
- ✅ No sensitive information exposed

### Test Scenario 2: Meeting with Attachments and Documents (AC-2)

**PRD Acceptance Criteria:** GIVEN I have a meeting in my Google Calendar at 4:30 PM with an agenda and an attached presentation or any other documents, WHEN the Meeting Prep Agent activates (e.g., 30 minutes before the meeting), THEN the AgentSpace window must display a summary of the agenda and a direct link to the documents.

**Objective:** Verify the agent can handle meetings with attached documents and agenda

**Preconditions:**
- Agent deployed and accessible via ADK Web or AgentSpace
- User has a calendar event at 4:30 PM with agenda in description
- Meeting has attached documents (presentations, PDFs, etc.)
- Documents are accessible via Google Drive
- User has authorized Calendar and Drive access

**Test Setup:**
1. Create test meeting with detailed agenda in description
2. Attach documents to the meeting (via Drive links in description or calendar attachments)
3. Ensure documents are accessible to test user

**Test Steps:**
1. Access agent interface 30 minutes before the meeting OR manually request
2. Send message: "Prepare a brief for my 4:30 PM meeting"
3. Wait for response

**Expected Results:**
- Agent displays summary of the agenda from meeting description
- Brief includes direct links to attached documents
- Documents are properly labeled with titles and types
- Links are clickable and accessible
- Response time < 30 seconds

**Validation Checkpoints:**
- ✅ Agent finds the meeting at the specified time
- ✅ Agenda summary is extracted from meeting description
- ✅ Attached documents are found and linked
- ✅ Links are clickable and accessible
- ✅ Document titles and types are correct
- ✅ No unauthorized documents included

### Test Scenario 3: Meeting with Slack Channel Integration (AC-3)

**PRD Acceptance Criteria:** GIVEN the meeting title contains "Project Phoenix," and there is a #project-phoenix Slack channel, WHEN the agent prepares the brief, THEN it must include a summary of the most recent, relevant messages from that channel, in relation to the meeting title.

**Objective:** Verify Slack message integration for relevant channels

**Preconditions:**
- Agent deployed and accessible via ADK Web or AgentSpace
- Slack integration configured (SLACK_BOT_TOKEN set in environment)
- Meeting titled "Project Phoenix Weekly Sync" or containing "Project Phoenix"
- Slack channel #project-phoenix exists with recent discussions
- Bot has access to the Slack channel

**Test Setup:**
1. Create or identify meeting with "Project Phoenix" in title
2. Ensure #project-phoenix Slack channel has recent relevant discussions
3. Verify bot has access to read channel messages

**Test Steps:**
1. Access agent interface
2. Send message: "Prepare a brief for my Project Phoenix meeting"
3. Wait for response

**Expected Results:**
- Agent finds the meeting with "Project Phoenix" in title
- Brief includes summary of recent messages from #project-phoenix channel
- Summary highlights relevant discussions related to the meeting topic
- Channel name is clearly indicated
- Response time < 30 seconds

**Validation Checkpoints:**
- ✅ Agent identifies meeting with "Project Phoenix" in title
- ✅ Slack channel #project-phoenix is searched
- ✅ Recent relevant messages are found and summarized
- ✅ Summary is concise and relevant to meeting topic
- ✅ Channel information is provided
- ✅ No private/unauthorized messages included

### Test Scenario 4: No Preparatory Materials Found (AC-4)

**PRD Acceptance Criteria:** GIVEN I have a meeting scheduled, WHEN the agent runs but cannot find any relevant attachments, previous meetings, or discussions, THEN it must inform me in the AgentSpace that "No preparatory materials could be found for this meeting."

**Objective:** Verify graceful handling when no materials exist

**Preconditions:**
- Agent deployed and accessible via ADK Web or AgentSpace
- Meeting with generic title (e.g., "Team Check-in")
- No related Drive documents exist
- No previous meeting notes or attachments
- No Slack activity related to meeting topic
- User has authorized necessary permissions

**Test Setup:**
1. Create meeting with generic title that won't match existing documents
2. Ensure no documents exist with matching keywords in Drive
3. Ensure no Slack channels have related discussions

**Test Steps:**
1. Access agent interface
2. Send message: "Prepare a brief for my Team Check-in meeting"
3. Wait for response

**Expected Results:**
- Agent successfully finds the meeting
- Brief is generated with basic meeting information
- Clear message: "No preparatory materials could be found for this meeting"
- Agent does not fail or error out
- Response time < 30 seconds

**Validation Checkpoints:**
- ✅ Agent finds the scheduled meeting
- ✅ Agent doesn't fail or error when no materials found
- ✅ Exact message "No preparatory materials could be found for this meeting" is displayed
- ✅ Basic meeting details (time, title, attendees) are still provided
- ✅ Response is professional and helpful

### Test Scenario 5: Document Labeling and Links (AC-5)

**PRD Acceptance Criteria:** GIVEN a brief has been prepared for my meeting, WHEN the agent adds the related documents to the AgentSpace window, THEN each document must be clearly labeled and link directly to the source file.

**Objective:** Verify proper document presentation and linking

**Preconditions:**
- Agent deployed and accessible via ADK Web or AgentSpace
- Meeting exists with related documents in Google Drive
- Documents include various types (Google Docs, PDFs, Sheets, etc.)
- User has authorized Calendar and Drive access

**Test Setup:**
1. Create meeting with related documents in Drive:
   - Google Doc: "Project Phoenix - Requirements.docx"
   - PDF: "Phoenix Implementation Plan.pdf"
   - Google Sheet: "Action Items - Team Meeting.gsheet"
2. Ensure documents are accessible to test user

**Test Steps:**
1. Access agent interface
2. Send message: "Prepare a brief for my Project Phoenix meeting"
3. Wait for response
4. Review document presentation in the brief

**Expected Results:**
- Brief includes all related documents
- Each document has a clear, descriptive label
- Each document has a direct, clickable link to the source file
- Document types are indicated (Doc, PDF, Sheet, etc.)
- Links open to the correct documents when clicked

**Validation Checkpoints:**
- ✅ All relevant documents are found and included
- ✅ Each document has a clear, descriptive label
- ✅ Each document has a direct link to the source file
- ✅ Links are clickable and functional
- ✅ Document types are clearly indicated
- ✅ Links open to the correct documents
- ✅ No broken or unauthorized links

### Test Scenario 6: Error Handling

**Objective:** Verify robust error handling

**Test Cases:**

**6a. No Upcoming Meetings:**
- Request brief when no meetings scheduled
- Expected: "No upcoming meetings found" message

**6b. Calendar Access Denied:**
- Test with user who hasn't granted Calendar permissions  
- Expected: Clear error message about permissions

**6c. Network/API Failures:**
- Simulate API failures (can be done by temporarily removing permissions)
- Expected: Graceful degradation with partial results

**6d. Invalid Meeting Requests:**
- Request brief for non-existent meeting
- Expected: Appropriate error message

**Validation Checkpoints:**
- ✅ No agent crashes or infinite loops
- ✅ Clear error messages provided
- ✅ User guided on how to resolve issues

## ADK Web Testing Guide

### Local Development Setup

ADK Web provides a convenient way to test the Meeting Prep Agent locally during development:

1. **Install ADK Web:**
   ```bash
   pip install google-adk-web
   ```

2. **Start the agent locally:**
   ```bash
   # From the project root directory
   adk web
   
   # This will start the server and you can access the meeting prep agent
   # The agent will be available at: http://localhost:8000/dev-ui?app=adk_agents
   ```

3. **Access the web interface:**
   - Open browser to `http://localhost:8000/dev-ui?app=adk_agents`
   - Complete OAuth authentication flow
   - Test agent interactions

### ADK Web Test Scenarios

#### Basic Functionality Test
1. Start agent with `adk web` from project root
2. Navigate to `http://localhost:8000/dev-ui?app=adk_agents`
3. Authenticate with Google OAuth
4. Send message: "Prepare a meeting brief"
5. Verify agent responds appropriately

#### OAuth Flow Test
1. Clear browser cache/cookies
2. Start fresh ADK Web session
3. Verify OAuth consent screen appears
4. Grant necessary permissions (Calendar, Drive, etc.)
5. Verify successful authentication
6. Test agent functionality after auth

#### Error Handling Test
1. Start agent without proper environment variables
2. Verify appropriate error messages
3. Fix configuration and restart
4. Test successful operation

### Debugging with ADK Web

ADK Web provides excellent debugging capabilities:

- **Real-time logs:** Console shows agent execution logs
- **OAuth debugging:** Clear visibility into auth flow
- **Interactive testing:** Immediate feedback on agent responses
- **Environment validation:** Easy to test different configurations

### Test Scenario 7: Performance and Scalability

**Objective:** Verify performance under various conditions

**Test Cases:**

**6a. Large Meeting (Many Attendees):**
- Meeting with 20+ attendees
- Expected: Brief generated within 30 seconds

**6b. Multiple Documents:**
- Meeting with 10+ related Drive documents
- Expected: Top 5 documents included, ranked by relevance

**6c. Concurrent Requests:**
- Multiple users requesting briefs simultaneously
- Expected: All requests handled without timeouts

**Validation Checkpoints:**
- ✅ Response time < 30 seconds for normal cases
- ✅ Response time < 60 seconds for complex cases
- ✅ No timeouts or failures under load

## Test Data Setup

### Calendar Test Data

Create test calendar events with varying characteristics:

1. **Basic Meeting:**
   ```
   Title: "Project Phoenix Weekly Sync"
   Time: Tomorrow 2:00 PM
   Attendees: 3-5 people
   Description: "Weekly sync for Project Phoenix"
   ```

2. **Meeting with Attachments:**
   ```
   Title: "Q4 Planning Review"
   Time: Next week
   Attachments: Link to Google Doc
   ```

3. **Recurring Meeting:**
   ```
   Title: "Team Standup"
   Recurrence: Daily
   Previous occurrences with notes
   ```

### Drive Test Data

Create test documents:

1. **Project Documents:**
   ```
   "Project Phoenix - Requirements.docx"
   "Phoenix Implementation Plan.pdf"
   "Weekly Notes - Phoenix Team.gdoc"
   ```

2. **Meeting Notes:**
   ```
   "Q4 Planning - Meeting Notes.gdoc"
   "Action Items - Team Meeting.gsheet"
   ```

### Slack Test Data (Optional)

If Slack integration enabled:

1. **Test Channel:** `#project-phoenix`
2. **Test Messages:** Recent discussions about project status
3. **Keywords:** Messages containing meeting-related terms

## Validation Criteria

### Functional Requirements

- ✅ **Calendar Integration:** Agent retrieves upcoming meetings
- ✅ **Drive Integration:** Agent finds and links relevant documents
- ✅ **Slack Integration:** Agent summarizes relevant messages (if configured)
- ✅ **Brief Generation:** Agent creates structured, readable briefs
- ✅ **Error Handling:** Agent handles errors gracefully
- ✅ **Security:** Agent respects permissions and doesn't expose unauthorized content

### Performance Requirements

- ✅ **Response Time:** < 30 seconds for typical requests
- ✅ **Availability:** 99% uptime during testing period
- ✅ **Scalability:** Handles multiple concurrent users

### User Experience Requirements

- ✅ **Clarity:** Briefs are easy to read and understand
- ✅ **Relevance:** Content is relevant to the meeting
- ✅ **Completeness:** All available relevant information included
- ✅ **Actionability:** Users can act on the information provided

## Troubleshooting Guide

### Common Issues

**Issue: "No upcoming meetings found"**
- Verify calendar has events in the next 24 hours
- Check calendar permissions in OAuth consent

**Issue: "Permission denied" errors**
- Verify OAuth scopes include required permissions
- Re-authorize if needed through AgentSpace

**Issue: Drive documents not found**
- Ensure documents contain meeting title keywords
- Verify Drive permissions for the test user

**Issue: Agent deployment fails**
- Check environment variables in `.env`
- Verify Google Cloud APIs are enabled
- Check Cloud Storage bucket permissions

**Issue: AgentSpace authorization fails**
- Verify CLIENT_ID and CLIENT_SECRET are correct
- Check OAuth 2.0 configuration in Google Cloud Console
- Ensure redirect URIs are properly configured

### Debug Steps

1. **Check Agent Logs:**
   ```bash
   # View reasoning engine logs in Google Cloud Console
   # Navigate to: AI Platform > Reasoning Engines > Your Engine > Logs
   ```

2. **Test Individual Components:**
   ```bash
   # Test config loading
   python -c "from config.settings import load_settings; print(load_settings())"
   
   # Test OAuth setup
   python -c "from agents.meeting_prep_agent import prereq_setup; print('OAuth setup working')"
   ```

3. **Verify API Access:**
   ```bash
   # Test Calendar API
   python -c "from tools.calendar_fetcher import get_next_event; print('Calendar API working')"
   
   # Test Drive API  
   python -c "from tools.drive_search import search_drive; print('Drive API working')"
   ```

## Success Criteria

The Meeting Prep Agent passes E2E testing when:

1. **All test scenarios pass** without critical failures
2. **Performance requirements** are met consistently
3. **User experience** is smooth and intuitive
4. **Error handling** is robust and informative
5. **Security and privacy** requirements are satisfied
6. **Integration points** (Calendar, Drive, Slack) work reliably

## Test Execution Checklist

### Pre-Testing
- [ ] Environment configured (.env file complete)
- [ ] Dependencies installed (requirements.txt)
- [ ] Google Cloud APIs enabled
- [ ] OAuth 2.0 credentials created
- [ ] Test data prepared (calendar events, documents)
- [ ] ADK Web installed (`pip install google-adk-web`)

### Local Testing with ADK Web
- [ ] ADK Web agent starts successfully (`adk web` from project root)
- [ ] Web interface accessible at http://localhost:8000/dev-ui?app=adk_agents
- [ ] OAuth authentication flow works
- [ ] Basic meeting brief generation works
- [ ] Error messages display correctly
- [ ] Real-time debugging functional

### AgentSpace Deployment Testing
- [ ] Agent deployment successful (reasoning engine)
- [ ] AgentSpace authorization created
- [ ] AgentSpace agent created
- [ ] AgentSpace interface accessible
- [ ] Production-like environment testing

### PRD Acceptance Criteria Testing
- [ ] AC-1: Recurring meeting with historical context
- [ ] AC-2: Meeting with attachments and agenda summary
- [ ] AC-3: Slack channel integration for Project Phoenix
- [ ] AC-4: "No preparatory materials found" message
- [ ] AC-5: Document labeling and direct links

### Core Functionality Testing
- [ ] Drive document integration works
- [ ] Calendar event parsing works
- [ ] Error handling validates correctly
- [ ] Performance requirements met

### Advanced Testing
- [ ] Slack integration tested (if configured)
- [ ] Multiple document types handled
- [ ] Recurring meeting support works
- [ ] Concurrent user support validated
- [ ] Security and permissions verified

### Post-Testing
- [ ] All test results documented
- [ ] Performance metrics collected
- [ ] Issues identified and prioritized
- [ ] Both ADK Web and AgentSpace deployments validated
- [ ] Ready for production deployment

---

## Notes

- This test plan covers all acceptance criteria defined in the Meeting Prep Agent PRD
- Test scenarios are designed for both ADK Web (local development) and AgentSpace (production) environments
- PRD acceptance criteria (AC-1 through AC-5) are specifically validated
- ADK Web provides excellent debugging and development testing capabilities
- Test data should be refreshed regularly to ensure realistic testing conditions
- Both local and cloud deployment paths are covered for comprehensive validation
- Consider automating these tests for continuous integration once manual testing is complete