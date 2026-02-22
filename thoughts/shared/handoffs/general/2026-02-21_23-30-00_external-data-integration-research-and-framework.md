---
date: 2026-02-21T23:30:00-05:00
session_name: general
researcher: claude
git_commit: (uncommitted)
branch: main
repository: generous-ledger
topic: "External Data Integration — Research, Architecture, and Adapter Framework"
tags: [research, architecture, data-integration, adapters, automation]
status: complete
last_updated: 2026-02-21
last_updated_by: claude
type: research_and_implementation
---

# Handoff: External Data Integration Research & Adapter Framework

## Task(s)

- **Research external data integration** (complete) — Investigated how to hook into external data sources (calendar, health, finance, tasks, reading, weather) and flow that data into the Obsidian vault automatically. Studied OpenClaw, HPI, Dogsheep, n8n, and the Obsidian plugin ecosystem.
- **Design adapter architecture** (complete) — Designed the collection layer, vault structure, frontmatter schemas, scheduling strategy, and credential management.
- **Build adapter framework** (complete) — Created shared Python libraries (vault_writer, credentials, sync_state, logging) and validated with a working weather adapter.
- **Write all adapters** (complete) — Weather (working, tested), Google Calendar, YNAB finance, Apple Health, and Todoist tasks adapters written.
- **Create Obsidian Base view** (complete) — Weather.base deployed to vault.
- **Write scheduling infrastructure** (complete) — install-schedules.sh for all adapter LaunchAgents.

## Critical References

- `thoughts/shared/research/2026-02-21-external-data-integration.md` — Full research document with ecosystem analysis, data source assessment, Obsidian API capabilities, OpenClaw comparison
- `thoughts/shared/plans/2026-02-21-data-integration-plan.md` — Implementation plan with 7 phases, frontmatter schemas, scheduling overview, technology choices
- `CLAUDE.md` — Current steward instructions (will need updates for data source awareness)
- `docs/DESIGN.md` — System architecture (mentions sync adapters as future feature)

## Recent Changes

**New files (in git repo, uncommitted):**

Adapter framework:
- `scripts/adapters/lib/__init__.py` — Package init
- `scripts/adapters/lib/vault_writer.py` — Write markdown with YAML frontmatter to vault
- `scripts/adapters/lib/credentials.py` — Read credentials from `~/.config/generous-ledger/`
- `scripts/adapters/lib/sync_state.py` — Track sync tokens and last-synced timestamps
- `scripts/adapters/lib/logging_config.py` — Shared logging to `~/.local/log/generous-ledger/`

Adapters:
- `scripts/adapters/weather.py` — **Tested and working.** Fetches from Open-Meteo (free, no API key), writes `data/weather/YYYY-MM-DD.md`
- `scripts/adapters/calendar.py` — Google Calendar OAuth + sync. Needs credentials to run.
- `scripts/adapters/finance.py` — YNAB budget summaries. Needs YNAB Personal Access Token.
- `scripts/adapters/health.py` — Apple Health XML export parser. Needs export file.
- `scripts/adapters/tasks.py` — Todoist active tasks snapshot. Needs Todoist API token.

Infrastructure:
- `scripts/adapters/install-schedules.sh` — Install macOS LaunchAgents for all adapters
- `scripts/adapters/config.example.yaml` — Example config file

Research & plans:
- `thoughts/shared/research/2026-02-21-external-data-integration.md`
- `thoughts/shared/plans/2026-02-21-data-integration-plan.md`

**Vault files (not in git):**
- `~/Documents/Achaean/data/weather/2026-02-21.md` — Today's weather (tested output)
- `~/Documents/Achaean/data/weather/2026-02-22.md` — Tomorrow's weather
- `~/Documents/Achaean/data/weather/2026-02-23.md` — Day after tomorrow
- `~/Documents/Achaean/Weather.base` — Table view over weather data

## Learnings

### Architecture: Vault as Integration Bus
The key insight: external data flows INTO the vault as markdown, the steward reads markdown. No database, no message queue — the filesystem IS the integration layer. This aligns perfectly with DESIGN.md decision #1 (vault as single source of truth) and keeps the system model-agnostic.

