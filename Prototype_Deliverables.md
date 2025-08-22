# 2.2. Prototype Deliverables

The scope will focus on the current GA features of Agentspace/Connector to bring Grab onboard and be familiar with Agent Development Kits (ADK), Agent Engine and Agentspace.

For data source connector that is currently not available, it will be put on hold to revisit in the future so that Grab start exploring earlier.

## In Scope:
• Prototyping will be done with the Agentspace UI display without custom UI
• The following data sources will be included.
• Prototyping will be done in Google Argolis account, where code will be shared with Grab

| Data source | Note |
|-------------|------|
| **Google Workspace** | **Include in prototyping scopes** |
| - Google Docs | |
| - Google Sheets | |
| - Google Calendar | |
| - Gmail | |
| - Google Drive | |
| **Slack** | **Include in prototyping scopes - Available via custom integration** |
| **Google Chat** | **Include in prototyping scopes - Available via Google Chat API** |
| **Zoom** | **Exclude for current phase until there is built in connector support.** |

---

## Use Case 1

• Instead of proactive or scheduled auto-trigger to display meeting brief. The display of information is triggered via a chat trigger word.
  ○ Generate meeting brief for next meeting
  ○ Generate meeting brief for specific meeting
  ○ Generate meeting brief with historical context
  ○ Analyze related documents and attachments

• A pre-configured date and time will be used to demonstrate the capabilities.

![AgentSpace Interface](agentspace-demo.png)

**The following features will be tested as part of prototyping:**

**Meeting Brief Generation - Triggered by Chat Commands**

| Test Case | Description | Notes |
|-----------|-------------|-------|
| **Meeting Brief - Next Meeting** | Sample request: <br><br>------------ <br>**User Query:** <br>"Generate meeting brief for my next meeting" <br><br>**Expected Response:** <br>Agent analyzes next calendar event, finds related documents, checks Slack/Chat for context, and provides comprehensive brief with historical data if recurring meeting. <br>------------ | Able to identify next meeting in Google Calendar <br><br>Extracts meeting details and attachments <br><br>Searches for related conversations |
| **Meeting Brief - Specific Meeting** | Sample docs: <br><br>------------ <br>**Discussion:** <br>We discussed the progress of the project and identified a few key challenges. We also reviewed the action items from the previous meeting and planned the next steps. <br><br>Super Admin to run through for the next step in the next meeting. <br>------------ | Able to identify specific meeting by title/time <br><br>Meeting title is tagged with @ symbol for identification |
| **Meeting Brief - Historical Context** | Sample docs: <br><br>------------ <br>**Agenda:** <br>The meeting with boss Ashmita is to finalize on the budget SME sales and marketing <br><br>**Summary:** <br>We have identified the list of items to purchase. <br><br>**Next step:** <br>Super Admin to finalize the final budget amount by 25 Aug 2025. <br>------------ | Able to identify recurring meetings <br><br>Provides historical context from previous instances |
| **Meeting Brief - Document Analysis** | Sample Sheets: <br><br>**Items Table:** <br>1. Plan for CEO dinner - Super Admin <br>2. Transport - David <br>3. Marketing - Summer | Able to identify tasks in Google sheets <br><br>Names are tagged with @ symbol for assignment tracking |
| **Meeting Brief - Important Actions** | Any of the morning Brief that comes with a due date. <br><br>------------ <br>**Discussion:** <br><br>Super Admin Please submit the customer refund requests by 31 Aug 2025, 5pm <br>------------ | This can be a duplicate of task, but marked with due date for "today" |
| **Meeting Brief - Upcoming Meetings** | Upcoming meeting | Able to identify upcoming meetings in chronological order <br><br>**Display of detailed** |

---

## Technical Implementation

### Core Components

The Meeting Prep Agent is built using Google Agent Development Kit (ADK) and deployed on Google Cloud AgentSpace platform:

```
google-calendar-agent/
├── agents/
│   └── meeting_prep_agent.py    # Main ADK agent implementation
├── config/
│   └── settings.py              # Configuration management
├── tools/                       # Integration utilities
├── scripts/                     # Deployment and setup utilities
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment configuration template
```

### Technology Stack
- **Platform:** Google Cloud AgentSpace
- **Framework:** Google Agent Development Kit (ADK)
- **AI Model:** Gemini 2.5 Flash
- **APIs:** Calendar API v3, Drive API v3, Slack API, Google Chat API
- **Authentication:** OAuth 2.0 with minimal required scopes
- **Language:** Python 3.12+

### Required OAuth Scopes
```
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/chat.spaces.readonly
https://www.googleapis.com/auth/chat.messages.readonly
```

### Deployment Configuration
```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
STAGING_BUCKET=gs://your-staging-bucket

# OAuth Credentials
CLIENT_ID=your-oauth-client-id
CLIENT_SECRET=your-oauth-client-secret

# Agent Configuration
AGENT_DISPLAY_NAME=Meeting_Prep_Agent
AUTH_ID=meeting-prep-auth
```

---

## Implementation Status

### Completed Features
✅ **Smart Calendar Integration** - Meeting parsing and event detection  
✅ **Document Processing** - Google Docs, Sheets, Drive integration  
✅ **Historical Context** - Recurring meeting intelligence  
✅ **Chat Integration** - Slack and Google Chat analysis  
✅ **AI Analysis** - Gemini 2.5 Flash powered insights  
✅ **Production Deployment** - Live on Google Cloud AgentSpace  

### Agent Resource
**Deployment Status:** ✅ Production Ready  
**Agent Resource:** `projects/777331773170/locations/us-central1/reasoningEngines/6897957720666669056`  
**Last Updated:** August 22, 2025

---

**Document Version:** 1.0  
**Generated:** August 22, 2025  
**Status:** ✅ Prototype Complete - Production Ready