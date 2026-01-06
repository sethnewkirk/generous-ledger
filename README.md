# Generous Ledger

An Obsidian plugin that brings Claude AI directly into your notes through simple `@Claude` mentions.

## Features

- **Inline AI Assistance**: Type `@Claude` followed by your question or prompt, press Enter, and get Claude's response directly in your note
- **Visual Feedback**: See real-time indicators when Claude is ready (🤖), processing (⏳), or encounters an error (⚠️)
- **Beautiful Formatting**: Responses appear in distinctive dark purple callout blocks
- **Customizable**: Choose between Claude Sonnet 4 (faster) or Opus 4.5 (more capable), adjust response length, and customize system prompts

## Installation

### From Obsidian Community Plugins (Coming Soon)

1. Open Settings → Community Plugins
2. Search for "Generous Ledger"
3. Click Install, then Enable

### Manual Installation

1. Download the latest release from GitHub
2. Extract the files to your vault's `.obsidian/plugins/generous-ledger/` directory
3. Reload Obsidian
4. Enable the plugin in Settings → Community Plugins

## Setup

1. Get an API key from [Anthropic Console](https://console.anthropic.com/)
2. Open Obsidian Settings → Generous Ledger
3. Paste your API key
4. Configure your preferences (model, max tokens, system prompt)

## Usage

1. **Ask a Question**: In any note, type your question followed by `@Claude`:
   ```
   What is the capital of France? @Claude
   ```

2. **Press Enter**: Hit Enter (not Shift+Enter) to send

3. **Get Response**: Claude's response appears below in a purple callout:
   ```
   > [!claude] Claude's Response
   > The capital of France is Paris...
   ```

### Tips

- Use `@claude` (lowercase) or `@Claude` (uppercase) - both work
- The entire paragraph is sent to Claude
- Shift+Enter adds a newline without triggering Claude
- You can edit responses like any other text

## Configuration

### Settings

- **API Key**: Your Anthropic API key (required)
- **Model**: Choose between Sonnet 4 (fast) or Opus 4.5 (powerful)
- **Max Tokens**: Control response length (1000-8000)
- **System Prompt**: Customize Claude's behavior

## Development

See [CLAUDE.md](./CLAUDE.md) for development instructions.

### Build Commands

```bash
# Install dependencies
npm install

# Development mode (auto-rebuild)
npm run dev

# Production build
npm run build
```

## Privacy & Security

- Your API key is stored locally in Obsidian's data
- All communication is directly between your computer and Anthropic's API
- No data is sent to third parties
- Responses are saved as plain text in your notes

## Roadmap

- [ ] Conversation threading (maintain context across multiple @Claude calls)
- [ ] Configurable context (send more than just the paragraph)
- [ ] Model switching per request
- [ ] Mobile support (iOS/Android)
- [ ] Custom response formats
- [ ] Streaming responses

## Support

- **Issues**: [GitHub Issues](https://github.com/sethnewkirk/generous-ledger/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sethnewkirk/generous-ledger/discussions)

## License

MIT

## Credits

Built with inspiration from:
- [Obsidian Copilot](https://github.com/logancyang/obsidian-copilot)
- [Obsidian Claude Code](https://github.com/Roasbeef/obsidian-claude-code)

---

Made with ❤️ for the Obsidian community