### OpenClaw Comparison
OpenClaw (140k+ GitHub stars) uses a similar pattern — skills/adapters that query external APIs — but processes data in real-time during conversations. Our approach pre-syncs data to vault files, which is better for:
1. Privacy (data stays local, never sent to APIs during conversation)
2. Reliability (briefings work even if an API is down)
3. Inspectability (user can see exactly what data the steward has)

### Adapters Should Run Outside Obsidian
Python scripts + cron/launchd is simpler and more reliable than in-plugin data fetching. The plugin stays focused on UI and steward interaction. Adapters can be written in any language, tested independently, and run when Obsidian is closed.

### Frontmatter-First Design
Obsidian Bases only queries YAML frontmatter (not Dataview inline fields). All structured data goes in frontmatter. File bodies are human-readable summaries. This ensures data is queryable via both Bases and Dataview.

### Weather Adapter Validates Framework
The weather adapter proved the framework works end-to-end: fetch API → shared vault writer → structured markdown in vault → Obsidian picks it up → Bases can query it. No changes needed to the core pattern for other adapters.

## Post-Mortem

### What Worked
- **Parallel research agents**: Four agents ran simultaneously covering codebase architecture, OpenClaw/ecosystem, Obsidian API, and data source details. Comprehensive coverage in minutes.
- **Simple framework first**: Building vault_writer.py + weather.py before anything else validated the entire architecture quickly.
- **Real data validation**: The weather adapter produced real weather files that Obsidian can actually render. Not just a design doc.

### What Needs Review
- **Adapter priority**: The plan proposes weather → calendar → health → finance → tasks. User may want a different order.
- **Health data source**: Manual XML export vs Health Auto Export app — user needs to decide.
- **Todoist vs Obsidian Tasks**: Need to know user's primary task system.
- **Finance granularity**: Weekly summaries may be too coarse or too detailed.
- **Calendar scope**: One calendar or multiple?

### Key Decisions
- Decision: Adapters run as external Python scripts, not inside the Obsidian plugin
  - Alternatives: Plugin-internal `registerInterval` + `requestUrl`, n8n workflows
  - Reason: Simpler, more testable, works when Obsidian is closed, better library ecosystem (Python)

- Decision: One file per day for most data types (not per-event)
  - Alternatives: Per-event files, weekly aggregation
  - Reason: Limits file count (Bases performance), provides natural grouping, easy for steward to load

- Decision: Credentials stored in `~/.config/generous-ledger/credentials/` not in vault
  - Alternatives: Obsidian plugin settings, vault `.env` file
  - Reason: Vault syncs to cloud; credentials must never leave the machine

## Artifacts

- `scripts/adapters/weather.py` — Working weather adapter (tested)
- `scripts/adapters/calendar.py` — Google Calendar adapter (needs credentials)
- `scripts/adapters/finance.py` — YNAB adapter (needs credentials)
- `scripts/adapters/health.py` — Apple Health XML parser (needs export)
- `scripts/adapters/tasks.py` — Todoist adapter (needs credentials)
- `scripts/adapters/lib/*` — Shared framework libraries
- `scripts/adapters/install-schedules.sh` — LaunchAgent installer
- `scripts/adapters/config.example.yaml` — Example configuration
- `thoughts/shared/research/2026-02-21-external-data-integration.md` — Full research report
- `thoughts/shared/plans/2026-02-21-data-integration-plan.md` — Implementation plan (7 phases)
- `~/Documents/Achaean/Weather.base` — Weather Base view
- `~/Documents/Achaean/data/weather/*.md` — Sample weather data

## Action Items & Next Steps

### Immediate — Review and Configure
1. **Read the plan** at `thoughts/shared/plans/2026-02-21-data-integration-plan.md` — covers phases, schemas, scheduling
2. **Review research** at `thoughts/shared/research/2026-02-21-external-data-integration.md` — covers ecosystem, comparisons, data source assessment
3. **Answer open questions** (see plan document) — which task manager? health export method? calendar scope?
4. **Check weather data in Obsidian** — open `Weather.base` to verify it renders correctly

