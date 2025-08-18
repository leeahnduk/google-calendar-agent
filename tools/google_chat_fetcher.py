from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional
import os
from datetime import datetime, timedelta

from config.settings import load_settings

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except Exception:  # Google Chat API optional in early stages
    Credentials = None  # type: ignore
    build = None  # type: ignore
    HttpError = Exception  # type: ignore


@dataclass
class GoogleChatMessage:
    """Represents a Google Chat message"""
    name: str  # Message resource name
    sender: str  # Sender's display name or email
    text: str  # Message text content
    create_time: str  # ISO timestamp when message was created
    space: str  # Chat space name
    thread_key: Optional[str] = None  # Thread key if message is part of a thread
    annotations: List[Any] = None  # Message annotations (mentions, links, etc.)


@dataclass
class GoogleChatSpace:
    """Represents a Google Chat space (room/DM)"""
    name: str  # Space resource name
    display_name: str  # Human-readable space name
    space_type: str  # ROOM, DM, GROUP_DM
    space_threading_state: Optional[str] = None


def fetch_google_chat_spaces(credentials: Credentials) -> List[GoogleChatSpace]:
    """Fetch all Google Chat spaces the user has access to"""
    if not credentials or build is None:
        return []
    
    try:
        service = build('chat', 'v1', credentials=credentials)
        
        # List all spaces
        spaces_result = service.spaces().list().execute()
        spaces_data = spaces_result.get('spaces', [])
        
        spaces = []
        for space_data in spaces_data:
            space = GoogleChatSpace(
                name=space_data.get('name', ''),
                display_name=space_data.get('displayName', ''),
                space_type=space_data.get('type', ''),
                space_threading_state=space_data.get('spaceThreadingState')
            )
            spaces.append(space)
        
        return spaces
        
    except HttpError as e:
        print(f"Error fetching Google Chat spaces: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error fetching Google Chat spaces: {e}")
        return []


def fetch_google_chat_messages(
    credentials: Credentials,
    meeting_title: str,
    lookback_days: int = 7,
    max_messages: int = 50
) -> List[GoogleChatMessage]:
    """
    Fetch Google Chat messages related to a meeting title.
    
    This function searches for:
    1. Group chats/rooms with names related to the meeting title
    2. Recent messages in those spaces
    3. Direct messages that mention the meeting topic
    
    Args:
        credentials: OAuth2 credentials for Google Chat API
        meeting_title: Meeting title to search for related conversations
        lookback_days: How many days back to search for messages
        max_messages: Maximum number of messages to return per space
        
    Returns:
        List of GoogleChatMessage objects
    """
    if not credentials or build is None:
        return []
    
    try:
        service = build('chat', 'v1', credentials=credentials)
        
        # Get all spaces first
        spaces = fetch_google_chat_spaces(credentials)
        if not spaces:
            return []
        
        # Find relevant spaces based on meeting title
        relevant_spaces = _find_relevant_spaces(spaces, meeting_title)
        
        all_messages = []
        cutoff_time = datetime.now() - timedelta(days=lookback_days)
        
        for space in relevant_spaces:
            try:
                # Fetch messages from this space
                messages_result = service.spaces().messages().list(
                    parent=space.name,
                    pageSize=min(max_messages, 100),  # API limit is 100
                    orderBy='createTime desc'
                ).execute()
                
                messages_data = messages_result.get('messages', [])
                
                for msg_data in messages_data:
                    # Parse message creation time
                    create_time_str = msg_data.get('createTime', '')
                    try:
                        create_time = datetime.fromisoformat(create_time_str.replace('Z', '+00:00'))
                        if create_time < cutoff_time:
                            continue  # Skip old messages
                    except ValueError:
                        continue  # Skip messages with invalid timestamps
                    
                    # Extract message details
                    sender_info = msg_data.get('sender', {})
                    sender_name = (
                        sender_info.get('displayName', '') or 
                        sender_info.get('name', '').split('/')[-1] or 
                        'Unknown'
                    )
                    
                    message = GoogleChatMessage(
                        name=msg_data.get('name', ''),
                        sender=sender_name,
                        text=msg_data.get('text', ''),
                        create_time=create_time_str,
                        space=space.display_name,
                        thread_key=msg_data.get('thread', {}).get('name'),
                        annotations=msg_data.get('annotations', [])
                    )
                    
                    # Filter for messages that might be relevant to the meeting
                    if _is_message_relevant(message, meeting_title):
                        all_messages.append(message)
                
            except HttpError as e:
                print(f"Error fetching messages from space {space.display_name}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error fetching messages from space {space.display_name}: {e}")
                continue
        
        # Sort by creation time (newest first) and limit results
        all_messages.sort(key=lambda m: m.create_time, reverse=True)
        return all_messages[:max_messages]
        
    except Exception as e:
        print(f"Error in fetch_google_chat_messages: {e}")
        return []


