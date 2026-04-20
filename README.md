# Generous Ledger

Generous Ledger is an Obsidian-based personal steward system. It combines:

- an Obsidian plugin for inline note interactions
- structured profile files in the vault
- a canonical `memory/` layer for normalized events and durable claims
- scheduled routines for daily, evening, weekly, and monthly stewardship
- adapter-fed data under `data/`
- dual runtime support for both Codex and Claude

The user-facing assistant identity is `Steward`. The primary inline trigger is `@Steward`, with temporary compatibility for `@Claude` and `@Codex`.

## Current Product Shape

The system is organized around two canonical documents:

- [`docs/FRAMEWORK.md`](./docs/FRAMEWORK.md): moral and reasoning framework
- [`docs/STEWARD_SPEC.md`](./docs/STEWARD_SPEC.md): operational behavior, vault structure, and protocols

Runtime wrappers remain at the vault root:

- [`AGENTS.md`](./AGENTS.md) for Codex
- [`CLAUDE.md`](./CLAUDE.md) for Claude

## Plugin Features

- configurable provider: `codex` or `claude`
- configurable assistant handle, defaulting to `Steward`
- inline paragraph triggering from Obsidian notes
- provider-specific per-note session tracking in frontmatter
- streaming responses for Claude
- final-response insertion for Codex
- onboarding terminal for initial profile creation

## Scheduled Features

Scripts under [`scripts/`](./scripts) run:

- morning briefing flow
- evening review flow
- weekly review flow
- monthly review flow
- ambient file watching

All briefing and routine entrypoints support `--provider` and `--vault`, with `GL_PROVIDER` and `GL_VAULT_PATH` as environment fallbacks.
Before provider-driven briefings and reviews run, the scripts compile the vault's recent signals into `memory/events/` and `memory/claims/` so the assistant sees a stable, wikilinked memory graph instead of only raw source files.

Current adapter coverage includes:

- weather forecasts
- Google Calendar events
- Gmail snapshots
- iMessage snapshots
- Apple Contacts snapshots
- Apple Reminders snapshots
- imported voice-note transcripts
- imported call-log snapshots
- weekly finance summaries

## Memory Model

The vault is still the system of record, but memory now has explicit layers:

- `data/` holds raw or semi-raw synced signals.
- `data/contacts/`, `data/tasks/`, `data/voice/`, and `data/calls/` extend the signal surface for people resolution, obligations, spoken capture, and relationship activity.
- `memory/events/` stores one normalized markdown event per promoted signal.
- `memory/claims/` stores durable fact, obligation, preference, pattern, or idea claims.
- `profile/` remains the steward's compiled operational surface for people, commitments, current state, and patterns.

Obsidian wikilinks are first-class relationship edges throughout the memory layer. Events, claims, and profile files link to each other so retrieval can expand through the local markdown graph before it falls back to search.

## Setup

1. Install dependencies with `npm install`.
2. Build the plugin with `npm run build`.
3. Copy plugin assets into your vault's `.obsidian/plugins/generous-ledger/` directory, or run `./scripts/deploy.sh`.
4. In Obsidian settings, choose a provider and confirm the binary path for either Codex or Claude.
5. Use `@Steward` in a note, or run the `Begin onboarding` command if `profile/` does not exist yet.

To create a fresh steward vault with the runtime predeployed, use:

```bash
./scripts/bootstrap-vault.sh --name Evander
```

## Development

Primary docs:

- [`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- [`docs/DESIGN.md`](./docs/DESIGN.md)

Validation commands:

```bash
npm run build
npm test
npm run test:python
npm run verify
```

Memory utilities:

```bash
./scripts/compile-memory.sh --vault /path/to/vault
./scripts/retrieve-memory.sh --vault /path/to/vault --workflow meeting-prep --subject "Max"
./scripts/check-memory.sh --vault /path/to/vault
```

`compile-memory` now also writes `memory/health-report.md` and `memory/health-report.json` so unresolved subjects, unlinked contacts, orphaned memory, and stale/conflicting claims stay visible.

## Historical Notes

Older documentation about the original Anthropic API-key plugin is retained only as historical reference. Active implementation and operator guidance should follow the current steward system docs listed above.
