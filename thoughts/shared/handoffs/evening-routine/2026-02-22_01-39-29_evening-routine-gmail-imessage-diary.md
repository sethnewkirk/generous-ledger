---
date: 2026-02-22T01:39:29-05:00
session_name: evening-routine
git_commit: e2eeccd
branch: main
repository: generous-ledger
topic: "Evening Routine, Gmail/iMessage Adapters, Diary Generation"
tags: [implementation, adapters, evening-routine, gmail, imessage, diary]
status: complete
last_updated: 2026-02-22
type: implementation_strategy
root_span_id: ""
turn_span_id: ""
---

# Handoff: Evening routine with Gmail, iMessage, and diary generation

## Task(s)

Implemented the full plan from `thoughts/shared/plans/2026-02-21-data-integration-plan.md` — specifically the evening routine extension covering Phases 1-9. All phases completed and committed.

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Remove health/tasks adapters | Completed |
| 2 | Gmail adapter | Completed |
| 3 | iMessage adapter | Completed |
| 4 | Evening routine scripts | Completed |
| 5 | Evening Review Protocol in CLAUDE.md | Completed |
| 6 | Update morning routine for email/messages | Completed |
| 7 | Diary Base view + Dashboard update | Completed |
| 8 | Scheduling (evening LaunchAgent) | Completed |
| 9 | Tests (Gmail + iMessage) | Completed |

Additionally fixed a stdlib calendar module shadowing bug and improved Gmail setup error handling.

## Critical References

- `CLAUDE.md` — Contains both Daily Briefing Protocol and new Evening Review Protocol
- `docs/DESIGN.md` — Updated adapter architecture docs
- `thoughts/shared/plans/2026-02-21-data-integration-plan.md` — Original plan (Phases 1-9)

## Recent changes

Three commits pushed to `main`:

**Commit `d1d94e8`** — Data sync adapter framework:
- `scripts/adapters/lib/` — Shared framework (vault_writer, credentials, sync_state, logging)
- `scripts/adapters/weather.py`, `calendar.py`, `finance.py` — Three data adapters
- `scripts/morning-routine.sh`, `scripts/daily-briefing.sh`, `scripts/deploy.sh`
- `bases/` — 7 Obsidian Base views (Calendar, Commitments, Dashboard, Diary, Finance, People, Weather)
- `templates/` — Profile templates restructured to per-person/per-commitment
- `docs/DESIGN.md` — Adapter architecture section added

**Commit `6fdcd3a`** — Evening routine + email/messages:
- `scripts/adapters/gmail.py` — Gmail OAuth adapter (~520 lines)
- `scripts/adapters/imessage.py` — iMessage local SQLite adapter (~610 lines)
- `scripts/evening-routine.sh`, `scripts/evening-briefing.sh` — Evening orchestration
- `scripts/install-schedule.sh` — Morning (6 AM) + evening (9 PM) LaunchAgents
- `CLAUDE.md` — Evening Review Protocol, data scanning steps 1d-1e, Data Sources table
- `scripts/adapters/tests/test_gmail.py` (39 tests), `test_imessage.py` (30 tests)
- `diary/.gitkeep`

**Commit `e2eeccd`** — Fix stdlib calendar shadowing:
- All adapters + tests: `sys.path.insert(0,...)` → `sys.path.append(...)`
- `scripts/adapters/gmail.py:46-53` — Removes script dir from sys.path + purges cached wrong-calendar
- `scripts/adapters/gmail.py:456-466` — Better error handling for missing credentials in --setup

## Learnings

### stdlib calendar module shadowing
`scripts/adapters/calendar.py` shadows the Python stdlib `calendar` module. When Python runs a script directly, it inserts the script's directory as `sys.path[0]`. Google auth libraries transitively import stdlib `calendar` (via `http.cookiejar`), causing `ImportError`. Fix: use `sys.path.append` instead of `insert(0,...)` and actively clean the script dir from sys.path after lib imports (`gmail.py:46-53`).

### iMessage attributedBody decoding
macOS Ventura+ stores iMessage text in `attributedBody` binary blob instead of the `text` column. Decoding requires splitting on `NSString`/`NSDictionary` markers. See `imessage.py` `decode_attributed_body()`. The `text` column is often NULL on newer macOS versions.

### Gmail OAuth reuses Calendar credentials
The Gmail adapter reuses the same `google-calendar.json` OAuth client config (same Google Cloud project) but stores its own token at `google-gmail-token.json`. User must enable Gmail API separately in the Cloud Console.

### HTML stripping in Gmail body
The Gmail adapter strips HTML tags from email bodies but some HTML entities and formatting remnants persist. The `strip_html_tags()` function in `gmail.py` is basic — could be improved with a proper HTML-to-text library.

