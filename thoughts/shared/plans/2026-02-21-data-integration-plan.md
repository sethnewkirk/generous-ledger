# Plan: External Data Integration for Generous Ledger

**Date:** 2026-02-21
**Research:** `thoughts/shared/research/2026-02-21-external-data-integration.md`
**Status:** Draft — awaiting user review

## Goal

Give the steward access to the user's calendar, health metrics, financial summaries, task state, reading highlights, and weather context — automatically, without manual data entry. Data flows into the vault as structured markdown. The steward reads it during briefings and on-demand interactions.

## Principles

1. **Vault is truth** — adapters write markdown, steward reads markdown, user inspects markdown
2. **Adapters are dumb pipes** — fetch, transform, write. No reasoning, no AI.
3. **Steward is the brain** — reads data files, applies virtue framework, generates insight
4. **Privacy by tier** — weather is public, health is personal, finance is sensitive. Storage reflects this.
5. **Idempotent everything** — re-running an adapter produces the same result, not duplicates
6. **Incremental where possible** — use sync tokens, delta queries, last-modified timestamps

## Vault Structure

```
data/
  calendar/
    2026-02-21.md          # Today's events
    2026-02-22.md          # Tomorrow's events
    ...
  health/
    2026-02-21.md          # Daily health summary
    2026-02-20.md
    ...
  finance/
    2026-02-week-08.md     # Weekly spending summary
    2026-01-summary.md     # Monthly summary
    ...
  tasks/
    active.md              # Current active tasks snapshot
    completed-2026-02-21.md # Completed today
    ...
  weather/
    2026-02-21.md          # Today's weather
    ...
  reading/
    (managed by Readwise plugin)
```

## Frontmatter Schemas

### Calendar Event Day (`data/calendar/YYYY-MM-DD.md`)
```yaml
type: calendar-day
date: 2026-02-21
event_count: 4
has_conflicts: false
source: google-calendar
last_synced: 2026-02-21T06:00:00-05:00
tags: [data, calendar]
```

Body: Human-readable list of events with times, locations, attendees.

### Health Daily (`data/health/YYYY-MM-DD.md`)
```yaml
type: health-daily
date: 2026-02-21
sleep_hours: 7.2
sleep_quality: good       # poor/fair/good/excellent (derived from metrics)
resting_hr: 58
hrv: 45
steps: 8432
active_minutes: 32
exercise: true
exercise_type: "strength training"
exercise_duration: 45
source: apple-health
last_synced: 2026-02-21T08:00:00-05:00
tags: [data, health]
```

Body: Human-readable summary with trends ("Sleep improved from 6.1h avg last week").

### Finance Weekly (`data/finance/YYYY-WW.md`)
```yaml
type: finance-weekly
week: 2026-W08
period_start: 2026-02-17
period_end: 2026-02-23
total_spent: 842.50
over_budget_categories: [dining-out, entertainment]
upcoming_bills: 2
source: ynab
last_synced: 2026-02-21T07:00:00-05:00
tags: [data, finance]
```

Body: Category breakdown, budget vs actual, upcoming scheduled transactions.

### Tasks Active (`data/tasks/active.md`)
```yaml
type: tasks-active
task_count: 12
overdue_count: 2
source: todoist
last_synced: 2026-02-21T06:15:00-05:00
tags: [data, tasks]
```

Body: Grouped by project, with due dates and priorities.

### Weather Daily (`data/weather/YYYY-MM-DD.md`)
```yaml
type: weather-daily
date: 2026-02-21
high_f: 45
low_f: 32
condition: partly-cloudy
precipitation_chance: 20
sunrise: "06:52"
sunset: "17:48"
source: open-meteo
tags: [data, weather]
```

Body: Brief forecast narrative.

## Implementation Phases

### Phase 0: Infrastructure (Foundation)

**What:** Create the adapter framework — shared utilities, credential management, scheduling, logging.

**Files to create:**
```
scripts/adapters/
  lib/
    vault_writer.py        # Shared: write markdown with frontmatter to vault
    credentials.py         # Shared: read credentials from ~/.config/generous-ledger/
    logging_config.py      # Shared: logging to ~/.local/log/generous-ledger/
    sync_state.py          # Shared: track sync tokens, last-synced timestamps
  weather.py               # First adapter (simplest, validates framework)
  install-schedules.sh     # Install all launchd plists
```

**Credential store:**
```
~/.config/generous-ledger/
  credentials/             # chmod 700
    google-calendar.json
    ynab.json
    readwise.json
  config.yaml              # vault_path, sync intervals, adapter toggles
  state/                   # sync tokens, last-synced timestamps
    calendar-sync-token.json
    health-last-export.json
    finance-knowledge.json
    tasks-sync-token.json
```

