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

Run the deployment command with all required environment variables:

```bash
cd /Users/anhduc/API/ADK/google-calendar-agent && \
source venv/bin/activate && \
export PYTHONPATH=/Users/anhduc/API/ADK/google-calendar-agent:$PYTHONPATH && \
export GOOGLE_CLOUD_PROJECT=aiproject-429506 && \
export GOOGLE_CLOUD_LOCATION=us-central1 && \
export STAGING_BUCKET=gs://duc_agentspace_staging_bucket && \
export AUTH_ID=meeting-prep-auth && \
export AGENT_DISPLAY_NAME="Meeting_Prep_Agent" && \
python agents/meeting_prep_agent.py
```

**Note:** This command may take 2-5 minutes to complete and might timeout. This is normal for agent deployments.

### Step 4: Verify Deployment

Check if the agent was successfully updated:

```bash
source /Users/anhduc/API/ADK/google-calendar-agent/.env && \
source /Users/anhduc/API/ADK/google-calendar-agent/venv/bin/activate && \
python -c "
import os
os.environ['GOOGLE_CLOUD_PROJECT'] = '${GOOGLE_CLOUD_PROJECT}'
os.environ['GOOGLE_CLOUD_LOCATION'] = '${GOOGLE_CLOUD_LOCATION}'
os.environ['STAGING_BUCKET'] = 'gs://${STAGING_BUCKET}'
os.environ['AUTH_ID'] = '${AUTH_ID}'
os.environ['AGENT_DISPLAY_NAME'] = '${AGENT_DISPLAY_NAME}'

import vertexai
from vertexai import agent_engines

vertexai.init(project='${GOOGLE_CLOUD_PROJECT}', location='${GOOGLE_CLOUD_LOCATION}')
agents = list(agent_engines.list(filter='display_name=\"${AGENT_DISPLAY_NAME}\"'))
print(f'Found {len(agents)} agents with display name \"${AGENT_DISPLAY_NAME}\"')
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

*Last updated: 2025-08-14*
*Agent Resource: projects/777331773170/locations/us-central1/reasoningEngines/6897957720666669056*