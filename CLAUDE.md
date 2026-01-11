# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Generous Ledger** is an Obsidian plugin that provides inline Claude AI assistance through `@Claude` mentions. Users type questions followed by `@Claude`, press Enter, and receive AI-generated responses directly in their notes with character-by-character streaming and intelligent thinking collapse.

## Development Commands

```bash
# Install dependencies
npm install

# Development mode (watch and auto-rebuild)
npm run dev

# Production build (TypeScript check + bundle)
npm run build

# Run tests
npm test

# Deploy to test vault
npm run build && cp main.js ~/path/to/vault/.obsidian/plugins/generous-ledger/

# Version bump (updates manifest.json and versions.json)
npm run version
```

## Testing in Obsidian

To test during development:

1. **Build and deploy**:
   ```bash
   npm run build && cp main.js ~/generous-ai/Vault/.obsidian/plugins/generous-ledger/
   ```

2. **Reload plugin** in Obsidian:
   - Settings → Community plugins → Toggle generous-ledger OFF then ON
   - Or: Cmd/Ctrl+R

3. **Test streaming**:
   - Short response (no collapse): `@Claude what is 2+2?`
   - Long response (thinking collapse): `@Claude explain binary search step by step`

4. **Check Developer Console**:
   - View → Toggle Developer Tools
   - Look for errors or streaming logs

## Architecture

### Technology Stack
- **TypeScript** - Type-safe development with strict null checks
- **esbuild** - Fast bundling, produces main.js
- **CodeMirror 6** - Editor extensions for @Claude detection and visual indicators
- **Claude Code CLI** - Subprocess integration with stream-json output
- **Jest** - Testing framework with MockEditor
- **Obsidian API** - Plugin framework (desktop only)

### Directory Structure

```
src/
├── main.ts                          # Plugin entry point, CLI process orchestration
├── settings.ts                      # Settings tab (model selection, system prompt)
├── core/                            # Shared infrastructure
│   ├── claude-code/                 # Claude Code CLI integration
│   │   ├── process-manager.ts       # Subprocess spawning and management
│   │   ├── stream-parser.ts         # JSON stream parsing, text extraction
│   │   └── session-manager.ts       # Frontmatter CRUD for session IDs
│   ├── format/                      # Format detection and rendering
│   │   ├── format-detector.ts       # Detects .md/.canvas/.base files
│   │   ├── format-renderer.ts       # Polymorphic renderers per format
│   │   └── __tests__/               # Jest tests for rendering
│   │       └── format-renderer.test.ts
│   └── skills/                      # Skills installation
│       └── skills-installer.ts      # Downloads obsidian-skills from repo
└── features/                        # Feature modules
    └── inline-assistant/            # @Claude inline feature
        ├── claudeDetector.ts        # CodeMirror extension for @Claude detection
        ├── paragraphExtractor.ts    # Paragraph boundary detection & extraction
        └── visualIndicator.ts       # Widget for visual feedback (🤖/⏳/⚠️/🔧)
```

### High-Level Data Flow

1. **Trigger Detection**: CodeMirror 6 StateField (`claudeIndicatorField`) monitors editor for `@claude` mentions (case-insensitive) and displays visual indicators

2. **Enter Key Handling**: High-priority keymap intercepts Enter key to spawn Claude Code CLI process. Concurrent requests prevented via `processingRequest` flag.

3. **Paragraph Extraction**: Scans up/down from cursor to find paragraph boundaries (blank lines). Strips YAML frontmatter and @Claude trigger from content.

4. **CLI Process Spawning**: Spawns Claude Code as subprocess with:
   - `-p <prompt>` - Direct prompt mode
   - `--output-format stream-json` - JSON streaming output
   - `--verbose` - Required for stream-json with -p
   - `--include-partial-messages` - Character-by-character streaming
   - `--permission-mode bypassPermissions` - Auto-approve operations
   - `--model <model>` - User-selected model (Sonnet/Opus)
   - `--resume <session-id>` - Session continuity (from frontmatter)

5. **Stream Parsing**: Parses JSON lines from stdout:
   - `stream_event` messages → Incremental text deltas
   - `tool_use` blocks → Visual indicator updates (🔧 Reading...)
   - `session_id` field → Saved to frontmatter for continuity

6. **Response Rendering**: Format-specific renderer:
   - **Markdown**: Callout block with thinking collapse
   - **Canvas**: New text node with edge (not yet functional - see handoffs)
   - **Base**: Companion .md file

