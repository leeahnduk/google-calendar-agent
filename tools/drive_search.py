from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from googleapiclient.discovery import build

from config.settings import load_settings
from agents.oauth_util import get_google_creds_from_tool_context


@dataclass
class DocumentReference:
    id: str
    title: str
    link: str
    mime_type: str
    source: str


def search_drive(tool_context: Any, query_terms: List[str], page_size: int = 10) -> List[DocumentReference]:
    settings = load_settings()
    creds = get_google_creds_from_tool_context(tool_context, settings.auth_id)
    service = build("drive", "v3", credentials=creds)

    q_parts = ["trashed = false"]
    for t in query_terms:
        safe = t.replace("\"", "\"")
        q_parts.append(f"name contains '{safe}'")
    q = " and ".join(q_parts)

    results = (
        service.files()
        .list(q=q, pageSize=page_size, fields="files(id, name, mimeType, webViewLink)")
        .execute()
    )
    files = results.get("files", [])
    return [
        DocumentReference(
            id=f["id"],
            title=f.get("name", ""),
            link=f.get("webViewLink", ""),
            mime_type=f.get("mimeType", ""),
            source="drive-search",
        )
        for f in files
    ]
