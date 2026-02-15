# Onboarding UX Fix Plan

## Problem Statement

The onboarding flow doesn't work because:
1. **Vague prompt** — "Begin onboarding. I am a new user of this vault." sounds like "help me learn Obsidian" rather than triggering the steward's onboarding protocol
2. **Claude modifies the file** — With bypassPermissions, Claude used Write tools to overwrite Onboarding.md instead of responding conversationally
3. **No context about the interaction mode** — Claude doesn't know it's responding inline in a note via a plugin, not in a terminal
4. **Framework didn't load properly** — Claude acted as a generic assistant, not the steward

## Desired User Experience

1. User installs plugin, opens Obsidian
2. Sees welcome notice: "Run 'Begin onboarding' from the command palette to begin."
3. Runs command → Onboarding.md opens with Claude's first question already streaming
4. User reads the question, types their answer below the callout, adds `@Claude`, presses Enter
5. Claude processes answer (may create a profile file), asks next question (rendered as new callout)
6. Repeat through 5 sections: identity → relationships → commitments → current state → help areas
7. After each section, Claude creates the corresponding profile file
8. Final message: Claude confirms onboarding complete, profile created
9. On next plugin load — no welcome notice (profile/index.md exists)

## Root Causes & Fixes

### Fix 1: Rewrite the initial onboarding prompt

The prompt sent to Claude Code in `-p` mode needs to be explicit and constraining.

**Current (broken):**
```
@Claude Begin onboarding. I am a new user of this vault.
```

**Proposed:**
```
You are responding inside an Obsidian note via the Generous Ledger plugin. Your response will be rendered as a callout block in the note — do NOT use the Write tool to modify this file.

Follow the Onboarding Protocol in CLAUDE.md. Begin with the opening statement, then ask the first question about identity and station. Ask ONE question at a time. Wait for the user's next message before continuing.

Do not explore the vault. Do not create any files yet. Just introduce yourself and ask the first question.
```

Key changes:
- Tells Claude it's responding inline (not terminal)
- Explicitly says don't Write to the current file
- Says don't explore the vault
- Says ask one question, then wait
- Defers file creation to later turns

### Fix 2: Add interaction context to CLAUDE.md

Add a section to CLAUDE.md explaining the plugin interaction mode:

```markdown
# Plugin Interaction Mode

When invoked via the Obsidian plugin (@Claude trigger):
- Your response is rendered as a callout block in the user's note
- Do NOT use Write/Edit tools to modify the current note — the plugin handles rendering
- You MAY use Write tools to create/update OTHER files (profile files, etc.)
- Each user message is a new turn — keep responses focused and conversational
- The user will type their response below your callout and trigger you again
```

### Fix 3: Separate the onboarding prompt from the file content

Instead of writing `@Claude Begin onboarding...` into Onboarding.md (which gets sent as the prompt AND stays in the file), the plugin should:

1. Create Onboarding.md with just a title and frontmatter (no @Claude text)
2. Send the onboarding prompt directly via `-p` without it appearing in the note
3. The response streams in as a callout

**Onboarding.md content (what the user sees):**
```markdown
---
claude_session_id:
---
# Onboarding
```

**Prompt sent to Claude (not in the file):**
```
You are responding inside an Obsidian note via the Generous Ledger plugin...
[full onboarding trigger prompt]
```

### Fix 4: Consider restricting tool use during conversational turns

The `--permission-mode bypassPermissions` flag gives Claude full tool access. During onboarding conversation turns (questions/answers), Claude shouldn't need most tools. Options:

- **Option A:** Keep bypassPermissions but rely on prompt instructions to constrain behavior. Simpler, less reliable.
- **Option B:** Use `--allowedTools` to restrict to Read-only during conversation, then expand when creating profile files. More complex, more reliable.
- **Option C:** Don't use bypassPermissions at all — use a more restrictive permission mode. Claude would need approval for file operations.

**Recommendation:** Option A for now (prompt constraints), revisit if Claude keeps going rogue. The onboarding prompt should be explicit enough.

## Implementation Steps

### Step 1: Update CLAUDE.md
Add "Plugin Interaction Mode" section explaining inline response constraints.

### Step 2: Rewrite startOnboarding() in main.ts
- Create Onboarding.md with just title/frontmatter (no @Claude text)
- Open the file
- Send the onboarding prompt directly via ClaudeCodeProcess (not via Enter key handler)
- Stream response into the open editor

### Step 3: Craft the onboarding prompt
A carefully worded prompt that:
- Sets context (you're in Obsidian, responding inline)
- Triggers the onboarding protocol from CLAUDE.md
- Constrains behavior (don't explore, don't modify this file, ask one question)

### Step 4: Test the full flow
1. Delete any existing profile/ and Onboarding.md
2. Reload plugin
3. Run "Begin onboarding"
4. Verify: steward introduction + first question
5. Answer the question, @Claude, Enter
6. Verify: Claude processes answer, may create profile file, asks next question
7. Complete all 5 sections
8. Verify: profile/ directory exists with all files

## Open Questions

1. **Should subsequent answers require @Claude?** — Current UX requires typing @Claude after each answer. This feels clunky during onboarding. Alternative: detect that we're in Onboarding.md and auto-trigger on Enter without needing @Claude.
2. **What if Claude creates profile files in the wrong location?** — The vault root is different from the project repo. Profile files should go to `<vault>/profile/`, not `<project>/profile/`.
3. **Should we show a different visual indicator during onboarding?** — Maybe a progress indicator showing which section we're on.
