# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Generous Ledger** is an Obsidian plugin that provides inline Claude AI assistance through `@Claude` mentions. Users can type questions followed by `@Claude`, press Enter, and receive AI-generated responses directly in their notes.

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

## Architecture

### Technology Stack
- **TypeScript** - Type-safe development
- **esbuild** - Fast bundling
- **CodeMirror 6** - Editor extensions for visual indicators
- **Anthropic SDK** - Claude API integration
- **Obsidian API** - Plugin framework

### Directory Structure

```
src/
├── main.ts                  # Plugin entry point, orchestrates all components
├── settings.ts              # Settings tab and configuration interface
├── api/
│   └── claudeClient.ts      # Anthropic API wrapper
├── editor/
│   ├── claudeDetector.ts    # CodeMirror extension for @Claude detection
│   ├── paragraphExtractor.ts # Utility to extract paragraph bounds
│   └── visualIndicator.ts   # Widget for visual feedback (🤖/⏳/⚠️)
└── renderer/
    └── responseRenderer.ts  # Formats and inserts Claude responses
```

### High-Level Architecture

1. **Trigger Detection**: CodeMirror 6 state field (`claudeIndicatorField`) monitors editor for `@claude` mentions and displays visual indicators
2. **Enter Key Handling**: DOM event listener intercepts Enter key (but not Shift+Enter) to trigger API call
3. **Paragraph Extraction**: Scans up/down from cursor to find paragraph boundaries (blank lines)
4. **API Communication**: Sends paragraph content (minus @Claude trigger) to Anthropic API
5. **Response Rendering**: Inserts response below paragraph in callout format with dark purple styling

### Key Design Decisions

**CodeMirror Integration**: Uses StateField for decorations rather than ViewPlugin because we need to maintain indicator state across viewport changes.

**Paragraph Detection**: Simple line-based scanning (blank lines as delimiters) rather than syntax tree parsing. Works reliably for Markdown without heavyweight dependencies.

**API Client Separation**: `ClaudeClient` is decoupled from plugin logic, making it easy to swap models or add features like streaming responses.

**Callout Format**: Responses use Obsidian's native callout syntax (`> [!claude]`) so they remain readable as Markdown even if plugin is disabled.

## Testing in Obsidian

To test during development:

1. **Create symlink** from plugin directory to Obsidian vault:
   ```bash
   ln -s /path/to/generous-ledger /path/to/vault/.obsidian/plugins/generous-ledger
   ```

2. **Run dev mode**: `npm run dev` (auto-rebuilds on changes)

3. **Reload plugin** in Obsidian: Cmd/Ctrl+R or toggle plugin off/on in settings

## Configuration

Settings are stored in `.obsidian/plugins/generous-ledger/data.json`:
- `apiKey` - User's Anthropic API key (required)
- `model` - Claude model identifier (default: `claude-sonnet-4-20250514`)
- `maxTokens` - Response length limit (default: 4096)
- `systemPrompt` - Custom behavior instructions (optional)

## Future Enhancements

The codebase is structured to support:
- **Conversation threading**: Maintain context across multiple @Claude calls in same note
- **Configurable context**: Send more than just the paragraph (e.g., entire note, selected text)
- **Model switching**: Per-request model selection
- **Streaming responses**: Real-time token-by-token rendering
- **Mobile support**: Requires REST API architecture instead of direct SDK use
