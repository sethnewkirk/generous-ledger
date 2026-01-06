# Architecture Documentation

## Overview

**Generous Ledger** is an Obsidian plugin that integrates Claude AI directly into note-taking through inline mentions. The architecture is designed to be modular, extensible, and safe.

---

## Technology Stack

- **TypeScript** - Type-safe development
- **esbuild** - Fast compilation and bundling
- **CodeMirror 6** - Editor integration for visual feedback
- **Anthropic SDK** - Direct Claude API communication
- **Obsidian API** - Plugin framework integration

---

## Project Structure

```
generous-ledger/
├── src/
│   ├── main.ts                      # Plugin entry point
│   ├── settings.ts                  # Settings interface
│   ├── core/                        # Shared infrastructure
│   │   └── api/
│   │       └── claudeClient.ts      # Anthropic API wrapper
│   └── features/                    # Feature modules
│       └── inline-assistant/        # @Claude inline feature
│           ├── claudeDetector.ts    # Mention detection
│           ├── paragraphExtractor.ts # Text extraction
│           ├── visualIndicator.ts   # Visual feedback widget
│           └── responseRenderer.ts  # Response formatting
│
├── styles/
│   └── main.css                     # Plugin styling
│
├── docs/                            # Documentation
│   ├── DEVELOPMENT.md              # Developer guide
│   ├── ARCHITECTURE.md             # This file
│   ├── SECURITY.md                 # Security audit & fixes
│   ├── IMPLEMENTATION_PLAN.md      # Original plan
│   └── CONTINUOUS_CLAUDE.md        # CC setup
│
├── thoughts/                        # Continuous Claude artifacts
│   ├── ledgers/                    # Session state
│   ├── shared/handoffs/            # Task post-mortems
│   └── shared/plans/               # Implementation plans
│
└── .claude/cache/                  # CC database (gitignored)
```

---

## High-Level Data Flow

### 1. Trigger Detection

```
User types "@Claude" in editor
        ↓
CodeMirror 6 StateField (claudeIndicatorField)
        ↓
findClaudeMentionInView() checks current line
        ↓
Visual indicator widget shown (🤖)
```

### 2. Request Initiation

```
User presses Enter (not Shift+Enter)
        ↓
DOM keydown listener intercepts
        ↓
handleEnterKey() validates context
        ↓
getParagraphAtCursor() extracts text
        ↓
hasClaudeMention() confirms @Claude present
```

### 3. API Communication

```
removeClaudeMentionFromText() cleans input
        ↓
Visual indicator changes to processing (⏳)
        ↓
ClaudeClient.sendMessage() calls Anthropic API
        ↓
Response validated and returned
```

### 4. Response Rendering

```
Verify still in same document
        ↓
Clear visual indicator
        ↓
renderClaudeResponse() formats as callout
        ↓
Insert below paragraph in Markdown
```

---

## Core Components

### Main Plugin (`main.ts`)

**Responsibilities:**
- Plugin lifecycle management (load/unload)
- Settings persistence
- CodeMirror extension registration
- Event handler coordination
- Request orchestration

**Key Methods:**
- `onload()` - Initialize plugin, register extensions
- `handleEnterKey()` - Process @Claude triggers
- `updateVisualIndicator()` - Real-time indicator updates

---

### Settings (`settings.ts`)

**Responsibilities:**
- User configuration interface
- API key management
- Model selection
- Token limits and system prompts

**Configuration:**
- `apiKey` - User's Anthropic API key
- `model` - Claude model selection (Sonnet/Opus)
- `maxTokens` - Response length limit
- `systemPrompt` - Behavior customization

---

### Claude Client (`core/api/claudeClient.ts`)

**Responsibilities:**
- Anthropic API abstraction
- Request/response handling
- Error management
- Configuration updates

**Design Decision:** Decoupled from plugin logic for:
- Easy model swapping
- Future streaming support
- Testability
- Reusability

---

### Inline Assistant Feature

#### Claude Detector (`claudeDetector.ts`)

**Responsibilities:**
- CodeMirror 6 integration
- @Claude mention detection
- Visual indicator state management

**Key Exports:**
- `claudeIndicatorField` - StateField for decorations
- `setIndicatorState` - State update effect
- `findClaudeMentionInView()` - Mention position finder

**Design Decision:** Uses StateField over ViewPlugin because we need to maintain indicator state across viewport changes.

---

#### Paragraph Extractor (`paragraphExtractor.ts`)

**Responsibilities:**
- Text boundary detection
- Content extraction
- Mention removal

**Algorithm:**
- Scan backward from cursor until blank line or document start
- Scan forward until blank line or document end
- Extract bounded text
- Remove @Claude trigger

**Design Decision:** Simple line-based scanning (blank line delimiters) rather than syntax tree parsing. Reliable for Markdown without heavyweight dependencies.

---

#### Visual Indicator (`visualIndicator.ts`)

