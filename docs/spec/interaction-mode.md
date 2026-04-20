# Spec / Interaction Mode

Normal Obsidian use is chat-first.

- `Steward Chat` is the primary conversation surface.
- The plugin may attach note context, profile context, and workflow context to a turn.
- Steward may update `profile/` and `memory/` when the rules warrant it.
- The UI should surface a compact activity summary after each turn.

In plugin-triggered interactions:

- do not edit the current note directly from the runtime
- let the plugin own note write-back actions
- keep replies concise and useful in chat, not terminal-like

Steward should feel like one continuous conversation that sometimes updates files, not a collection of disconnected tools.
