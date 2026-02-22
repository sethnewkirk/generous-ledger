# Research: External Data Integration for Generous Ledger

**Date:** 2026-02-21
**Context:** How to hook into external data sources and integrate them into the Obsidian vault automatically, so the steward has richer context for daily briefings and on-demand interactions.

## Executive Summary

The steward needs data from the user's life — calendar events, health metrics, financial summaries, task states, reading highlights — to fulfill its duty of faithful stewardship. Currently all profile data is manually entered during onboarding. This research explores how to make the vault a living mirror of the user's commitments and patterns by automatically syncing external data sources into structured markdown files.

The key architectural insight: **the vault is already the single source of truth** (DESIGN.md decision #1). External data should flow INTO the vault as markdown with structured frontmatter. The steward (Claude) reads vault files, never queries APIs directly. This means the integration problem is cleanly separated: sync adapters write markdown → steward reads markdown.

---

## Architecture: The Adapter Pattern

### Current Architecture (from DESIGN.md)

```
External Data Sources → [sync adapters] → Vault (Markdown) → Claude (reasoning) → Vault (updates)
```

The design already calls for this pattern but nothing is implemented yet. The reasoning engine is model-agnostic and reads markdown — adding data sources means writing new adapters, not changing core logic.

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  COLLECTION LAYER (runs outside Obsidian)                       │
│                                                                 │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────┐ ┌──────────┐   │
│  │ Calendar │ │  Health   │ │ YNAB   │ │Tasks │ │ Readwise │   │
│  │ Adapter  │ │  Adapter  │ │Adapter │ │Adapt.│ │ Adapter  │   │
│  └────┬─────┘ └────┬─────┘ └───┬────┘ └──┬───┘ └────┬─────┘   │
│       │             │           │          │          │          │
│       ▼             ▼           ▼          ▼          ▼          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Vault Writer (shared lib)                    │   │
│  │  - Creates/updates .md files with YAML frontmatter       │   │
│  │  - Idempotent writes (won't duplicate on re-run)         │   │
│  │  - Respects file naming conventions (kebab-case)         │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │ writes .md files
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  VAULT (~/Documents/Achaean/)                                   │
│                                                                 │
│  data/                                                          │
│    calendar/     ← event files with frontmatter                 │
│    health/       ← daily metric summaries                       │
│    finance/      ← monthly/weekly budget summaries              │
│    tasks/        ← active task snapshots                        │
│    reading/      ← highlights (managed by Readwise plugin)      │
│    weather/      ← daily weather context                        │
│                                                                 │
│  *.base files    ← table views over data/ folders               │
│                                                                 │
│  profile/        ← existing user model (people, commitments)    │
└────────────────────────┬────────────────────────────────────────┘
                         │ reads .md files
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEWARD (Claude Code CLI)                                      │
│  - Reads profile/ + data/ for context                           │
│  - Daily briefing scans data/ folders                           │
│  - On-demand interactions load relevant data files              │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Adapters run OUTSIDE Obsidian** — as standalone scripts triggered by cron/launchd, not as Obsidian plugin code. This means:
   - They work even when Obsidian is closed
   - They can be written in Python (better library ecosystem for APIs)
   - The plugin stays focused on UI and steward interaction
   - Testing is simpler (no Obsidian runtime needed)

2. **Vault as the integration bus** — adapters write markdown, steward reads markdown. No shared database, no message queue. The filesystem IS the integration layer.

3. **Frontmatter-first** — all structured data in YAML frontmatter so Obsidian Bases can query it. File bodies contain human-readable summaries.

4. **Idempotent writes** — running an adapter twice for the same data should not create duplicates. Use deterministic file names (e.g., `2026-02-21-events.md` or `event-{google-event-id}.md`).

5. **Privacy tiers** — not all data is equally sensitive. Weather is public; finance is critical. Storage and retention should reflect this.

---

## Data Source Assessment

### Tier 1: High Value, Low Friction (Do First)

#### Google Calendar
- **API**: Google Calendar API v3, OAuth 2.0
- **Sync strategy**: Sync tokens for incremental updates. `events.list()` with `syncToken` returns only changes since last sync. Webhook notifications via Google Pub/Sub for real-time updates (optional, requires GCP project).
- **Data to extract**: Event title, start/end time, location, attendees (names only), description
- **Output format**: One file per day (`data/calendar/2026-02-21.md`) with events listed. Frontmatter includes date, event count, has-conflicts flag.
- **Value for steward**: Knows what the user has today, can reference in briefings, can identify scheduling conflicts with commitments
- **Difficulty**: Low-Medium (Google OAuth is well-documented)
- **Privacy**: Low risk (event titles/times, not content of meetings)

#### Weather (Open-Meteo)
- **API**: Open-Meteo free API, no key needed
- **Sync strategy**: Daily cron job fetches forecast
- **Data to extract**: High/low temp, precipitation, conditions, sunrise/sunset
- **Output format**: Appended to daily calendar file or separate `data/weather/2026-02-21.md`
- **Value for steward**: Context for briefings ("dress warm today"), pattern correlation with health/mood
- **Difficulty**: Very Low (no auth, simple REST)
- **Privacy**: None

#### Readwise (Reading Highlights)
- **API**: Readwise API + official Obsidian plugin
- **Sync strategy**: Use the existing official Readwise Obsidian plugin — it already syncs highlights into vault with customizable templates
- **Output format**: Managed by Readwise plugin (configurable folder, templates)
- **Value for steward**: Can reference what the user is reading, surface relevant highlights
- **Difficulty**: Very Low (plugin already exists and works well)
- **Privacy**: Low

### Tier 2: High Value, Medium Friction

#### Apple Health
- **API**: No remote API. Must export XML from Health app or use "Health Auto Export" iOS app
- **Sync strategy**:
  - Option A: Health Auto Export app pushes data to a local REST endpoint, adapter writes to vault
  - Option B: Periodic manual XML export, parsed by Python script
  - Option C: Apple Health MCP Server (DuckDB-based) for querying, adapter writes summaries
- **Data to extract**: Sleep duration/quality, resting heart rate, HRV, step count, active minutes, exercise sessions
- **Output format**: Daily summary file `data/health/2026-02-21.md` with metrics in frontmatter
- **Value for steward**: Can identify patterns ("sleep has declined 3 consecutive nights"), correlate with commitments ("you've been working late"), accountability ("gym consistency commitment is stalling")
- **Difficulty**: Medium (Apple's walled garden makes automation harder)
- **Privacy**: Medium (health data is personal but not financial)

#### YNAB (Finance)
- **API**: YNAB API v1, Personal Access Token (simple auth)
- **Sync strategy**: Delta sync via `last_knowledge_of_server` parameter
- **Data to extract**: Category spending summaries, budget vs actual, account balances (aggregated), upcoming scheduled transactions
- **Output format**: Weekly or monthly summary `data/finance/2026-02-week-08.md`. Only aggregated data — never individual transactions in the vault.
- **Value for steward**: "Dining out is 15% over budget this month", "credit card payment due in 3 days"
- **Difficulty**: Low (user already has penny-wise with YNAB integration)
- **Privacy**: High (financial data — store only summaries, never raw transactions or account numbers)

### Tier 3: Medium Value, Low-Medium Friction

#### Todoist (Tasks)
- **API**: Sync API v9 with incremental sync tokens, or REST API v1
- **Sync strategy**: Sync tokens for delta updates
- **Data to extract**: Active tasks with due dates, completed tasks (for journaling), project structure
- **Output format**: Active tasks snapshot `data/tasks/active.md` updated on each sync. Completed tasks appended to daily note.
- **Value for steward**: Cross-reference tasks with commitments, identify overdue items, surface in briefings
- **Difficulty**: Low-Medium
- **Privacy**: Low
- **Duplication concern**: Need to decide if Obsidian or Todoist is the task system of record. Recommendation: Todoist for capture/execution, Obsidian for reflection/archive.

#### Contacts (Google/Apple via CardDAV)
- **API**: Google People API or CardDAV protocol
- **Sync strategy**: Full sync periodically (contacts change rarely)
- **Data to extract**: Name, email, phone, organization, birthday
- **Value for steward**: Enriches `profile/people/` files with contact details, birthday reminders
- **Difficulty**: Medium (CardDAV is verbose XML)
- **Privacy**: Medium (other people's PII)

### Tier 4: Skip or Defer

#### Email (Gmail)
- **Why defer**: High privacy risk, complex auth (Google security review for sensitive scopes), low signal-to-noise ratio. The steward doesn't need to read emails — it needs to know about commitments and obligations, which come from calendar, tasks, and direct user input.
- **If pursued later**: Metadata only (sender, subject, date). Never store message bodies.

#### Social Media / Messaging
- **Why skip**: APIs are expensive/restricted (Twitter: $100/mo), messaging apps have no APIs (iMessage, WhatsApp), privacy risk is extreme, and value for a virtue-ethics steward is minimal.

#### Location Tracking
- **Why defer**: Requires always-on tracking (OwnTracks), privacy implications, and calendar event locations are a good enough proxy.

---

## Obsidian Integration Mechanisms

### How Data Gets Into the Vault

Ranked by recommendation for this project:

1. **Direct file writing** (RECOMMENDED) — Python/Node scripts write `.md` files directly into the vault folder. Obsidian detects filesystem changes and indexes them. Simplest, most reliable, no plugin dependency.

2. **Obsidian CLI (1.12+)** — `obsidian create <path> --content "..."` for files, `obsidian daily:prepend` for daily notes. Good for enriching daily notes with weather/calendar data.

3. **Plugin with registerInterval + requestUrl** — For data that benefits from Obsidian-aware context. The plugin polls APIs and writes files via the Vault API. Good for tight integration but adds complexity to the plugin.

4. **Existing community plugins** — Readwise already has an excellent plugin. Don't rebuild what exists.

### How the Steward Reads Data

The steward (Claude Code CLI) already reads markdown files via Read/Write tools. The daily briefing protocol in CLAUDE.md would be extended:

```
Current:
1. Scan profile/people/ for birthdays
2. Scan profile/commitments/ for status
3. Check patterns.md
4. Read current.md

Extended:
1. Scan profile/people/ for birthdays
2. Scan profile/commitments/ for status
3. Scan data/calendar/ for today's events
4. Scan data/health/ for recent metrics (sleep, HRV trends)
5. Scan data/finance/ for budget alerts
6. Scan data/tasks/ for overdue items
7. Check patterns.md
8. Read current.md
```

### Obsidian Bases for User-Facing Views

Each data folder gets a `.base` file at vault root for table views:

- `Calendar.base` — upcoming events, filterable by date range
- `Health.base` — daily metrics, charts via Obsidian chart plugins
- `Finance.base` — spending by category, budget status
- `Tasks.base` — active tasks, overdue items, by project

Bases query frontmatter properties using filter syntax like:
```yaml
filters:
  and:
    - "file.inFolder(\"data/calendar\")"
    - "date >= now() - \"7 days\""
```

---

## Comparison with OpenClaw

OpenClaw is the most similar project in scope — a personal AI assistant that connects to 50+ external services. Key architectural differences:

| Aspect | OpenClaw | Generous Ledger (proposed) |
|--------|----------|---------------------------|
| **Core** | Agentic AI with tool use | Virtue ethics steward |
| **Data flow** | Skills query APIs in real-time | Adapters pre-sync to vault |
| **Storage** | Session memory + gateway state | Markdown files in vault |
| **UI** | Messaging platforms (WhatsApp, etc.) | Obsidian (notes + terminal) |
| **Auth** | Credential store (`~/.openclaw/credentials/`) | Per-adapter config files |
| **Scheduling** | Built-in scheduler | launchd/cron (macOS native) |
| **Scale** | 140k+ stars, 50+ integrations | Personal project, focused set |

**What to learn from OpenClaw:**
1. **Selective context injection** — OpenClaw doesn't inject all skills into every prompt. Similarly, the steward should only load data files relevant to the current request, not the entire data/ directory.
2. **Credential management** — OpenClaw stores credentials at `~/.openclaw/credentials/` with 0600 permissions. We should similarly isolate API keys from the vault.
3. **MCP bridge** — OpenClaw has an MCP bridge for external tool access. The steward could potentially expose vault data as MCP resources.

**What NOT to copy from OpenClaw:**
1. Real-time API queries during conversation — the vault-first approach is better for privacy and reliability
2. Gateway daemon complexity — overkill for a single-user system
3. Multi-platform messaging — Obsidian is the only UI

---

## Similar Projects Worth Studying

### HPI (Human Programming Interface)
Python library by karlicoss providing unified API to personal data. Offline-first, works against local data exports. Most architecturally pure approach — each data source is a Python module. Fork by purarue adds more modules.

### Dogsheep
Collection of `{service}-to-sqlite` CLI tools by Simon Willison. Exports personal data into SQLite, queryable via Datasette. Key insight: SQLite as universal intermediate format. The `healthkit-to-sqlite` tool is directly relevant for Apple Health data.

### n8n
Self-hosted workflow automation (400+ integrations). Could serve as the orchestration layer for data pipelines. Visual workflow builder, webhook support, generous free tier for self-hosting. However, may be overkill when simple Python scripts + cron achieve the same result.

---

## Credential Management

API keys and OAuth tokens should NOT live in the Obsidian vault (it syncs to cloud). Proposed approach:

```
~/.config/generous-ledger/
  credentials/
    google-calendar.json     # OAuth tokens
    ynab.json                # Personal access token
    readwise.json            # API token
    health-auto-export.json  # Webhook secret
  config.yaml                # Adapter settings (sync intervals, vault path, etc.)
```

Permissions: `chmod 700 ~/.config/generous-ledger/credentials/`

The adapter scripts read credentials from this directory, never from the vault.

---

## Scheduling

macOS launchd is already used for the daily briefing (`com.generous-ledger.daily-briefing.plist`). Additional agents:

```
com.generous-ledger.sync-calendar.plist    — every 30 minutes
com.generous-ledger.sync-health.plist      — every 6 hours
com.generous-ledger.sync-weather.plist     — daily at 5:30 AM (before briefing)
com.generous-ledger.sync-finance.plist     — weekly on Monday
com.generous-ledger.sync-tasks.plist       — every 15 minutes
```

Each plist runs a Python/Node script that:
1. Reads credentials from `~/.config/generous-ledger/credentials/`
2. Fetches data from the API (with incremental sync where possible)
3. Writes/updates markdown files in the vault
4. Logs to `~/.local/log/generous-ledger/`

---

## Open Questions

1. **Health Auto Export vs manual XML** — Is the iOS app reliable enough for continuous sync? Or should we design around periodic manual exports?
2. **Todoist vs Obsidian Tasks** — Which is the user's primary task system? This determines sync direction.
3. **How much calendar detail?** — Just event titles/times, or also attendees and descriptions?
4. **Finance granularity** — Weekly summaries? Monthly? Should the steward know about individual large transactions?
5. **Bases performance** — How do Bases perform with hundreds or thousands of data files? May need to aggregate rather than create individual files per data point.
6. **Obsidian Sync conflicts** — When adapters write files that are also synced via Obsidian Sync to mobile, how are conflicts handled?