7. **Thinking Collapse**: On finalize, if multi-paragraph response:
   - Last paragraph = answer (visible)
   - Earlier paragraphs = thinking (collapsed in `[!note]- Thinking` callout)

### Key Design Decisions

**Claude Code CLI over Anthropic SDK**: Full tool access (Read, Write, Bash, Grep, etc.) enables richer interactions. Session persistence built-in via `--resume` flag.

**Stream Event Parsing**: Parse `stream_event` messages with `content_block_delta` events for character-by-character streaming. Ignore `assistant` messages (full accumulated text) to avoid duplicates.

**Thinking Collapse Heuristic**: Simple paragraph-based separation:
- ≤1 paragraph OR (2 paragraphs AND <100 chars) → No collapse
- Multiple paragraphs → Last = answer, rest = thinking
- Works naturally with Claude's response structure

**Nested Collapsible Callout**: Use Obsidian's native `> > [!note]- Thinking` syntax instead of HTML `<details>` tags (which don't render inside blockquotes).

**Format Detection System**: Polymorphic renderers allow different output strategies per format (.md callouts, .canvas nodes, .base companion files).

**Session Persistence**: Store Claude Code session ID in note frontmatter (`claude_session_id`). Each note maintains separate conversation context.

**Test-Driven Development**: Thinking collapse feature developed with TDD approach using MockEditor that simulates Obsidian's Editor API.

### Critical Components

**main.ts**:
- Plugin lifecycle (onload/onunload)
- Claude Code CLI readiness check
- Enter key handler registration
- Process spawning and event handling
- Format detection and renderer creation
- Visual indicator updates during tool use
- Clear session command

**process-manager.ts**:
- `ClaudeCodeProcess` - EventEmitter-based subprocess wrapper
- `query()` - Spawns claude CLI with arguments
- Stdout parsing - Line-based JSON message extraction
- Stderr capture - Error logging
- `findClaudePath()` - Locates CLI in common install locations
- `checkClaudeCodeVersion()` - Validates installation and auth

**stream-parser.ts**:
- `StreamMessage` interface - Typed stream event structure
- `extractStreamingText()` - Accumulates text from `content_block_delta` events
- `extractSessionId()` - Finds session ID in message stream
- `extractCurrentToolUse()` - Determines active tool for indicator

**session-manager.ts**:
- `getSessionId()` - Reads `claude_session_id` from frontmatter
- `setSessionId()` - Writes session ID to frontmatter
- `clearSession()` - Removes session ID (fresh conversation)
- Frontmatter validation and error handling

**format-detector.ts**:
- `detectFormat()` - Returns 'markdown' | 'canvas' | 'base' by extension
- `buildFormatContext()` - Creates format-specific context object
- `findNodeAtPosition()` - Locates canvas node containing @Claude
- `findConnectedNodes()` - Finds linked canvas nodes

**format-renderer.ts**:
- `ResponseRenderer` interface - init/append/finalize methods
- `MarkdownRenderer` - Callout-based rendering with thinking collapse
- `CanvasRenderer` - Creates node + edge (untested, no trigger mechanism)
- `BaseRenderer` - Writes companion .md file
- `separateThinkingFromAnswer()` - Heuristic for collapse logic

**claudeDetector.ts**:
- `claudeIndicatorField` - StateField managing decorations
- `setIndicatorState` - Effect for state updates
- `findClaudeMentionInView()` - Detects @Claude on current line

**paragraphExtractor.ts**:
- `getParagraphAtCursor()` - Scans up/down for blank lines
- `hasClaudeMention()` - Case-insensitive @Claude detection
- `removeClaudeMentionFromText()` - Strips trigger and frontmatter
- Edge case handling for document boundaries

**visualIndicator.ts**:
- Widget rendering for different states (waiting/processing/error)
- Tool name display (🔧 Reading..., 🔧 Writing..., etc.)
- Position-based decoration tracking

## Configuration

Settings stored in `.obsidian/plugins/generous-ledger/data.json`:
- `model` - Claude model identifier (default: `claude-sonnet-4-20250514`)
  - Options: Sonnet 4 (faster) or Opus 4 (more capable)
- `maxTokens` - Response length limit (default: 4096)
- `systemPrompt` - Custom behavior instructions (optional)
- `claudeCodePath` - Path to CLI (default: 'claude')
- `additionalFlags` - Extra CLI flags (default: [])