**Responsibilities:**
- CodeMirror 6 widget creation
- State visualization (🤖/⏳/⚠️)
- Accessibility labels

**States:**
- `ready` - @Claude detected, ready to send
- `processing` - API call in progress
- `error` - Request failed

---

#### Response Renderer (`responseRenderer.ts`)

**Responsibilities:**
- Format Claude responses as Obsidian callouts
- Handle empty lines properly
- Position insertion correctly
- Error rendering

**Output Format:**
```markdown
> [!claude] Claude's Response
> Response text here
> With proper formatting
```

**Design Decision:** Uses Obsidian's native callout syntax so responses remain readable as Markdown even if plugin is disabled.

---

## Key Design Decisions

### 1. CodeMirror 6 Integration

**Choice:** StateField for decorations
**Rationale:** Need to maintain indicator state across viewport changes. ViewPlugin would lose state when content scrolls out of view.

### 2. Paragraph Detection

**Choice:** Line-based scanning with blank line delimiters
**Rationale:**
- Simple and reliable for Markdown
- No heavyweight syntax parsing needed
- Fast performance
- Works with all Markdown variants

### 3. API Client Architecture

**Choice:** Separate ClaudeClient class
**Rationale:**
- Testable in isolation
- Easy to swap models
- Supports future streaming
- Reusable for other features

### 4. Response Format

**Choice:** Obsidian callout blocks
**Rationale:**
- Native Obsidian syntax
- Readable without plugin
- Collapsible
- Themeable
- Consistent with Obsidian UX

### 5. Modular Feature Organization

**Choice:** Features in separate directories
**Rationale:**
- Clear boundaries for future features
- Easy to add new capabilities
- Shared core (API client) separate from features
- Scalable architecture

---

## Future Extensibility

The architecture supports these planned enhancements:

### Conversation Threading
**Location:** `src/features/conversation/`
**Integration:** Extend ClaudeClient to maintain message history

### Extended Context
**Location:** `src/core/context/`
**Integration:** New context extractors (whole note, selection, vault search)

### Model Switching
**Location:** Settings UI + claudeDetector
**Integration:** Per-request model selection via syntax (`@Claude:opus`)

### Streaming Responses
**Location:** ClaudeClient + responseRenderer
**Integration:** Token-by-token rendering with progress indication

### Mobile Support
**Location:** `src/core/api-proxy/`
**Integration:** REST API proxy since Anthropic SDK requires Node.js

---

## Security Architecture

### API Key Handling
- Stored in Obsidian's data.json (local only)
- Password field in settings UI
- Never logged or transmitted except to Anthropic

### Request Validation
- Content validation before API call
- Document context verification after async operation
- Concurrent request prevention
- Bounds checking on all array access

### Error Handling
- All API errors caught and handled
- User-friendly error messages
- Errors rendered in document for transparency
- Console logging for debugging

---

## Performance Considerations

### Visual Indicator
- Lightweight widget (3 emoji states)
- Only processes visible viewport
- Minimal re-renders

### Paragraph Extraction
- O(n) where n = paragraph length
- Early termination on blank lines
- No regex overhead

### API Calls
- Async/await non-blocking
- Single request at a time
- User can continue editing during request

### Bundle Size
- Main bundle: ~121KB
- Tree-shaking enabled
- Only required Anthropic SDK features

---

## Testing Strategy

### Critical Paths
1. @Claude detection and visual feedback
2. Enter key handling (with Shift+Enter bypass)
3. Paragraph boundary detection
4. API communication
5. Response rendering
6. Error handling

### Edge Cases
- Last line of document
- Empty content
- Document switch during request
- Network failures
- Invalid API responses
- Very long paragraphs

---

## Development Workflow

```bash
# Development cycle
npm run dev          # Watch mode, auto-rebuild
# Test in Obsidian (Cmd/Ctrl+R to reload)

# Production build
npm run build        # TypeScript check + bundle

# Version bump
npm run version      # Update manifest + versions.json
```

---

## Dependencies

### Runtime
- `obsidian` - Plugin API
- `@anthropic-ai/sdk` - Claude API client
- `@codemirror/state` - Editor state
- `@codemirror/view` - Editor view/decorations

### Development
- `typescript` - Type checking
- `esbuild` - Fast bundling
- `@types/node` - Node.js types

---

## Maintenance Notes

### Adding New Features
1. Create feature directory in `src/features/`
2. Export feature interface from feature's index
3. Register in `main.ts`
4. Update settings if needed
5. Add tests
6. Document in this file

### Modifying Core API
1. Update `ClaudeClient` interface
2. Maintain backward compatibility
3. Update all feature consumers
4. Test error handling
5. Update type definitions

### Updating Dependencies
1. Test with `npm run build`
2. Verify Obsidian API compatibility
3. Check bundle size impact
4. Update type definitions if needed

---

**Last Updated:** 2026-01-06
**Plugin Version:** 1.0.0
**Architecture Version:** 1.0
