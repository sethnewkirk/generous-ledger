---
date: 2026-02-21T00:06:45-05:00
session_name: general
researcher: claude
git_commit: c317ebd
branch: main
repository: generous-ledger
topic: "Retro Terminal Onboarding UI"
tags: [implementation, terminal-ui, onboarding, obsidian-plugin, typewriter, fullscreen]
status: in_progress
last_updated: 2026-02-21
last_updated_by: claude
type: implementation_strategy
root_span_id:
turn_span_id:
---

# Handoff: Retro Terminal Onboarding UI — Centered Layout Built, Polish Needed

## Task(s)

- **Replace markdown-based onboarding with retro terminal UI** (in progress) — The old `Onboarding.md` callout-based flow has been replaced with a custom `ItemView` that renders a fullscreen black terminal with green monospace text, typewriter effect for steward responses, and CRT-style scanlines/vignette. Three iterations completed: initial implementation, fullscreen fix, centered layout.
- **Interview behavior review** (not started) — User wants to examine and improve how the 5-section interview acts. This is the next step.

Working from implementation plan at `/Users/seth/.claude/plans/purrfect-zooming-lemur.md`.

## Critical References

- `CLAUDE.md` — The steward framework delivery mechanism. All onboarding protocols, interview flow, and profile creation rules live here.
- `/Users/seth/.claude/plans/purrfect-zooming-lemur.md` — The terminal UI implementation plan (Phases 1-5).
- `/Users/seth/.claude/plans/shimmying-snuggling-waterfall.md` — Master implementation plan (all 6 phases complete, this terminal work is a UX overhaul of Phase 4).

## Recent Changes

**All changes are uncommitted.** Git is still at `c317ebd`. Files changed:

- `src/terminal-session.ts` (new) — `TerminalSessionStore` class storing session ID and conversation log via `plugin.saveData()` with read-modify-write pattern to avoid clobbering settings.
- `src/terminal-view.ts` (new) — `OnboardingTerminalView extends ItemView`. Three iterations:
  1. Initial: scrolling chat log with bottom input bar
  2. Fullscreen fix: `enterFullscreen()`/`exitFullscreen()` methods, Escape key exit, no longer applies fullscreen on workspace restore
  3. Current: centered single-question layout. Question appears vertically centered (max 60ch). When user types, question disappears and answer echoes in its place. Spinner shows while loading.
- `src/main.ts` — Added: `registerView()`, `startTerminalOnboarding()`, `sendTerminalMessage()`, `sendTerminalPrompt()`, `activateTerminalView()`, `beginTerminalInterview()`. Changed: `start-onboarding` command now calls terminal flow. `saveSettings()` updated to read-modify-write. `ClaudeCodeOptions` imported for proper typing.
- `styles.css` — Added ~140 lines: fullscreen takeover rules (hides sidebar, tabs, title bar, status bar), centered content layout, scanlines/vignette, spinner animation, answer echo styling, hidden input, system messages in top-left corner.

## Learnings

### Obsidian Workspace Restore Trap
`ItemView.onOpen()` fires when Obsidian restores workspace state on startup. If you add `document.body.addClass('gl-terminal-fullscreen')` in `onOpen()`, it will hide all Obsidian chrome on every app launch — bricking the UI. Solution: only apply fullscreen when the user explicitly triggers the command, via a separate `enterFullscreen()` method called from the orchestrator.

### Plugin saveData Clobbering
`plugin.saveData()` overwrites the entire JSON blob. If settings and terminal session data share the same blob, both must use read-modify-write: `const data = await loadData(); data.key = value; await saveData(data)`. The original `saveSettings()` did `saveData(this.settings)` which would clobber the terminal session.

### ClaudeCodeOptions Key Names
The `ClaudeCodeProcess.query()` expects `claudeCodePath` not `claudePath`. Using `any` type hid this bug — always use the proper `ClaudeCodeOptions` interface.

### CSS Scanline Opacity
Initial scanlines at `rgba(0,0,0,0.15)` on 2px spacing made the background look grey, not black. Reduced to `rgba(0,0,0,0.08)` on 4px spacing — barely visible but adds texture.

## Post-Mortem

### What Worked
- **Parallel agent implementation**: Phases 1-3 (session store, view, CSS) were independent and built simultaneously by three agents, then Phase 4 (wiring) by a fourth. Clean build on first try.
- **Decoupled architecture**: `ClaudeCodeProcess` EventEmitter was already cleanly separated from rendering. Swapping in the terminal view required zero changes to `claude-process.ts` or `stream-parser.ts`.
- **Iterative design with user screenshots**: Three rounds of feedback (initial → fullscreen fix → centered layout) converged quickly.

