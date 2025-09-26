# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Environment
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Google Cloud, OAuth, and Slack settings
```

### Testing
```bash
# Run tests
pytest

# Run specific test
pytest tests/test_scheduler.py

# Run tests with verbose output
pytest -v
```

### Deployment
```bash
# Deploy to Google Cloud AgentSpace
python agents/meeting_prep_agent.py

# Verify deployment
python -c "
import vertexai
from vertexai import agent_engines
vertexai.init(project='your-project', location='us-central1')
agents = list(agent_engines.list(filter='display_name=\"Meeting_Prep_Agent\"'))
print(f'Found {len(agents)} agents')
print(f'Last updated: {agents[0].update_time}')
"
```

## Architecture Overview

This is a Google Calendar Meeting Prep Agent built with Google ADK (Agent Development Kit) that automatically generates comprehensive meeting briefs by analyzing calendar events, Drive attachments, chat messages, and providing AI-powered insights.

### Core Components

- **agents/meeting_prep_agent.py**: Main agent implementation containing the `prepare_meeting_brief` function
- **config/settings.py**: Centralized configuration management using environment variables
- **tools/**: Utility modules for specific integrations:
  - `calendar_fetcher.py`: Google Calendar API integration
  - `attachment_ingest.py`: Google Drive document processing
  - `slack_fetcher.py`: Slack integration for message analysis
  - `google_chat_fetcher.py`: Google Chat integration
  - `drive_search.py`: Enhanced Drive search capabilities
- **agents/oauth_util.py**: OAuth 2.0 authentication utilities

### Key Architecture Patterns

1. **Function-scoped imports**: All imports must be within the main `prepare_meeting_brief` function for AgentSpace deployment compatibility
2. **Tool-based architecture**: Each integration is modularized into separate tool files
3. **Environment-driven configuration**: All settings managed through `.env` file and `config/settings.py`
4. **OAuth credential management**: Uses Google OAuth 2.0 with minimal required scopes

### Agent Framework Integration

- Built on Google ADK (Agent Development Kit)
- Deployed to Google Cloud AgentSpace
- Uses Vertex AI Gemini 2.5 Flash model for AI analysis
- Integrates with Google Calendar, Drive, Chat, Gmail, and Slack APIs

### Required OAuth Scopes
```
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/chat.spaces.readonly
https://www.googleapis.com/auth/chat.messages.readonly
https://www.googleapis.com/auth/gmail.readonly
```

### Environment Configuration

Key environment variables (see `.env.example` for full list):
- `GOOGLE_CLOUD_PROJECT`: Your Google Cloud project ID
- `GOOGLE_CLOUD_LOCATION`: Deployment region (default: us-central1)
- `STAGING_BUCKET`: Google Cloud Storage bucket for staging
- `AUTH_ID`: OAuth authorization identifier
- `AGENT_DISPLAY_NAME`: Display name for the agent
- `SLACK_BOT_TOKEN`: Optional Slack integration token
- `GOOGLE_CHAT_ENABLED`: Enable Google Chat integration (true/false)

### Development Notes

- Keep all imports within the `prepare_meeting_brief` function for AgentSpace compatibility
- Test locally before deploying to AgentSpace
- Use the verification script to confirm successful deployment
- All credential files are protected by `.gitignore` - never commit sensitive data
- Agent runs in Google Cloud's secure serverless environment with read-only access

## Multi-Agent Revamp Progress Tracking

**IMPORTANT**: This repository is undergoing a multi-agent architecture revamp. Always refer to `MultiAgent_Revamp_Plan.md` for the complete implementation plan and current progress.

### Progress Tracking Protocol

1. **After completing each task/phase** in `MultiAgent_Revamp_Plan.md`:
   - Update the progress status in the plan document
   - Document lessons learned and any deviations from the original plan
   - Note any technical challenges encountered and their solutions
   - Update architecture diagrams if changes were made

2. **Before starting any new development work**:
   - Check `MultiAgent_Revamp_Plan.md` for current phase and status
   - Review lessons learned from previous phases
   - Understand the current implementation state
   - Follow the established patterns and avoid known pitfalls

3. **Progress Documentation Format**:
   ```markdown
   ## Phase X Progress Update
   **Status**: [Completed/In Progress/Blocked]
   **Date**: YYYY-MM-DD
   **Completed Tasks**:
   - Task 1: Description and outcome
   - Task 2: Description and outcome

   **Lessons Learned**:
   - Lesson 1: What worked well
   - Lesson 2: What to avoid in future

   **Next Steps**: What needs to be done next
   ```

4. **Architecture State Tracking**:
   - Keep track of which components have been migrated
   - Document any breaking changes or compatibility issues
   - Maintain a clear view of what's using old vs new architecture

### Current Revamp Status
**Phase**: Planning Complete - Implementation Ready
**Next**: Begin Phase 1 - Core Infrastructure
**Key Files**: `MultiAgent_Revamp_Plan.md` contains the complete roadmap

### Critical Development Notes

1. **Function-scoped imports**: All imports MUST be within the main function for AgentSpace deployment compatibility
2. **Monolithic tool migration**: The current `prepare_meeting_brief` function in `agents/meeting_prep_agent.py` is 1137 lines and needs to be broken down
3. **Testing strategy**: Run `pytest` for all tests, `pytest tests/test_scheduler.py` for specific tests
4. **Linting**: No specific linting command found - check with user if needed
5. **Agent deployment**: Deploy with `python agents/meeting_prep_agent.py` to Google Cloud AgentSpace

### Important File Locations

- **Main agent**: `agents/meeting_prep_agent.py` (1137 lines - target for refactoring)
- **Core tools**: `tools/` directory contains modular integrations
- **Configuration**: `config/settings.py` centralizes environment management
- **OAuth utilities**: `agents/oauth_util.py` handles authentication
- **Development support**: `agents/meeting_prep_agent_dev_ui_support.py` (393 lines)