# Architecture

Generous Ledger is an Obsidian-native steward system with a provider-neutral core. The vault is the data layer, the plugin is one trigger surface, and scheduled scripts are the other.

## Canonical Layers

1. `docs/FRAMEWORK.md`
   Defines the moral and reasoning framework.
2. `docs/STEWARD_SPEC.md`
   Defines the operational rules, vault structure, and stewardship protocols.
3. Canonical vault memory
   `data/`, `memory/`, `profile/`, `diary/`, and `reviews/`.
4. Runtime wrappers
   `AGENTS.md` for Codex and `CLAUDE.md` for Claude.

## Runtime Architecture

### Plugin Layer

The Obsidian plugin handles:

- configurable provider selection
- configurable assistant handle
- note trigger detection
- onboarding terminal UI
- per-note session persistence
- response rendering back into the current note

The runtime never edits the active note directly. The plugin owns note rendering.

### Provider Layer

The plugin normalizes two providers behind one internal contract:

- `claude`
- `codex`

Each provider implementation supplies:

- availability and readiness checks
- prompt execution
- optional session resume
- normalized final text extraction
- normalized error reporting

Claude retains streaming note rendering. Codex support is conservative for now and inserts the final response when execution completes.

### Session Layer

Per-note session state lives in frontmatter:

```yaml
steward_sessions:
  claude: "<session-id>"
  codex: "<session-id>"
```

Legacy `claude_session_id` is migrated opportunistically when the note is next written successfully.

### Scheduled Routine Layer

Scripts under `scripts/` support daily, evening, weekly, monthly, and ambient stewardship flows. They share:

- `--provider codex|claude`
- `--vault PATH`
- `GL_PROVIDER`
- `GL_VAULT_PATH`

All briefing scripts delegate provider execution through one shared runner under `scripts/lib/`.

### Memory Compiler Layer

The vault memory system is a compiler, not a passive store.

- source signals arrive in `data/` and ordinary markdown notes
- adapters may be direct API/database connectors or import bridges for future mobile and voice workflows
- promoted signals are normalized into `memory/events/`
- durable conclusions are written to `memory/claims/`
- `profile/` is projected from claims plus recent events
- `memory/index.json` is a rebuildable retrieval index, never the source of truth
- `memory/health-report.md` and `memory/health-report.json` surface unresolved subjects, unlinked contacts, orphaned memory, and stale/conflicting claims

Obsidian wikilinks are part of the data model. Memory objects, profile pages, and operational notes link to each other so retrieval can traverse the local markdown graph before it falls back to lexical search.

The current signal surface includes:

- Google Calendar, Gmail, and iMessage snapshots
- Apple Contacts and Apple Reminders snapshots
- imported voice-note transcripts and call-log entries
- finance and weather summaries
- ordinary vault markdown and daily notes

## Data Flow

### Inline Note Flow

1. User writes a paragraph containing `@Steward`.
2. Trigger detection finds the configured handle or a legacy alias.
3. The plugin resolves the configured provider.
4. The provider executes from the vault root.
5. The plugin renders a `steward` callout into the note.
6. The note's provider-specific session id is updated in frontmatter.

### Onboarding Flow

1. The plugin checks for `profile/index.md`.
2. If no profile exists, the onboarding terminal opens.
3. The configured provider runs the onboarding protocol from the shared steward spec.
4. The provider creates profile files in the vault.
5. When `profile/index.md` appears, the terminal session is cleared and closed.

### Scheduled Flow

1. Adapters populate `data/`.
2. The memory compiler promotes recent signals into `memory/events/` and `memory/claims/`, then refreshes `profile/` projections and the derived index.
3. A briefing or review script resolves provider and vault path.
4. The shared runner executes the provider against the deployed wrapper plus shared docs.
5. The provider writes its briefing or review outputs into the vault.
6. Ephemeral email and message files are deleted only after success.

## Repository Structure

```text
src/
  main.ts
  settings.ts
  trigger.ts
  renderer.ts
  session-manager.ts
  session-state.ts
  claude-process.ts
  codex-process.ts
  terminal-session.ts
  terminal-view.ts

docs/
  FRAMEWORK.md
  STEWARD_SPEC.md
  DESIGN.md
  DEVELOPMENT.md
  ARCHITECTURE.md

scripts/
  compile-memory.sh
  check-memory.sh
  retrieve-memory.sh
  deploy.sh
  install-schedule.sh
  morning-routine.sh
  evening-routine.sh
  weekly-routine.sh
  monthly-routine.sh
  ambient-watcher.sh
  *-briefing.sh
  lib/
  steward_memory/
```

## Design Constraints

- The vault is the system of record.
- The assistant identity is neutral `Steward`; providers are implementation choices.
- The live vault may not be a git repository, so Codex runs must tolerate non-repo execution.
- Provider drift should be minimized by keeping operational rules in shared docs and runtime-specific behavior in thin wrappers.
