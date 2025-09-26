# 🚀 Multi-Agent Revamp Plan for Google Calendar Meeting Prep Agent

## 📋 **Executive Summary**

This document outlines the comprehensive plan to transform the current single-agent Google Calendar Meeting Prep Agent into a sophisticated multi-agent system capable of handling diverse query types with appropriate response formats and enhanced functionality.

## 🎯 **Objectives**

1. **Intent-based Query Routing**: Automatically detect user intent and route to appropriate specialist agents
2. **Flexible Response Formats**: Provide brief summaries or detailed analysis based on user request
3. **Enhanced Search Capabilities**: Search meetings by time, subject, and attendee
4. **Export Functionality**: Export responses to Google Docs
5. **Maintain Existing Features**: Preserve all current functionality while adding new capabilities

## 📊 **Current State Analysis**

### **Current Architecture**
```
Root Agent (LlmAgent)
└── prepare_brief (Sub-agent)
    └── prepare_meeting_brief (Tool) - 1137 lines monolithic function
```

### **Current Limitations**
- **Single response format**: Always returns full detailed brief
- **No query classification**: Treats all requests identically
- **Limited search**: Only "next meeting" capability
- **No export options**: Cannot save responses
- **Monolithic tool**: All functionality in one massive function

### **Current Capabilities to Preserve**
- Google Calendar integration
- Google Drive attachment processing
- Slack message analysis
- Google Chat integration
- Gmail attachment search
- AI-powered document analysis (Gemini 2.5 Flash)
- Historical meeting context
- Comprehensive document tables

## 🏗️ **Target Multi-Agent Architecture**

```
Query Router Agent (New)
├── Meeting Brief Agent (Enhanced)
│   └── generate_meeting_brief (Tool)
├── Meeting Details Agent (New)
│   └── generate_meeting_details (Tool)
├── Meeting Search Agent (New)
│   ├── search_meeting_by_time (Tool)
│   └── search_meeting_by_subject (Tool)
└── Export Agent (New)
    └── export_to_google_docs (Tool)
```

## 🔧 **Implementation Plan**

### **Phase 1: Core Infrastructure**

#### **Step 1.1: Create Shared Core Functions**
**File**: `tools/meeting_core.py`

Extract reusable components from the monolithic `prepare_meeting_brief`:

```python
# Core data classes (already exist, extract to shared module)
@dataclass
class EventContext:
    id: str
    summary: str
    description: str
    start_iso: str
    end_iso: str
    attendees: List[EventAttendee]
    recurring_event_id: Optional[str] = None
    html_link: Optional[str] = None
    location: Optional[str] = None
    attachments: List[Dict] = None

@dataclass
class MeetingContext:
    event: EventContext
    drive_documents: List[DriveDocument]
    slack_context: Optional[Dict] = None
    google_chat_context: Optional[Dict] = None
    gmail_attachments: List[GmailAttachment] = None
    historical_context: Optional[Dict] = None

# Core functions to extract:
def get_user_credentials(tool_context: ToolContext) -> Credentials
def find_next_meeting(calendar_service, user_timezone: str) -> EventContext
def find_meeting_by_time(calendar_service, time_query: str, user_timezone: str) -> EventContext
def find_meeting_by_subject(calendar_service, subject_query: str) -> EventContext
def process_drive_documents(drive_service, event: EventContext) -> List[DriveDocument]
def get_slack_context(event: EventContext) -> Optional[Dict]
def get_google_chat_context(event: EventContext) -> Optional[Dict]
def get_gmail_attachments(gmail_service, event: EventContext) -> List[GmailAttachment]
def analyze_with_gemini(context: MeetingContext, analysis_type: str) -> str
```

#### **Step 1.2: Create Query Classification**
**File**: `tools/query_classifier.py`

