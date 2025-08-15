# 🤖 Google Calendar Meeting Prep Agent

An intelligent AI agent that automatically prepares comprehensive meeting briefs by analyzing your Google Calendar events, Drive attachments, and providing AI-powered insights for better meeting preparation.

![Meeting Prep Agent Demo](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Python Version](https://img.shields.io/badge/Python-3.12+-blue)
![Google Cloud](https://img.shields.io/badge/Platform-Google%20Cloud%20AgentSpace-orange)

## 🌟 Features

### 📅 **Smart Calendar Integration**
- Automatically fetches your next upcoming meeting from Google Calendar
- Extracts meeting details: title, time, attendees, location, description
- **Historical Context**: For recurring meetings, finds and analyzes past instances
- **Past Meeting Analysis**: Links to previous meeting notes and summaries

### 📎 **Advanced Attachment Processing** 
- **Google Drive Integration**: Automatically detects and extracts content from:
  - Google Docs (text content)
  - Google Sheets (CSV data)
  - Google Slides (presentation text)
  - PDF files (metadata and links)
  - Plain text files
- **Smart URL Detection**: Finds Drive links in meeting descriptions
- **Content Preview**: Shows relevant excerpts from attached documents

### 📚 **Historical Context & Meeting Memory**
- **Recurring Meeting Support**: Automatically detects recurring meetings
- **Historical Analysis**: Finds and references past meeting instances
- **Past Notes Integration**: Links to previous meeting notes and documents
- **Timeline Tracking**: Shows meeting history over the last 60 days
- **Context Continuity**: Maintains context across recurring meeting series

### 💬 **Slack Integration** 
- **Smart Channel Detection**: Automatically finds relevant Slack channels based on meeting titles
- **Message Analysis**: Scans recent discussions (last 7 days) for meeting context
- **AI-Powered Relevance**: Uses Gemini 2.5 Flash to analyze and summarize Slack conversations
- **Direct Links**: Provides links to relevant Slack messages and threads
- **Channel Suggestions**: Recommends channels to check manually when auto-detection fails

### 🧠 **AI-Powered Analysis**
- **Gemini 2.5 Flash Integration**: Latest AI model for superior meeting context analysis
- **Attachment Intelligence**: AI analyzes document content and provides:
  - Document summaries
  - Key discussion points
  - Action items identification
  - Preparation recommendations
  - Relevant questions to consider
- **Meeting Context Research**: AI provides background insights and preparation guidance
- **Slack Integration**: Scans relevant Slack channels for recent discussions
- **Historical Analysis**: AI analyzes past meeting instances for context and continuity

### 📋 **Enhanced Meeting Briefs**
- **Professional Formatting**: Clean markdown with emojis and structured sections
- **Comprehensive Output**: Includes meeting details, historical context, Slack discussions, attachment analysis, and AI insights
- **Historical Context**: Past meeting summaries and action items for recurring meetings
- **Slack Context**: Recent relevant discussions from related channels
- **Actionable Content**: Focus on preparation and discussion points
- **One-Click Access**: Direct links to meeting, attachments, and Slack messages

## 🚀 Quick Start

### Prerequisites

- Google Cloud Project with AgentSpace enabled
- Python 3.12+
- Google Calendar and Drive API access
- OAuth 2.0 credentials configured

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/leeahnduk/google-calendar-agent.git
cd google-calendar-agent
```

2. **Set up virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your Google Cloud, OAuth, and Slack settings
```

### Configuration

**🔒 Security First**: Never commit sensitive credentials!

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your actual values (NEVER commit this file!)
# The .env file is protected by .gitignore
```

Required settings in `.env`:
```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_PROJECT_NUMBER=your-project-number
GOOGLE_CLOUD_LOCATION=us-central1
STAGING_BUCKET=gs://your-staging-bucket

# OAuth Credentials (from Google Cloud Console)
CLIENT_ID=your-oauth-client-id
CLIENT_SECRET=your-oauth-client-secret

# Agent Configuration
AGENT_DISPLAY_NAME=Meeting_Prep_Agent
AUTH_ID=meeting-prep-auth

# Optional: Slack Integration
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret
```

**⚠️ Security Note**: The `.env` file is automatically excluded from version control. See [SECURITY.md](SECURITY.md) for detailed security guidelines.

### 💬 Slack Integration Setup (Optional)

To enable Slack integration for enhanced meeting context:

#### Step 1: Create Slack App

1. **Visit Slack API**: https://api.slack.com/apps
2. **Create New App**: Choose "From scratch"
3. **App Name**: "Meeting Prep Agent"
4. **Workspace**: Select your workspace

#### Step 2: Configure Bot Permissions

1. **Go to "OAuth & Permissions"**
2. **Add Bot Token Scopes**:
   ```
   channels:history    # Read public channel messages
   channels:read      # View basic channel info
   users:read         # Read user profile info
   ```

#### Step 3: Install App to Workspace

1. **Click "Install to Workspace"**
2. **Review permissions** and approve
3. **Copy Bot User OAuth Token** (starts with `xoxb-`)

#### Step 4: Configure Environment

Add to your `.env` file:
```bash
# Slack Integration
SLACK_BOT_TOKEN=xoxb-your-copied-token-here
SLACK_SIGNING_SECRET=your-signing-secret-from-basic-info
```

#### Step 5: Add Bot to Channels

For the agent to read channel messages:
```
/invite @Meeting_Prep_Agent
```

**Note**: The agent will automatically search for channels matching meeting titles (e.g., "Project Phoenix" → `#project-phoenix`).

### Deployment

Deploy to Google Cloud AgentSpace:

```bash
# Set environment variables
export PYTHONPATH=$(pwd):$PYTHONPATH
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export STAGING_BUCKET=gs://your-staging-bucket
export AUTH_ID=meeting-prep-auth
export AGENT_DISPLAY_NAME="Meeting_Prep_Agent"

# Deploy the agent
python agents/meeting_prep_agent.py
```

## 🛠️ Usage

### In AgentSpace

1. Navigate to your AgentSpace web interface
2. Find your "Meeting_Prep_Agent"
3. Ask: **"Generate the meeting brief for my next meeting"**
4. Receive a comprehensive brief with AI analysis

### Example Output

```markdown
# 📅 Meeting Brief

## Project Phoenix Weekly Sync

**🕐 Time:** 2025-08-14T15:00:00+00:00  
**⏱️ Duration:** Until 2025-08-14T16:00:00+00:00

**📝 Description:** Weekly sync for Project Phoenix development team

**👥 Attendees:**
- john@company.com (accepted)
- sarah@company.com (tentative)
- mike@company.com (accepted)

**📍 Location:** Conference Room A / Google Meet

## 📎 Attachments

### [Project Phoenix - Sprint Review](https://drive.google.com/file/d/xyz/view)
**Type:** application/vnd.google-apps.document
**Preview:** Sprint 3 completed with 95% story completion rate...

## 📚 Historical Context (Recurring Meeting)

**Previous Instance:** 2025-08-07T15:00:00+00:00
**Previous Description:** Sprint 2 review - discussed API implementation delays...

**Meeting History:** This meeting has occurred 4 time(s) in the last 60 days.

*Note: For detailed notes from previous sessions, check your meeting notes repository.*

## 💬 Slack Context

**Channel:** #project-phoenix
**Recent Messages:** 12 messages in the last 7 days

**Key Discussion Points:**
- API integration testing completed successfully
- Database migration scheduled for next sprint
- New team member onboarding in progress

**Recent Updates:**
- Performance benchmarks exceeded expectations
- Security review passed with minor recommendations

**Direct Links:**
- [Message from @sarah](https://slack.com/app_redirect?channel=C123&message_ts=1692123456)
- [Message from @mike](https://slack.com/app_redirect?channel=C123&message_ts=1692123789)

## 📋 Attachment Analysis

**Document Summary**: Sprint review document shows excellent progress with 95% completion rate...

**Key Points**:
- All major features implemented on schedule
- Performance metrics exceed baseline by 30%
- Minor bug fixes identified for next sprint

**Action Items**:
- Complete remaining 5% of sprint backlog
- Plan next sprint features and priorities
- Address performance optimization opportunities

## 🧠 AI Research & Insights (Powered by Gemini 2.5 Flash)

**Key Topics**: This appears to be a recurring development team sync focusing on sprint progress...

**Preparation Points**:
- Review sprint metrics and completion rates
- Prepare updates on individual contributions
- Consider blockers and dependencies for next sprint

**Enhanced AI Analysis**: Leveraging Google's latest Gemini 2.5 Flash model for superior context understanding and more accurate insights.
```

## 🏗️ Architecture

### Core Components

```
google-calendar-agent/
├── agents/
│   └── meeting_prep_agent.py    # Main agent implementation
├── config/
│   └── settings.py              # Configuration management
├── tools/                       # Utility functions
├── tests/                       # Test suites
├── requirements.txt             # Python dependencies
├── .env                         # Environment configuration
└── update_features.md           # Feature update guide
```

### Key Features Implementation

- **Calendar Integration**: Uses Google Calendar API v3
- **Drive Processing**: Google Drive API v3 for document access
- **AI Analysis**: Vertex AI Gemini 2.0 Flash model
- **Agent Framework**: Google ADK (Agent Development Kit)
- **Deployment**: Google Cloud AgentSpace

## 🔧 Development

### Adding New Features

1. **Modify the main function** in `agents/meeting_prep_agent.py`:
```python
def prepare_meeting_brief(tool_context: ToolContext):
    # Add your feature implementation here
    # Keep imports within the function for deployment compatibility
```

2. **Deploy updates**:
```bash
python agents/meeting_prep_agent.py
```

3. **Verify deployment**:
```bash
python -c "
import vertexai
from vertexai import agent_engines
vertexai.init(project='your-project', location='us-central1')
agents = list(agent_engines.list(filter='display_name=\"Meeting_Prep_Agent\"'))
print(f'Found {len(agents)} agents')
print(f'Last updated: {agents[0].update_time}')
"
```

### Best Practices

- **Self-contained functions**: Keep all imports within the main function
- **Error handling**: Always provide graceful fallbacks
- **Content limits**: Respect API limits for document content
- **Testing**: Test locally before deploying to AgentSpace

## 📊 API Integrations

### Google APIs Used
- **Calendar API v3**: Event fetching and details
- **Drive API v3**: Document access and content extraction
- **OAuth2 API v2**: User authentication and profile info

### AI/ML Services
- **Vertex AI**: Google Cloud's ML platform
- **Gemini 2.5 Flash**: Latest advanced language model for enhanced analysis and insights

### Required OAuth Scopes
```
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/userinfo.email
```

## 🔒 Security & Privacy

- **OAuth 2.0**: Secure authentication with minimal required scopes
- **Read-only access**: Agent only reads data, never modifies
- **Content limits**: Document content is limited to 3000 characters
- **No data storage**: Agent doesn't store or cache user data
- **Secure deployment**: Runs in Google Cloud's secure environment
- **Credential Protection**: Comprehensive .gitignore prevents credential leaks
- **Security Guidelines**: See [SECURITY.md](SECURITY.md) for detailed security practices

### Required OAuth Scopes (Minimal Access)
```
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/userinfo.email
```

## 📈 Performance

- **Response time**: Typically 5-15 seconds for complete analysis
- **Document processing**: Handles multiple attachments efficiently
- **AI analysis**: Optimized prompts for relevant insights
- **Scalability**: Serverless deployment scales automatically

## 🐛 Troubleshooting

### Common Issues

1. **Module Import Errors**
   - Solution: Ensure all imports are within the `prepare_meeting_brief` function

2. **OAuth Errors**
   - Solution: Refresh authorization in AgentSpace interface
   - Clear browser cache for AgentSpace domain

3. **Deployment Timeouts**
   - Normal behavior for large deployments
   - Use verification script to confirm success

4. **No Meetings Found**
   - Check calendar permissions and upcoming events
   - Verify timezone settings

### Debug Steps

1. Check agent logs in Google Cloud Console
2. Verify OAuth scopes and permissions
3. Test with a simple calendar event
4. Check environment variable configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔒 Security

Security is a top priority. Please review our [Security Guidelines](SECURITY.md) before contributing or deploying. 

**Never commit sensitive credentials** - they are protected by our comprehensive `.gitignore`.

## 🙏 Acknowledgments

- Google Cloud AgentSpace team for the platform
- Google API teams for Calendar and Drive integration
- Vertex AI team for Gemini model access

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/leeahnduk/google-calendar-agent/issues)
- **Documentation**: See `update_features.md` for detailed deployment guide
- **Google Cloud Support**: For AgentSpace platform issues

---

**⚡ Agent Status**: Production Ready  
**📅 Last Updated**: August 14, 2025  
**🚀 Agent Resource**: `projects/777331773170/locations/us-central1/reasoningEngines/6897957720666669056`
