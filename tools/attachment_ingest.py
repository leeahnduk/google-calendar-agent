from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple
import re

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import load_settings
from agents.oauth_util import get_google_creds_from_tool_context
from tools.drive_search import DocumentReference


_DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
_DRIVE_SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


def _parse_drive_id_from_url(url: str) -> Optional[str]:
    # Common patterns: https://drive.google.com/file/d/<id>/view , /folders/<id>
    m = re.search(r"/file/d/([^/]+)/", url)
    if m:
        return m.group(1)
    m = re.search(r"/folders/([^/?#]+)", url)
    if m:
        return m.group(1)
    return None


def _ensure_folder(service, name: str, parent_id: Optional[str]) -> Optional[str]:
    q = ["mimeType = 'application/vnd.google-apps.folder'", f"name = '{name}'", "trashed = false"]
    if parent_id:
        q.append(f"'{parent_id}' in parents")
    res = service.files().list(q=" and ".join(q), fields="files(id, name)", pageSize=1).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    # create
    body = {"name": name, "mimeType": _DRIVE_FOLDER_MIME}
    if parent_id:
        body["parents"] = [parent_id]
    try:
        created = service.files().create(body=body, fields="id").execute()
        return created.get("id")
    except HttpError:
        return None


def ingest_event_attachments(tool_context: Any, event: dict, parent_root: str = "MeetingPrep") -> List[DocumentReference]:
    """
    Best-effort: create MeetingPrep/<eventId> folder and add Drive shortcuts for any Calendar attachments
    that reference Drive files. If lacking write scope/permission, fall back to returning original links.
    """
    settings = load_settings()
    creds = get_google_creds_from_tool_context(tool_context, settings.auth_id)
    service = build("drive", "v3", credentials=creds)

    event_id = event.get("id", "")
    attachments = event.get("attachments", [])
    description = event.get("description", "") or ""

    # Collect candidate drive file ids from attachments and description URLs
    file_ids: List[str] = []
    for att in attachments:
        fid = att.get("fileId") or _parse_drive_id_from_url(att.get("fileUrl", ""))
        if fid:
            file_ids.append(fid)
    for url in re.findall(r"https?://\S+", description):
        fid = _parse_drive_id_from_url(url)
        if fid:
            file_ids.append(fid)

    # Deduplicate
    seen = set()
    file_ids = [fid for fid in file_ids if not (fid in seen or seen.add(fid))]

    doc_refs: List[DocumentReference] = []

    # Try to ensure folder structure
    root_id = _ensure_folder(service, parent_root, None)
    event_folder_id = _ensure_folder(service, event_id, root_id) if root_id else None

    for fid in file_ids:
        try:
            fmeta = service.files().get(fileId=fid, fields="id, name, mimeType, webViewLink").execute()
            link = fmeta.get("webViewLink", f"https://drive.google.com/file/d/{fid}/view")
            doc_refs.append(
                DocumentReference(
                    id=fid,
                    title=fmeta.get("name", fid),
                    link=link,
                    mime_type=fmeta.get("mimeType", ""),
                    source="calendar-attachment",
                )
            )

            # Attempt to create a shortcut inside the event folder
            if event_folder_id:
                shortcut_body = {
                    "name": fmeta.get("name", fid),
                    "mimeType": _DRIVE_SHORTCUT_MIME,
                    "parents": [event_folder_id],
                    "shortcutDetails": {"targetId": fid},
                }
                try:
                    service.files().create(body=shortcut_body, fields="id").execute()
                except HttpError:
                    # Insufficient permissions or read-only scope; ignore
                    pass
        except HttpError:
            # Fallback only with id
            doc_refs.append(
                DocumentReference(
                    id=fid,
                    title=fid,
                    link=f"https://drive.google.com/file/d/{fid}/view",
                    mime_type="",
                    source="calendar-attachment",
                )
            )

    return doc_refs
