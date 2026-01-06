# Thoughts Directory

This directory contains Continuous Claude v2 artifacts for managing development sessions.

## Structure

### `ledgers/`
**Continuity Ledgers** - Session state snapshots taken at key moments.

Use these to:
- Save context before clearing a long conversation
- Resume work after a break
- Hand off work to a future session

Create with: `/continuity_ledger`

### `shared/handoffs/`
**Session Handoffs** - Post-mortem documents for completed tasks.

Contains:
- What worked / what didn't
- Key decisions made
- Files modified
- Lessons learned

### `shared/plans/`
**Implementation Plans** - Design documents created during planning phase.

Use for:
- Architecture designs
- Multi-step feature implementations
- Complex refactoring plans

## Git Tracking

All content in this directory is tracked in version control, providing a searchable history of:
- Development decisions
- Implementation approaches
- Lessons learned
- Session continuity

The artifact index database (`.claude/cache/artifact-index/context.db`) indexes this content for fast searching, but is gitignored since it can be rebuilt from the source files.
