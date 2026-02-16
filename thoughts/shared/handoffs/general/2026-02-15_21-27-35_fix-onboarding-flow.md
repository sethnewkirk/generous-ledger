---
date: 2026-02-15T21:27:35-05:00
session_name: general
researcher: claude
git_commit: b9ad605
branch: main
repository: generous-ledger
topic: "Fix Onboarding Flow — Session Resume, Prompt Delivery, Error Display"
tags: [bugfix, onboarding, streaming, session-management]
status: complete
last_updated: 2026-02-15
last_updated_by: claude
type: implementation_strategy
root_span_id:
turn_span_id:
---

# Handoff: Fix Onboarding Flow

## Task(s)

- **Fix onboarding UX bugs** (completed) — Three root causes identified and fixed: vague prompt, wrong session ID extraction, blank error display.
- **Phase 5: Profile-aware on-demand mode** (not started)
- **Phase 6: Scheduled daily briefings** (not started)
- **Scroll lock during streaming bug** (not started) — Known bug from previous handoff, not addressed this session.

Working from the implementation plan at `/Users/seth/.claude/plans/shimmying-snuggling-waterfall.md` and the onboarding fix plan at `thoughts/shared/plans/2026-02-15-onboarding-ux-fix.md`. Phases 0-4 were completed in the prior session.

## Critical References

- `CLAUDE.md` — The steward framework delivery mechanism. Most important file. Now includes "Plugin Interaction Mode" section.
- `/Users/seth/.claude/plans/shimmying-snuggling-waterfall.md` — The approved implementation plan (Phases 0-6).
- `thoughts/shared/plans/2026-02-15-onboarding-ux-fix.md` — The onboarding fix plan that guided this session's work.

## Recent Changes

### Commit `b9ad605`: Fix onboarding flow

- `CLAUDE.md:67-74` — Added "Plugin Interaction Mode" section telling Claude not to Write to the current note, respond conversationally, etc.
- `src/main.ts:155-183` — Rewrote `handleEnterKey()` to support onboarding mode: in `Onboarding.md`, Enter triggers Claude without requiring `@Claude` in the text. Skips callout blocks, frontmatter, and headings.
- `src/main.ts:342-370` — Rewrote `startOnboarding()`: deletes existing Onboarding.md to clear stale session IDs, creates fresh file with just frontmatter+heading, sends a detailed constraining prompt directly via `sendPromptToEditor()`.
- `src/main.ts:372-459` — New `sendPromptToEditor(file, prompt)` method: sends a prompt string directly to Claude Code CLI and streams the response into the active editor, without needing `@Claude` in the document.
- `src/main.ts:244-254` — Message handler now processes both `stream_event` and `assistant` type messages, with `extractTextContent` as fallback when streaming text is empty.
- `src/main.ts:277-286` — Close handler checks for `extractError()` and displays error callouts instead of blank responses.
- `src/stream-parser.ts:64-80` — `extractSessionId()` now prefers session_id from `result` messages (authoritative) over `init` system messages.
- `src/stream-parser.ts:82-95` — New `extractError()` function: parses `errors` array and `is_error` flag from result messages.
- `src/stream-parser.ts:24-27` — Added `is_error` and `errors` fields to `StreamMessage` interface.
- `src/claude-process.ts:70-74` — Improved logging with `[GL]` prefix for stderr and process exit code.

## Learnings

### Session ID Resolution (critical bug)
The Claude Code CLI `--output-format stream-json` emits `session_id` on multiple message types: `system` (init), `assistant`, and `result`. The `init` message's session_id is assigned at process start and differs from the `result` message's session_id (which is the authoritative one for the actual conversation). `extractSessionId()` was returning the first match (from `init`), causing `--resume` to fail with "No conversation found." Fix: always prefer the `result` message's session_id.

### Onboarding Prompt Quality
The vault is named "Achaean" — Claude interpreted this as an RPG/game context and went full fantasy mode ("traveler," "chronicler's ledger"). The onboarding prompt must explicitly state: "personal steward — not a game assistant, not an RPG character." Must constrain tool use: "Do NOT explore the vault. Do NOT use any tools except Read on CLAUDE.md and docs/FRAMEWORK.md."

### Vault Deployment
The CLAUDE.md, docs/FRAMEWORK.md, and templates/ must exist in BOTH the project repo AND the vault (`~/Documents/Achaean/`). Users will accidentally delete vault copies when cleaning up test artifacts. The `startOnboarding()` method now handles stale Onboarding.md files, but the framework files must be manually redeployed if deleted.

### Stream Message Types
Claude Code stream-json sends: `system` (hook_started, hook_response, init), `stream_event` (content_block_delta, content_block_start, content_block_stop), `assistant` (partial messages with `--include-partial-messages`), `result` (success or error_during_execution). Text can arrive via stream_event deltas OR assistant message content blocks — must handle both.

