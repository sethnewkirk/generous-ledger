---
date: 2026-02-22T15:53:40-05:00
session_name: evening-routine
git_commit: 422034b
branch: main
repository: generous-ledger
topic: "iMessage Adapter Testing & Full Disk Access"
tags: [testing, imessage, full-disk-access, evening-routine]
status: complete
last_updated: 2026-02-22
type: implementation_strategy
root_span_id: ""
turn_span_id: ""
---

# Handoff: iMessage adapter testing — blocked on Full Disk Access

## Task(s)

Resumed from `thoughts/shared/handoffs/evening-routine/2026-02-22_01-39-29_evening-routine-gmail-imessage-diary.md`. All 9 phases of the evening routine plan were already complete. This session focused on:

1. **Commit ledger and handoff** — Completed. Committed as `422034b`.
2. **Test iMessage adapter** — Blocked. Full Disk Access not propagating to python3 subprocess.

Plan document: `thoughts/shared/plans/2026-02-21-data-integration-plan.md`

## Critical References

- `thoughts/shared/plans/2026-02-21-data-integration-plan.md` — Original implementation plan
- `scripts/adapters/imessage.py` — iMessage adapter (the file being tested)
- `CLAUDE.md:170-237` — Evening Review Protocol and Data Sources table

## Recent changes

- Committed `thoughts/ledgers/CONTINUITY_CLAUDE-evening-routine.md` and `thoughts/shared/handoffs/evening-routine/2026-02-22_01-39-29_evening-routine-gmail-imessage-diary.md` as `422034b`.

## Learnings

### Full Disk Access inheritance on macOS

The iMessage adapter reads `~/Library/Messages/chat.db`, which requires Full Disk Access (FDA). Key findings:

- `/usr/bin/python3` is a **shim** — the real binary is `/Library/Developer/CommandLineTools/usr/bin/python3`. Granting FDA to the shim alone is insufficient.
- macOS FDA is **inherited from the parent process**. The terminal app (Terminal.app, iTerm2, or whichever app Claude Code runs in) must also have FDA.
- After enabling FDA, the **terminal must be restarted** for it to take effect.
- The error message is `sqlite3.DatabaseError: authorization denied` — this is the macOS sandbox blocking the read, not a SQLite permission error.

### No known contacts warning

The adapter logs `No known contacts found in profile/people/` because no people files with `email:` frontmatter exist yet. This is expected — contact matching (`known_contact_messages`) won't work until people files are created. Not a blocker for basic functionality.

## Post-Mortem

### What Worked
- Handoff resume process was clean — all commits from prior session present, git state matched expectations.
- Committing the ledger and handoff was straightforward.

### What Failed
- Tried: Running `python3 scripts/adapters/imessage.py --vault ~/Documents/Achaean` → Failed with `authorization denied` because FDA wasn't granted to the correct binaries/parent process.
- Tried: User enabled FDA for python3 → Still failed because the terminal app itself needs FDA, and/or the terminal needs restart after enabling.

### Key Decisions
- Decision: Not attempting workarounds (copying chat.db, using osascript, etc.) — proper FDA is the correct fix.
  - Alternatives: Could copy chat.db to a readable location, or use AppleScript bridge
  - Reason: The adapter will run via LaunchAgent in production, which has its own FDA grant. Hacking around it for testing would mask real issues.

## Artifacts

- `thoughts/shared/handoffs/evening-routine/2026-02-22_01-39-29_evening-routine-gmail-imessage-diary.md` — Prior handoff (now committed)
- `thoughts/ledgers/CONTINUITY_CLAUDE-evening-routine.md` — Session ledger (now committed)

## Action Items & Next Steps

1. **Fix Full Disk Access** — Ensure FDA is granted to: (a) `/Library/Developer/CommandLineTools/usr/bin/python3`, (b) the terminal app running Claude Code. Restart terminal after.
2. **Re-test iMessage adapter** — `python3 scripts/adapters/imessage.py --vault ~/Documents/Achaean`
3. **Test evening routine end-to-end** — `scripts/evening-routine.sh`
4. **Install schedules** — `scripts/install-schedule.sh` for morning (6 AM) + evening (9 PM) LaunchAgents
5. **Deploy** — `./scripts/deploy.sh --config --bases`
6. **Improve HTML stripping** — Gmail body has HTML remnants; consider `html2text` or `beautifulsoup`
7. **Add profile/people/ files** — Gmail contact matching needs people files with `email:` frontmatter

## Other Notes

- Vault path: `~/Documents/Achaean/`
- Credentials: `~/.config/generous-ledger/credentials/` (outside vault)
- Two untracked files from a prior session remain: `scripts/adapters/config.example.yaml` and `scripts/adapters/install-schedules.sh` — not part of this work.
- Python 3.9.6 on this machine — Google auth libraries emit FutureWarning about EOL but work fine.
