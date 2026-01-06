# Repository Reorganization

**Date:** 2026-01-06
**Commit:** 37f0557

## Overview

The repository has been reorganized for better scalability and maintainability. The new structure supports easy addition of features and provides clear separation of concerns.

---

## Before (Scattered Structure)

```
generous-ledger/
├── CLAUDE.md                        # Developer docs
├── CONTINUOUS_CLAUDE_SETUP.md       # CC docs
├── IMPLEMENTATION_PLAN.md           # Planning docs
├── README.md                        # User docs
├── SECURITY_AUDIT.md               # Security docs
├── SECURITY_FIXES_APPLIED.md       # Security docs
├── src/
│   ├── main.ts
│   ├── settings.ts
│   ├── api/
│   │   └── claudeClient.ts
│   ├── editor/                     # Mixed concerns
│   │   ├── claudeDetector.ts
│   │   ├── paragraphExtractor.ts
│   │   └── visualIndicator.ts
│   └── renderer/
│       └── responseRenderer.ts
└── styles.css
```

**Issues:**
- Documentation scattered in root
- No clear feature boundaries
- Hard to add new features
- Unclear what's core vs feature-specific

---

## After (Organized Structure)

```
generous-ledger/
├── README.md                        # Main entry point
│
├── docs/                            # All documentation
│   ├── README.md                   # Docs index
│   ├── DEVELOPMENT.md              # Developer guide
│   ├── ARCHITECTURE.md             # System design
│   ├── SECURITY.md                 # Security info
│   ├── IMPLEMENTATION_PLAN.md      # Original plan
│   └── CONTINUOUS_CLAUDE.md        # CC setup
│
├── src/
│   ├── main.ts                     # Plugin entry
│   ├── settings.ts                 # Settings UI
│   │
│   ├── core/                       # Shared infrastructure
│   │   └── api/
│   │       └── claudeClient.ts     # API wrapper
│   │
│   └── features/                   # Feature modules
│       └── inline-assistant/       # @Claude feature
│           ├── claudeDetector.ts
│           ├── paragraphExtractor.ts
│           ├── visualIndicator.ts
│           └── responseRenderer.ts
│
├── styles/                          # Organized styling
│   └── main.css
│
├── thoughts/                        # Continuous Claude
│   ├── ledgers/
│   ├── shared/handoffs/
│   └── shared/plans/
│
└── .claude/cache/                  # CC database (gitignored)
```

**Benefits:**
- Clean root directory
- Documentation centralized
- Clear feature boundaries
- Easy to add new features
- Shared code in core/
- Professional structure

---

## Changes Made

### Documentation Organization

**Moved to `docs/`:**
- `CLAUDE.md` → `docs/DEVELOPMENT.md`
- `CONTINUOUS_CLAUDE_SETUP.md` → `docs/CONTINUOUS_CLAUDE.md`
- `IMPLEMENTATION_PLAN.md` → `docs/IMPLEMENTATION_PLAN.md`

**Combined:**
- `SECURITY_AUDIT.md` + `SECURITY_FIXES_APPLIED.md` → `docs/SECURITY.md`

**Created:**
- `docs/ARCHITECTURE.md` - System architecture documentation
- `docs/README.md` - Documentation index

### Source Code Organization

**Core Infrastructure:**
- `src/api/claudeClient.ts` → `src/core/api/claudeClient.ts`

**Feature Modules:**
- `src/editor/claudeDetector.ts` → `src/features/inline-assistant/claudeDetector.ts`
- `src/editor/paragraphExtractor.ts` → `src/features/inline-assistant/paragraphExtractor.ts`
- `src/editor/visualIndicator.ts` → `src/features/inline-assistant/visualIndicator.ts`
- `src/renderer/responseRenderer.ts` → `src/features/inline-assistant/responseRenderer.ts`

**Styling:**
- `styles.css` → `styles/main.css`

### Import Updates

All import paths in `src/main.ts` updated:
```typescript
// Before
import { ClaudeClient } from './api/claudeClient';
import { getParagraphAtCursor, ... } from './editor/paragraphExtractor';

// After
import { ClaudeClient } from './core/api/claudeClient';
import { getParagraphAtCursor, ... } from './features/inline-assistant/paragraphExtractor';
```

---

## Adding New Features

The new structure makes it easy to add features:

### Example: Conversation Threading

```
src/features/conversation/
├── index.ts                 # Feature export
├── conversationManager.ts   # History management
├── contextBuilder.ts        # Build conversation context
└── threadRenderer.ts        # Render threaded responses
```

### Example: Vault Search

```
src/features/vault-search/
├── index.ts
├── searchProvider.ts        # Search implementation
├── resultRanker.ts         # Rank search results
└── contextInjector.ts      # Inject search into prompts
```

### Integration Pattern

1. Create feature directory in `src/features/`
2. Implement feature interface
3. Register in `src/main.ts`:
   ```typescript
   import { ConversationFeature } from './features/conversation';

   async onload() {
       // ... existing code ...
       this.conversationFeature = new ConversationFeature(this);
       this.conversationFeature.register();
   }
   ```
4. Add feature-specific settings if needed
5. Document in `docs/ARCHITECTURE.md`

---

## Shared Core Pattern

**Core modules** (`src/core/`) are used by multiple features:

### Current Core
- `api/claudeClient.ts` - API communication

### Future Core Candidates
- `context/contextProvider.ts` - Unified context extraction
- `cache/responseCache.ts` - Response caching
- `history/sessionManager.ts` - Session history
- `validation/inputValidator.ts` - Input validation

**Rule:** Move to core when used by 2+ features.

---

## Migration Checklist

If you're working with an older version:

- [ ] Update git branch to latest
- [ ] Run `npm install` (dependencies unchanged)
- [ ] Update any custom code to use new import paths
- [ ] Run `npm run build` to verify
- [ ] Check documentation links in your notes
- [ ] Update any scripts that reference old paths

---

## Verification

```bash
# Build should succeed
npm run build

# File structure
ls -R src/
ls -R docs/
ls -R styles/

# Git history preserved
git log --follow src/core/api/claudeClient.ts
```

---

## Future Planned Features

With this structure, these features are easy to add:

1. **Conversation Threading** (`src/features/conversation/`)
2. **Vault Search Integration** (`src/features/vault-search/`)
3. **Custom Response Formats** (`src/features/formatters/`)
4. **Streaming Responses** (`src/core/streaming/`)
5. **Model Switching** (extend `inline-assistant`)
6. **Mobile Support** (`src/core/api-proxy/`)

---

**Last Updated:** 2026-01-06
**Reorganization Version:** 1.0
