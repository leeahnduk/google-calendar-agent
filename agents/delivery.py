from __future__ import annotations

from typing import List

from tools.drive_search import DocumentReference
from tools.slack_fetcher import SlackMessage
from tools.calendar_fetcher import EventContext
from agents.synthesis import render_brief_markdown


def summarize_slack_for_brief(messages: List[SlackMessage]) -> str:
    if not messages:
        return ""
    # Minimal deterministic summary: show latest 5 with user + trimmed text
    clipped = messages[:5]
    lines = []
    for m in clipped:
        text = (m.text or "").strip().replace("\n", " ")
        if len(text) > 160:
            text = text[:157] + "..."
        lines.append(f"- <{m.permalink}|{m.channel}> {m.user}: {text}")
    return "\n".join(lines)


def build_panel_markdown(event: EventContext,
                         key_docs: List[DocumentReference],
                         slack_msgs: List[SlackMessage],
                         historical: str | None = None) -> str:
    slack_summary = summarize_slack_for_brief(slack_msgs)

    no_materials = not key_docs and not slack_summary and not (historical and historical.strip())
    if no_materials:
        return f"# {event.summary}\n\nNo preparatory materials could be found for this meeting.\n"

    return render_brief_markdown(
        event=event,
        key_docs=key_docs,
        slack_summary=slack_summary,
        historical=historical or "",
        action_items=[],
        disclaimers=[],
    )
