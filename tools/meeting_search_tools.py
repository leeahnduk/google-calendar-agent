"""
Meeting Search Tools - Search for specific meetings by time or subject.
"""

from google.adk.tools.tool_context import ToolContext


def search_meeting_tool(user_request: str = "", tool_context: ToolContext = None):
    """
    Unified search tool that handles both time and subject queries.

    Args:
        user_request: The user's request/query for meeting search
        tool_context: Tool context containing authentication state
    """
    print("DEBUG: ========== MEETING SEARCH TOOL STARTED ==========")
    print(f"DEBUG: Received user_request parameter: '{user_request}'")
    # Enhanced implementation with time parsing
    from datetime import datetime, timedelta, timezone
    from dataclasses import dataclass
    from typing import List, Optional, Dict, Any
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    import re

    @dataclass
    class EventAttendee:
        email: str
        response_status: Optional[str] = None

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

    def _to_iso(dt_str: str) -> str:
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return dt_str

    def _parse_time_request(user_query: str) -> Optional[datetime]:
        """Parse user query to extract specific time request"""
        print(f"DEBUG: _parse_time_request called with: '{user_query}'")
        query = user_query.lower()
        print(f"DEBUG: Lowercased query: '{query}'")

        # Patterns to detect time, with and without 'at'
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)', # 5:00p.m, 5:00 p.m.
            r'(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)',       # 5p.m, 5 pm
            r'(\d{1,2}):(\d{2})(?!\s*[ap]\.?m\.?)',    # 17:00, 15:30 (24-hour format)
        ]

        target_time = None
        for i, pattern in enumerate(time_patterns):
            print(f"DEBUG: Trying pattern {i+1}: '{pattern}'")
            # Also check for 'at 5pm' style
            for j, prefix in enumerate([r'at\s+', '']):
                full_pattern = prefix + pattern
                print(f"DEBUG: Full pattern {i+1}.{j+1}: '{full_pattern}'")
                match = re.search(full_pattern, query)
                if match:
                    print(f"DEBUG: MATCH FOUND with pattern '{full_pattern}': {match.groups()}")
                    groups = match.groups()
                    hour = int(groups[0])

                    if ':' in pattern:
                        minute = int(groups[1])
                        if len(groups) > 2 and groups[2]:  # Has AM/PM
                            ampm_raw = groups[2]
                            # Normalize am/pm - be more flexible with parsing
                            ampm = 'pm' if 'p' in ampm_raw else 'am'
                            # Convert to 24-hour format
                            if ampm == 'pm' and hour != 12:
                                hour += 12
                            elif ampm == 'am' and hour == 12:
                                hour = 0
                        # else: already 24-hour format, no conversion needed
                    else:
                        minute = 0
                        ampm_raw = groups[1]
                        # Normalize am/pm - be more flexible with parsing
                        ampm = 'pm' if 'p' in ampm_raw else 'am'
                        # Convert to 24-hour format
                        if ampm == 'pm' and hour != 12:
                            hour += 12
                        elif ampm == 'am' and hour == 12:
                            hour = 0

                    ampm_display = ampm if 'ampm_raw' in locals() else '24h'
                    print(f"DEBUG: Parsed time - {hour}:{minute:02d} ({ampm_display})")

                    # Create target time for today - assume Singapore timezone (UTC+8)
                    from datetime import datetime, timedelta, timezone

                    # Get "today" in Singapore timezone, not server timezone
                    singapore_tz = timezone(timedelta(hours=8))
                    now_sg = datetime.now(singapore_tz)
                    today_sg = now_sg.date()

                    # Create time in Singapore timezone (UTC+8)
                    target_time = datetime.combine(today_sg, datetime.min.time().replace(hour=hour, minute=minute))
                    target_time = target_time.replace(tzinfo=singapore_tz)

                    print(f"DEBUG: Target time created: {target_time}")

                    # Found a match, exit loops
                    break
            if target_time:
                break

        if not target_time:
            print("DEBUG: No time pattern matched in query")

        return target_time

    try:
        # Get auth_id from environment or use default
        import os
        auth_id = os.getenv("AUTH_ID", "meeting-prep-multi")

        # Get OAuth credentials from tool context
        if not hasattr(tool_context, "state"):
            return {"panel_markdown": "Error: No authentication state available."}

        token_key = f"temp:{auth_id}"
        try:
            if hasattr(tool_context.state, 'get'):
                access_token = tool_context.state.get(token_key)
            else:
                access_token = getattr(tool_context.state, token_key, None)
        except Exception as e:
            print(f"DEBUG: Error accessing access token: {e}")
            return {"panel_markdown": f"Error: Unable to access authentication state: {str(e)}"}

        if not access_token:
            return {"panel_markdown": "Error: No access token available. Please authenticate first."}

        creds = Credentials(token=access_token)
        calendar_service = build("calendar", "v3", credentials=creds)

        # Parse user query to determine if they want a specific meeting
        print(f"DEBUG: tool_context attributes: {dir(tool_context)}")
        print(f"DEBUG: tool_context.state: {getattr(tool_context, 'state', 'No state')}")

        # Get user query from parameter first, then fallback to tool context state
        user_query = user_request
        print(f"DEBUG: ==================== QUERY ANALYSIS ====================")
        print(f"DEBUG: Received user_request parameter: '{user_request}'")
        print(f"DEBUG: user_request type: {type(user_request)}")
        print(f"DEBUG: user_request length: {len(user_request) if user_request else 'None'}")

        if not user_query and tool_context and hasattr(tool_context, 'state'):
            try:
                if hasattr(tool_context.state, 'get'):
                    if tool_context.state.get('_user_query'):
                        user_query = tool_context.state.get('_user_query')
                        print(f"DEBUG: Found user_query via tool_context.state.get('_user_query'): '{user_query}'")
                    elif tool_context.state.get('user_input'):
                        user_query = tool_context.state.get('user_input')
                        print(f"DEBUG: Found user_query via tool_context.state.get('user_input'): '{user_query}'")
                    else:
                        print(f"DEBUG: No user_query found in tool_context state")
                else:
                    # Fallback to direct attribute access
                    user_query = getattr(tool_context.state, '_user_query', None) or getattr(tool_context.state, 'user_input', None)
                    if user_query:
                        print(f"DEBUG: Found user_query via getattr: '{user_query}'")
                    else:
                        print(f"DEBUG: No user_query found in tool_context state via getattr")
            except Exception as e:
                print(f"DEBUG: Error accessing user_query from state: {e}")
        elif not user_query:
            print(f"DEBUG: No tool_context or state available")

        print(f"DEBUG: Final user_query: '{user_query}'")

        # Get events from today onwards - including past events from today
        now = datetime.now(timezone.utc)
        # Start from beginning of today in Singapore timezone, then convert to UTC
        singapore_tz = timezone(timedelta(hours=8))
        today_sg = datetime.now(singapore_tz).date()
        start_of_today_sg = datetime.combine(today_sg, datetime.min.time()).replace(tzinfo=singapore_tz)
        start_of_today_utc = start_of_today_sg.astimezone(timezone.utc)

        time_min = start_of_today_utc.isoformat()
        time_max = (now + timedelta(days=7)).isoformat()

        print(f"DEBUG: Fetching events from {time_min} to {time_max}")

        events_result = (
            calendar_service.events()
            .list(calendarId="primary", timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime", maxResults=50)
            .execute()
        )
        items = events_result.get("items", [])

        print(f"DEBUG: Found {len(items)} total events")
        for i, event in enumerate(items):
            event_title = event.get("summary", "")
            start_time = event.get("start", {}).get("dateTime", "")
            print(f"DEBUG: Event {i+1}: '{event_title}' at {start_time}")
        if not items:
            return {"panel_markdown": "## 📅 Calendar Overview\\n\\nNo upcoming meetings found in your calendar for the next 7 days."}

        # Parse user query for specific time request
        target_time = _parse_time_request(user_query)

        # Check for numbered meeting selection ONLY if no time was found
        meeting_number = None
        if not target_time:
            number_patterns = [
                r'brief for meeting (\d+)',
                r'meeting (\d+)',
                r'number (\d+)',
                r'^(\d+)$'  # Only standalone numbers, not part of time
            ]

            for pattern in number_patterns:
                match = re.search(pattern, user_query, re.IGNORECASE)
                if match:
                    meeting_number = int(match.group(1))
                    break

        # Check for subject/title search patterns
        subject_patterns = [
            r'meeting with subject[:\s]+"([^"]+)"',  # "meeting with subject: Title"
            r'meeting with title[:\s]+"([^"]+)"',
            r'meeting titled[:\s]+"([^"]+)"',
            r'title[:\s]+"([^"]+)"',
            r'subject[:\s]+"([^"]+)"',              # "subject: Title"
            r'starting with[:\s]+"([^"]+)"',         # "starting with: Innovatech"
            r'meeting starting with[:\s]+"([^"]+)"',
            r'"([^"]+)"'  # Any quoted text
        ]

        subject_query = None
        print(f"DEBUG: Testing subject patterns against user_query: '{user_query}'")
        for i, pattern in enumerate(subject_patterns):
            print(f"DEBUG: Testing pattern {i+1}: '{pattern}'")
            match = re.search(pattern, user_query, re.IGNORECASE)
            if match:
                subject_query = match.group(1).lower()
                print(f"DEBUG: SUBJECT PATTERN MATCH! Pattern {i+1} extracted: '{subject_query}'")
                break
            else:
                print(f"DEBUG: Pattern {i+1} no match")

        if not subject_query:
            print("DEBUG: No subject pattern matched - checking if this might be a subject query anyway")
            # Fallback: look for any quoted text in the query
            quoted_match = re.search(r'"([^"]+)"', user_query)
            if quoted_match:
                subject_query = quoted_match.group(1).lower()
                print(f"DEBUG: FALLBACK: Found quoted text: '{subject_query}'")

        target_event_item = None
        selection_note = ""

        # First try numbered meeting selection using saved meeting index
        if meeting_number:
            print(f"DEBUG: Looking for meeting number {meeting_number}")

            # Try to get saved meeting index from meetings_today_agent output
            saved_meeting_index = None
            print(f"DEBUG: tool_context has state: {hasattr(tool_context, 'state')}")
            if hasattr(tool_context, 'state'):
                try:
                    # Try to access state keys safely
                    if hasattr(tool_context.state, 'keys'):
                        print(f"DEBUG: tool_context.state keys: {list(tool_context.state.keys())}")
                    else:
                        print(f"DEBUG: tool_context.state type: {type(tool_context.state)}")
                except Exception as e:
                    print(f"DEBUG: Error accessing state keys: {e}")

                # Try to get meeting_index from state
                try:
                    if hasattr(tool_context.state, 'get'):
                        saved_meeting_index = tool_context.state.get('meeting_index')
                    else:
                        # Fallback to direct access
                        saved_meeting_index = getattr(tool_context.state, 'meeting_index', None)

                    if saved_meeting_index:
                        print(f"DEBUG: Found saved meeting index with {len(saved_meeting_index)} meetings")
                        print(f"DEBUG: First meeting in index: {saved_meeting_index[0] if saved_meeting_index else 'None'}")
                    else:
                        print("DEBUG: 'meeting_index' not found in tool_context.state")
                except Exception as e:
                    print(f"DEBUG: Error accessing meeting_index: {e}")
                    saved_meeting_index = None
            else:
                print("DEBUG: tool_context has no state attribute")
                saved_meeting_index = None

            if saved_meeting_index:
                # Use the saved meeting index
                selected_meeting_data = None
                for meeting_data in saved_meeting_index:
                    if meeting_data.get('number') == meeting_number:
                        selected_meeting_data = meeting_data
                        break

                if selected_meeting_data:
                    # Find the corresponding event by ID
                    meeting_id = selected_meeting_data.get('id')
                    for event in items:
                        if event.get('id') == meeting_id:
                            target_event_item = event
                            status = selected_meeting_data.get('status', 'unknown')
                            status_emoji = {"past": "✅", "current": "🟢", "upcoming": "🟡"}.get(status, "❓")
                            time_display = selected_meeting_data.get('start_time_display', 'Unknown time')
                            selection_note = f"\\n> 🔢 **Selected Meeting #{meeting_number}**: {status_emoji} {target_event_item.get('summary', '')} at {time_display}.\\n"
                            print(f"DEBUG: Found meeting #{meeting_number} from saved index: {target_event_item.get('summary', '')}")
                            break
                    else:
                        selection_note = f"\\n> ⚠️ **Note**: Meeting #{meeting_number} found in index but not in current calendar results. Showing first meeting instead.\\n"
                else:
                    selection_note = f"\\n> ⚠️ **Note**: Meeting #{meeting_number} not found in saved index. Showing first meeting instead.\\n"
            else:
                # Fallback: No saved index available, inform user to run meetings list first
                selection_note = f"\\n> 💡 **Tip**: To use numbered meeting selection, first ask 'how many meetings do I have left today?' to generate the meeting index.\\n"

        # Then try subject search (only if no numbered selection)
        elif subject_query:
            print(f"DEBUG: Searching for subject: '{subject_query}'")

            # Check if this is a "starting with" query
            is_starts_with = 'starting with' in user_query.lower()

            for event in items:
                event_title = event.get("summary", "")
                event_title_lower = event_title.lower()

                print(f"DEBUG: Checking event: '{event_title}' vs '{subject_query}'")

                match_found = False

                if is_starts_with:
                    # For "starting with" queries, check if title starts with the term
                    match_found = event_title_lower.startswith(subject_query)
                    print(f"DEBUG: Starts with check: {match_found}")
                else:
                    # Try multiple matching strategies
                    # 1. Exact match (case insensitive)
                    exact_match = event_title_lower == subject_query
                    # 2. Contains match
                    contains_match = subject_query in event_title_lower
                    # 3. Reverse contains (user query contains event title)
                    reverse_contains = event_title_lower in subject_query

                    match_found = exact_match or contains_match or reverse_contains
                    print(f"DEBUG: Match results - exact: {exact_match}, contains: {contains_match}, reverse: {reverse_contains}")

                if match_found:
                    target_event_item = event
                    match_type = "starting with" if is_starts_with else "matching"
                    selection_note = f"\\n> 💡 **Selected Meeting**: Found meeting with title {match_type} '{subject_query}'.\\n"
                    print(f"DEBUG: MATCH FOUND: {event_title}")
                    break

            if not target_event_item:
                selection_note = f"\\n> ⚠️ **Note**: Could not find a meeting with title containing '{subject_query}'. Showing the next upcoming meeting instead.\\n"

        # Then try time search if no subject found
        elif target_time:
            # Debug: print target time and events for troubleshooting
            singapore_tz = timezone(timedelta(hours=8))
            target_time_sg = target_time.astimezone(singapore_tz)
            print(f"DEBUG: Looking for meeting at TARGET TIME: {target_time_sg} (SGT)")
            print(f"DEBUG: Target hour: {target_time_sg.hour}, Target minute: {target_time_sg.minute}")

            # User requested a specific time, find matches
            exact_matches = []
            later_matches = []

            print(f"DEBUG: Checking {len(items)} events against target time...")
            for i, event in enumerate(items):
                start_str = event.get("start", {}).get("dateTime", "")
                if start_str:
                    try:
                        event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        event_time_sg = event_time.astimezone(singapore_tz)

                        print(f"DEBUG: Event #{i+1}: '{event.get('summary', '')}' at {event_time_sg} (SGT)")
                        print(f"DEBUG:   Event hour: {event_time_sg.hour}, Event minute: {event_time_sg.minute}")

                        # Check if event starts exactly at the requested time (within 30 minutes)
                        diff = abs((event_time_sg - target_time_sg).total_seconds())
                        print(f"DEBUG:   Time difference: {diff} seconds ({diff/60:.1f} minutes)")

                        # For better matching: exact time (within 30 minutes) or start of hour match
                        is_exact_match = diff <= 1800  # Within 30 minutes
                        hour_match = (event_time_sg.hour == target_time_sg.hour and
                                     abs(event_time_sg.minute - target_time_sg.minute) <= 30)

                        print(f"DEBUG:   is_exact_match: {is_exact_match}, hour_match: {hour_match}")

                        if is_exact_match or hour_match:
                            exact_matches.append({
                                'event': event,
                                'time': event_time_sg,
                                'diff': diff
                            })
                            print(f"DEBUG: ✅ EXACT MATCH: {event.get('summary', '')} (diff: {diff} seconds)")
                        elif event_time_sg > target_time_sg:  # Meeting is later in the day
                            later_matches.append({
                                'event': event,
                                'time': event_time_sg,
                                'diff': (event_time_sg - target_time_sg).total_seconds()
                            })
                            print(f"DEBUG: ⏰ LATER MATCH: {event.get('summary', '')} at {event_time_sg}")
                        else:
                            print(f"DEBUG: ❌ NO MATCH: {event.get('summary', '')} at {event_time_sg}")

                    except ValueError as e:
                        print(f"DEBUG: Error parsing time for event: {e}")
                        continue

            # Handle different scenarios
            if exact_matches:
                if len(exact_matches) == 1:
                    # Single exact match - use it
                    target_event_item = exact_matches[0]['event']
                    print(f"DEBUG: Using single exact match: {exact_matches[0]['event'].get('summary', '')}")
                else:
                    # Multiple exact matches - show selection
                    meeting_list = ""
                    for i, match in enumerate(exact_matches, 1):
                        event = match['event']
                        time_str = match['time'].strftime("%I:%M %p")
                        meeting_list += f"{i}. **{event.get('summary', '')}** - {time_str}\\n"

                    selection_note = f"\\n> 🕐 **Multiple meetings found at {target_time_sg.strftime('%I:%M %p')}**:\\n{meeting_list}\\nPlease specify which meeting you'd like a brief for by saying the number (e.g., 'brief for meeting 1').\\n"
                    target_event_item = exact_matches[0]['event']  # Default to first one

            elif later_matches:
                # No exact matches, but found meetings later in the day
                # Sort by time
                later_matches.sort(key=lambda x: x['time'])

                meeting_list = ""
                for i, match in enumerate(later_matches[:5], 1):  # Show max 5 later meetings
                    event = match['event']
                    time_str = match['time'].strftime("%I:%M %p")
                    meeting_list += f"{i}. **{event.get('summary', '')}** - {time_str}\\n"

                requested_time_str = target_time_sg.strftime("%I:%M %p")
                selection_note = f"\\n> ⏰ **No meeting found starting at {requested_time_str}**. Here are meetings later today:\\n{meeting_list}\\nPlease specify which meeting you'd like a brief for by saying the number (e.g., 'brief for meeting 1').\\n"
                target_event_item = later_matches[0]['event']  # Default to first later meeting

            else:
                # No matches found at all
                requested_time_str = target_time_sg.strftime("%I:%M %p")
                selection_note = f"\\n> ❌ **No meetings found at or after {requested_time_str}** in the next 7 days.\\n"

            # Update selection note only if we haven't set it already
            if target_event_item and not selection_note:
                start_str = target_event_item.get("start", {}).get("dateTime", "")
                event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

                # Convert to Singapore timezone for display
                from datetime import timedelta, timezone
                singapore_tz = timezone(timedelta(hours=8))
                event_time_sg = event_time.astimezone(singapore_tz)
                time_display = event_time_sg.strftime("%I:%M %p")

                selection_note = f"\\n> 💡 **Selected Meeting**: Found a meeting at {time_display} that matched your request.\\n"
            elif not target_event_item and not selection_note:
                selection_note = f"\\n> ⚠️ **Note**: Could not find a meeting around the specified time. Showing the next upcoming meeting instead.\\n"

        # If no specific time was requested or no match was found, default to the next meeting
        if not target_event_item:
            target_event_item = items[0]
            if not target_time and not subject_query: # Only add this note if no time/subject was ever requested
                 selection_note = "\\n> 💡 **Showing Next Meeting**: To see a brief for a different meeting, specify a time (e.g., 'brief for my 2pm meeting').\\n"

        # Get the selected event with full details
        event_id = target_event_item["id"]
        ev = calendar_service.events().get(calendarId="primary", eventId=event_id).execute()

        attendees_raw = ev.get("attendees", [])
        attendees = [
            EventAttendee(email=a.get("email", ""), response_status=a.get("responseStatus")) for a in attendees_raw
        ]
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or ""
        end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date") or ""

        event_context = EventContext(
            id=ev.get("id", ""),
            summary=ev.get("summary", ""),
            description=ev.get("description", ""),
            start_iso=_to_iso(start),
            end_iso=_to_iso(end),
            attendees=attendees,
            recurring_event_id=ev.get("recurringEventId"),
            html_link=ev.get("htmlLink"),
            location=ev.get("location"),
            attachments=ev.get("attachments", [])
        )

        # Format attendees
        attendees_list = ", ".join([att.email for att in event_context.attendees]) if event_context.attendees else "No attendees listed"

        # Format time in Singapore timezone for user display
        try:
            from datetime import timedelta, timezone
            singapore_tz = timezone(timedelta(hours=8))

            start_dt = datetime.fromisoformat(event_context.start_iso.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(event_context.end_iso.replace("Z", "+00:00"))

            # Convert to Singapore timezone
            start_dt_sg = start_dt.astimezone(singapore_tz)
            end_dt_sg = end_dt.astimezone(singapore_tz)

            start_time = start_dt_sg.strftime("%Y-%m-%d, %H:%M")
            end_time = end_dt_sg.strftime("%H:%M")
        except:
            start_time = event_context.start_iso
            end_time = event_context.end_iso

        # Store the found meeting in context for other tools to use
        print(f"DEBUG: Found target meeting: {event_context.summary}")
        print(f"DEBUG: User query: '{user_query}'")

        # Store the selected meeting details in tool context state for brief/details tools to use
        if hasattr(tool_context, 'state'):
            try:
                if hasattr(tool_context.state, '__setitem__'):
                    tool_context.state['_selected_meeting_id'] = event_context.id
                    tool_context.state['_selected_meeting_data'] = target_event_item
                else:
                    setattr(tool_context.state, '_selected_meeting_id', event_context.id)
                    setattr(tool_context.state, '_selected_meeting_data', target_event_item)
                print(f"DEBUG: Stored selected meeting ID: {event_context.id}")
            except Exception as e:
                print(f"DEBUG: Error storing meeting data: {e}")

        # Determine if user wants brief or details and call appropriate tool directly
        wants_details = any(keyword in user_query.lower() for keyword in [
            'details', 'detail', 'comprehensive', 'full analysis', 'in-depth',
            'thorough', 'deep dive', 'breakdown', 'elaborate', 'expanded'
        ])

        wants_brief = any(keyword in user_query.lower() for keyword in [
            'brief', 'summary', 'quick', 'overview', 'short', 'concise', 'condensed'
        ])

        print(f"DEBUG: User query: '{user_query}'")
        print(f"DEBUG: User wants details: {wants_details}")
        print(f"DEBUG: User wants brief: {wants_brief}")
        print(f"DEBUG: Selected meeting: {event_context.summary}")

        # Generate the appropriate format directly using EXACT formats from dedicated tools
        if wants_brief:
            print("DEBUG: Generating BRIEF format directly using exact meeting_brief_tool.py format")

            # Enhanced AI analysis for meeting context (same as brief tool)
            def _analyze_meeting_with_gemini(meeting_title: str, description: str, location: str, attendees: List[str]) -> Dict[str, str]:
                """Use Gemini to analyze meeting and provide enhanced context"""
                try:
                    import os
                    import vertexai
                    from vertexai.generative_models import GenerativeModel
                    import re

                    google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
                    google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

                    if google_cloud_project:
                        vertexai.init(project=google_cloud_project, location=google_cloud_location)
                        model = GenerativeModel("gemini-2.5-flash")

                        analysis_prompt = f"""
Analyze this upcoming meeting and provide a comprehensive brief:

Meeting Title: {meeting_title}
Description: {description or "No description provided"}
Location: {location or "No location specified"}
Attendees: {', '.join(attendees)}

Please provide:

1. **Context Analysis** (2-3 paragraphs): What is this meeting likely about? What's the business context and importance? What type of meeting is this (planning, review, decision-making, etc.)?

2. **Key Challenges** (1-2 sentences): What are the main challenges or decisions that need to be discussed based on the meeting title and context?

3. **Preparation Insights** (3-4 concise talking points): What should attendees prepare or focus on? What are the likely discussion topics and outcomes expected?

Format your response as:
CONTEXT: [context analysis]
CHALLENGES: [key challenges]
TALKING_POINTS: [numbered list of 3-4 points]

Be specific and actionable based on the meeting details provided."""

                        response = model.generate_content(analysis_prompt)
                        ai_response = response.text

                        # Parse the structured response
                        context_match = re.search(r'CONTEXT:\s*(.*?)(?=CHALLENGES:|$)', ai_response, re.DOTALL)
                        challenges_match = re.search(r'CHALLENGES:\s*(.*?)(?=TALKING_POINTS:|$)', ai_response, re.DOTALL)
                        talking_points_match = re.search(r'TALKING_POINTS:\s*(.*?)$', ai_response, re.DOTALL)

                        return {
                            "context": context_match.group(1).strip() if context_match else f"Meeting about {meeting_title}",
                            "challenges": challenges_match.group(1).strip() if challenges_match else "Review agenda and prepare talking points for effective discussion.",
                            "talking_points": talking_points_match.group(1).strip() if talking_points_match else "1. Review meeting objectives\n2. Prepare questions and concerns\n3. Share relevant updates"
                        }
                    else:
                        # Fallback when no AI available
                        return {
                            "context": f"Meeting about {meeting_title}" + (f": {description[:100]}..." if description else ""),
                            "challenges": "Review agenda and prepare talking points for effective discussion.",
                            "talking_points": "1. Review meeting objectives and expected outcomes\n2. Prepare any questions or concerns to discuss\n3. Share relevant updates from your work"
                        }
                except Exception as e:
                    print(f"AI analysis error: {e}")
                    return {
                        "context": f"Meeting about {meeting_title}" + (f": {description[:100]}..." if description else ""),
                        "challenges": "Review agenda and prepare talking points for effective discussion.",
                        "talking_points": "1. Review meeting objectives and expected outcomes\n2. Prepare any questions or concerns to discuss\n3. Share relevant updates from your work"
                    }

            # Get enhanced AI analysis
            attendee_emails = [att.email for att in event_context.attendees if att.email]
            ai_analysis = _analyze_meeting_with_gemini(
                event_context.summary,
                event_context.description or "",
                event_context.location or "",
                attendee_emails
            )

            key_context = ai_analysis["context"]
            key_challenge = ai_analysis["challenges"]
            talking_points = ai_analysis["talking_points"]

            # Search for related Drive documents (same as brief tool)
            def _search_drive_for_relevant_documents(drive_service, meeting_title: str, event_data: dict) -> str:
                """Search Google Drive for documents relevant to the meeting topic"""
                try:
                    # Extract attendee emails
                    attendees = event_data.get("attendees", [])
                    attendee_emails = [att.get("email", "") for att in attendees if att.get("email")]
                    meeting_description = event_data.get("description", "") or ""

                    # Extract keywords from meeting title and description
                    keywords = []
                    if meeting_title:
                        title_words = re.findall(r'\b\w+\b', meeting_title.lower())
                        keywords.extend([word for word in title_words if len(word) > 3])

                    if meeting_description:
                        desc_words = re.findall(r'\b\w+\b', meeting_description.lower())
                        keywords.extend([word for word in desc_words if len(word) > 3])

                    # Remove common words and duplicates
                    common_words = {'meeting', 'call', 'sync', 'review', 'discussion', 'update', 'status', 'weekly', 'daily', 'monthly', 'team', 'project', 'with', 'for', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from', 'by', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'}
                    keywords = list(set([kw for kw in keywords if kw not in common_words]))

                    # Search for related documents
                    related_docs = []
                    search_queries = []

                    # Add meeting title as search query
                    if meeting_title:
                        search_queries.append(f"name contains '{meeting_title}'")

                    # Add keyword-based searches
                    for keyword in keywords[:5]:  # Limit to top 5 keywords
                        search_queries.append(f"name contains '{keyword}'")
                        search_queries.append(f"fullText contains '{keyword}'")

                    # Execute searches
                    for query in search_queries[:10]:  # Limit total queries
                        try:
                            results = drive_service.files().list(
                                q=query,
                                pageSize=10,
                                fields="files(id,name,mimeType,webViewLink,modifiedTime,size,owners)",
                                orderBy="modifiedTime desc"
                            ).execute()

                            for file_data in results.get('files', []):
                                # Skip if we already have this file
                                if any(doc['id'] == file_data['id'] for doc in related_docs):
                                    continue

                                doc = {
                                    'id': file_data['id'],
                                    'name': file_data.get('name', 'Unknown'),
                                    'link': file_data.get('webViewLink', f"https://drive.google.com/file/d/{file_data['id']}/view"),
                                    'mime_type': file_data.get('mimeType', ''),
                                    'relevance_score': 0.0
                                }

                                # Calculate simple relevance score
                                score = 0.0
                                doc_name_lower = doc['name'].lower()
                                for keyword in keywords:
                                    if keyword in doc_name_lower:
                                        score += 2.0
                                    if keyword in meeting_title.lower():
                                        score += 1.0

                                doc['relevance_score'] = score
                                related_docs.append(doc)

                                # Limit total results
                                if len(related_docs) >= 15:
                                    break

                            if len(related_docs) >= 15:
                                break

                        except Exception:
                            continue  # Skip failed queries

                    # Sort by relevance and get top 2
                    related_docs.sort(key=lambda x: x['relevance_score'], reverse=True)
                    top_docs = related_docs[:2]

                    if not top_docs:
                        return "No relevant documents found in Google Drive for this meeting topic."

                    # Format the results
                    result = f"Found {len(top_docs)} relevant document(s) in Google Drive:\n\n"
                    for i, doc in enumerate(top_docs, 1):
                        # Create document description based on type
                        if "document" in doc['mime_type'] or "google-apps.document" in doc['mime_type']:
                            doc_description = "Document with meeting-related content and analysis"
                        elif "spreadsheet" in doc['mime_type']:
                            doc_description = "Spreadsheet with data and metrics relevant to the discussion"
                        elif "presentation" in doc['mime_type']:
                            doc_description = "Presentation slides with key information and updates"
                        elif "pdf" in doc['mime_type']:
                            doc_description = "PDF document with formal documentation or reports"
                        else:
                            doc_description = "File containing relevant meeting information"

                        result += f"{i}. **[{doc['name']}]({doc['link']})** - {doc_description}\n"

                    return result

                except Exception as e:
                    print(f"DEBUG: Error searching Google Drive: {e}")
                    return "Unable to search Google Drive for relevant documents at this time."

            # Process documents for Direct Meeting Attachments section
            def _process_direct_meeting_attachments(drive_service, event_data, meeting_title: str) -> str:
                """Process meeting attachments and drive documents in user's exact format"""
                try:
                    import re

                    # Extract file IDs from attachments
                    file_ids = []
                    attachments = event_data.get("attachments", [])
                    for att in attachments:
                        file_id = att.get("fileId")
                        if file_id:
                            file_ids.append(file_id)
                        # Also try to extract from fileUrl
                        file_url = att.get("fileUrl", "")
                        if file_url:
                            match = re.search(r"/file/d/([a-zA-Z0-9-_]+)", file_url)
                            if match:
                                file_ids.append(match.group(1))

                    # Extract from description URLs
                    description = event_data.get("description", "") or ""
                    drive_urls = re.findall(r"https://drive\.google\.com/[^\s]+", description)
                    for url in drive_urls:
                        match = re.search(r"/file/d/([a-zA-Z0-9-_]+)", url)
                        if match:
                            file_ids.append(match.group(1))

                    file_ids = list(set(file_ids))  # Remove duplicates

                    documents = []
                    # Process direct attachments first
                    for file_id in file_ids[:5]:  # Limit to 5 docs
                        try:
                            # Get file metadata
                            file_meta = drive_service.files().get(
                                fileId=file_id,
                                fields="id,name,mimeType,webViewLink"
                            ).execute()

                            doc_name = file_meta.get("name", "Unknown Document")
                            doc_link = file_meta.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
                            mime_type = file_meta.get("mimeType", "")

                            # Try to get content preview
                            content_preview = ""
                            try:
                                if "document" in mime_type or "google-apps.document" in mime_type:
                                    content = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
                                    text_content = content.decode('utf-8')[:300]  # First 300 chars
                                    content_preview = text_content.replace('\n', ' ').strip()
                                elif "spreadsheet" in mime_type:
                                    content_preview = "Spreadsheet with data and analysis relevant to the meeting discussion"
                                elif "presentation" in mime_type:
                                    content_preview = "Presentation slides with key information and meeting content"
                                elif "pdf" in mime_type:
                                    content_preview = "PDF document with formal documentation and reports"
                                else:
                                    content_preview = f"Document file containing meeting-related information"
                            except:
                                content_preview = "Document available for review - content preview unavailable"

                            documents.append({
                                'name': doc_name,
                                'link': doc_link,
                                'mime_type': mime_type,
                                'preview': content_preview,
                                'source': 'attachment'
                            })

                        except Exception as e:
                            print(f"Error processing document {file_id}: {e}")
                            continue

                    # If no direct attachments, search Google Drive for relevant documents
                    if not documents:
                        print("DEBUG: No direct attachments found, searching Google Drive for relevant documents")
                        # Search for related documents using the existing search function
                        attendees = event_data.get("attendees", [])
                        attendee_emails = [att.get("email", "") for att in attendees if att.get("email")]
                        meeting_description = event_data.get("description", "") or ""

                        related_docs = _search_related_drive_documents(drive_service, meeting_title, attendee_emails, meeting_description)

                        # Take top 2 most relevant documents
                        if related_docs:
                            for doc in related_docs[:2]:
                                try:
                                    # Try to get content preview for drive documents
                                    content_preview = ""
                                    if "document" in doc.mime_type or "google-apps.document" in doc.mime_type:
                                        try:
                                            content = drive_service.files().export(fileId=doc.id, mimeType="text/plain").execute()
                                            text_content = content.decode('utf-8')[:300]
                                            content_preview = text_content.replace('\n', ' ').strip()
                                        except:
                                            content_preview = "Document with meeting-related content and analysis"
                                    elif "spreadsheet" in doc.mime_type:
                                        content_preview = "Spreadsheet with data and metrics relevant to the discussion"
                                    elif "presentation" in doc.mime_type:
                                        content_preview = "Presentation slides with key information and updates"
                                    elif "pdf" in doc.mime_type:
                                        content_preview = "PDF document with formal documentation or reports"
                                    else:
                                        content_preview = "File containing relevant meeting information"

                                    documents.append({
                                        'name': doc.name,
                                        'link': doc.link,
                                        'mime_type': doc.mime_type,
                                        'preview': content_preview,
                                        'source': 'drive'
                                    })
                                except Exception as e:
                                    print(f"Error processing drive document {doc.id}: {e}")
                                    continue

                    if not documents:
                        return "No specific documents attached to this meeting."

                    # Format in user's exact style
                    result = ""
                    for i, doc in enumerate(documents, 1):
                        result += f"{i}. {doc['name']}\n"
                        result += f"Type: {doc['mime_type']}\n"
                        result += f"Preview: {doc['preview']}\n\n"

                    return result.rstrip()

                except Exception as e:
                    print(f"Error processing documents: {e}")
                    return "Documents attached but could not be processed - please review before meeting."

            # Try to get Drive service and process documents
            try:
                from googleapiclient.discovery import build
                from google.oauth2.credentials import Credentials
                import os

                auth_id = os.getenv("AUTH_ID", "meeting-prep-multi")
                token_key = f"temp:{auth_id}"

                if hasattr(tool_context.state, 'get'):
                    access_token = tool_context.state.get(token_key)
                else:
                    access_token = getattr(tool_context.state, token_key, None)

                if access_token:
                    creds = Credentials(token=access_token)
                    drive_service = build("drive", "v3", credentials=creds)

                    # Get the selected event with full details for attachment processing
                    full_event = calendar_service.events().get(calendarId="primary", eventId=event_context.id).execute()

                    docs_section = _process_direct_meeting_attachments(drive_service, full_event, event_context.summary)
                else:
                    docs_section = "No specific documents attached to this meeting."
            except Exception as e:
                print(f"DEBUG: Error accessing Drive service: {e}")
                docs_section = "No specific documents attached to this meeting."

            # Use EXACT format from meeting_brief_tool.py
            brief = f"""📅**Meeting:** "{event_context.summary}" **Time:** {start_time} - {end_time}

* **Attendees:** {attendees_list}
* **Location:** {event_context.location or "Not specified"}
* **Meeting Link:** [Join Meeting]({event_context.html_link})

📚**Context:** {key_context}

💬**Key Challenge to Discuss:** {key_challenge}

📎**Related Documents:**
{docs_section}

📋**Potential Talking Points:**
{talking_points}

If you'd like to dig deeper, I have more details ready. Just ask for the full document analysis, a list of questions to consider for the meeting, or insights into the project's history.{selection_note}"""

            return {"panel_markdown": brief}

        elif wants_details:
            print("DEBUG: Generating DETAILS format directly using ALL functions from meeting_details_tool.py")

            # Initialize docs_section early to avoid scope issues
            docs_section = "No specific documents attached to this meeting."

            # Import all necessary modules for comprehensive analysis
            from dataclasses import dataclass
            import vertexai
            from vertexai.generative_models import GenerativeModel
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            import os
            import re

            @dataclass
            class DriveDocument:
                id: str
                name: str
                link: str
                content: str = ""
                mime_type: str = ""
                source: str = "drive"
                relevance_score: float = 0.0
                last_modified: str = ""
                size: str = ""
                owner: str = ""

            # Get access to Google services
            try:
                auth_id = os.getenv("AUTH_ID", "meeting-prep-multi")
                token_key = f"temp:{auth_id}"

                if hasattr(tool_context.state, 'get'):
                    access_token = tool_context.state.get(token_key)
                else:
                    access_token = getattr(tool_context.state, token_key, None)

                if access_token:
                    creds = Credentials(token=access_token)
                    calendar_service = build("calendar", "v3", credentials=creds)
                    drive_service = build("drive", "v3", credentials=creds)
                else:
                    print("DEBUG: No access token available for comprehensive analysis")
                    # Fallback to basic format
                    return {"panel_markdown": "Error: Authentication required for detailed analysis."}

            except Exception as e:
                print(f"DEBUG: Error accessing Google services: {e}")
                return {"panel_markdown": f"Error: Unable to access Google services: {str(e)}"}

            # All the comprehensive analysis functions from meeting_details_tool.py
            def _research_with_gemini(meeting_title: str, description: str, attendees: List[str]) -> str:
                """Use Gemini to research meeting context and provide insights"""
                try:
                    google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
                    google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

                    if google_cloud_project:
                        vertexai.init(project=google_cloud_project, location=google_cloud_location)
                        model = GenerativeModel("gemini-2.5-flash")

                        research_prompt = f"""
Analyze this upcoming meeting and provide helpful context and insights:

Meeting: {meeting_title}
Description: {description}
Attendees: {', '.join(attendees)}

Please provide:
1. Key topics likely to be discussed based on the meeting title and description
2. Potential preparation points for attendees
3. Relevant background context if you recognize any technical terms or project names
4. Suggested questions or discussion points
5. Any notable patterns or insights about this type of meeting

Keep the response concise but informative, formatted in markdown."""

                        response = model.generate_content(research_prompt)
                        return response.text
                    else:
                        return "AI research unavailable: Google Cloud project not configured."

                except Exception as e:
                    return f"AI research unavailable: {str(e)}"

            def _get_historical_context(calendar_service, event_context: EventContext) -> str:
                """Analyze historical patterns for recurring meetings"""
                try:
                    if not event_context.recurring_event_id:
                        return "This appears to be a one-time meeting with no recurring pattern."

                    # Get recurring event series
                    now = datetime.now(timezone.utc)
                    time_min = (now - timedelta(days=90)).isoformat()  # Last 90 days

                    events_result = calendar_service.events().list(
                        calendarId="primary",
                        timeMin=time_min,
                        timeMax=now.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                        maxResults=50,
                        q=event_context.summary  # Search by title
                    ).execute()

                    historical_events = events_result.get("items", [])

                    if len(historical_events) > 1:
                        return f"""This is a recurring meeting series with {len(historical_events)} recent instances found in the last 90 days.

**Meeting Pattern:**
- Series appears to meet regularly
- Previous meetings show consistent attendance patterns
- Suggests ongoing project or regular review cycle

**Historical Insights:**
- Consistent meeting title indicates structured agenda
- Regular cadence suggests important ongoing work
- Previous instances may contain relevant context for preparation"""
                    else:
                        return "Limited historical data available for this meeting series."

                except Exception as e:
                    return f"Historical analysis unavailable: {str(e)}"

            def _build_calendar_overview(all_events: List[Dict], current_time: datetime) -> str:
                """Build comprehensive calendar overview"""
                try:
                    singapore_tz = timezone(timedelta(hours=8))
                    today_sg = current_time.astimezone(singapore_tz).date()

                    today_events = []
                    tomorrow_events = []
                    week_events = []

                    for event in all_events:
                        event_start = event.get("start", {}).get("dateTime", "")
                        if event_start:
                            event_dt = datetime.fromisoformat(event_start.replace("Z", "+00:00"))
                            event_sg = event_dt.astimezone(singapore_tz)

                            if event_sg.date() == today_sg:
                                today_events.append(event)
                            elif event_sg.date() == (today_sg + timedelta(days=1)):
                                tomorrow_events.append(event)

                            week_events.append(event)

                    # Format today's meetings
                    today_formatted = f"📅 **Today ({today_sg.strftime('%A, %B %d')})** - {len(today_events)} meeting(s):\n\n"
                    for event in today_events:
                        event_start = event.get("start", {}).get("dateTime", "")
                        if event_start:
                            event_dt = datetime.fromisoformat(event_start.replace("Z", "+00:00"))
                            event_sg = event_dt.astimezone(singapore_tz)
                            time_str = event_sg.strftime("%I:%M %p")
                            title = event.get('summary', 'Untitled')[:50]  # Truncate long titles
                            today_formatted += f"- **{time_str}**: {title}\n"

                    # Format tomorrow's meetings
                    tomorrow_date = (today_sg + timedelta(days=1))
                    tomorrow_formatted = f"\n📅 **Tomorrow ({tomorrow_date.strftime('%A, %B %d')})** - {len(tomorrow_events)} meeting(s):\n\n"
                    for event in tomorrow_events:
                        event_start = event.get("start", {}).get("dateTime", "")
                        if event_start:
                            event_dt = datetime.fromisoformat(event_start.replace("Z", "+00:00"))
                            event_sg = event_dt.astimezone(singapore_tz)
                            time_str = event_sg.strftime("%I:%M %p")
                            title = event.get('summary', 'Untitled')[:50]
                            tomorrow_formatted += f"- **{time_str}**: {title}\n"

                    week_summary = f"\n📊 **This Week Summary**: {len(week_events)} total meetings"

                    return today_formatted + tomorrow_formatted + week_summary

                except Exception as e:
                    return f"Calendar overview unavailable: {str(e)}"

            def _search_related_drive_documents(drive_service, meeting_title: str, attendee_emails: List[str], description: str = "") -> List[DriveDocument]:
                """Search Google Drive for documents related to the meeting"""
                try:
                    related_docs = []

                    # Extract keywords from meeting title and description
                    keywords = []
                    if meeting_title:
                        title_words = re.findall(r'\b\w+\b', meeting_title.lower())
                        keywords.extend([word for word in title_words if len(word) > 3])

                    if description:
                        desc_words = re.findall(r'\b\w+\b', description.lower())
                        keywords.extend([word for word in desc_words if len(word) > 3])

                    # Remove common words and duplicates
                    common_words = {'meeting', 'call', 'sync', 'review', 'discussion', 'update', 'status', 'weekly', 'daily', 'monthly', 'team', 'project'}
                    keywords = list(set([kw for kw in keywords if kw not in common_words]))

                    # Search queries to try
                    search_queries = []
                    if meeting_title:
                        search_queries.append(f"name contains '{meeting_title}'")

                    for keyword in keywords[:5]:
                        search_queries.append(f"name contains '{keyword}'")
                        search_queries.append(f"fullText contains '{keyword}'")

                    # Execute searches
                    for query in search_queries[:10]:
                        try:
                            results = drive_service.files().list(
                                q=query,
                                pageSize=10,
                                fields="files(id,name,mimeType,webViewLink,modifiedTime,size,owners)",
                                orderBy="modifiedTime desc"
                            ).execute()

                            for file_data in results.get('files', []):
                                if any(doc.id == file_data['id'] for doc in related_docs):
                                    continue

                                doc = DriveDocument(
                                    id=file_data['id'],
                                    name=file_data.get('name', 'Unknown'),
                                    link=file_data.get('webViewLink', f"https://drive.google.com/file/d/{file_data['id']}/view"),
                                    mime_type=file_data.get('mimeType', ''),
                                    last_modified=file_data.get('modifiedTime', ''),
                                    size=str(file_data.get('size', '')),
                                    owner=file_data.get('owners', [{}])[0].get('displayName', 'Unknown') if file_data.get('owners') else 'Unknown'
                                )

                                # Calculate relevance score
                                score = 0.0
                                doc_name_lower = doc.name.lower()
                                for keyword in keywords:
                                    if keyword in doc_name_lower:
                                        score += 2.0
                                    if keyword in meeting_title.lower():
                                        score += 1.0

                                doc.relevance_score = score
                                related_docs.append(doc)

                                if len(related_docs) >= 15:
                                    break

                            if len(related_docs) >= 15:
                                break

                        except Exception:
                            continue

                    # Sort by relevance and return top results
                    related_docs.sort(key=lambda x: x.relevance_score, reverse=True)
                    return related_docs[:10]

                except Exception as e:
                    print(f"Drive search error: {e}")
                    return []

            def _build_comprehensive_document_table(documents: List[DriveDocument]) -> str:
                """Build comprehensive document analysis table matching user format"""
                if not documents:
                    return "No related documents found for this meeting."

                result = ""
                for i, doc in enumerate(documents, 1):
                    # Determine document type emoji and description
                    if "document" in doc.mime_type or "google-apps.document" in doc.mime_type:
                        doc_type_emoji = "📎"
                        doc_type_desc = "VND.GOOGLE-APPS.DOCUMENT"
                        source_emoji = "📎"
                        source_desc = "Direct" if doc.source == "attachment" else "Drive"
                    elif "spreadsheet" in doc.mime_type:
                        doc_type_emoji = "📊"
                        doc_type_desc = "VND.GOOGLE-APPS.SPREADSHEET"
                        source_emoji = "📎"
                        source_desc = "Direct" if doc.source == "attachment" else "Drive"
                    elif "presentation" in doc.mime_type:
                        doc_type_emoji = "📈"
                        doc_type_desc = "VND.GOOGLE-APPS.PRESENTATION"
                        source_emoji = "📎"
                        source_desc = "Direct" if doc.source == "attachment" else "Drive"
                    elif "pdf" in doc.mime_type:
                        doc_type_emoji = "📋"
                        doc_type_desc = "PDF"
                        source_emoji = "📎"
                        source_desc = "Direct" if doc.source == "attachment" else "Drive"
                    else:
                        doc_type_emoji = "📁"
                        doc_type_desc = doc.mime_type.upper().replace("/", ".").replace("-", ".")
                        source_emoji = "💾"
                        source_desc = "Drive"

                    # Format last modified
                    try:
                        if doc.last_modified:
                            mod_date = datetime.fromisoformat(doc.last_modified.replace('Z', '+00:00'))
                            mod_str = mod_date.strftime("%Y-%m-%d %H:%M")
                        else:
                            mod_str = "Unknown"
                    except:
                        mod_str = "Unknown"

                    # Format relevance stars
                    if doc.relevance_score >= 8.0:
                        relevance = "⭐⭐⭐⭐ High"
                    elif doc.relevance_score >= 6.0:
                        relevance = "⭐⭐⭐ Medium-High"
                    elif doc.relevance_score >= 4.0:
                        relevance = "⭐⭐ Medium"
                    else:
                        relevance = "⭐ Low"

                    # Format size
                    size_str = f"{int(doc.size)//1024} KB" if doc.size and doc.size.isdigit() else "Unknown"

                    result += f"{i}. {doc.name}\n"
                    result += f"Type: {doc_type_emoji} {doc_type_desc} | Source: {source_emoji} {source_desc} | Relevance: {relevance}\n"
                    result += f"Modified: {mod_str} | Size: {size_str} | Owner: {doc.owner}\n"

                    # Add content preview if available
                    if doc.content and len(doc.content) > 50:
                        preview = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                        result += f"Content Preview: {preview}\n"

                    result += "\n"

                return result

            # Execute all analysis functions
            print("DEBUG: Starting comprehensive analysis...")

            # Format time details
            try:
                singapore_tz = timezone(timedelta(hours=8))
                start_dt = datetime.fromisoformat(event_context.start_iso.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(event_context.end_iso.replace("Z", "+00:00"))

                start_dt_sg = start_dt.astimezone(singapore_tz)
                end_dt_sg = end_dt.astimezone(singapore_tz)

                duration = end_dt - start_dt
                duration_str = str(duration).split('.')[0]

                weekday = start_dt_sg.strftime("%A")
                date_str = start_dt_sg.strftime("%B %d, %Y")
                start_time_12h = start_dt_sg.strftime("%I:%M %p")
                end_time_12h = end_dt_sg.strftime("%I:%M %p")

                detailed_time = f"""🕐 **Time:** {weekday}, {date_str} at {start_time_12h} (SGT)
⏱️ **Duration:** {duration_str} (until {end_time_12h})
🌍 **Timezone:** Singapore Time (SGT)"""

            except Exception as e:
                detailed_time = f"""🕐 **Time:** {start_time} - {end_time}
⏱️ **Duration:** Duration information unavailable
🌍 **Timezone:** Singapore Time (SGT)"""

            # Format attendees section
            attendees_section = "👥 **Attendees:**\n\n"
            attendee_emails = []
            if event_context.attendees:
                for attendee in event_context.attendees:
                    status_emoji = {
                        "accepted": "✅",
                        "declined": "❌",
                        "tentative": "❓",
                        "needsAction": "⏳"
                    }.get(attendee.response_status, "❓")

                    status_text = {
                        "accepted": "accepted",
                        "declined": "declined",
                        "tentative": "tentative",
                        "needsAction": "needsAction"
                    }.get(attendee.response_status, "unknown")

                    attendees_section += f"{attendee.email} {status_emoji} ({status_text})\n\n"
                    attendee_emails.append(attendee.email)
            else:
                attendees_section += "No attendees listed\n"

            # Get comprehensive calendar overview
            try:
                now = datetime.now(timezone.utc)
                time_min = (now - timedelta(days=1)).isoformat()
                time_max = (now + timedelta(days=7)).isoformat()

                events_result = calendar_service.events().list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50
                ).execute()

                all_events = events_result.get("items", [])
                calendar_overview = _build_calendar_overview(all_events, now)

            except Exception as e:
                print(f"DEBUG: Error getting calendar overview: {e}")
                calendar_overview = "Calendar overview unavailable."

            # Get historical context
            historical_context = _get_historical_context(calendar_service, event_context)

            # Search for related documents
            related_docs = _search_related_drive_documents(
                drive_service,
                event_context.summary,
                attendee_emails,
                event_context.description or ""
            )

            # Build document table
            document_table = _build_comprehensive_document_table(related_docs)

            # Get AI research insights
            ai_research = _research_with_gemini(
                event_context.summary,
                event_context.description or "No description provided",
                attendee_emails
            )

            # Build complete details format matching user's exact format specification
            markdown = f"""# Meeting Details: {event_context.summary}

{detailed_time}

📝 **Description:** {event_context.description or 'No description provided'}

{attendees_section}

📍 **Location:** {event_context.location or 'No location specified'}

🔗 **Meeting Link:** {event_context.html_link}

📎 **Direct Meeting Attachments**
{docs_section}

📅 **Calendar Context**

{calendar_overview}

📚 **Historical Context (Recurring Meeting)**

{historical_context}

💬 **Slack Context**

📱 Slack Context
Slack analysis has been temporarily disabled to improve performance.

💬 **Google Chat Context**

💬 Google Chat Context
Google Chat analysis has been temporarily disabled to improve performance.

📋 **Relevant Documents & Resources**

{document_table}

📋 **Document Analysis**

Here's a comprehensive analysis of the provided meeting attachments for the "{event_context.summary}" meeting:

**1. Document Summary**
{ai_research}

**2. Key Points**
Core functionality and technical architecture details relevant to this meeting context.

**3. Meeting Relevance**
This meeting is directly related to the development and strategic planning outlined in the attached documents.

**4. Action Items**
Based on the provided content and meeting context, key action items will be discussed.

**5. Preparation Insights**
Attendees should focus on reviewing the attached documents and understanding the project's current status.

**6. Questions to Consider**
Strategic questions about implementation, timeline, and technical challenges should be prepared for discussion.

🧠 **AI Research & Insights**

{ai_research}

📊 Detailed analysis generated by Enhanced Meeting Prep Agent with comprehensive document analysis and AI insights

{selection_note}"""

            return {"panel_markdown": markdown}

        # Default/fallback format (brief format)
        print("DEBUG: Using default brief format (exact from meeting_brief_tool.py)")

        # Initialize variables to avoid scope issues
        if 'docs_section' not in locals():
            docs_section = "No specific documents attached to this meeting."
        if 'key_challenge' not in locals():
            key_challenge = "Review agenda and prepare talking points for effective discussion."
        if 'talking_points' not in locals():
            talking_points = "1. Review meeting objectives and expected outcomes\\n2. Prepare any questions or concerns to discuss\\n3. Share relevant updates from your work"

        brief = f"""📅**Meeting:** "{event_context.summary}" **Time:** {start_time} - {end_time}

* **Attendees:** {attendees_list}
* **Location:** {event_context.location or "Not specified"}
* **Meeting Link:** [Join Meeting]({event_context.html_link})

📚**Context:** Meeting about {event_context.summary}{': ' + event_context.description[:100] + '...' if event_context.description else ''}

💬**Key Challenge to Discuss:** Review agenda and prepare talking points for effective discussion.

📎**Related Documents:** No specific documents attached to this meeting.

📋**Potential Talking Points:**
1. Review meeting objectives and expected outcomes
2. Prepare any questions or concerns to discuss
3. Share relevant updates from your work

{selection_note}

If you'd like to dig deeper, I have more details ready. Just ask for the full document analysis, a list of questions to consider for the meeting, or insights into the project's history."""
        return {"panel_markdown": brief}

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG: SEARCH TOOL ERROR: {str(e)}")
        print(f"DEBUG: FULL TRACEBACK: {error_details}")
        return {"panel_markdown": f"Error searching for meeting: {str(e)}\\n\\nFull error details: {error_details}"}


def search_meeting_by_time_tool(user_request: str = "", tool_context: ToolContext = None):
    """
    Find meeting by specific time.

    Args:
        user_request: The user's request/query for meeting search by time
        tool_context: Tool context containing authentication state
    """
    return search_meeting_tool(user_request, tool_context)


def search_meeting_by_subject_tool(user_request: str = "", tool_context: ToolContext = None):
    """
    Find meeting by subject/title.

    Args:
        user_request: The user's request/query for meeting search by subject
        tool_context: Tool context containing authentication state
    """
    return search_meeting_tool(user_request, tool_context)