**No API key required**: Uses Claude Code CLI authentication (`claude` command handles auth).

## Commands

- **Clear Claude conversation for this note**: Removes `claude_session_id` from frontmatter, starting fresh conversation

## Build Configuration

**esbuild.config.mjs**:
- Entry: `src/main.ts`
- Output: `main.js` (CommonJS format)
- Target: ES2018
- External: All Obsidian and CodeMirror packages
- Development: inline sourcemaps, watch mode
- Production: tree-shaking, no sourcemaps

**tsconfig.json**:
- Module: ESNext
- Target: ES2022
- Strict null checks enabled
- Source maps: inline

**jest.config.js**:
- Preset: ts-jest
- Test environment: node
- Transform: TypeScript files via ts-jest
- Module name mapper: Obsidian module mocks

## Testing

**Test Framework**: Jest with ts-jest

**MockEditor**: Simulates Obsidian Editor API for testing
- `replaceRange()` - Handles insert and replace operations
- `getCursor()` - Returns cursor position
- `getLine()` - Returns line content
- `lastLine()` - Returns last line number
- `getAllContent()` - Returns full document text

**Test Coverage**:
- Streaming UX behavior (append/finalize)
- Thinking collapse logic (single paragraph, multi-paragraph, short responses)
- MockEditor correctness (insert, replace, newline splitting)

**Run tests**: `npm test`

## Security Notes

**CLI Process Spawning**:
- Spawns subprocess with explicit stdin/stdout/stderr pipes
- Closes stdin immediately (CLI expects this in -p mode)
- No shell interpretation (direct spawn, not shell command)
- Timeout protection (15 minute default)

**Session ID Validation**:
- Validates frontmatter session ID format (>10 chars)
- Shows warning if invalid, starts fresh
- Never trusts malformed data

**Concurrent Request Prevention**:
- `processingRequest` flag prevents overlapping invocations
- Process aborted on plugin unload
- Try/finally ensures flag always reset

**Path Resolution**:
- Checks common install locations before falling back to PATH
- Full path used for subprocess spawn (avoids PATH injection)

## Streaming UX Details

### Character-by-Character Streaming

**How it works**:
1. CLI outputs `stream_event` messages with `content_block_delta` events
2. Each event has `delta.text` field with 1-N characters
3. `extractStreamingText()` accumulates deltas into full text
4. Renderer updates document on each new delta

**Why it matters**: Users see responses appear in real-time as Claude generates them, creating more interactive experience.

### Thinking Collapse

**Trigger conditions**:
- Response has >1 paragraph separated by blank lines
- If 2 paragraphs, total length >100 chars
- Otherwise, treated as short answer (no collapse)

**Rendering**:
```markdown
> [!claude] Claude
> > [!note]- Thinking
> > [thinking paragraph 1]
> > [thinking paragraph 2]
>
> [final answer paragraph]
```

**User experience**:
- Sees full response stream character-by-character
- On completion, thinking collapses automatically
- Can expand "Thinking" to see reasoning
- Final answer remains visible

## Known Limitations

1. **Canvas support**: Enter key handler doesn't work for canvas nodes (requires alternative trigger mechanism - see `thoughts/shared/handoffs/obsidian-claude-code-integration/2026-01-10_22-07-57_canvas-support.md`)

2. **Base format**: Untested (creates companion .md file, may need refinement)

3. **Mobile support**: Requires Claude Code CLI which needs Node.js (desktop only)

4. **Rate limiting**: None (users manage their own Claude Code usage)

## Future Enhancements

Planned features documented in handoffs:

- **Canvas invocations**: Command-based trigger or markdown-to-canvas output
- **Extended context**: Whole note, selection, vault search integration
- **Custom triggers**: Alternative syntax beyond @Claude
- **Response history**: Previous responses browser/search
- **Throttling**: Rate limit for canvas JSON writes

## Handoffs & Documentation

Session state preserved in `thoughts/shared/handoffs/obsidian-claude-code-integration/`:
- `2026-01-10_21-48-04_streaming-ux-complete.md` - Streaming implementation
- `2026-01-10_22-07-57_canvas-support.md` - Canvas investigation
- `2026-01-10_22-20-55_cleanup-and-polish.md` - Cleanup session

Continuity ledger: `thoughts/ledgers/CONTINUITY_CLAUDE-obsidian-claude-code-integration.md`
