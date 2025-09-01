# Meeting Prep Agent - Feature Update Guide

This guide explains how to update and deploy new features for the Meeting Prep Agent in AgentSpace.

## 📋 Prerequisites

- Google Cloud project: `aiproject-429506`
- Agent deployed in AgentSpace
- Virtual environment with Python 3.12
- OAuth authorization configured

## 🔄 Feature Update Process

### Step 1: Environment Setup

Navigate to the project directory and activate the virtual environment:

```bash
cd /Users/anhduc/API/ADK/google-calendar-agent
source venv/bin/activate
```

### Step 2: Make Code Changes

Edit the agent code in `agents/meeting_prep_agent.py`:
- The main function to modify is `prepare_meeting_brief(tool_context: ToolContext)`
- This function contains all the logic for generating meeting briefs
- Add new features by modifying this function or adding helper functions within it

**Important Notes:**
- Keep all imports and dependencies within the function to avoid deployment issues
- Use self-contained implementations to prevent module import errors
- Test locally if possible before deploying

### Step 3: Deploy Updated Agent

Run the deployment command (environment variables are loaded from .env file):

```bash
cd /Users/anhduc/API/ADK/google-calendar-agent && \
source venv/bin/activate && \
export PYTHONPATH=/Users/anhduc/API/ADK/google-calendar-agent:$PYTHONPATH && \
python agents/meeting_prep_agent.py
```

**Note:** All configuration values (including AUTH_ID, GOOGLE_CLOUD_PROJECT, etc.) are automatically loaded from the `.env` file.

**Note:** This command may take 2-5 minutes to complete and might timeout. This is normal for agent deployments.

### Step 4: Verify Deployment

Check if the agent was successfully updated:

```bash
cd /Users/anhduc/API/ADK/google-calendar-agent && \
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
print(f'Using AUTH_ID: {settings.auth_id}')
for agent in agents:
    print(f'Agent: {agent.display_name}')
    print(f'Updated: {agent.update_time}')
"
```

**Success Indicators:**
- Script shows "Found 1 agents"
- Update timestamp is recent (within last few minutes)
- No errors in the output

### Step 5: Test in AgentSpace

1. Go to the AgentSpace web interface
2. Navigate to your Meeting Prep Agent
3. Test the new features by asking: "generate the meeting brief for my next meeting"
4. Verify new functionality works as expected

## 🛠️ Common Development Patterns

### Adding New Features

When adding new features to the `prepare_meeting_brief` function:

1. **Import libraries within the function:**
   ```python
   def prepare_meeting_brief(tool_context: ToolContext):
       from datetime import datetime
       from googleapiclient.discovery import build
       # ... other imports
   ```

2. **Create helper functions within the main function:**
   ```python
   def prepare_meeting_brief(tool_context: ToolContext):
       def _helper_function(param):
           # Helper logic here
           return result
       
       # Main logic here
   ```

3. **Handle errors gracefully:**
   ```python
   try:
       # Feature implementation
       result = new_feature()
   except Exception as e:
       return {"panel_markdown": f"Error: {str(e)}"}
   ```

### Current Agent Features

The agent currently includes:
- **Basic meeting info** (title, time, attendees, location)
- **Google Drive attachment processing** (extracts and previews files)
- **Gemini AI research** (analyzes meeting context and provides insights)
- **Enhanced formatting** (emojis, sections, markdown)
- **📚 Historical Context** (NEW - Aug 15, 2025):
  - Automatic detection of recurring meetings
  - Past meeting instance analysis (60-day lookback)
  - Previous meeting summaries and context continuity
- **💬 Multi-Platform Chat Integration** (ENHANCED - Aug 18, 2025):
  - **Slack Integration:** Smart channel detection, message analysis, direct links
  - **Google Chat Integration:** Space discovery, attendee-based search, topic matching
  - **Multi-Platform Support:** Configurable preferences (slack/google_chat/both)
  - **AI-Powered Analysis:** Unified chat context analysis across platforms

### Example Feature Addition

To add a new feature like "meeting history analysis":

```python
def prepare_meeting_brief(tool_context: ToolContext):
    # ... existing imports and setup ...
    
    def _analyze_meeting_history(calendar_service, attendees):
        """New feature: analyze past meetings with same attendees"""
        try:
            # Implementation here
            return "Historical context..."
        except Exception:
            return "No historical data available"
    
    # ... existing logic ...
    
    # Add new feature
    history_analysis = _analyze_meeting_history(calendar_service, attendee_emails)
    
    # Update markdown template to include new section
    markdown = f"""
    # Meeting Brief
    
    ## ... existing sections ...
    
    ## 📚 Meeting History
    {history_analysis}
    
    ---
    """
```

## 📁 Key Files

- **`agents/meeting_prep_agent.py`** - Main agent code
- **`.env`** - Environment configuration
- **`requirements.txt`** - Python dependencies
- **`venv/`** - Python virtual environment

