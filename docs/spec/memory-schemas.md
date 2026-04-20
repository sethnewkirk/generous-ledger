# Spec / Memory Schemas

Memory artifacts are markdown files with machine-readable frontmatter and readable bodies.

Event files should contain:

- stable event ids
- source metadata
- time metadata
- sensitivity and retention fields
- subject wikilinks
- concise summaries

Claim files should contain:

- stable claim ids and slots
- claim type
- status and confidence
- validity window
- subject wikilinks
- supporting event links
- related or superseded claim links

Claims should be versioned through status changes rather than silently overwritten.
