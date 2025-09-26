"""
Meeting Search Tools - Search for specific meetings by time or subject.
"""

from google.adk.tools.tool_context import ToolContext


def search_meeting_tool(tool_context: ToolContext):
    """
    Unified search tool that handles both time and subject queries.
    """
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
        query = user_query.lower()

        # Patterns to detect time, with and without 'at'
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)', # 5:00p.m, 5:00 p.m.
            r'(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)',       # 5p.m, 5 pm
            r'(\d{1,2}):(\d{2})(?!\s*[ap]\.?m\.?)',    # 17:00, 15:30 (24-hour format)
        ]

        target_time = None
        for pattern in time_patterns:
            # Also check for 'at 5pm' style
            for prefix in [r'at\s+', '']:
                full_pattern = prefix + pattern
                match = re.search(full_pattern, query)
                if match:
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
                    today = datetime.now().date()

                    # Create time in Singapore timezone (UTC+8)
                    singapore_tz = timezone(timedelta(hours=8))
                    target_time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
                    target_time = target_time.replace(tzinfo=singapore_tz)

                    print(f"DEBUG: Target time created: {target_time}")

                    # Found a match, exit loops
                    break
            if target_time:
                break

        return target_time

    try:
        # Get auth_id from environment or use default
        import os
        auth_id = os.getenv("AUTH_ID", "grab_meeting_multi")

        # Get OAuth credentials from tool context
        if not hasattr(tool_context, "state"):
            return {"panel_markdown": "Error: No authentication state available."}

        token_key = f"temp:{auth_id}"
        access_token = tool_context.state.get(token_key)
        if not access_token:
            return {"panel_markdown": "Error: No access token available. Please authenticate first."}

        creds = Credentials(token=access_token)
        calendar_service = build("calendar", "v3", credentials=creds)

        # Parse user query to determine if they want a specific meeting
        user_query = tool_context.user_query if hasattr(tool_context, 'user_query') else ""

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

        # Check for numbered meeting selection first
        number_patterns = [
            r'brief for meeting (\d+)',
            r'meeting (\d+)',
            r'number (\d+)',
            r'(\d+)'  # Just a number
        ]

        meeting_number = None
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
        for pattern in subject_patterns:
            match = re.search(pattern, user_query, re.IGNORECASE)
            if match:
                subject_query = match.group(1).lower()
                break

        target_event_item = None
        selection_note = ""

        # First try numbered meeting selection using saved meeting index
        if meeting_number:
            print(f"DEBUG: Looking for meeting number {meeting_number}")

            # Try to get saved meeting index from meetings_today_agent output
            saved_meeting_index = None
            if hasattr(tool_context, 'state') and 'meeting_index' in tool_context.state:
                saved_meeting_index = tool_context.state['meeting_index']
                print(f"DEBUG: Found saved meeting index with {len(saved_meeting_index)} meetings")

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
            print(f"DEBUG: Looking for meeting at {target_time}")

            # User requested a specific time, find matches
            exact_matches = []
            later_matches = []

            singapore_tz = timezone(timedelta(hours=8))
            target_time_sg = target_time.astimezone(singapore_tz)

            for event in items:
                start_str = event.get("start", {}).get("dateTime", "")
                if start_str:
                    try:
                        event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        event_time_sg = event_time.astimezone(singapore_tz)

                        print(f"DEBUG: Event '{event.get('summary', '')}' at {event_time_sg}")

                        # Check if event starts exactly at the requested time (within 30 minutes)
                        diff = abs((event_time_sg - target_time_sg).total_seconds())

                        # For better matching: exact time (within 30 minutes) or start of hour match
                        is_exact_match = diff <= 1800  # Within 30 minutes

                        # Special case: if user asks for 4:00pm, match meeting that starts at 4:00pm
                        hour_match = (event_time_sg.hour == target_time_sg.hour and
                                     abs(event_time_sg.minute - target_time_sg.minute) <= 30)

                        if is_exact_match or hour_match:
                            exact_matches.append({
                                'event': event,
                                'time': event_time_sg,
                                'diff': diff
                            })
                            print(f"DEBUG: EXACT MATCH: {event.get('summary', '')} (diff: {diff} seconds)")
                        elif event_time_sg > target_time_sg:  # Meeting is later in the day
                            later_matches.append({
                                'event': event,
                                'time': event_time_sg,
                                'diff': (event_time_sg - target_time_sg).total_seconds()
                            })
                            print(f"DEBUG: LATER MATCH: {event.get('summary', '')} at {event_time_sg}")

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

        # Get key context and challenge (simplified for brief)
        key_context = f"Meeting about {event_context.summary}" + (f": {event_context.description[:100]}..." if event_context.description else "")
        key_challenge = "Review agenda and prepare talking points for effective discussion."

        # Get top 3 documents (simplified)
        docs_section = "No specific documents attached to this meeting."
        if event_context.attachments:
            docs_section = f"{len(event_context.attachments)} document(s) attached - review before meeting."

        # Generate talking points (simplified)
        talking_points = """1. Review meeting objectives and expected outcomes
2. Prepare any questions or concerns to discuss
3. Share relevant updates from your work"""

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

    except Exception as e:
        return {"panel_markdown": f"Error searching for meeting: {str(e)}"}


def search_meeting_by_time_tool(tool_context: ToolContext):
    """
    Find meeting by specific time.
    """
    return search_meeting_tool(tool_context)


def search_meeting_by_subject_tool(tool_context: ToolContext):
    """
    Find meeting by subject/title.
    """
    return search_meeting_tool(tool_context)