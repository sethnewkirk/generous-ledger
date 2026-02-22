# Session: evening-routine
Updated: 2026-02-22T01:30:00-05:00

## Goal
Add evening routine (Gmail + iMessage adapters → diary generation) and clean up unused health/tasks adapters. Done when evening routine runs end-to-end and morning routine also pulls email/messages.

## Constraints
- Adapters follow calendar.py patterns exactly (OAuth, VaultWriter, logging, argparse)
- Raw email/message data is ephemeral — wiped after Claude processes it
- Python 3.9 compatibility (`from __future__ import annotations`)
- sys.path must use `append` not `insert(0,...)` — calendar.py shadows stdlib calendar module

## Key Decisions
- Reuse google-calendar.json OAuth client config for Gmail (same Google Cloud project)
- Separate token file: google-gmail-token.json
- iMessage reads chat.db directly (SQLite read-only) — no API keys needed
- sys.path.append + cleanup block in gmail.py to prevent stdlib calendar shadowing
- Two commits: adapter framework (prior work) + evening routine (this session)

## State
- Done:
  - [x] Phase 1: Remove health/tasks adapters
  - [x] Phase 2: Gmail adapter
  - [x] Phase 3: iMessage adapter
  - [x] Phase 4: Evening routine scripts
  - [x] Phase 5: Evening Review Protocol in CLAUDE.md
  - [x] Phase 6: Update morning routine for email/messages
  - [x] Phase 7: Diary Base view + Dashboard update
  - [x] Phase 8: Scheduling (evening LaunchAgent)
  - [x] Phase 9: Tests (107 total, all passing)
  - [x] sys.path fix for stdlib calendar shadowing
  - [x] Gmail setup error handling improvement
  - [x] Committed and pushed (2 commits)
  - [x] Deployed to vault (--config --bases)
  - [x] pip3 installed google-auth-oauthlib + google-api-python-client
  - [x] Saved OAuth client config to credentials dir
- Now: [→] Gmail OAuth setup — user hit "localhost refused to connect" after granting access
- Next: Test Gmail adapter end-to-end, test iMessage adapter, test evening routine

## Open Questions
- UNCONFIRMED: Gmail OAuth redirect — localhost connection refused after consent. Likely the setup process was killed (TaskStop) before the local server could receive the callback. Need to re-run --setup.
- UNCONFIRMED: iMessage Full Disk Access — not yet tested whether Terminal/python3 has permission

## Working Set
- Branch: `main` (pushed to origin)
- Key files: `scripts/adapters/gmail.py`, `scripts/adapters/imessage.py`, `scripts/evening-routine.sh`, `scripts/evening-briefing.sh`, `CLAUDE.md`
- Test cmd: `python3 -m unittest discover scripts/adapters/tests/ -v`
- Gmail setup: `python3 scripts/adapters/gmail.py --setup`
- Credential dir: `~/.config/generous-ledger/credentials/`
- Vault: `~/Documents/Achaean/`
