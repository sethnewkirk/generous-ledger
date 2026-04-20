# Development Guide

This repository contains both the Obsidian plugin and the scheduled stewardship tooling.

## Core Commands

```bash
npm install
npm run dev
npm run build
npm test
npm run test:python
npm run verify
npm run version
```

## What `verify` Covers

- TypeScript compile and bundle
- Jest tests for plugin and provider helpers
- Python adapter test suite

## Plugin Development

The plugin build output is `main.js` in the repo root.

Settings now include:

- `provider`
- `assistantHandle`
- `codexPath`
- `claudePath`
- `codexModel`
- `claudeModel`

The plugin should never assume a default provider. If `provider` is unset, it must fail with a clear setup notice.

## Runtime Documents

Keep these aligned:

- `docs/FRAMEWORK.md`
- `docs/STEWARD_SPEC.md`
- `AGENTS.md`
- `CLAUDE.md`

`FRAMEWORK.md` and `STEWARD_SPEC.md` are canonical. `AGENTS.md` and `CLAUDE.md` should stay thin.

## Scheduled Scripts

All briefing and routine scripts must support:

- `--provider codex|claude`
- `--vault PATH`
- `GL_PROVIDER`
- `GL_VAULT_PATH`

Use `scripts/lib/` helpers instead of duplicating provider invocation logic.

## Deployment

Deploy to a vault with:

```bash
./scripts/deploy.sh
```

Bootstrap a brand-new clean vault with:

```bash
./scripts/bootstrap-vault.sh --name Evander
```

That script is responsible for copying:

- plugin assets
- `AGENTS.md`
- `CLAUDE.md`
- `docs/FRAMEWORK.md`
- `docs/STEWARD_SPEC.md`
- templates
- bases

## Schedule Installation

Install launch agents with:

```bash
./scripts/install-schedule.sh --provider codex
```

or:

```bash
./scripts/install-schedule.sh --provider claude
```

Provider selection is mandatory when installing schedules.
