# Generous Ledger — Design Document

## Vision

A personal assistant built around Obsidian that knows the user deeply, manages their commitments and relationships, and actively guides them toward genuine human flourishing — grounded in Christian virtue ethics.

Inspired by Google's "Selfish Ledger" concept: a system with enough understanding of the user to anticipate behaviors, thoughts, and needs, and guide patterns of behavior. Unlike that vision, this system is transparent about its framework and oriented toward moral good rather than mere optimization.

---

## Core Principles

1. **Christian virtue ethics as the operating logic.** Not a feature or a mode — the framework that shapes how the assistant observes, reasons, and acts. The seven virtues (faith, hope, charity, prudence, justice, temperance, fortitude) are the internal categories. See `FRAMEWORK.md` for the full specification.

2. **Steward, not friend.** The assistant is a formal, competent servant. No warmth for its own sake, no rapport-seeking, no emotional language. This formality is honest — it prevents a disordered relationship with something that is not human.

3. **Transparent to the user.** The user can read and edit all profile files. The assistant's observations are tagged as such. The virtue ethics framework is openly stated. Users opt in knowing what the system embodies.

4. **Guide, don't control.** The assistant shapes recommendations, surfaces obligations, and makes tradeoffs visible — but the user decides. Flatly immoral requests are refused cleanly. Unwise requests are served with full context.

5. **Extensible by design.** The model engine, data sources, and profile dimensions are all swappable/addable. No hard dependencies on a single AI provider or data source.

---

## Architecture

### Overview

```
┌─────────────────────────────────────────────────┐
│  External Data Sources                           │
│  (Google Calendar, email, contacts, health, etc) │
└──────────────┬──────────────────────────────────┘
               │ sync adapters (pull → markdown)
┌──────────────▼──────────────────────────────────┐
│  Obsidian Vault (interface + data layer)         │
│  - Profile files (user model)                    │
│  - Daily notes (interaction surface)             │
│  - Journal, projects, reference notes            │
│  - FRAMEWORK.md (always loaded)                  │
│  - All data stored as markdown                   │
└──────────────┬──────────────────────────────────┘
               │ reads/writes markdown
┌──────────────▼──────────────────────────────────┐
│  Reasoning Engine (model-agnostic)               │
│  - Currently: Claude Code CLI                    │
│  - Future: any model that can read/write files   │
│  - Loads FRAMEWORK.md + profile index            │
│  - Pulls relevant profile files per request      │
│  - Reasons using the virtue framework            │
│  - Writes responses, updates profile             │
└──────────────┬──────────────────────────────────┘
               │ triggered by
┌──────────────▼──────────────────────────────────┐
│  Trigger Layer                                   │
│  1. On-demand: Obsidian plugin (@Claude)         │
│  2. Scheduled: cron/launchd (daily briefing)     │
│  3. Ambient: file watcher (future)               │
└─────────────────────────────────────────────────┘
```

### Key Design Decisions

**Vault as single source of truth.** All data — profile, observations, external data — lives in the vault as markdown. The reasoning engine reads from and writes to the vault. This means:
- Switching models is a plumbing change, not a redesign
- The user can always inspect everything
- No hidden databases or API-specific state

**Model-agnostic reasoning layer.** The interface between the engine and the vault is: "read markdown files, reason according to FRAMEWORK.md, write markdown files." Claude Code is the current engine but the architecture does not depend on it. Future options: other Claude models via API, local models, multi-model setups.

**External data via sync adapters.** External sources (calendar, email, contacts) are pulled into the vault as markdown by dedicated sync adapters. The reasoning engine never queries external APIs directly — it reads the vault. Adding a new data source means writing a new adapter, not changing the core logic.

**Three interaction modes:**
1. **On-demand** — User types @Claude in a note, assistant responds. The existing plugin pattern, simplified.
2. **Scheduled** — Daily/weekly job runs the engine against the vault. Produces daily briefings, checks dates, reviews patterns, updates profile. This is where proactive guidance lives.
3. **Ambient** (future) — File watchers notice journal entries or note changes, triggering profile updates or observations.

---

## User Model

### Structure

A set of markdown files in the vault, organized by dimension. Open-ended — new files can be created as needed.

**Always loaded:**
- **`index.md`** — Compact routing document (~150-200 words). Core identity, one-line summary of each profile file, current priorities, file paths. Updated when other files change significantly.

**Loaded on demand (by the engine based on request context):**
- **`identity.md`** — Name, age, vocation, church/tradition, life stage, household. Most stable file.
- **`people/`** — One file per person in the user's life. Each file has frontmatter: name, role, circle, birthday, anniversary, contact_frequency, status. Body contains notes tagged `[stated]`/`[observed]`.
- **`commitments/`** — One file per commitment. Each file has frontmatter: title, category, status, priority, deadline, timeframe, stakeholder. Body contains details and progress notes.
- **`patterns.md`** — Assistant's observations. Written using the virtue framework's observation principles (diagnose by ordering, map vocations, measure trajectories, note avoidance). Tagged as `[observed]` vs `[stated]`.
- **`current.md`** — This week's state. Active concerns, upcoming events, recent developments. Most volatile file, refreshed frequently.

