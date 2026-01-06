# Documentation Index

Welcome to the Generous Ledger documentation!

## For Users

- **[Main README](../README.md)** - Getting started, installation, and usage

## For Developers

- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Development setup, commands, and workflow
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture and design decisions
- **[SECURITY.md](./SECURITY.md)** - Security audit results and fixes

## Planning & History

- **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** - Original implementation plan
- **[CONTINUOUS_CLAUDE.md](./CONTINUOUS_CLAUDE.md)** - Continuous Claude v2 setup

## Quick Links

### Development Commands
```bash
npm install        # Install dependencies
npm run dev        # Development mode (watch)
npm run build      # Production build
```

### Architecture Overview
- **Core:** Shared infrastructure (API client)
- **Features:** Modular feature implementations
  - `inline-assistant` - @Claude mention feature
- **Settings:** User configuration interface

### Key Files
- `src/main.ts` - Plugin entry point
- `src/settings.ts` - Settings interface
- `src/core/api/claudeClient.ts` - API wrapper
- `src/features/inline-assistant/` - Main feature

### Project Structure
```
generous-ledger/
├── src/              # Source code
│   ├── core/         # Shared infrastructure
│   └── features/     # Feature modules
├── styles/           # CSS styling
├── docs/            # This directory
└── thoughts/        # Continuous Claude artifacts
```

---

**Need Help?**
- Check the specific documentation files above
- Review code comments in source files
- See security audit for known issues
- Check implementation plan for design rationale
