# Meeting Prep Agent – Implementation Plan

## Goals and MVP Scope
- Deliver an AgentSpace experience that prepares a concise brief 30 minutes before a meeting (and on-demand), covering:
  - Agenda/title/description, attendees (Calendar)
  - Direct links to attachments (via Drive workaround)
  - Related Drive documents (top-N)
  - Most recent, relevant Slack messages (by matching meeting title/keywords)
  - Link to previous occurrence notes/transcript (for recurring events)
  - Clear “No preparatory materials” message when nothing is found
- Use ADK on Agent Engine, AgentSpace OAuth, Google Calendar + Drive connectors; include Slack basic integration.

## Acceptance Criteria Mapping
- AC: Prior recurring notes/transcript link and summary → “Historical Context” fetcher + brief section
- AC: 30 minutes pre-meeting brief with document links → scheduler + attachments-to-Drive workaround + link rendering in AgentSpace
- AC: Slack channel summary for meeting title (e.g., #project-phoenix) → Slack fetcher filtered by channel/title keywords
- AC: No materials message → guard clause during synthesis
- AC: Documents labeled and linked → uniform `DocumentReference` rendering in brief

## High-level Architecture
- Agent Engine (ADK) application (root agent + tools)
- AgentSpace as frontend surface (OAuth, delivery target)
- OAuth via AgentSpace (server-side auth; token in tool/agent context)
- Connectors & APIs
  - Google Calendar (events, recurrence, attendees, description)
  - Google Drive (search, file metadata, webView links)
  - Slack Web API (channels.list, conversations.history, search.messages) or channel by convention
- Data Gatherers (tools): CalendarFetcher, DriveSearcher, SlackFetcher, AttachmentIngestion (calendar→drive workaround)
- Synthesizer: LLM prompt templates for narrative + sections
- Scheduler/Trigger: 30-min pre-meeting cron + on-demand command
- Observability: structured logs, tracing via ADK

Sequence (pre-meeting):
1. Trigger (T-30) or manual
2. Retrieve target event (next upcoming within window) + context (recurrence)
3. Gather: prior occurrence artifacts, attachments (workaround), Drive search by title/attendees, Slack messages by title keywords/channel
4. Synthesize brief (sections: Agenda, Key Docs, Slack Summary, Historical Notes, Action Items)
5. Deliver to AgentSpace (render with labeled links)

## Environments & Config
- Projects: `dev`, `staging`, `prod` (or single project with separate Agent Engine apps)
- Config via env:
  - `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `STAGING_BUCKET`
  - `AUTH_ID` (Agentspace Authorization)
  - `AGENT_DISPLAY_NAME`
  - Slack: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` (for Web API usage)
  - Calendar time window & trigger offsets: `BRIEF_LEAD_MINUTES`, `HISTORICAL_LOOKBACK_DAYS`

## Auth & AgentSpace Setup
- Create Authorization (serverSideOauth2) with required scopes:
  - `https://www.googleapis.com/auth/calendar.readonly`
  - `https://www.googleapis.com/auth/drive.readonly`
  - `https://www.googleapis.com/auth/userinfo.email`
- Use `create_authorization.sh` (from PRD) with your `CLIENT_ID/SECRET`.
- Create Agent (ADK) with `create_agent.sh`, bind `AUTH_ID`, and provision reasoning engine.
- Access token retrieval pattern (from PRD) inside tools:
  ```py
  access_token = tool_context.state[f"temp:{auth_id}"]
  creds = Credentials(token=access_token)
  ```

## Data Model (internal)
- `EventContext` { id, summary, description, start, end, attendees[], recurrenceId?, location, organizers[] }
- `DocumentReference` { id, title, link, source: ['calendar-attachment','drive-search','historical'], mimeType }
- `SlackMessage` { ts, user, text, channel, permalink }
- `HistoricalContext` { prevOccurrenceId, notesLink?, transcriptLink?, summary? }
- `Brief` { header, agenda, keyDocs[], historicalNotes, slackSummary, actionItems[], disclaimers[] }

## Retrieval Strategy
- Calendar:
  - Find next event for the user/window; detect recurrence via `recurringEventId`
  - Grab description/agenda/attendees; parse keywords (title, project tags)
- Attachments workaround:
  - Enumerate event’s `attachments` or `description` links; if not accessible, save copies or references into Drive folder by event ID; include Drive links
- Drive search:
  - Query: title, normalized keywords, attendee emails, project codes
  - Time-bounded boolean query: last 90 days (configurable)
  - Return top 5 by recency + type preference (Docs, Slides, Sheets, PDFs)
- Slack:
  - Heuristic: map title slug to `#project-<slug>` if exists; else `search.messages` by title keywords within lookback window
  - Summarize last N relevant messages (e.g., 30) into key bullets (decisions, blockers, links)
- Historical:
  - If recurring, fetch immediate prior occurrence (same `recurringEventId`) and find notes/transcript link (Drive patterns or description link); generate short summary via LLM

## Prompts & Synthesis
- System prompt: “Meeting Brief Synthesizer” with instructions to:
  - Be concise; bullet points; attribute links; add explicit ‘No materials’ when empty
  - Sections order: Agenda → Key Documents → Recent Slack → Historical Decisions/Action Items
- Few-shot examples: 2–3 meeting types (project sync, customer call)
- Safety: strip PII beyond attendee names, avoid external sources for MVP

## Connectors & Tooling (Implementation)
- Tools (Python/ADK):
  - `calendar_fetcher(tool_context)`: build calendar service; get event + recurrence
  - `drive_search(tool_context, query)`: Drive `files.list` with `q` filters
  - `slack_fetcher(context, title, channels[])`: Web API `conversations.list/history` or `search.messages`
  - `attachment_ingest(event)`: copy/save URIs to Drive folder `MeetingPrep/<eventId>/`
  - `synthesizer(contexts)`: call LLM with prompt and gathered content → `Brief`
  - `deliver_agentspace(brief)`: format to AgentSpace panel (labels, links)

## Observability & Ops
- Logging: structured (operation, eventId, userEmail, durationMs, counts)
- Tracing: enable ADK tracing; tag subtool spans
- Metrics: briefs_generated, gather_failures_by_source, avg_latency_ms, token_usage
- Error policy: partial data allowed; degrade gracefully with per-source errors in “disclaimers”

## Performance & Quotas
- Batch Drive and Slack requests; cap counts (Drive top 10 files; Slack last 200 msgs in channel)
- Cache last brief for 30 minutes per event; avoid duplicate fetch on repeated triggers

## Security & Privacy
- Access strictly via user’s AgentSpace OAuth token
- Respect channel/document permissions; do not surface unauthorized content
- Mask tokens; no persistence of tokens
- Retention: brief ephemeral (<= 2 hours post-meeting) unless user saves

## Testing Plan
- Unit: parsers (calendar, drive, slack), prompt builders, renderers
- Integration: live calls behind feature flag in dev project (service account fallback not used)
- E2E scenarios:
  1) Recurring project sync with prior notes/transcript
  2) Meeting with attachments only
  3) New meeting title with Slack channel match
  4) No materials found
  5) Large attendee list; performance sanity