```python
from enum import Enum
from typing import Dict, Any
import re

class QueryIntent(Enum):
    MEETING_BRIEF = "brief"
    MEETING_DETAILS = "details"
    SEARCH_BY_TIME = "search_time"
    SEARCH_BY_SUBJECT = "search_subject"
    EXPORT_REQUEST = "export"
    GENERAL_CALENDAR = "general"

class QueryClassifier:
    def __init__(self):
        self.brief_keywords = [
            "brief", "summary", "summarize", "quick", "overview",
            "key points", "prepare", "prep"
        ]
        self.details_keywords = [
            "details", "deep dive", "full analysis", "insights",
            "comprehensive", "in-depth", "analyze", "breakdown"
        ]
        self.time_patterns = [
            r"\d{1,2}:\d{2}\s*(am|pm|AM|PM)",  # 2:30 PM
            r"\d{1,2}\s*(am|pm|AM|PM)",       # 2 PM
            r"at\s+\d{1,2}:\d{2}",            # at 14:30
            r"meeting\s+at\s+",               # meeting at...
            r"today", r"tomorrow", r"next"
        ]
        self.subject_patterns = [
            r"subject[:\s]+[\"'](.+?)[\"']",   # subject: "title"
            r"meeting\s+with\s+subject",       # meeting with subject
            r"titled\s+[\"'](.+?)[\"']"        # titled "title"
        ]
        self.export_keywords = [
            "export", "save", "google doc", "document",
            "save to drive", "create document"
        ]

    def classify_query(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()

        # Check for export intent first
        if any(keyword in query_lower for keyword in self.export_keywords):
            return {
                "intent": QueryIntent.EXPORT_REQUEST,
                "confidence": 0.9,
                "original_query": query
            }

        # Check for time-based search
        time_match = None
        for pattern in self.time_patterns:
            match = re.search(pattern, query_lower)
            if match:
                time_match = match.group()
                break

        if time_match:
            return {
                "intent": QueryIntent.SEARCH_BY_TIME,
                "confidence": 0.85,
                "time_query": time_match,
                "original_query": query
            }

        # Check for subject-based search
        subject_match = None
        for pattern in self.subject_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                subject_match = match.group(1) if match.groups() else match.group()
                break

        if subject_match or "subject" in query_lower:
            return {
                "intent": QueryIntent.SEARCH_BY_SUBJECT,
                "confidence": 0.85,
                "subject_query": subject_match,
                "original_query": query
            }

        # Check for detail vs brief intent
        brief_score = sum(1 for keyword in self.brief_keywords if keyword in query_lower)
        details_score = sum(1 for keyword in self.details_keywords if keyword in query_lower)

        if details_score > brief_score:
            return {
                "intent": QueryIntent.MEETING_DETAILS,
                "confidence": 0.8,
                "original_query": query
            }
        elif brief_score > 0:
            return {
                "intent": QueryIntent.MEETING_BRIEF,
                "confidence": 0.8,
                "original_query": query
            }

        # Default to brief for general queries
        return {
            "intent": QueryIntent.MEETING_BRIEF,
            "confidence": 0.6,
            "original_query": query
        }
```

### **Phase 2: Specialized Agent Tools**

#### **Step 2.1: Meeting Brief Tool**
**File**: `tools/meeting_brief_tool.py`

```python
from google.adk.tools.tool_context import ToolContext
from .meeting_core import get_user_credentials, find_next_meeting, MeetingContext
from .query_classifier import QueryClassifier
from typing import Dict, Any

def generate_meeting_brief(tool_context: ToolContext) -> str:
    """
    Generate a concise meeting brief following the specified format.
    Handles: brief, summary, quick overview queries
    """
    try:
        # Get user query and classify
        user_query = tool_context.request.get("query", "")
        classifier = QueryClassifier()
        classification = classifier.classify_query(user_query)

        # Get meeting context
        creds = get_user_credentials(tool_context)
        meeting_context = find_next_meeting(creds, user_query)

        # Generate brief format output
        return format_meeting_brief(meeting_context)

    except Exception as e:
        return f"Error generating meeting brief: {str(e)}"

def format_meeting_brief(context: MeetingContext) -> str:
    """Format meeting in brief style as specified in requirements"""
    event = context.event

    # Format attendees
    attendees_list = ", ".join([att.email for att in event.attendees])

    # Format time
    start_time = event.start_iso  # Format as needed
    end_time = event.end_iso

    # Get key context from AI analysis
    key_context = analyze_meeting_context_brief(context)
    key_challenge = extract_key_challenge(context)

    # Get top 3 documents
    top_docs = get_top_documents(context.drive_documents, limit=3)
    docs_section = format_documents_brief(top_docs)

    # Generate talking points
    talking_points = generate_talking_points(context, limit=3)

    brief = f"""📅**Meeting:** "{event.summary}" **Time:** {start_time} - {end_time}

* **Attendees:** {attendees_list}
* **Location:** {event.location or "Not specified"}
* **Meeting Link:** [Join Meeting]({event.html_link})

📚**Context:** {key_context}

💬**Key Challenge to Discuss:** {key_challenge}

📎**Related Documents:**
{docs_section}

📋**Potential Talking Points:**
{talking_points}

If you'd like to dig deeper, I have more details ready. Just ask for the full document analysis, a list of questions to consider for the meeting, or insights into the project's history."""

    return brief

def analyze_meeting_context_brief(context: MeetingContext) -> str:
    """Generate brief context using Gemini"""
    # Use existing Gemini analysis but with brief-focused prompt
    prompt = f"""
    Analyze this meeting and provide a BRIEF 1-2 sentence context summary:
    Meeting: {context.event.summary}
    Description: {context.event.description}
    Attendees: {[att.email for att in context.event.attendees]}

    Focus on: What is this meeting about and why is it important?
    Keep it concise and actionable.
    """
    # Implementation using existing Gemini integration
    pass

def extract_key_challenge(context: MeetingContext) -> str:
    """Extract key challenge or discussion point"""
    # AI analysis to identify main challenge/blocker
    pass

def generate_talking_points(context: MeetingContext, limit: int = 3) -> str:
    """Generate max 3 talking points as 1-liners"""
    # AI generation of concise talking points
    pass
```

