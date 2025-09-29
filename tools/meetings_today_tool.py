"""
Meetings Today Tool - Shows remaining meetings for today with numbered index for easy selection.
"""

from google.adk.tools.tool_context import ToolContext


def meetings_remaining_today_tool(tool_context: ToolContext):
    """
    Show all remaining meetings for today with numbered index.
    Handles: "How many meetings do I have left today?", "Show my remaining meetings"
    """
    from datetime import datetime, timedelta, timezone
    from dataclasses import dataclass
    from typing import List, Optional, Dict, Any
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    import json

    @dataclass
    class MeetingInfo:
        number: int
        id: str
        title: str
        start_time: str
        end_time: str
        start_time_display: str
        end_time_display: str
        duration_minutes: int
        location: str
        attendees: List[str]
        description: str
        meeting_link: str
        status: str  # upcoming, current, past

    try:
        # Get auth_id from environment or use default
        import os
        auth_id = os.getenv("AUTH_ID", "grab_meeting_multi_doc_v2")

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

        # Get current time and today's time range in Singapore timezone
        singapore_tz = timezone(timedelta(hours=8))
        now_sg = datetime.now(singapore_tz)

        # Start from beginning of today, end at end of today
        start_of_today_sg = datetime.combine(now_sg.date(), datetime.min.time()).replace(tzinfo=singapore_tz)
        end_of_today_sg = datetime.combine(now_sg.date(), datetime.max.time()).replace(tzinfo=singapore_tz)

        # Convert to UTC for API call
        start_of_today_utc = start_of_today_sg.astimezone(timezone.utc)
        end_of_today_utc = end_of_today_sg.astimezone(timezone.utc)

        print(f"DEBUG: Fetching today's meetings from {start_of_today_utc} to {end_of_today_utc}")

        # Fetch all events for today
        events_result = (
            calendar_service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_today_utc.isoformat(),
                timeMax=end_of_today_utc.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=50
            )
            .execute()
        )
        items = events_result.get("items", [])

        if not items:
            return {
                "panel_markdown": "## 📅 Today's Meetings\n\nNo meetings found for today.",
                "meeting_index": []
            }

        # Process and categorize meetings
        meetings_index = []
        remaining_meetings = []
        past_meetings = []
        current_meeting = None

        for i, event in enumerate(items, 1):
            # Parse event details
            event_title = event.get("summary", "Untitled Meeting")
            start_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
            end_str = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")

            if not start_str or not end_str:
                continue

            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

                # Convert to Singapore timezone for comparison and display
                start_dt_sg = start_dt.astimezone(singapore_tz)
                end_dt_sg = end_dt.astimezone(singapore_tz)

                # Calculate duration
                duration = end_dt_sg - start_dt_sg
                duration_minutes = int(duration.total_seconds() / 60)

                # Determine status
                if now_sg >= end_dt_sg:
                    status = "past"
                elif now_sg >= start_dt_sg and now_sg < end_dt_sg:
                    status = "current"
                else:
                    status = "upcoming"

                # Format attendees
                attendees_raw = event.get("attendees", [])
                attendees = [att.get("email", "") for att in attendees_raw if att.get("email")]

                # Create meeting info
                meeting_info = MeetingInfo(
                    number=i,
                    id=event.get("id", ""),
                    title=event_title,
                    start_time=start_dt.isoformat(),
                    end_time=end_dt.isoformat(),
                    start_time_display=start_dt_sg.strftime("%I:%M %p"),
                    end_time_display=end_dt_sg.strftime("%I:%M %p"),
                    duration_minutes=duration_minutes,
                    location=event.get("location", ""),
                    attendees=attendees,
                    description=event.get("description", ""),
                    meeting_link=event.get("htmlLink", ""),
                    status=status
                )

                meetings_index.append(meeting_info)

                # Categorize for display
                if status == "past":
                    past_meetings.append(meeting_info)
                elif status == "current":
                    current_meeting = meeting_info
                else:
                    remaining_meetings.append(meeting_info)

            except Exception as e:
                print(f"DEBUG: Error processing event {event_title}: {e}")
                continue

        # Build response
        current_time_display = now_sg.strftime("%I:%M %p")

        response = f"## 📅 Today's Meetings (as of {current_time_display})\n\n"

        # Show current meeting
        if current_meeting:
            response += f"### 🟢 **Currently In Progress:**\n"
            response += f"**{current_meeting.number}. {current_meeting.title}**\n"
            response += f"⏰ {current_meeting.start_time_display} - {current_meeting.end_time_display} ({current_meeting.duration_minutes} min)\n"
            if current_meeting.location:
                response += f"📍 {current_meeting.location}\n"
            response += f"🔗 [Join Meeting]({current_meeting.meeting_link})\n\n"

        # Show remaining meetings
        if remaining_meetings:
            response += f"### ⏳ **Remaining Meetings Today:** {len(remaining_meetings)}\n\n"
            for meeting in remaining_meetings:
                status_emoji = "🟡" if meeting.status == "upcoming" else "🔴"
                response += f"{status_emoji} **{meeting.number}. {meeting.title}**\n"
                response += f"⏰ {meeting.start_time_display} - {meeting.end_time_display} ({meeting.duration_minutes} min)\n"
                if meeting.location:
                    response += f"📍 {meeting.location}\n"
                if meeting.attendees:
                    attendee_count = len(meeting.attendees)
                    response += f"👥 {attendee_count} attendee{'s' if attendee_count != 1 else ''}\n"
                response += f"🔗 [Join Meeting]({meeting.meeting_link})\n\n"
        else:
            response += f"### ✅ **No More Meetings Today!**\n\nYou're all done for the day! 🎉\n\n"

        # Show past meetings summary
        if past_meetings:
            response += f"### ✅ **Completed Today:** {len(past_meetings)} meeting{'s' if len(past_meetings) != 1 else ''}\n\n"

        # Add instructions for using numbered selection
        if remaining_meetings or current_meeting:
            response += "---\n\n"
            response += "💡 **Quick Actions:**\n"
            response += "• To get a brief for any meeting, say: `brief for meeting 2`\n"
            response += "• To get details for any meeting, say: `deep dive for meeting 4`\n"
            response += "• To export a brief for any meeting to Google Docs, say: `export the meeting brief to Google Docs for meeting 4`\n"
            response += "• To export a deep dive for any meeting to Google Docs, say: `export the meeting details to Google Docs for meeting 2`\n"

        # Store meeting index in tool context for future reference
        meeting_index_data = []
        for meeting in meetings_index:
            meeting_index_data.append({
                "number": meeting.number,
                "id": meeting.id,
                "title": meeting.title,
                "start_time": meeting.start_time,
                "end_time": meeting.end_time,
                "start_time_display": meeting.start_time_display,
                "end_time_display": meeting.end_time_display,
                "duration_minutes": meeting.duration_minutes,
                "location": meeting.location,
                "attendees": meeting.attendees,
                "description": meeting.description,
                "meeting_link": meeting.meeting_link,
                "status": meeting.status
            })

        # Store meeting index in tool context state for other agents to use
        if hasattr(tool_context, 'state'):
            try:
                if hasattr(tool_context.state, '__setitem__'):
                    tool_context.state['meeting_index'] = meeting_index_data
                else:
                    setattr(tool_context.state, 'meeting_index', meeting_index_data)
                print(f"DEBUG: Saved meeting index with {len(meeting_index_data)} meetings to tool_context.state")
            except Exception as e:
                print(f"DEBUG: Error storing meeting_index in state: {e}")

        return {
            "panel_markdown": response,
            "meeting_index": meeting_index_data,
            "total_meetings_today": len(meetings_index),
            "remaining_meetings": len(remaining_meetings),
            "current_meeting": current_meeting.number if current_meeting else None
        }

    except Exception as e:
        return {"panel_markdown": f"Error fetching today's meetings: {str(e)}"}