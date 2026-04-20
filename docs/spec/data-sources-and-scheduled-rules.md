# Spec / Data Sources And Scheduled Rules

Scheduled routines should prefer direct file I/O over Obsidian CLI when practical.

Source rules:

- normalize source data before promotion into memory
- treat raw communications carefully and retain only short justified excerpts
- preserve source links and metadata even when ephemeral inputs rotate away

Routine rules:

- run memory compilation before provider-driven briefing or review work
- fail clearly when the provider is unavailable or misconfigured
- keep provider selection explicit
- preserve ephemeral communication files on failed runs for retry and debugging

The routine layer should be deterministic, auditable, and light on hidden side effects.