#### **Step 2.2: Meeting Details Tool**
**File**: `tools/meeting_details_tool.py`

```python
def generate_meeting_details(tool_context: ToolContext) -> str:
    """
    Generate comprehensive meeting analysis with full details.
    Handles: details, deep dive, full analysis, insights queries
    """
    # Use the existing comprehensive format from current prepare_meeting_brief
    # This preserves all current functionality but only triggers for detail requests
    pass
```

#### **Step 2.3: Meeting Search Tools**
**File**: `tools/meeting_search_tools.py`

```python
def search_meeting_by_time(tool_context: ToolContext) -> str:
    """
    Find and brief specific meeting by time.
    Handles: "meeting at 2pm", "10:30 meeting today", etc.
    """
    user_query = tool_context.request.get("query", "")
    time_query = extract_time_from_query(user_query)

    # Parse time and find matching meeting
    creds = get_user_credentials(tool_context)
    meeting = find_meeting_by_time(creds, time_query)

    if not meeting:
        return "No meeting found at the specified time."

    # Return brief or details based on query context
    return generate_appropriate_response(meeting, user_query)

def search_meeting_by_subject(tool_context: ToolContext) -> str:
    """
    Find and brief specific meeting by subject/title.
    Handles: 'meeting with subject: "title"' queries
    """
    user_query = tool_context.request.get("query", "")
    subject_query = extract_subject_from_query(user_query)

    # Search by subject and find matching meeting
    creds = get_user_credentials(tool_context)
    meeting = find_meeting_by_subject(creds, subject_query)

    if not meeting:
        return f"No meeting found with subject: {subject_query}"

    # Return brief or details based on query context
    return generate_appropriate_response(meeting, user_query)

def extract_time_from_query(query: str) -> str:
    """Extract time expression from user query"""
    # Implementation to parse various time formats
    pass

def extract_subject_from_query(query: str) -> str:
    """Extract subject/title from user query"""
    # Implementation to parse subject patterns
    pass
```

#### **Step 2.4: Google Docs Export Tool**
**File**: `tools/export_tool.py`

```python
def export_to_google_docs(tool_context: ToolContext) -> str:
    """
    Export previous agent response to Google Docs.
    Creates a new document in user's Google Drive.
    """
    try:
        # Get the content to export (from previous response)
        content_to_export = tool_context.request.get("content", "")
        if not content_to_export:
            return "No content available to export."

        # Get credentials
        creds = get_user_credentials(tool_context)

        # Create Google Docs service
        from googleapiclient.discovery import build
        docs_service = build('docs', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        # Create new document
        document = docs_service.documents().create(body={
            'title': f'Meeting Brief - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        }).execute()

        doc_id = document['documentId']

        # Insert content
        requests = [{
            'insertText': {
                'location': {'index': 1},
                'text': content_to_export
            }
        }]

        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        # Get document URL
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        return f"✅ Successfully exported to Google Docs: [View Document]({doc_url})"

    except Exception as e:
        return f"Error exporting to Google Docs: {str(e)}"
```

### **Phase 3: Agent Implementation**

#### **Step 3.1: Query Router Agent**
**File**: `agents/query_router_agent.py`

