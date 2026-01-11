# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Generous Ledger** is an Obsidian plugin that provides inline Claude AI assistance through `@Claude` mentions. Users type questions followed by `@Claude`, press Enter, and receive AI-generated responses directly in their notes as callout blocks.

## Development Commands

```bash
# Install dependencies
npm install

# Development mode (watch and auto-rebuild)
npm run dev

# Production build (TypeScript check + bundle)
npm run build

# Version bump (updates manifest.json and versions.json)
npm run version
```

## Testing in Obsidian

To test during development:

1. **Create symlink** from plugin directory to Obsidian vault:
   ```bash
   ln -s /path/to/generous-ledger /path/to/vault/.obsidian/plugins/generous-ledger
   ```

2. **Run dev mode**: `npm run dev` (auto-rebuilds on changes)

3. **Reload plugin** in Obsidian: Cmd/Ctrl+R or toggle plugin off/on in settings

## Architecture

### Technology Stack
- **TypeScript** - Type-safe development with strict null checks
- **esbuild** - Fast bundling, produces ~121KB main.js
- **CodeMirror 6** - Editor extensions for real-time visual indicators
- **Anthropic SDK** - Claude API integration (streaming responses added)
- **Obsidian API** - Plugin framework (desktop only)

### Directory Structure

```
src/
├── main.ts                          # Plugin entry point, orchestrates all components
├── settings.ts                      # Settings tab and configuration interface
├── core/                            # Shared infrastructure
│   └── api/
│       └── claudeClient.ts          # Anthropic API wrapper
└── features/                        # Feature modules
    └── inline-assistant/            # @Claude inline feature
        ├── claudeDetector.ts        # CodeMirror extension for @Claude detection
        ├── paragraphExtractor.ts    # Paragraph boundary detection & extraction
        ├── visualIndicator.ts       # Widget for visual feedback (🤖/⏳/⚠️)
        └── responseRenderer.ts      # Formats and inserts Claude responses
```

### High-Level Data Flow

1. **Trigger Detection**: CodeMirror 6 StateField (`claudeIndicatorField`) monitors editor for `@claude` mentions (case-insensitive) on current line and displays visual indicators

2. **Enter Key Handling**: High-priority keymap intercepts Enter key (but not Shift+Enter) to trigger API call. Concurrent requests are prevented via `processingRequest` flag.

3. **Paragraph Extraction**: Scans up/down from cursor to find paragraph boundaries (blank lines). Handles edge cases like last line of document with bounds checking.

4. **API Communication**: Sends paragraph content (minus @Claude trigger) to Anthropic API with streaming support. Indicators update to processing state (⏳).

5. **Response Rendering**: Verifies document hasn't changed during async call, then inserts response below paragraph in callout format (`> [!claude]`) with dark purple styling

### Key Design Decisions

**CodeMirror StateField over ViewPlugin**: Uses StateField for decorations to maintain indicator state across viewport changes. ViewPlugin would lose state when content scrolls out of view.

**Line-based Paragraph Detection**: Simple blank-line-delimited scanning rather than syntax tree parsing. Fast, reliable for Markdown, no heavyweight dependencies. Handles multi-line paragraphs and edge cases (first/last line).

**Decoupled API Client**: `ClaudeClient` class is separate from plugin logic for testability, model swapping, and streaming response support.

**Obsidian Callout Format**: Responses use native `> [!claude]` syntax so they remain readable as Markdown even if plugin is disabled. Empty lines preserved with lone `>` characters.

**Security-First**: Race condition fixes ensure `processingRequest` flag is always reset (try/finally). Document verification prevents insertion into wrong file if user switches during API call. Array bounds checking prevents crashes.

### Critical Components

**main.ts**:
- Plugin lifecycle (onload/onunload)
- Settings persistence
- CodeMirror extension registration
- Enter key handler with validation
- Request orchestration
- Visual indicator updates

**claudeDetector.ts**:
- `claudeIndicatorField` - StateField managing decorations
- `setIndicatorState` - Effect for state updates
- `findClaudeMentionInView()` - Detects @Claude on current line

**paragraphExtractor.ts**:
- `getParagraphAtCursor()` - Scans up/down for blank lines, returns text + position
- `hasClaudeMention()` - Case-insensitive @Claude detection
- `removeClaudeMentionFromText()` - Strips trigger from content
- Edge case: Bounds checking for last line access

**claudeClient.ts**:
- `sendMessage()` - API wrapper with streaming support
- `updateSettings()` - Reconfigure model/tokens
- Response validation (checks for empty content array)
- Error handling for network failures

**responseRenderer.ts**:
- `initClaudeResponse()` - Creates initial callout structure
- `appendClaudeResponse()` - Streams content
- `finalizeClaudeResponse()` - Closes callout
- `renderClaudeError()` - User-friendly error display
- Empty line handling: `line.trim() ? '> ${line}' : '>'`

## Configuration

Settings stored in `.obsidian/plugins/generous-ledger/data.json`:
- `apiKey` - User's Anthropic API key (required, stored as plain text per Obsidian standard)
- `model` - Claude model identifier (default: `claude-sonnet-4-20250514`)
- `maxTokens` - Response length limit (default: 4096, range: 1000-8000)
- `systemPrompt` - Custom behavior instructions (optional)

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

## Security Notes

**Fixed Critical Issues**:
1. Race condition in `processingRequest` flag - now uses try/finally
2. Paragraph boundary crash on last line - added bounds checking
3. Null reference in API response - validates content array before access
4. Document switch during API call - verifies active view hasn't changed
5. Stale position references - recalculates in error handlers

**API Key Handling**:
- Stored locally in Obsidian's data.json
- Password field in settings UI
- Never logged or transmitted except to Anthropic

**Acceptable Low-Priority Items**:
- No rate limiting (user's API key, their responsibility)
- Global keydown listener (minor performance impact)
- No max content length (intentional for v1)

## Future Extensibility

The modular architecture supports these planned enhancements:

- **Conversation threading**: Extend ClaudeClient to maintain message history across @Claude calls
- **Extended context**: New context extractors (whole note, selection, vault search)
- **Model switching**: Per-request model selection via syntax (`@Claude:opus`)
- **Mobile support**: REST API proxy (Anthropic SDK requires Node.js)

## Documentation

- **[DEVELOPMENT.md](./docs/DEVELOPMENT.md)** - Setup and workflow
- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - Detailed system design
- **[SECURITY.md](./docs/SECURITY.md)** - Security audit and fixes
