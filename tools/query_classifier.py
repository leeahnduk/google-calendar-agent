"""
Query classification system for the multi-agent meeting preparation system.

This module analyzes user queries to determine intent and route them to
the appropriate specialist agents.
"""

from enum import Enum
from typing import Dict, Any, Optional
import re


class QueryIntent(Enum):
    """Possible user query intents"""
    MEETING_BRIEF = "brief"
    MEETING_DETAILS = "details"
    SEARCH_BY_TIME = "search_time"
    SEARCH_BY_SUBJECT = "search_subject"
    EXPORT_REQUEST = "export"
    GENERAL_CALENDAR = "general"


class QueryClassifier:
    """Classifies user queries to determine the appropriate response type"""

    def __init__(self):
        # Keywords that indicate the user wants a brief/summary
        self.brief_keywords = [
            "brief", "summary", "summarize", "quick", "overview",
            "key points", "outline", "short", "concise", "highlights", "snapshot",
            "information", "info", "recap", "condensed", "abstract", "fast",
            "a glance", "rapid", "instant", "takeaways"
        ]

        # Keywords that indicate the user wants detailed analysis
        self.details_keywords = [
            "details", "deep dive", "full analysis", "insights",
            "comprehensive", "in-depth", "analyze", "breakdown",
            "thorough", "complete", "detailed", "extensive",
            "elaborate", "explain", "research", "full", "expanded"
        ]

        # Time patterns for meeting search (more specific)
        self.time_patterns = [
            r"\d{1,2}:\d{2}\s*p\.?m\.?",      # 2:30p.m, 2:30 p.m, 2:30pm
            r"\d{1,2}:\d{2}\s*a\.?m\.?",      # 2:30a.m, 2:30 a.m, 2:30am
            r"\d{1,2}\s*p\.?m\.?",            # 2p.m, 2 p.m, 2pm
            r"\d{1,2}\s*a\.?m\.?",            # 2a.m, 2 a.m, 2am
            r"\d{1,2}:\d{2}\s*(am|pm|AM|PM)", # 2:30 PM
            r"\d{1,2}\s*(am|pm|AM|PM)",       # 2 PM
            r"\d{1,2}:\d{2}\s*[A-Z]{3}",      # 19:00 SGT
            r"at\s+\d{1,2}:\d{2}",            # at 14:30
            r"meeting\s+at\s+\d{1,2}",        # meeting at 2
            r"\b\d{1,2}:\d{2}\b",             # 14:30 (24-hour) - more specific
            r"at\s+\d{1,2}\s*(am|pm|AM|PM)",  # at 2pm
            r"this\s+morning", r"this\s+afternoon", r"this\s+evening",
            r"later\s+today", r"in\s+\d+\s+minutes?", r"in\s+\d+\s+hours?"
        ]

        # Separate patterns for relative time that need more context
        self.relative_time_patterns = [
            r"today", r"tomorrow", r"yesterday"  # These alone don't indicate time search
        ]

        # Subject patterns for meeting search
        self.subject_patterns = [
            r"subject[:\s]+[\"'](.+?)[\"']",   # subject: "title"
            r"meeting\s+with\s+subject",       # meeting with subject
            r"titled\s+[\"'](.+?)[\"']",       # titled "title"
            r"meeting\s+titled",               # meeting titled
            r"called\s+[\"'](.+?)[\"']",       # called "title"
            r"named\s+[\"'](.+?)[\"']"         # named "title"
        ]

        # Export-related keywords
        self.export_keywords = [
            "export", "save", "google doc", "document",
            "save to drive", "create document", "download",
            "pdf", "create file", "save as", "export to"
        ]

        # Calendar-related general queries
        self.calendar_keywords = [
            "schedule", "calendar", "meetings", "appointments",
            "agenda", "what do i have", "how many meetings",
            "free time", "busy", "conflicts", "availability"
        ]

    def classify_query(self, query: str) -> Dict[str, Any]:
        """
        Classify a user query and return intent with confidence and metadata.

        Args:
            query: The user's query string

        Returns:
            Dictionary containing:
            - intent: QueryIntent enum value
            - confidence: Float between 0.0 and 1.0
            - metadata: Additional extracted information
            - original_query: The original query string
        """
        if not query:
            return {
                "intent": QueryIntent.GENERAL_CALENDAR,
                "confidence": 0.5,
                "metadata": {},
                "original_query": query
            }

        query_lower = query.lower().strip()

        # Check for export intent first (highest priority)
        if self._has_export_intent(query_lower):
            return {
                "intent": QueryIntent.EXPORT_REQUEST,
                "confidence": 0.9,
                "metadata": {"export_type": self._extract_export_type(query_lower)},
                "original_query": query
            }

        # Check for time-based search
        time_info = self._extract_time_info(query_lower)
        if time_info:
            # Special handling for relative times - need more context
            if time_info["time_expression"] in ["today", "tomorrow", "yesterday"]:
                # Only treat as time search if there are other indicators
                if any(word in query_lower for word in ["meeting", "at", "schedule", "calendar"]):
                    return {
                        "intent": QueryIntent.SEARCH_BY_TIME,
                        "confidence": 0.75,
                        "metadata": {
                            "time_query": time_info["time_expression"],
                            "parsed_time": time_info.get("parsed_time")
                        },
                        "original_query": query
                    }
            else:
                # Specific time mentioned
                return {
                    "intent": QueryIntent.SEARCH_BY_TIME,
                    "confidence": 0.85,
                    "metadata": {
                        "time_query": time_info["time_expression"],
                        "parsed_time": time_info.get("parsed_time")
                    },
                    "original_query": query
                }

        # Check for subject-based search
        subject_info = self._extract_subject_info(query)
        if subject_info:
            return {
                "intent": QueryIntent.SEARCH_BY_SUBJECT,
                "confidence": 0.85,
                "metadata": {
                    "subject_query": subject_info["subject"],
                    "search_type": subject_info.get("search_type", "contains")
                },
                "original_query": query
            }

        # Analyze brief vs details intent
        brief_score = self._calculate_keyword_score(query_lower, self.brief_keywords)
        details_score = self._calculate_keyword_score(query_lower, self.details_keywords)

        # Check for specific brief/details indicators
        if details_score > brief_score and details_score > 0:
            return {
                "intent": QueryIntent.MEETING_DETAILS,
                "confidence": min(0.9, 0.6 + (details_score * 0.1)),
                "metadata": {"analysis_type": "comprehensive"},
                "original_query": query
            }
        elif brief_score > 0:
            return {
                "intent": QueryIntent.MEETING_BRIEF,
                "confidence": min(0.9, 0.6 + (brief_score * 0.1)),
                "metadata": {"analysis_type": "summary"},
                "original_query": query
            }

        # Check for general calendar queries
        calendar_score = self._calculate_keyword_score(query_lower, self.calendar_keywords)
        if calendar_score > 0:
            return {
                "intent": QueryIntent.GENERAL_CALENDAR,
                "confidence": min(0.8, 0.5 + (calendar_score * 0.1)),
                "metadata": {"query_type": "calendar_overview"},
                "original_query": query
            }

        # Default to brief for ambiguous queries
        return {
            "intent": QueryIntent.MEETING_BRIEF,
            "confidence": 0.6,
            "metadata": {"analysis_type": "default"},
            "original_query": query
        }

    def _has_export_intent(self, query_lower: str) -> bool:
        """Check if query has export intent"""
        return any(keyword in query_lower for keyword in self.export_keywords)

    def _extract_export_type(self, query_lower: str) -> str:
        """Extract the type of export requested"""
        if "pdf" in query_lower:
            return "pdf"
        elif "google doc" in query_lower or "document" in query_lower:
            return "google_docs"
        else:
            return "google_docs"  # Default

    def _extract_time_info(self, query_lower: str) -> Optional[Dict[str, Any]]:
        """Extract time information from query"""
        # First check specific time patterns
        for pattern in self.time_patterns:
            match = re.search(pattern, query_lower)
            if match:
                time_expression = match.group() if hasattr(match, 'group') else pattern
                return {
                    "time_expression": time_expression,
                    "pattern_matched": pattern,
                    "full_match": match.group() if hasattr(match, 'group') else None
                }

        # Then check relative time patterns (lower priority)
        for pattern in self.relative_time_patterns:
            if pattern in query_lower:
                return {
                    "time_expression": pattern,
                    "pattern_matched": pattern,
                    "full_match": pattern
                }

        return None

    def _extract_subject_info(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract subject/title information from query"""
        query_lower = query.lower()

        # Check for explicit subject patterns
        for pattern in self.subject_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if match.groups():
                    # Extract the captured group (the subject)
                    subject = match.group(1)
                else:
                    # Pattern matched but no capture group, look for subject in context
                    subject = None

                return {
                    "subject": subject,
                    "search_type": "exact",
                    "pattern_matched": pattern
                }

        # Check for implicit subject mentions
        if "subject" in query_lower and not any(keyword in query_lower for keyword in ["no subject", "without subject"]):
            # Try to extract quoted strings as potential subjects
            quoted_matches = re.findall(r'["\']([^"\']+)["\']', query)
            if quoted_matches:
                return {
                    "subject": quoted_matches[0],
                    "search_type": "contains",
                    "pattern_matched": "quoted_string"
                }

            # Look for subject after "subject" keyword
            subject_match = re.search(r'subject[:\s]+([^,\.\?!]+)', query_lower)
            if subject_match:
                return {
                    "subject": subject_match.group(1).strip(),
                    "search_type": "contains",
                    "pattern_matched": "subject_keyword"
                }

        return None

    def _calculate_keyword_score(self, query: str, keywords: list) -> int:
        """Calculate a score based on keyword matches"""
        score = 0
        for keyword in keywords:
            if keyword in query:
                # Give higher score for exact word matches
                if re.search(r'\b' + re.escape(keyword) + r'\b', query):
                    score += 2
                else:
                    score += 1
        return score

    def get_confidence_description(self, confidence: float) -> str:
        """Get a human-readable description of confidence level"""
        if confidence >= 0.9:
            return "Very High"
        elif confidence >= 0.8:
            return "High"
        elif confidence >= 0.7:
            return "Medium"
        elif confidence >= 0.6:
            return "Low"
        else:
            return "Very Low"

    def should_route_to_specialist(self, classification: Dict[str, Any]) -> bool:
        """Determine if query should be routed to a specialist agent"""
        return (
            classification["confidence"] >= 0.7 and
            classification["intent"] in [
                QueryIntent.SEARCH_BY_TIME,
                QueryIntent.SEARCH_BY_SUBJECT,
                QueryIntent.EXPORT_REQUEST
            ]
        )


def classify_user_query(query: str) -> Dict[str, Any]:
    """
    Convenience function to classify a user query.

    Args:
        query: The user's query string

    Returns:
        Classification result dictionary
    """
    classifier = QueryClassifier()
    return classifier.classify_query(query)


# Example usage and test cases
if __name__ == "__main__":
    # Test cases for different query types
    test_queries = [
        "Give me a brief for my next meeting",
        "I need detailed analysis of tomorrow's presentation",
        "Meeting at 2pm today",
        "Find meeting with subject: 'Product Review'",
        "Export this to Google Docs",
        "What meetings do I have today?",
        "Show me comprehensive insights for the quarterly review",
        "Quick summary of my 10:30 meeting",
        "Save the meeting brief as a PDF",
        "Meeting titled 'Sprint Planning' next week"
    ]

    classifier = QueryClassifier()

    for query in test_queries:
        result = classifier.classify_query(query)
        print(f"Query: '{query}'")
        print(f"Intent: {result['intent'].value}")
        print(f"Confidence: {result['confidence']:.2f} ({classifier.get_confidence_description(result['confidence'])})")
        print(f"Metadata: {result['metadata']}")
        print("-" * 50)