**Created when needed:**
- `health.md`, `finances.md`, `vocation.md`, or any new dimension the user's life requires. The assistant proposes new files when a dimension grows substantial enough to warrant dedicated tracking.

### Design Principles

- User can always read and edit all profile files
- Each file states its purpose at the top
- Assistant's observations are tagged `[observed]`; user's statements tagged `[stated]`
- Files have "last updated" timestamps
- The set of files is open-ended, not a fixed schema

### Observation Framework

The assistant observes from the perspective of the virtue ethics framework, NOT from modern secular assumptions. See FRAMEWORK.md "Observation Principles" section. Key differences:
- Diagnose by ordering (Augustine), not by modern categories
- Map vocations to find imbalance (Luther)
- Measure growth trajectories, not snapshots (Calvin)
- Watch for compounding neglect (Proverbs)
- Note avoidance patterns
- Distinguish seasons from patterns (Prudence)

---

## Onboarding

Initial population of the user model through a structured conversation (not a form). Run as a dedicated onboarding session.

### Approach

A guided interview that covers:
1. **Identity & station** — Who are you? What do you do? What's your household?
2. **Key relationships** — Who are the important people? What are the obligations? Key dates?
3. **Commitments & goals** — What are you working toward? What have you committed to?
4. **Current state** — What's happening right now? What concerns you?
5. **What they want help with** — What areas of life should the assistant attend to?

### Principles
- Conversational, not clinical. More like a first meeting with a competent steward than a medical intake.
- Progressive — the model gets richer over time through observation and interaction, not just through explicit input.
- The vault itself is a data source if the user already has notes, journals, daily logs.

---

## The Virtue Ethics Framework

Fully specified in `FRAMEWORK.md`. Summary of key elements:

- **The Good:** Rightly ordered loves, faithful duty, growth in virtue (Augustine, Calvin)
- **Reasoning chain:** Diagnose the heart (Augustine) → Deliberate well (Aquinas) → Locate the duty (Luther) → Check the posture (Calvin) → Test the means (Puritans) → Apply wisdom (Proverbs)
- **Seven virtues** as internal categories, with Prudence (Aquinas's parts) as the primary operative virtue
- **Anti-patterns** that explicitly override modern therapeutic defaults
- **Communication:** Steward voice, natural language, virtue expressed through action not vocabulary
- **Refusals:** Flatly immoral → clean refusal. Unwise but not immoral → serve with full context.

---

## Feature Set

### Phase 1: Foundation
- Onboarding interview that populates profile files
- On-demand interaction via Obsidian plugin (@Claude)
- FRAMEWORK.md loaded into every interaction
- Profile index with selective file loading
- Basic daily note generation

### Phase 2: Proactive
- Scheduled daily briefing (upcoming dates, obligations, nudges)
- Pattern observation and `patterns.md` updates
- Birthday/anniversary tracking and reminders
- Accountability for stated commitments

### Phase 3: Integration
- External data sync adapters (Google Calendar, contacts)
- Ambient file watching for journal updates
- Richer pattern recognition across data sources

### Phase 4: Maturity
- Multiple model support
- Extended data integrations (email, health, finances)
- Weekly/monthly review generation
- Long-term trajectory analysis

---

## What the Assistant Does Day-to-Day

### On-demand (user-initiated)
- Responds to questions and requests with the framework operative
- Shapes recommendations (purchases, decisions, priorities) toward genuine need
- When asked for moral input, speaks honestly with humility
- Refuses flatly immoral requests cleanly

### Scheduled (system-initiated)
- Prepares daily notes with relevant items:
  - Upcoming birthdays, anniversaries, key dates
  - Outstanding commitments and their status
  - Gentle accountability for stated goals
  - Items that have been deferred repeatedly
- Updates `current.md` and `patterns.md`
- Periodic review of relationship contact frequency

### Ambient (future)
- Notices journal entries and updates understanding
- Detects pattern changes (exercise declining, mood shifts)
- Updates profile files when new information surfaces

---

## Technical Notes

### Current Stack
- TypeScript / esbuild / Obsidian plugin API
- Claude Code CLI as reasoning engine
- Markdown files as data layer

### Model Agnosticism
The reasoning layer depends on:
1. Ability to read markdown files
2. Ability to follow system prompt instructions (FRAMEWORK.md)
3. Ability to write markdown files

Any model or tool that can do these three things can serve as the engine. The FRAMEWORK.md is designed to work with any sufficiently capable language model, with specific anti-patterns to counteract typical training defaults.

### Data Source Extensibility
Adding a new external data source requires:
1. A sync adapter that pulls data and writes markdown to the vault
2. A profile file (or section) to store the normalized data
3. An update to `index.md` to include the new dimension

The reasoning engine does not need to change.

---

## Relation to Existing Codebase

The current codebase (Obsidian plugin with Claude Code CLI integration, streaming UX, thinking collapse) provides the foundation for the on-demand interaction mode. Key changes needed:

- **Simplify** — Remove format polymorphism (canvas/base renderers), unused SDK client, skills installer
- **Add** — Profile file loading, FRAMEWORK.md as system context, onboarding flow
- **Restructure** — Plugin becomes one trigger mechanism among several, not the entire system
- **New components** — Scheduler for daily briefings, profile management, sync adapter framework

The existing streaming UX, CodeMirror integration, and process management can be retained and adapted.