def _find_relevant_spaces(spaces: List[GoogleChatSpace], meeting_title: str) -> List[GoogleChatSpace]:
    """Find chat spaces that might be relevant to the meeting"""
    relevant_spaces = []
    
    # Clean and normalize meeting title for matching
    title_words = set(word.lower().strip() for word in meeting_title.split() if len(word) > 2)
    
    for space in spaces:
        if space.space_type == 'DM':
            # For DMs, we'll check content rather than space name
            relevant_spaces.append(space)
        else:
            # For rooms/group chats, check if space name contains meeting keywords
            space_name_words = set(word.lower().strip() for word in space.display_name.split())
            
            # Check for word overlap
            if title_words.intersection(space_name_words):
                relevant_spaces.append(space)
            
            # Also check for common meeting-related patterns
            meeting_patterns = [
                'meeting', 'sync', 'standup', 'review', 'planning', 
                'project', 'team', 'discussion', 'call'
            ]
            
            if any(pattern in space.display_name.lower() for pattern in meeting_patterns):
                # If it's a general meeting space, include it
                relevant_spaces.append(space)
    
    return relevant_spaces


def _is_message_relevant(message: GoogleChatMessage, meeting_title: str) -> bool:
    """Check if a message is relevant to the meeting topic"""
    # Basic relevance check based on content
    title_words = set(word.lower().strip() for word in meeting_title.split() if len(word) > 2)
    message_words = set(word.lower().strip() for word in message.text.split())
    
    # Check for word overlap
    if title_words.intersection(message_words):
        return True
    
    # Check for meeting-related keywords
    meeting_keywords = [
        'meeting', 'agenda', 'discussion', 'sync', 'review', 
        'action', 'todo', 'follow', 'next steps', 'decision'
    ]
    
    if any(keyword in message.text.lower() for keyword in meeting_keywords):
        return True
    
    # For very short messages or messages with no relevant content, exclude
    if len(message.text.strip()) < 10:
        return False
    
    return True


def search_google_chat_history(
    credentials: Credentials,
    meeting_title: str,
    attendee_emails: List[str],
    lookback_days: int = 14
) -> List[GoogleChatMessage]:
    """
    Search for Google Chat history related to a specific meeting and its attendees.
    
    This is a more targeted search that looks for:
    1. Direct messages with meeting attendees
    2. Group conversations involving attendees
    3. Messages mentioning the meeting topic
    
    Args:
        credentials: OAuth2 credentials for Google Chat API
        meeting_title: Meeting title to search for
        attendee_emails: List of attendee email addresses
        lookback_days: How many days back to search
        
    Returns:
        List of relevant GoogleChatMessage objects
    """
    if not credentials or build is None:
        return []
    
    try:
        service = build('chat', 'v1', credentials=credentials)
        
        # Get all spaces
        spaces = fetch_google_chat_spaces(credentials)
        if not spaces:
            return []
        
        relevant_messages = []
        cutoff_time = datetime.now() - timedelta(days=lookback_days)
        
        # Search in DMs with attendees
        dm_spaces = [space for space in spaces if space.space_type == 'DM']
        
        for space in dm_spaces:
            try:
                # Get space members to see if any attendees are involved
                members_result = service.spaces().members().list(parent=space.name).execute()
                members = members_result.get('memberships', [])
                
                # Check if any meeting attendees are in this DM
                space_emails = []
                for member in members:
                    member_info = member.get('member', {})
                    if member_info.get('type') == 'HUMAN':
                        email = member_info.get('name', '').split('/')[-1]
                        if '@' in email:  # Basic email validation
                            space_emails.append(email.lower())
                
                # If this DM involves meeting attendees, get recent messages
                if any(email.lower() in space_emails for email in attendee_emails):
                    messages = fetch_google_chat_messages(
                        credentials, meeting_title, lookback_days, 20
                    )
                    relevant_messages.extend([msg for msg in messages if msg.space == space.display_name])
                    
            except HttpError:
                continue  # Skip spaces we can't access
        
        # Also search in group spaces for meeting-related discussions
        group_spaces = [space for space in spaces if space.space_type in ['ROOM', 'GROUP_DM']]
        for space in group_spaces:
            if _space_involves_attendees(service, space, attendee_emails):
                messages = fetch_google_chat_messages(
                    credentials, meeting_title, lookback_days, 10
                )
                relevant_messages.extend([msg for msg in messages if msg.space == space.display_name])
        
        # Remove duplicates and sort by time
        seen_messages = set()
        unique_messages = []
        for msg in relevant_messages:
            msg_key = (msg.name, msg.create_time)
            if msg_key not in seen_messages:
                seen_messages.add(msg_key)
                unique_messages.append(msg)
        
        unique_messages.sort(key=lambda m: m.create_time, reverse=True)
        return unique_messages[:50]  # Limit to 50 most recent relevant messages
        
    except Exception as e:
        print(f"Error in search_google_chat_history: {e}")
        return []


def _space_involves_attendees(service, space: GoogleChatSpace, attendee_emails: List[str]) -> bool:
    """Check if a chat space involves any of the meeting attendees"""
    try:
        members_result = service.spaces().members().list(parent=space.name).execute()
        members = members_result.get('memberships', [])
        
        space_emails = []
        for member in members:
            member_info = member.get('member', {})
            if member_info.get('type') == 'HUMAN':
                email = member_info.get('name', '').split('/')[-1]
                if '@' in email:
                    space_emails.append(email.lower())
        
        return any(email.lower() in space_emails for email in attendee_emails)
        
    except HttpError:
        return False