```python
from google.adk.agents import LlmAgent
from tools.query_classifier import QueryClassifier, QueryIntent

def create_query_router() -> LlmAgent:
    return LlmAgent(
        name="query_router",
        model="gemini-2.5-flash",
        description="Routes user queries to appropriate specialist agents",
        instruction="""
        You are a query router that analyzes user requests about meetings and calendar events.

        Your job is to:
        1. Understand what the user is asking for
        2. Route them to the appropriate specialist agent
        3. Provide clear instructions to the specialist

        Routing Rules:
        - "brief", "summary", "quick", "overview" → meeting_brief_agent
        - "details", "deep dive", "full analysis", "insights" → meeting_details_agent
        - Time mentions ("2pm", "10:30", "at X time") → meeting_search_agent (time)
        - "subject:", "titled", "meeting with subject" → meeting_search_agent (subject)
        - "export", "save", "google doc" → export_agent

        Always include the original user query when routing.
        """,
        tools=[],  # Router doesn't need tools, just routes to other agents
    )
```

#### **Step 3.2: Specialized Agents**
```python
# Meeting Brief Agent
meeting_brief_agent = LlmAgent(
    name="meeting_brief_agent",
    model="gemini-2.5-flash",
    description="Generates concise meeting briefs and summaries",
    instruction="""
    You generate concise meeting briefs using the specified format:
    📅**Meeting:** "Title" **Time:** YYYY-MM-DD, HH:MM - HH:MM
    * Attendees, Location, Meeting Link
    📚**Context:** Brief description
    💬**Key Challenge:** Key discussion points
    📎**Related Documents:** Top 3 docs
    📋**Potential Talking Points:** Max 3 suggestions

    Keep responses concise and actionable.
    """,
    tools=[generate_meeting_brief],
)

# Meeting Details Agent
meeting_details_agent = LlmAgent(
    name="meeting_details_agent",
    model="gemini-2.5-flash",
    description="Provides comprehensive meeting analysis and insights",
    instruction="""
    You provide detailed, comprehensive meeting analysis including:
    - Full meeting context and background
    - Complete document analysis
    - Historical meeting patterns
    - Detailed AI insights
    - Comprehensive attendee information
    - Full slack/chat context

    Use the existing detailed format for thorough analysis.
    """,
    tools=[generate_meeting_details],
)

# Meeting Search Agent
meeting_search_agent = LlmAgent(
    name="meeting_search_agent",
    model="gemini-2.5-flash",
    description="Searches for meetings by time or subject",
    instruction="""
    You search for specific meetings based on:
    - Time queries: "meeting at 2pm", "10:30 meeting today"
    - Subject queries: "meeting with subject: X"

    After finding the meeting, provide appropriate brief or details.
    """,
    tools=[search_meeting_by_time, search_meeting_by_subject],
)

# Export Agent
export_agent = LlmAgent(
    name="export_agent",
    model="gemini-2.5-flash",
    description="Exports responses to Google Docs",
    instruction="""
    You export meeting briefs and analysis to Google Docs.
    Create properly formatted documents with timestamps.
    """,
    tools=[export_to_google_docs],
)
```

#### **Step 3.3: Updated Root Agent**
```python
root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="root_agent",
    instruction="""
    You are an intelligent meeting preparation assistant that routes queries to specialist agents.

    Your workflow:
    1. Analyze the user's request
    2. Determine which specialist agent should handle it
    3. Route appropriately and coordinate responses

    Specialist agents available:
    - meeting_brief_agent: For summaries, briefs, quick overviews
    - meeting_details_agent: For detailed analysis, deep dives, insights
    - meeting_search_agent: For time/subject-based meeting searches
    - export_agent: For saving responses to Google Docs

    Always ensure users get the most appropriate response format for their needs.
    """,
    sub_agents=[
        meeting_brief_agent,
        meeting_details_agent,
        meeting_search_agent,
        export_agent
    ],
)
```

### **Phase 4: Migration Strategy**

#### **Step 4.1: Backward Compatibility**
- Keep existing function signatures
- Maintain all current environment variables
- Preserve existing OAuth scopes
- Ensure all current features work unchanged

#### **Step 4.2: Deployment Steps**
1. **Create new tool files** without modifying existing agent
2. **Test tools individually** in isolation
3. **Create new agent file** alongside existing one
4. **Gradual migration** of functionality
5. **Switch deployment** once validated

