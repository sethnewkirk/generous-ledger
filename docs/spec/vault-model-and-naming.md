# Spec / Vault Model And Naming

The vault stores canonical markdown artifacts in place.

Core operational surfaces:

- `profile/` contains the compiled steward view.
- `memory/` contains canonical normalized events and claims.
- `diary/` and `reviews/` hold episodic and periodic synthesis.
- `data/` holds source snapshots and normalized imports.

Naming rules:

- Use Title Case filenames with spaces.
- Use Obsidian wikilinks such as `[[Max]]` and `[[Quarterly Planning]]`.
- Prefer human-readable canonical paths over opaque ids in bodies.
- Keep machine ids in frontmatter where stability matters.

Profile files should be readable by the user and useful to the steward. Avoid turning them into raw dumps.
