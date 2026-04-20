# Spec / Memory And Retrieval

Memory is vault-first, compiled-first, and workflow-driven.

Memory model:

- `memory/events/` stores append-only promoted events.
- `memory/claims/` stores durable claims with `active`, `provisional`, or `superseded` status.
- `profile/` remains the steward-facing compiled operational layer.

Retrieval order:

1. `profile/index.md` and the directly relevant compiled profile files
2. linked recent `memory/claims/` and `memory/events/`
3. episodic context from `diary/` and `reviews/`
4. local search fallback

Before broad search, expand through direct wikilinks and backlinks. Prefer narrow, interpretable recall over broad context stuffing.