## Post-Mortem

### What Worked
- The fix plan at `thoughts/shared/plans/2026-02-15-onboarding-ux-fix.md` correctly identified all four root causes
- Diagnostic logging (`[GL]` prefix) with full JSON dump of result messages quickly revealed the session ID mismatch
- The explicit, constraining onboarding prompt successfully overrode Claude's tendency to roleplay based on vault name

### What Failed
- Tried: relying on prompt instructions alone ("Ask ONE question at a time") → Failed because: Claude still asked two questions. Prompt constraints are soft.
- Tried: `extractTextContent` as fallback for blank replies → Didn't help because: the real issue was `error_during_execution` with zero API calls, not missing text extraction.
- Tried: keeping existing Onboarding.md and just clearing session → Failed because: metadata cache returns stale frontmatter values; must delete and recreate.

### Key Decisions
- Decision: Delete and recreate Onboarding.md on every `startOnboarding()` call
  - Alternatives: Clear session ID in existing file, or check for stale IDs
  - Reason: Obsidian's metadata cache can return stale frontmatter; deleting guarantees clean state
- Decision: Keep `--permission-mode bypassPermissions` (Option A from fix plan)
  - Alternatives: `--allowedTools` to restrict during conversation turns
  - Reason: Prompt constraints are working now; added complexity not worth it yet
- Decision: Keep diagnostic `[GL]` logging in production build
  - Reason: Still debugging; useful for next session. Remove once onboarding is stable.

## Artifacts

- `CLAUDE.md:67-74` — Plugin Interaction Mode section
- `src/main.ts` — Rewritten onboarding flow, `sendPromptToEditor()`, error handling
- `src/stream-parser.ts` — `extractError()`, fixed `extractSessionId()`
- `src/claude-process.ts` — Improved logging
- `thoughts/shared/plans/2026-02-15-onboarding-ux-fix.md` — Onboarding fix plan (reference)
- `thoughts/shared/handoffs/general/2026-02-15_16-15-00_phases-0-through-4-complete.md` — Previous handoff

## Action Items & Next Steps

### Immediate (before Phase 5)
1. **Test full onboarding flow end-to-end** — The session resume now works, but a complete 5-section interview has not been verified. Test: identity → relationships → commitments → current state → help areas. Verify profile files are created in `~/Documents/Achaean/profile/`.
2. **Fix scroll lock during streaming** — Known bug: user can't scroll while Claude streams. `renderer.append()` resets scroll position on each update. Fix: only auto-scroll if user is already at the bottom.
3. **Remove diagnostic logging** — Remove `[GL]` console.log statements from `src/main.ts` and `src/claude-process.ts` once onboarding is confirmed stable.

### Phase 5: Profile-Aware On-Demand Mode
Per the plan (`/Users/seth/.claude/plans/shimmying-snuggling-waterfall.md`):
1. Add post-interaction protocol to CLAUDE.md — after each interaction, update profile files when new info surfaces (already written in CLAUDE.md)
2. Add selection support to the plugin — if text is selected, use selection as prompt instead of paragraph
3. Test: "I've been working 60+ hours for four weeks and my wife says she feels neglected. @Claude" → should reference spouse from profile, surface vocation imbalance

### Phase 6: Scheduled Daily Briefings
No plugin needed — cron + Claude CLI + Obsidian CLI:
1. Create `scripts/daily-briefing.sh`
2. Create `scripts/install-schedule.sh` for macOS LaunchAgent at 6:00 AM
3. CLAUDE.md daily briefing protocol is already written

## Other Notes

### Vault Path and Deployment
The user's vault is at `~/Documents/Achaean/`. Full deployment:
```bash
npm run build && cp main.js manifest.json styles.css ~/Documents/Achaean/.obsidian/plugins/generous-ledger/
cp CLAUDE.md ~/Documents/Achaean/CLAUDE.md
cp docs/FRAMEWORK.md ~/Documents/Achaean/docs/FRAMEWORK.md
mkdir -p ~/Documents/Achaean/templates && cp templates/profile-*.md ~/Documents/Achaean/templates/
obsidian plugin:reload id=generous-ledger
```

### Rendering Issues
The user noted the callout rendering "doesn't look great." The `separateThinkingFromAnswer` function in `src/renderer.ts` splits on paragraph boundaries, which can misfire. The thinking collapse (`> > [!note]- Thinking`) renders oddly when mixed with the answer text. This is a known cosmetic issue to address later.

### Cost Per Interaction
Each onboarding turn costs ~$0.12 (Sonnet 4.5 with cache creation). Subsequent turns in the same session should be cheaper due to cache hits.
