# Claude Runtime Wrapper

This file is the Claude-specific entrypoint for the Generous Ledger steward system.

## Canonical Sources

Use the policy-loader contract first:

- `docs/policy/manifest.json` defines the module graph and deterministic bundles.
- `docs/STEWARD_CORE.md` is the generated always-on core artifact.
- `docs/FRAMEWORK.md` and `docs/STEWARD_SPEC.md` are stable human-readable indexes into the canonical module directories.

If the loader is unavailable, follow the index docs into `docs/framework/` and `docs/spec/` rather than assuming the full policy lives in one large file.

## Claude Runtime Notes

- Provider id: `claude`
- Default user-facing identity: `Steward`
- Primary plugin trigger: `@Steward`
- Compatibility aliases: `@Claude`, `@Codex`
- Live vault runs should execute from the vault root with `claude -p`
- Claude must be installed and authenticated before scheduled runs or plugin use
- In plugin-triggered note interactions, do not edit the current note directly; the plugin renders the response
- In scheduled routines, prefer direct file I/O over Obsidian CLI when practical

## Repository Development

```bash
npm install
npm run build
npm test
npm run test:python
npm run verify
```

Deploy with `scripts/deploy.sh`. Install schedules with `scripts/install-schedule.sh --provider claude`.
