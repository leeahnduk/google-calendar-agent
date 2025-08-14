from __future__ import annotations

from dataclasses import dataclass
from typing import List

from tools.drive_search import DocumentReference
from tools.slack_fetcher import SlackMessage
from tools.calendar_fetcher import EventContext


@dataclass
class Brief:
    header: str
    agenda: str
    key_docs: List[DocumentReference]
    historical_notes: str
    slack_summary: str
    action_items: List[str]
    disclaimers: List[str]


def render_brief_markdown(event: EventContext, key_docs: List[DocumentReference], slack_summary: str,
                          historical: str | None, action_items: List[str] | None,
                          disclaimers: List[str] | None) -> str:
    lines: List[str] = []
    lines.append(f"# {event.summary}")
    when = f"{event.start_iso} – {event.end_iso}"
    lines.append(f"{when}")
    lines.append("")
    if event.description:
        lines.append("## Agenda")
        lines.append(event.description.strip())
        lines.append("")
    lines.append("## Key Documents")
    if key_docs:
        for d in key_docs:
            lines.append(f"- [{d.title}]({d.link}) ({d.source})")
    else:
        lines.append("- No documents found")
    lines.append("")
    lines.append("## Recent Slack")
    lines.append(slack_summary.strip() or "No recent relevant messages found")
    lines.append("")
    if historical:
        lines.append("## Historical")
        lines.append(historical.strip())
        lines.append("")
    if action_items:
        lines.append("## Action Items")
        for a in action_items:
            lines.append(f"- {a}")
        lines.append("")
    if disclaimers:
        lines.append("## Notes")
        for d in disclaimers:
            lines.append(f"- {d}")
        lines.append("")
    return "\n".join(lines)