### Next — Enable Adapters
5. **Install weather schedule**: `./scripts/adapters/install-schedules.sh weather` — daily at 5:30 AM
6. **Set up Google Calendar** (if desired): Follow setup instructions in `calendar.py` docstring
7. **Set up YNAB** (if desired): Create `~/.config/generous-ledger/credentials/ynab.json` with token
8. **Set up Todoist** (if desired): Create `~/.config/generous-ledger/credentials/todoist.json` with token

### Completed in Follow-Up Session
9. ~~**Update Daily Briefing Protocol** in CLAUDE.md to scan `data/` folders~~ ✓ Done
10. ~~**Add "Data Sources" section** to CLAUDE.md describing what's available in `data/`~~ ✓ Done
11. ~~**Update docs/DESIGN.md** to document the adapter architecture~~ ✓ Done
12. **Test daily briefing** with weather data available — not yet tested
15. ~~**Dashboard Base** — Composite `Dashboard.base` showing today's events + health + tasks + weather~~ ✓ Done

Additional work completed in follow-up session:
- Created `scripts/deploy.sh` — comprehensive deployment to vault
- Created `scripts/morning-routine.sh` — runs adapters then briefing
- Updated `scripts/install-schedule.sh` — now uses morning routine
- Created `bases/` directory with 8 Base views (Weather, People, Commitments, Health, Calendar, Tasks, Finance, Dashboard)
- Updated templates for new individual-file profile structure (profile-person.md, profile-commitment.md)
- Removed old monolithic templates (profile-relationships.md, profile-commitments.md)
- Fixed Python 3.9 compatibility (`from __future__ import annotations`)
- Added 33 unit tests for adapter framework and formatting functions
- Weather adapter now reads location from config.yaml
- Deployed updated CLAUDE.md, templates, and Base views to vault

### Future — Additional Integrations
13. **Readwise plugin** — Install official Readwise Obsidian plugin for reading highlights
14. **Contact enrichment** — CardDAV sync to enrich `profile/people/` with contact details

## Other Notes

### Running Adapters Manually
```bash
# Weather (no credentials needed)
python3 scripts/adapters/weather.py

# With custom vault path
python3 scripts/adapters/weather.py --vault ~/Documents/Achaean

# Calendar (needs setup first)
python3 scripts/adapters/calendar.py --setup    # First-time OAuth
python3 scripts/adapters/calendar.py            # Subsequent runs

# Finance (needs YNAB token)
python3 scripts/adapters/finance.py

# Health (needs Apple Health export)
python3 scripts/adapters/health.py --export ~/Downloads/apple_health_export/export.xml --days 30

# Tasks (needs Todoist token)
python3 scripts/adapters/tasks.py
```

### Proposed CLAUDE.md Daily Briefing Update
The Daily Briefing Protocol should be extended with steps between current steps 1 and 2:

```
1. Read profile/index.md to orient.
1a. Scan data/calendar/ for today's events and upcoming schedule.
1b. Scan data/weather/ for today's forecast.
1c. Scan data/health/ for recent health metrics (sleep trends, activity).
1d. Scan data/finance/ for budget alerts (over-budget categories).
1e. Scan data/tasks/ for overdue or due-today items.
2. Scan profile/people/ for birthdays...
(rest unchanged)
```

### Additional Artifacts (Follow-Up Session)
- `scripts/deploy.sh` — Deploy to vault (plugin + config + bases)
- `scripts/morning-routine.sh` — Sequential adapter runs + daily briefing
- `bases/*.base` — 8 Obsidian Base view files (source of truth; deployed to vault)
- `templates/profile-person.md` — Template for individual person files
- `templates/profile-commitment.md` — Template for individual commitment files
- `scripts/adapters/tests/` — 33 unit tests for framework and adapters

### Project State
The weather adapter is tested end-to-end and producing real vault data. All adapter code has `from __future__ import annotations` for Python 3.9 compatibility. 33 unit tests pass covering vault writer, sync state, weather formatting, health classification, finance summaries, and task formatting. The other adapters need credentials to test against real APIs but share the same validated framework patterns.

CLAUDE.md and all Base views have been deployed to the vault via `scripts/deploy.sh`. The vault's CLAUDE.md now matches the repo version (individual-file profile structure, data source awareness, updated daily briefing protocol).