**Vault writer API:**
```python
from lib.vault_writer import VaultWriter

writer = VaultWriter(vault_path="~/Documents/Achaean")

writer.write_data_file(
    folder="weather",
    filename="2026-02-21.md",
    frontmatter={"type": "weather-daily", "date": "2026-02-21", ...},
    body="Partly cloudy, high of 45°F. Light winds from the northwest.",
    overwrite=True  # idempotent: replace if exists
)
```

**Estimate:** Small. Mostly boilerplate — credential reading, YAML writing, file management.

### Phase 1: Weather + Calendar (Quick Wins)

**Weather adapter** (`scripts/adapters/weather.py`):
- Fetch from Open-Meteo API (no auth needed)
- Write `data/weather/YYYY-MM-DD.md`
- Schedule: daily at 5:30 AM (before briefing at 6:00 AM)

**Google Calendar adapter** (`scripts/adapters/calendar.py`):
- OAuth 2.0 with Google Calendar API v3
- First run: full sync, store sync token
- Subsequent runs: incremental sync using stored token
- Write `data/calendar/YYYY-MM-DD.md` for today + next 7 days
- Schedule: every 30 minutes

**Base views:**
- `Calendar.base` at vault root — table of upcoming events
- Weather data embedded in daily note via briefing

**CLAUDE.md updates:**
- Daily Briefing Protocol extended to scan `data/calendar/` and `data/weather/`
- Add data/ section describing what's available

### Phase 2: Health Metrics

**Apple Health adapter** (`scripts/adapters/health.py`):
- Parse Apple Health XML export (user manually exports periodically)
- OR integrate with Health Auto Export iOS app (pushes to local endpoint)
- Extract: sleep, resting HR, HRV, steps, active minutes, exercises
- Write `data/health/YYYY-MM-DD.md` with metrics in frontmatter
- Calculate trends (7-day averages, week-over-week changes)
- Schedule: every 6 hours (for Health Auto Export) or on-demand (for XML)

**Dependencies:** User needs to choose between manual XML export and Health Auto Export app.

**Base views:**
- `Health.base` at vault root — daily metrics table, filterable by date range

**CLAUDE.md updates:**
- Daily Briefing scans `data/health/` for sleep/activity trends
- Patterns.md can reference health data for accountability observations

### Phase 3: Finance Summaries (YNAB)

**YNAB adapter** (`scripts/adapters/finance.py`):
- YNAB API v1 with Personal Access Token
- Delta sync via `last_knowledge_of_server`
- Extract: category spending, budget vs actual, upcoming bills
- Write `data/finance/YYYY-WNN.md` (weekly) and `data/finance/YYYY-MM-summary.md` (monthly)
- NEVER store individual transactions or account numbers
- Schedule: weekly on Monday at 6 AM

**Note:** User already has penny-wise project. This adapter could potentially reuse penny-wise's YNAB client code or be a simpler wrapper.

**Base views:**
- `Finance.base` at vault root — spending by category, budget status

### Phase 4: Tasks (Todoist)

**Todoist adapter** (`scripts/adapters/tasks.py`):
- Todoist Sync API v9 with sync tokens
- Extract: active tasks (title, due date, priority, project, labels), recently completed
- Write `data/tasks/active.md` (overwritten each sync) and `data/tasks/completed-YYYY-MM-DD.md`
- Schedule: every 15 minutes

**Design decision needed:** Is Todoist the user's primary task system? If so, this is high value. If Obsidian Tasks is primary, this adapter may not be needed.

### Phase 5: Readwise (Reading Highlights)

**Approach:** Use the existing official Readwise Obsidian plugin. No custom adapter needed.

**Setup:**
1. Install Readwise plugin from Obsidian community plugins
2. Configure sync folder (e.g., `data/reading/`)
3. Configure template to include frontmatter with source, author, highlight count
4. Enable auto-sync

**CLAUDE.md updates:**
- Steward can reference reading highlights when relevant to conversations
- Daily briefing can note new highlights added

### Phase 6: Steward Intelligence Upgrade

**What:** Update CLAUDE.md and daily briefing to USE all the new data.