### What Failed
- **Fullscreen in onOpen()**: Caused Obsidian to boot into a black screen. Had to recover via `Obsidian eval` CLI command.
- **Initial scanlines too heavy**: Made background look grey/silver, not the intended black CRT look.
- **Input bar white background**: Obsidian's default input styles leaked through. Required `!important` overrides. Later redesigned to a hidden input element for the centered layout.

### Key Decisions
- Decision: Use `ItemView` (full tab) instead of `Modal` for the terminal
  - Alternatives: Modal overlay, standalone terminal window
  - Reason: Persistent, dockable, full DOM control. Modal dismissed on Escape (fragile).
- Decision: Centered single-question layout (typeform-like) instead of scrolling chat log
  - Alternatives: Keep scrolling chat log
  - Reason: User feedback — wanted full attention pulled in, one question at a time.
- Decision: Fullscreen via body class toggling Obsidian chrome visibility
  - Alternatives: Obsidian's built-in fullscreen, custom window
  - Reason: CSS class on body is simplest. Toggled explicitly (not in onOpen) to avoid workspace restore trap.
- Decision: Store session in `plugin.saveData()` blob alongside settings
  - Alternatives: Separate file, keep Onboarding.md as session store
  - Reason: Obsidian-idiomatic, no extra files. Read-modify-write pattern prevents conflicts.

## Artifacts

- `src/terminal-view.ts` — The complete view class with typewriter, centered layout, answer mode, spinner
- `src/terminal-session.ts` — Session persistence (session ID + conversation log)
- `src/main.ts:386-574` — Terminal orchestrator methods (activateTerminalView, startTerminalOnboarding, beginTerminalInterview, sendTerminalMessage, sendTerminalPrompt)
- `src/main.ts:117-122` — Updated saveSettings() with read-modify-write
- `styles.css:81-234` — All terminal CSS (fullscreen, layout, scanlines, spinner, answer echo)
- `/Users/seth/.claude/plans/purrfect-zooming-lemur.md` — Implementation plan

## Action Items & Next Steps

### Immediate — Polish Terminal UI
1. **Test the centered layout** — User hasn't yet confirmed the latest iteration (centered question, answer-over-question, spinner). May need further tweaks.
2. **Spinner animation** — Currently uses CSS rotation on a `/` character. May want something more polished (blinking dots, pulsing cursor, or actual `|/-\` text cycling via JS).

### Next Priority — Interview Behavior
3. **Examine interview flow** — User explicitly said the next step is "examine the interview and how it's supposed to act." Review the 5-section onboarding protocol in CLAUDE.md and how Claude actually behaves through the terminal. Consider:
   - Does Claude ask one question at a time as instructed?
   - Does it create profile files progressively?
   - Does the prompt need adjustment for the terminal context (no markdown, no tools on this file)?
   - Should the interview be more conversational or structured?
4. **Test end-to-end onboarding** — Run through all 5 sections, verify profile files are created correctly in `profile/`.

### Later
5. **Commit all changes** — Everything is uncommitted. Use `/commit` skill.
6. **Session resume** — Verify that closing and reopening the terminal replays the last question correctly.
7. **Old onboarding cleanup** — The `startOnboarding()` and `sendPromptToEditor()` methods still exist in `main.ts`. The Onboarding.md-specific Enter key handler is also still there. Clean up after validating the new flow.

## Other Notes

### Vault Deployment
```bash
npm run build && cp main.js manifest.json styles.css ~/Documents/Achaean/.obsidian/plugins/generous-ledger/
/Applications/Obsidian.app/Contents/MacOS/Obsidian plugin:reload id=generous-ledger
```

### Recovery from Fullscreen Bug
If Obsidian ever boots into a black screen (fullscreen class stuck on body):
```bash
/Applications/Obsidian.app/Contents/MacOS/Obsidian eval "code=document.body.classList.remove('gl-terminal-fullscreen')"
```
Or open dev tools (Cmd+Opt+I) and run `document.body.classList.remove('gl-terminal-fullscreen')`.

### Profile Exists at Vault Root
The user's vault at `~/Documents/Achaean/` already has a `profile/` directory from earlier testing. The terminal's profile-exists guard will trigger. To test fresh onboarding, temporarily rename `profile/` or type "redo" in the terminal.