#### **Step 4.3: Testing Plan**
```bash
# Test individual tools
python -m pytest tests/test_meeting_brief_tool.py
python -m pytest tests/test_meeting_search_tools.py
python -m pytest tests/test_export_tool.py

# Test agent integration
python -m pytest tests/test_multi_agent_integration.py

# Deploy to staging
python agents/meeting_prep_agent_multi.py

# Validate in AgentSpace
# Switch production deployment
```

### **Phase 5: Enhanced Features**

#### **Step 5.1: Advanced Query Understanding**
- Natural language time parsing
- Fuzzy subject matching
- Intent confidence scoring
- Multi-intent handling

#### **Step 5.2: Response Personalization**
- User preference learning
- Format customization
- Historical context awareness
- Proactive suggestions

#### **Step 5.3: Export Enhancements**
- Multiple export formats (PDF, Word, Slides)
- Template customization
- Batch export capabilities
- Integration with other tools

## 📁 **File Structure After Revamp**

```
google-calendar-agent/
├── agents/
│   ├── meeting_prep_agent.py              # Current (preserved)
│   ├── meeting_prep_agent_multi.py        # New multi-agent version
│   └── query_router_agent.py              # New router logic
├── tools/
│   ├── meeting_core.py                    # Shared core functions
│   ├── query_classifier.py               # Intent classification
│   ├── meeting_brief_tool.py              # Brief generation
│   ├── meeting_details_tool.py            # Detailed analysis
│   ├── meeting_search_tools.py            # Search functionality
│   └── export_tool.py                     # Google Docs export
├── tests/
│   ├── test_query_classifier.py           # Classification tests
│   ├── test_meeting_brief_tool.py         # Brief tool tests
│   ├── test_meeting_search_tools.py       # Search tests
│   ├── test_export_tool.py                # Export tests
│   └── test_multi_agent_integration.py    # Integration tests
└── MultiAgent_Revamp_Plan.md              # This document
```

## 🎯 **Success Metrics**

### **Functional Requirements**
- ✅ Correctly routes brief vs detailed queries
- ✅ Searches meetings by time with 90%+ accuracy
- ✅ Searches meetings by subject with fuzzy matching
- ✅ Exports to Google Docs successfully
- ✅ Maintains all existing functionality
- ✅ Preserves response time < 15 seconds

### **Quality Requirements**
- ✅ Clean, modular, maintainable code
- ✅ Comprehensive test coverage (>80%)
- ✅ Proper error handling and fallbacks
- ✅ Documentation and examples
- ✅ Backward compatibility

### **User Experience Requirements**
- ✅ Intuitive query understanding
- ✅ Appropriate response formats
- ✅ Clear error messages
- ✅ Consistent behavior
- ✅ Fast response times

## 🚨 **Risk Mitigation**

### **Technical Risks**
- **Agent coordination complexity**: Start with simple routing, add sophistication gradually
- **Performance degradation**: Profile and optimize, maintain existing performance benchmarks
- **Integration failures**: Comprehensive testing at each phase

### **User Impact Risks**
- **Breaking changes**: Maintain full backward compatibility
- **Feature regression**: Extensive testing of existing functionality
- **User confusion**: Clear documentation and gradual rollout

### **Deployment Risks**
- **Production failures**: Blue-green deployment strategy
- **Rollback capability**: Keep existing agent as fallback
- **Monitoring**: Enhanced logging and alerting

## ⏱️ **Timeline Estimate**

- **Phase 1 (Infrastructure)**: 2-3 days
- **Phase 2 (Tools)**: 3-4 days
- **Phase 3 (Agents)**: 2-3 days
- **Phase 4 (Migration)**: 2-3 days
- **Phase 5 (Enhancement)**: 3-5 days

**Total Estimated Time**: 12-18 days

## 📈 **Future Enhancements**

1. **Machine Learning Integration**: User behavior learning
2. **Advanced Analytics**: Meeting pattern analysis
3. **Multi-modal Support**: Voice queries, image analysis
4. **Third-party Integrations**: Teams, Zoom, Outlook
5. **Collaborative Features**: Shared briefs, team insights
6. **Mobile Optimization**: Responsive formats
7. **API Endpoints**: External system integration

---

**Document Version**: 1.0
**Last Updated**: September 24, 2025
**Author**: Claude Code Agent Revamp Team
**Status**: Planning Phase Complete - Ready for Implementation