## 🔧 Troubleshooting

### Common Issues

1. **Module Import Errors:**
   - Solution: Use imports within functions, not at module level
   - Keep all logic self-contained within `prepare_meeting_brief`

2. **OAuth Errors:**
   - Solution: Check if authorization needs refresh in AgentSpace
   - Clear browser cache/cookies for AgentSpace domain

3. **Deployment Timeouts:**
   - Normal behavior for large deployments
   - Use verification step to confirm success

4. **Agent Not Found:**
   - Check `AGENT_DISPLAY_NAME` matches exactly: "Meeting_Prep_Agent"
   - Verify project and location settings

### Debug Steps

1. Check agent logs in Google Cloud Console under "AI Platform > Reasoning Engines"
2. Test OAuth flow by trying to use agent in AgentSpace
3. Verify all environment variables are set correctly
4. Check that virtual environment has all required dependencies

## 📝 Best Practices

1. **Test incrementally** - Add one feature at a time
2. **Keep functions self-contained** - Avoid complex module dependencies
3. **Handle errors gracefully** - Always provide fallback responses
4. **Update documentation** - Keep this guide current with changes
5. **Backup before major changes** - Keep a copy of working code

## 🔗 Useful Resources

- **AgentSpace Web Interface:** `https://vertexaisearch.cloud.google.com/`
- **Google Cloud Console:** `https://console.cloud.google.com/`
- **Agent Logs:** Google Cloud Console > AI Platform > Reasoning Engines
- **OAuth Management:** Google Cloud Console > APIs & Services > Credentials

---

## 🚀 Latest Deployment - January 2025

**📋 Enhanced Meeting Brief with Comprehensive Document Search - Meeting_Prep_Agent_New (Updated):**
- **Comprehensive Document Integration:** Enhanced meeting briefs now include extensive document search across multiple sources
- **Gmail Integration:** Added Gmail API integration to search emails between attendees and extract attachments
- **Advanced Drive Search:** Enhanced Google Drive search to find related documents beyond just meeting attachments
- **AI-Powered Relevance Scoring:** Documents are now ranked by relevance to meeting context using AI analysis
- **Comprehensive Document Table:** New detailed table showing all relevant documents with metadata, relevance scores, and direct links
- **Multi-Source Document Discovery:** Searches across:
  - Direct meeting attachments (highest priority)
  - Gmail attachments from attendee communications
  - Related documents in Google Drive
- **Enhanced Document Analysis:** AI analyzes document content and provides comprehensive insights
- **Technical Improvements:**
  - Added Gmail API integration with email search capabilities
  - Implemented document relevance scoring algorithm
  - Enhanced document metadata extraction and formatting
  - Added comprehensive document table generation
  - Improved error handling for multi-API integration
- **Deployment Status:** ✅ Ready for deployment
- **Agent Resource:** `projects/777331773170/locations/us-central1/reasoningEngines/510305336683397120`

**New Features Added:**
1. **Gmail Integration:** Search emails between attendees for relevant attachments and documents
2. **Comprehensive Drive Search:** Find related documents in Google Drive beyond just attachments
3. **Document Relevance Scoring:** AI-powered ranking of documents by relevance to meeting context
4. **Comprehensive Document Table:** Detailed table with document metadata, relevance scores, and direct links
5. **Multi-Source Document Discovery:** Unified search across Gmail, Drive, and direct attachments
6. **Enhanced Document Analysis:** AI analysis of document content for meeting preparation insights

## 🚀 Previous Deployment - August 25, 2025

**🎯 Enhanced Question Handling & AgentSpace Issue Resolution - Meeting_Prep_Agent_New (Updated):**
- **Enhanced Capabilities:** Expanded agent to handle comprehensive calendar and meeting management queries
- **Calendar Context:** Added automatic calendar overview showing today/tomorrow/week schedule in meeting briefs
- **Advanced Chat Debugging:** Enhanced Google Chat integration with detailed debugging and troubleshooting information
- **Broader Query Handling:** Agent now ALWAYS uses prepare_brief tool for ANY calendar question
- **Enhanced Prompt:** Updated instruction to explicitly handle "How many meetings", "Show schedule", etc.
- **AgentSpace Issue Resolution:** Identified and documented 404 error as AgentSpace frontend bug
- **Technical Improvements:**
  - Extended calendar lookback to 7 days for better context
  - Added meeting pattern analysis and schedule insights
  - Enhanced error handling and user guidance
  - Improved Google Chat authentication troubleshooting
  - Fixed instruction prompt to ensure broader question handling
- **Deployment Status:** ✅ Successfully deployed and verified
- **Agent Resource:** `projects/777331773170/locations/us-central1/reasoningEngines/510305336683397120`

