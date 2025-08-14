from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List
import os

from config.settings import load_settings

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except Exception:  # slack optional in early stages
    WebClient = None  # type: ignore
    SlackApiError = Exception  # type: ignore


@dataclass
class SlackMessage:
    ts: str
    user: str
    text: str
    channel: str
    permalink: str


def fetch_slack_messages(title: str, lookback_days: int = 7, max_messages: int = 50) -> List[SlackMessage]:
    settings = load_settings()
    if not settings.slack_bot_token or WebClient is None:
        return []

    client = WebClient(token=settings.slack_bot_token)

    channel_cand = f"#" + title.lower().replace(" ", "-")
    channels = []
    try:
        res = client.conversations_list(limit=1000)
        channels = res.get("channels", [])
    except SlackApiError:
        return []

    channel_id = None
    for ch in channels:
        if ch.get("name", "").lower() == channel_cand.strip("#"):
            channel_id = ch.get("id")
            break

    messages: List[SlackMessage] = []
    if channel_id:
        try:
            res = client.conversations_history(channel=channel_id, limit=max_messages)
            for m in res.get("messages", []):
                msg = SlackMessage(
                    ts=m.get("ts", ""),
                    user=m.get("user", ""),
                    text=m.get("text", ""),
                    channel=channel_cand,
                    permalink=f"https://slack.com/app_redirect?channel={channel_id}&message_ts={m.get('ts','')}",
                )
                messages.append(msg)
        except SlackApiError:
            return []

    return messages