**CLAUDE.md changes:**
- New "Data Sources" section describing `data/` folder structure
- Updated Daily Briefing Protocol to scan all data folders
- Updated Interaction Protocols: load relevant data files for on-demand requests
- Guidelines for when to reference which data (don't dump everything into every response)

**Daily briefing enhancements:**
```
Morning Report — February 21, 2026

SCHEDULE
- 9:00 AM: Team standup (virtual)
- 11:30 AM: Dentist appointment (123 Main St)
- 2:00 PM: 1:1 with manager

HEALTH
- Sleep: 6.4 hours (below your 7h target, third night in a row)
- Resting HR: 62 bpm (elevated from your 58 baseline)

OBLIGATIONS
- Kate's birthday in 5 days. No gift purchased yet (commitment: gift-for-kate, status: not-started).
- Gym consistency commitment: no exercise logged in 4 days.

FINANCE
- Dining out this week: $127 (budget: $100). On track to exceed monthly budget by ~20%.

TASKS
- 2 overdue: "Drop classes" (due yesterday), "Submit expense report" (due 2 days ago)

WEATHER
- 45°F, partly cloudy. Good day for the walk you've been deferring.

OBSERVATION
Your sleep has declined three consecutive nights while work hours have increased.
The dentist appointment and the meeting are both important — but the pattern of
compressed rest warrants attention. Consider whether tonight can be protected.
```

### Phase 7: Base Views and Dashboard

**Create comprehensive Base views:**
- `Dashboard.base` — composite view: today's events + health metrics + overdue tasks + budget alerts
- `Calendar.base` — next 7 days of events
- `Health.base` — daily metrics with trend columns
- `Finance.base` — weekly spending by category
- `Tasks.base` — active tasks sorted by due date

**Optional: Daily note template**
Auto-populate daily notes with weather, calendar, and health data using Templater or the briefing script.

---

## Scheduling Overview

| Adapter | Frequency | Schedule | Dependencies |
|---------|-----------|----------|-------------|
| Weather | Daily | 5:30 AM | None |
| Calendar | Every 30 min | */30 * * * * | Google OAuth |
| Health | Every 6 hours | 0 */6 * * * | Health Auto Export OR manual XML |
| Finance | Weekly | Monday 6:00 AM | YNAB PAT |
| Tasks | Every 15 min | */15 * * * * | Todoist token |
| Readwise | Managed by plugin | Auto | Readwise API key |
| Daily Briefing | Daily | 6:00 AM | All adapters should have run |

## Technology Choices

- **Adapter language:** Python 3.11+ (best library ecosystem for APIs, easy YAML/markdown generation)
- **Package management:** uv (fast, user already uses it)
- **Scheduling:** macOS launchd (already used for daily briefing)
- **Credential storage:** `~/.config/generous-ledger/credentials/` with 0700 permissions
- **Sync state:** JSON files in `~/.config/generous-ledger/state/`
- **Logging:** `~/.local/log/generous-ledger/` (consistent with existing briefing logs)

## What This Does NOT Include

- **Real-time streaming** — all adapters are batch/polling. Real-time would add complexity without proportional value.
- **Two-way sync** — data flows INTO the vault only. The steward doesn't push back to external systems.
- **Email integration** — deferred due to high privacy risk and low signal-to-noise.
- **Social media** — skipped entirely (APIs expensive/restricted, low value for virtue-ethics steward).
- **Location tracking** — deferred (calendar locations are a good proxy).
- **Plugin-internal data fetching** — adapters run externally to keep the plugin focused on UI.

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Google OAuth complexity | Use google-auth-oauthlib Python library; follow Google's quickstart guide |
| Apple Health data access | Start with manual XML export; evaluate Health Auto Export app later |
| Vault file conflicts with Obsidian Sync | Adapters write to `data/` which syncs one-way (desktop writes, mobile reads) |
| Credential exposure | Credentials live outside vault in `~/.config/` with restrictive permissions |
| API rate limits | Respect per-API limits; calendar (250 quota/sec), YNAB (200/hr), Todoist (generous) |
| Bases performance with many files | Aggregate by day/week rather than per-event files; test with realistic data volumes |
| Scope creep | Each phase is independently valuable; can stop after any phase |

## Open Questions for User

1. **Apple Health**: Do you use an Apple Watch? Would you install Health Auto Export ($3 iOS app) for continuous sync, or prefer periodic manual XML exports?
2. **Todoist**: Is Todoist your primary task manager, or do you use something else?
3. **Finance granularity**: Weekly summaries sufficient, or do you want the steward to know about individual large transactions?
4. **Calendar scope**: Just your primary Google Calendar, or multiple calendars?
5. **Phase priority**: Does this phase ordering make sense, or would you reorder?
6. **Readwise**: Do you use Readwise? If not, what's your reading/highlighting workflow?