**Previous Features:**
1. **Calendar Overview Integration:** Automatic display of upcoming meetings in briefs
2. **Enhanced Chat Debugging:** Detailed Google Chat API status and troubleshooting info
3. **Expanded Query Support:** Handles calendar management questions beyond just meeting briefs
4. **Schedule Analysis:** Pattern recognition and conflict detection
5. **Proactive Suggestions:** Smart recommendations for meeting prep and schedule optimization

---

## 🚀 Previous Deployment - August 19, 2025

**🆕 New Agent Creation & AgentSpace Registration - Meeting_Prep_Agent_New (06:51:41 UTC):**
- **Complete Solution:** Created and registered new agent `Meeting_Prep_Agent_New` in AgentSpace
- **Reasoning Engine:** `projects/777331773170/locations/us-central1/reasoningEngines/510305336683397120`
- **AgentSpace Agent ID:** `14215929426136558776`
- **OAuth Authorization:** `meeting-prep-new-auth` (active OAuth client with correct scopes)
- **AgentSpace Engine:** `argolis-demo-agent_1752114481275`
- **Status:** ✅ Successfully created, deployed, and registered in AgentSpace
- **Visibility:** Agent now appears in AgentSpace UI under "From your organization"

**✅ Resolution Steps Completed:**
1. Created new reasoning engine with clean OAuth configuration (06:33:30 UTC)
2. Configured missing AgentSpace environment variables  
3. Registered agent in AgentSpace using discovery engine API (06:51:41 UTC)
4. Agent now visible and ready for use in AgentSpace

**Previous Issues Resolved:**
- OAuth client configuration conflicts with old agent
- Missing AgentSpace registration causing agent to be invisible in UI
- Environment variable configuration for AgentSpace deployment

---

## 🚀 Previous Deployment - August 18, 2025

**💬 Google Chat Integration - Multi-Platform Chat Support (08:11:03 UTC):**
- **New Feature:** Complete Google Chat API integration for meeting context
- **Enhancement:** Multi-platform chat support (Slack + Google Chat simultaneously)
- **Technical Fix:** Resolved AgentSpace module import compatibility issues
- **Capabilities:**
  - Google Chat space and message fetching with OAuth2
  - Attendee-based conversation search across DMs and group chats
  - Meeting topic matching and relevance filtering
  - AI-powered analysis of Google Chat discussions
  - Configurable integration preferences (slack/google_chat/both)
- **Deployment Status:** ✅ Successfully deployed and AgentSpace compatible

---

## 🚀 Previous Deployment - August 15, 2025

**🤖 AI Model Upgrade - Gemini 2.5 Flash (06:33:57 UTC):**
- **Model Upgrade:** Updated from Gemini 2.0 Flash to Gemini 2.5 Flash
- **Enhanced Capabilities:** Superior AI analysis across all features
- **Performance Boost:** Improved context understanding and response quality
- **Deployment Status:** ✅ Successfully deployed and verified

**✅ Successfully Deployed PRD-Compliant Features:**

### 📚 Historical Context Feature
- **Deployment Time:** 2025-08-15 06:12:05 UTC
- **Feature Status:** ✅ Production Ready
- **Capabilities:**
  - Automatic recurring meeting detection
  - 60-day historical timeline analysis
  - Previous meeting context and summaries
  - Graceful handling for non-recurring meetings

### 💬 Slack Integration Feature  
- **Deployment Time:** 2025-08-15 06:12:05 UTC
- **Feature Status:** ✅ Production Ready
- **Capabilities:**
  - Smart channel detection from meeting titles
  - Recent message retrieval and AI analysis
  - Key discussion points and action items extraction
  - Direct links to relevant Slack conversations
  - Comprehensive error handling

### 🎯 PRD Compliance Status
All acceptance criteria from the Meeting Prep Agent PRD are now fully implemented:
- ✅ **AC-1:** Recurring meeting historical context
- ✅ **AC-2:** Document retrieval and agenda summary
- ✅ **AC-3:** Slack channel integration
- ✅ **AC-4:** "No materials found" handling
- ✅ **AC-5:** Document labeling and direct links

### 🧪 Testing Instructions
Refer to the updated `Testplan.md` for comprehensive testing scenarios for the new features.

---

*Last updated: 2025-08-19*
*Primary Agent: Meeting_Prep_Agent_New*
*Reasoning Engine: projects/777331773170/locations/us-central1/reasoningEngines/510305336683397120*
*AgentSpace Agent ID: 14215929426136558776*
*Latest Registration: 2025-08-19 06:51:41 UTC*
*AI Model: Gemini 2.5 Flash (Latest)*
*Features: Multi-Platform Chat Integration (Slack + Google Chat)*
*OAuth Authorization: meeting-prep-new-auth (Active OAuth client with all required scopes)*
*AgentSpace Status: ✅ Fully Registered and Visible in UI*