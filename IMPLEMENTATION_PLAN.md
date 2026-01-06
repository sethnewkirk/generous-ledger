# Generous Ledger - Obsidian Plugin Implementation Plan

## Project Overview

**Plugin Name:** Generous Ledger
**Primary Feature:** Inline Claude AI assistant triggered by `@Claude` mentions

## Feature Specification

When a user types `@Claude` (case-insensitive) in a paragraph and presses Enter (not Shift+Enter):
1. Visual indicator shows the command has been recognized
2. Paragraph content is sent to Claude's API
3. Response appears below in dark purple font
4. User can continue editing normally

---

## Architecture & Technology Stack

### Core Technologies
- **Language:** TypeScript (for type safety and Obsidian API compatibility)
- **Build System:** esbuild (fast compilation, standard for Obsidian plugins)
- **Editor Framework:** CodeMirror 6 (Obsidian's underlying editor)
- **API Integration:** Anthropic SDK (@anthropic-ai/sdk)
- **Runtime:** Obsidian desktop (requires Node.js environment)

### Plugin Structure
```
generous-ledger/
├── src/
│   ├── main.ts                    # Plugin entry point
│   ├── settings.ts                # Settings tab for API key
│   ├── editor/
│   │   ├── claudeDetector.ts      # Detects @Claude mentions
│   │   ├── paragraphExtractor.ts  # Extracts paragraph content
│   │   └── visualIndicator.ts     # Widget for visual feedback
│   ├── api/
│   │   └── claudeClient.ts        # Anthropic API wrapper
│   └── renderer/
│       └── responseRenderer.ts    # Renders Claude responses
├── manifest.json                  # Plugin metadata
├── package.json                   # Dependencies
├── tsconfig.json                  # TypeScript config
├── esbuild.config.mjs            # Build configuration
└── styles.css                     # Plugin styling
```

---

## Implementation Components

### 1. Trigger Detection System

**Component:** `claudeDetector.ts`

**Approach:** CodeMirror 6 View Plugin
- Monitor editor state changes for `@claude` pattern (case-insensitive)
- Track cursor position relative to mention
- Distinguish Enter vs Shift+Enter keypresses

**Technical Details:**
- Use `ViewPlugin.fromClass()` for reactive editor monitoring
- Implement `keydown` event listener in editor extension
- Regex pattern: `/@claude\b/i` to detect trigger
- State tracking: maintain "pending command" flag when @Claude detected

**Challenges & Solutions:**
- **Challenge:** Determining paragraph boundaries in Markdown
- **Solution:** Use CodeMirror's syntax tree to find block boundaries (paragraphs are typically bounded by double newlines or block elements)

### 2. Visual Indicator

**Component:** `visualIndicator.ts`

**Approach:** Widget Decoration
- Show inline icon/badge when `@Claude` is typed
- Indicate "processing" state while API call is in progress
- Clear indicator after response is rendered

**Implementation:**
```typescript
class ClaudeIndicatorWidget extends WidgetType {
  constructor(private state: 'ready' | 'processing') {}

  toDOM(view: EditorView): HTMLElement {
    const span = document.createElement("span");
    span.className = `claude-indicator ${this.state}`;
    span.innerText = this.state === 'ready' ? '🤖' : '⏳';
    return span;
  }
}
```

**Styling (styles.css):**
- Subtle background highlight on `@Claude` text
- Animated spinner/pulse during processing
- Color scheme aligned with Obsidian's theme system

### 3. Paragraph Extraction

**Component:** `paragraphExtractor.ts`

**Logic:**
1. Find cursor position when Enter is pressed
2. Scan backward to find paragraph start (previous blank line or document start)
3. Scan forward to find paragraph end (next blank line or document end)
4. Extract text content, excluding the `@Claude` trigger itself

**Edge Cases:**
- Multiple `@Claude` mentions in same paragraph → send entire paragraph once
- `@Claude` in middle of paragraph → include full paragraph
- `@Claude` in list item → treat list item as paragraph
- `@Claude` in blockquote/callout → extract that block

### 4. Claude API Integration

**Component:** `claudeClient.ts`

**Setup:**
```typescript
import Anthropic from '@anthropic-ai/sdk';

export class ClaudeClient {
  private client: Anthropic;

  constructor(apiKey: string) {
    this.client = new Anthropic({ apiKey });
  }

  async sendMessage(content: string): Promise<string> {
    const message = await this.client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [{ role: 'user', content }]
    });

    return message.content[0].text;
  }
}
```

**Configuration Options:**
- Model selection (Sonnet for speed, Opus for complex reasoning)
- Max tokens limit
- Temperature/creative settings
- System prompts (optional: e.g., "You are a helpful assistant in Obsidian")

**Error Handling:**
- Network failures → show inline error message
- API key issues → prompt user to check settings
- Rate limits → queue requests or show cooldown message

### 5. Response Rendering

**Component:** `responseRenderer.ts`

**Approach:** Insert formatted text below trigger paragraph

**Implementation:**
1. After API response received, calculate insertion position (end of paragraph + newline)
2. Insert response text with special formatting marker
3. Apply dark purple styling via CSS class

**Format Options:**

**Option A: Plain text with CSS class**
```
@Claude What is quantum computing?

[Response in dark purple]
Quantum computing is a type of computation that harnesses quantum mechanical phenomena...
```

**Option B: Blockquote format**
```
@Claude What is quantum computing?

> [!claude] Claude's Response
> Quantum computing is a type of computation that harnesses quantum mechanical phenomena...
```

**Recommendation:** Option B (callout format)
- More visually distinct
- Plays well with Obsidian's callout syntax
- Easier to identify and edit later
- Can be collapsed if needed

**CSS Styling:**
```css
.claude-response {
  color: #9370DB; /* Dark purple */
  border-left: 3px solid #9370DB;
  padding-left: 12px;
  margin: 8px 0;
  font-style: italic;
}

.claude-response-callout {
  --callout-color: 147, 112, 219; /* RGB for dark purple */
}
```

### 6. Settings Management

**Component:** `settings.ts`

**Settings Panel:**
- **API Key** (password field, required)
- **Model Selection** (dropdown: Sonnet 4 / Opus 4.5)
- **Max Response Length** (slider: 1000-8000 tokens)
- **Response Format** (dropdown: Callout / Plain text / Inline)
- **Custom System Prompt** (textarea, optional)

**Storage:**
- Store settings in Obsidian's data.json (encrypted for API key)
- Validate API key on save (test with simple API call)

---

## User Experience Flow

### Happy Path
1. User types paragraph: "What is the capital of France? @Claude"
2. Visual indicator appears next to `@Claude` (🤖)
3. User presses Enter
4. Indicator changes to processing state (⏳)
5. Response appears below in dark purple:
   ```
   > [!claude] Response
   > The capital of France is Paris. It has been the country's capital since...
   ```
6. User can continue editing or ask another question

### Edge Cases Handled
- **Shift+Enter pressed:** Insert newline, don't trigger API
- **@claude lowercase:** Still triggers (case-insensitive)
- **Multiple @Claude in document:** Each triggers independently
- **No API key set:** Show notification: "Please set your Claude API key in settings"
- **Network error:** Show inline error message, allow retry
- **Empty paragraph:** Don't send request, show hint

---

## Technical Considerations

### CodeMirror 6 Integration
- **View Plugin** for real-time `@Claude` detection (better performance than state field)
- **Decorations** for visual indicators (widget type)
- **Transaction Filters** to intercept Enter key and prevent default newline when triggering

### Paragraph Detection Strategy
Using CodeMirror's syntax tree:
```typescript
function getParagraphBounds(state: EditorState, pos: number) {
  const tree = syntaxTree(state);
  const node = tree.resolveInner(pos);
  // Find nearest paragraph/block node
  let block = node;
  while (block && !['paragraph', 'blockquote', 'list_item'].includes(block.type.name)) {
    block = block.parent;
  }
  return { from: block.from, to: block.to };
}
```

### API Call Optimization
- **Debouncing:** Prevent accidental double-triggers
- **Cancellation:** If user presses Escape, cancel pending request
- **Caching:** (Future enhancement) Cache responses for identical queries
- **Streaming:** (Future enhancement) Stream responses token-by-token

### Performance
- Minimal editor overhead (view plugin only processes visible range)
- Async API calls don't block editor
- Lazy-load Anthropic SDK only when first @Claude triggered

---

## Development Phases

### Phase 1: Setup & Foundation (Estimated: 4-6 hours)
- [ ] Initialize Obsidian plugin project structure
- [ ] Set up TypeScript, esbuild, manifest.json
- [ ] Create settings tab for API key input
- [ ] Install and configure Anthropic SDK
- [ ] Test basic API connectivity

### Phase 2: Editor Integration (Estimated: 6-8 hours)
- [ ] Implement CodeMirror view plugin for @Claude detection
- [ ] Add visual indicator widget
- [ ] Implement Enter key interception
- [ ] Build paragraph extraction logic
- [ ] Handle edge cases (Shift+Enter, multiple mentions)

### Phase 3: API & Response Handling (Estimated: 4-5 hours)
- [ ] Create Claude API wrapper with error handling
- [ ] Implement response insertion logic
- [ ] Style responses with dark purple formatting
- [ ] Add loading states and error messages

### Phase 4: Polish & Testing (Estimated: 3-4 hours)
- [ ] Test across different note formats (lists, tables, callouts)
- [ ] Ensure compatibility with Obsidian themes
- [ ] Add keyboard shortcuts (optional: Cmd/Ctrl+Shift+C to insert @Claude)
- [ ] Write user documentation

**Total Estimated Time:** 17-23 hours of focused development

---

## Clarifying Questions

Before implementation begins, please clarify:

### 1. API Key Management
**Question:** Should users provide their own Anthropic API key, or will you provide a shared key?
- **Option A:** User brings their own key (more common, recommended)
- **Option B:** Plugin includes shared key (requires backend proxy for security)

### 2. Response Format Preference
**Question:** Which response format do you prefer?
- **Option A:** Callout block (e.g., `> [!claude] Response`)
- **Option B:** Plain text with dark purple styling
- **Option C:** Indented quote block
- **Option D:** Custom markdown format (specify)

### 3. Context Awareness
**Question:** Should Claude have context beyond the paragraph?
- **Option A:** Only send the paragraph containing @Claude
- **Option B:** Send entire note as context (better responses, higher cost)
- **Option C:** Send paragraph + N lines before/after for context
- **Option D:** User configurable in settings

### 4. Response Editing
**Question:** What should happen if user edits a Claude response?
- **Option A:** Nothing - it's just text, user can edit freely
- **Option B:** Show indicator that response was modified
- **Option C:** Option to regenerate if edited

### 5. Conversation Threading
**Question:** (Future feature) Should multiple @Claude calls in same note form a conversation?
- **Option A:** Each @Claude is independent (simpler)
- **Option B:** Maintain conversation history within note (more powerful, complex)

### 6. Mobile Support
**Question:** Is mobile support required?
- **Note:** Current plan targets desktop only (requires Node.js runtime). Mobile would require REST API approach (more complex architecture)

---

## Dependencies

### npm Packages
```json
{
  "dependencies": {
    "@anthropic-ai/sdk": "^0.30.0",
    "obsidian": "latest"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@typescript-eslint/eslint-plugin": "^6.0.0",
    "esbuild": "^0.20.0",
    "typescript": "^5.3.0"
  }
}
```

### Obsidian Minimum Version
- Target: Obsidian 1.4.0+ (for stable CodeMirror 6 API)

---

## Success Criteria

The feature is complete when:
1. ✅ User can type `@Claude` (any case) and see visual indicator
2. ✅ Pressing Enter sends paragraph to API and renders response
3. ✅ Shift+Enter inserts newline without triggering API
4. ✅ Response appears in dark purple, clearly distinguished from user's text
5. ✅ Error states are handled gracefully with user-friendly messages
6. ✅ Settings allow API key configuration
7. ✅ Performance is smooth (no noticeable lag during typing)

---

## Next Steps

1. **Answer clarifying questions above**
2. **Review and approve this plan**
3. **Set up development environment**
4. **Begin Phase 1 implementation**

---

## References & Inspiration

- [Obsidian Claude Code Plugin](https://github.com/Roasbeef/obsidian-claude-code) - Full SDK integration approach
- [Obsidian Copilot](https://github.com/logancyang/obsidian-copilot) - Multi-provider AI integration
- [Obsidian Sample Plugin](https://github.com/obsidianmd/obsidian-sample-plugin) - Official template
- [CodeMirror Decorations Docs](https://marcusolsson.github.io/obsidian-plugin-docs/editor/extensions/decorations) - Visual indicators guide
- [Anthropic API Docs](https://docs.anthropic.com/en/api/messages) - Claude API reference
