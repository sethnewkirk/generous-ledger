# Continuous Claude v2 Setup

This project is configured for [Continuous Claude v2](https://github.com/parcadei/Continuous-Claude-v2), a context management system for Claude Code sessions.

## Directory Structure

```
thoughts/
├── ledgers/           # Continuity ledgers (session state snapshots)
├── shared/
│   ├── handoffs/      # Session handoff documents
│   └── plans/         # Implementation plans

.claude/
└── cache/
    └── artifact-index/
        └── context.db # SQLite database for searching artifacts
```

## Database Setup

⚠️ **Database not yet initialized** - SQLite3 was not available during setup.

To initialize the artifact index database, run:

```bash
cd /home/user/generous-ledger
curl -fsSL https://raw.githubusercontent.com/parcadei/Continuous-Claude-v2/main/scripts/artifact_schema.sql | sqlite3 .claude/cache/artifact-index/context.db
```

Or download the schema manually and run:
```bash
sqlite3 .claude/cache/artifact-index/context.db < artifact_schema.sql
```

## Features

- **Continuity Ledgers**: Save session state before clearing context
- **Handoffs**: Document completed tasks for future sessions
- **Plans**: Store implementation plans
- **Artifact Search**: Query past decisions and learnings
- **Hooks System**: Automate workflows at key lifecycle points

## Usage

Once Claude Code is running with Continuous Claude v2:

- `/continuity_ledger` - Create a session state snapshot
- Use `/handoff` to document completed work
- Store plans in `thoughts/shared/plans/`
- Query artifact index for past decisions

## Notes

- All `thoughts/` content is tracked in git
- `.claude/cache/` is gitignored (local only)
- Database is optional - works without it, just no search functionality