- Synthetic data seeding: sample Drive docs, Slack sandbox channel, test calendar events

## Milestones & Task Breakdown

### M0 – Project Bootstrap (0.5–1 day)
- Adopt repo structure `agents/`, `tools/`, `prompts/`, `config/`, `scripts/`, `tests/` [DONE]
- Add `.env.example` and configuration loader [DONE]
- Verify bootstrap: run basic import of `config.settings.load_settings()` [TODO]

### M1 – AgentSpace OAuth & Agent Registration (1–2 days)
- Run `create_authorization.sh` and `create_agent.sh` using reference code in `sample/` to set up Authorization + Agent [PENDING]
- Implement token retrieval in tool context [DONE via `agents/oauth_util.py`]
- Smoke test: `whoami`, timezone, primary calendar list [DONE via `tools/whoami.py` (call at runtime)]
 - Define ADK agent following `sample/` patterns [IN PROGRESS - `agents/meeting_prep_agent.py`]

### M2 – Calendar Fetcher & Trigger (1–1.5 days)
- Implement `calendar_fetcher` (next event, recurrence lookup) [DONE basic `get_next_event`]
- Implement scheduler (T-30) and on-demand trigger [DONE basic `agents/scheduler.py`, `agents/trigger.py`]
- Unit tests [IN PROGRESS - added `tests/test_scheduler.py`]

### M3 – Drive Search & Attachment Workaround (2–3 days)
- Implement `attachment_ingest` to Drive folder by `eventId` [DONE basic `tools/attachment_ingest.py`]
- Implement `drive_search` with ranking + filters [DONE basic `search_drive`]
- Unit/integration tests (dev project) [PENDING]

### M4 – Slack Integration (1.5–2 days)
- Implement Slack fetcher (channel heuristic + search) [DONE basic `fetch_slack_messages`]
- Summarization prompt for Slack messages [DONE `prompts/slack_summary_prompt.txt`]
- Integration in sandbox workspace [PENDING]

### M5 – Synthesis & Delivery (1–2 days)
- Implement LLM synthesis (sections, templates) [IN PROGRESS - `agents/synthesis.py` renderer]
- Render in AgentSpace panel with labeled links [DONE basic markdown via `agents/delivery.py`]
- Add “no materials” message path [DONE basic handling in `build_panel_markdown`]

### M6 – QA, Telemetry, Demo (1–2 days)
- Add metrics, tracing tags
- Full E2E against seeded dataset
- Record demo and finalize README

Total: ~8–11 working days for MVP.

## Definition of Done
- All ACs satisfied in dev; documented setup; green E2E runs; demo brief matches design; telemetry dashboards for core KPIs

## Risks & Mitigations
- Slack relevance quality → start with channel heuristic; iterate with vector similarity later
- Calendar attachments access limitations → enforce Drive copy + link policy; document manual steps
- Rate limits → batch & cap; exponential backoff; caching
- OAuth scope misconfig → use PRD scripts; test each API early

## Out of Scope (MVP)
- External web/company enrichment
- Writing back to Calendar/Slack
- Non-Google data sources beyond Slack

## Operational Runbook (Quick Start)
1. Create Authorization (Agentspace) → run `create_authorization.sh` with Calendar/Drive scopes
2. Create Agent (ADK) → run `create_agent.sh` with `AUTH_ID`
3. Configure `.env` with project, auth, slack tokens
4. Deploy app (ADK Agent Engine) and verify token handoff via `whoami`
5. Seed sample events/docs/slack messages; run on-demand brief
6. Enable scheduler (T-30) and validate automatic brief delivery

## Repository Skeleton (suggested)
```
agents/
  meeting_prep_agent.py
  synthesis.py
  delivery.py
  __init__.py
tools/
  calendar_fetcher.py
  drive_search.py
  slack_fetcher.py
  attachment_ingest.py
prompts/
  brief_system.txt
  brief_examples.json
config/
  settings.py
scripts/
  create_authorization.sh
  create_agent.sh
tests/
  test_calendar_fetcher.py
  test_drive_search.py
  test_slack_fetcher.py
  test_synthesis.py
```

## References
- PRD Use Case 2: Meeting Prep Agent (this repo `prd/Use Case 2_ Meeting Prep Agent PRD.md`)
- Sample ADK code (PRD excerpt) for OAuth token usage and agent deployment