## Post-Mortem

### What Worked
- Agent orchestration pattern: spawning implementation agents for each phase preserved main context effectively. Parallel agent launches for independent phases (2+3, 6+7+8) maximized throughput.
- Following `calendar.py` as a template for `gmail.py` ensured consistent patterns across all adapters.
- 107 tests all passing after every change gave confidence in the implementation.

### What Failed
- Tried: `sys.path.insert(0,...)` for all adapters → Failed because: `calendar.py` shadows stdlib `calendar` module, breaking Google auth imports chain (`http.cookiejar` → `from calendar import timegm`).
- Tried: `sys.path.append(...)` alone → Still failed because Python auto-inserts script dir as `sys.path[0]` when running directly.
- Tried: `Path(p).resolve()` comparison to clean sys.path → Failed because empty string `''` (CWD) doesn't resolve the same way. Fixed with `os.path.realpath(p or '.')`.
- Gmail `--setup` originally crashed with raw traceback when credentials missing → Fixed with proper try/except and step-by-step instructions.

### Key Decisions
- Decision: Use `sys.path.append` + active cleanup instead of renaming `calendar.py` to `gcalendar.py`
  - Alternatives: Rename calendar.py, use importlib, use package structure with `__init__.py`
  - Reason: Renaming would break existing references in morning-routine.sh, tests, and docs. Cleanup approach is surgical and contained to gmail.py.
- Decision: Wipe email/message data after Claude processes it (ephemeral pattern)
  - Alternatives: Keep raw data, archive to separate folder
  - Reason: Privacy by design — raw email content shouldn't persist in the vault. Diary entry and profile updates are the durable outputs.
- Decision: Two separate commits for prior adapter framework + this session's evening work
  - Reason: Prior session's adapter framework was never committed; logically separate from evening routine additions.

## Artifacts

- `scripts/adapters/gmail.py` — Gmail adapter (complete)
- `scripts/adapters/imessage.py` — iMessage adapter (complete)
- `scripts/evening-routine.sh` — Evening orchestrator
- `scripts/evening-briefing.sh` — Evening Claude invocation
- `scripts/adapters/tests/test_gmail.py` — 39 Gmail tests
- `scripts/adapters/tests/test_imessage.py` — 30 iMessage tests
- `bases/Diary.base` — Diary Base view
- `diary/.gitkeep` — Diary output directory
- `CLAUDE.md:170-209` — Evening Review Protocol
- `CLAUDE.md:211-237` — Data Sources table
- `thoughts/ledgers/CONTINUITY_CLAUDE-evening-routine.md` — Session ledger
- `thoughts/shared/plans/2026-02-21-data-integration-plan.md` — Original plan

## Action Items & Next Steps

1. **Test iMessage adapter** — Run `python3 scripts/adapters/imessage.py --vault ~/Documents/Achaean`. Requires Full Disk Access for Terminal/python3 in System Settings → Privacy & Security → Full Disk Access.
2. **Test evening routine end-to-end** — Run `scripts/evening-routine.sh` to verify full flow (gmail → imessage → briefing → cleanup). Note: requires Claude Code CLI (`claude` binary) for the briefing step.
3. **Install schedules** — Run `scripts/install-schedule.sh` to install both LaunchAgents (6 AM morning, 9 PM evening).
4. **Deploy after any further changes** — `./scripts/deploy.sh --config --bases` to push updated files to vault.
5. **Improve HTML stripping** — Gmail body text has HTML remnants. Consider using `html2text` or `beautifulsoup` for cleaner extraction.
6. **Add profile/people/ files** — Gmail contact matching (`known_contact_messages`) only works once people files with `email:` frontmatter exist. Onboarding or manual creation needed.
7. **Commit remaining files** — `thoughts/ledgers/CONTINUITY_CLAUDE-evening-routine.md` and this handoff are not yet committed.

## Other Notes

- The vault path is `~/Documents/Achaean/` — all data files write there.
- Credentials live at `~/.config/generous-ledger/credentials/` (outside vault, never synced).
- Google Cloud project ID: `115084302451` — both Calendar and Gmail APIs enabled.
- Gmail OAuth token saved at `~/.config/generous-ledger/credentials/google-gmail-token.json`.
- Python 3.9.6 on this machine — all adapters use `from __future__ import annotations` for compatibility. Google auth libraries emit FutureWarning about Python 3.9 EOL but work fine.
- `scripts/adapters/config.example.yaml` and `scripts/adapters/install-schedules.sh` are untracked files from a prior session — not part of this implementation.
