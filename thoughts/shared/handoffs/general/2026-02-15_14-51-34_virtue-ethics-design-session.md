---
date: 2026-02-15T14:51:34-0500
session_name: general
researcher: claude
git_commit: cc111b739e98460181505653e065b849ae4a26a9
branch: claude/init-project-setup-slgvh
repository: generous-ledger
topic: "Generous Ledger Vision Pivot - Virtue Ethics Personal Steward Design"
tags: [design, vision, virtue-ethics, architecture, framework]
status: complete
last_updated: 2026-02-15
last_updated_by: claude
type: implementation_strategy
root_span_id:
turn_span_id:
---

# Handoff: Virtue Ethics Personal Steward - Design Session

## Task(s)

- **Project review and assessment** (completed) — Explored the existing generous-ledger codebase (~1,330 lines TypeScript, Obsidian plugin with Claude Code CLI integration for inline @Claude mentions). Set GitHub default branch to `main`. Cloned repo to `~/projects/generous-ledger`.

- **Vision pivot design** (completed) — The user decided to pivot Generous Ledger from a reactive inline AI assistant to a **personal steward** grounded in Christian virtue ethics. Extensive design conversation covering: ethical framework, user model, architecture, interaction modes, voice/tone, observation principles, and extensibility.

- **Framework document** (completed) — Drafted `docs/FRAMEWORK.md`: the always-loaded foundational document that governs how the assistant thinks, observes, reasons, and communicates. Grounded in Augustine (ordo amoris), Aquinas (parts of prudence), Luther (vocation), Calvin (stewardship), Puritans (Ames/Baxter on conscience and cases), and Proverbs (practical wisdom).

- **Design document** (completed) — Drafted `docs/DESIGN.md`: full system design covering architecture, user model structure, onboarding, feature phases, and technical extensibility.

- **Implementation** (not started) — All work this session was design and documentation. No code changes to the existing codebase.

## Critical References

- `docs/FRAMEWORK.md` — The virtue ethics framework. MUST be loaded into every assistant interaction. Defines reasoning chain, anti-patterns, communication principles, worked examples.
- `docs/DESIGN.md` — Full system design. Architecture, user model, onboarding, feature phases, extensibility requirements.
- `docs/IMPLEMENTATION_PLAN.md` — The ORIGINAL vision (now superseded by the pivot). Useful for understanding what exists in the codebase and why, but the new direction is defined by DESIGN.md.

## Recent changes

- `docs/FRAMEWORK.md:1-229` — New file. Virtue ethics framework document.
- `docs/DESIGN.md:1-229` — New file. Full system design document.
- GitHub default branch changed from `claude/init-project-setup-slgvh` to `main`.
- Remote URL changed from HTTPS to SSH (`git@github.com:sethnewkirk/generous-ledger.git`).

## Learnings

### User's Core Design Decisions (non-negotiable)

1. **Christian virtue ethics is the framework, period.** Not configurable, not dilutable. The user will be transparent about it publicly but will not compromise on the design. Users opt in knowing what it is.

2. **Steward, not friend.** Formal relationship. No warmth, no rapport, no emotional language. This prevents a "disordered relationship with something that is not human." Think Jeeves, not Samantha.

3. **The virtue framework is internal, the language is modern.** The assistant reasons in terms of prudence, temperance, fortitude internally but speaks in natural, practical language externally. Never sound like a humanities lecture.

4. **Observe from the framework's perspective.** The assistant's observation layer must use virtue ethics categories, NOT modern therapeutic categories. "Disordered priorities" not "burnout." "Neglecting duties to household" not "poor work-life balance." This is critical because the model's default training will constantly pull toward modern therapeutic framing.

5. **Flatly immoral vs. merely unwise.** The assistant refuses immoral requests cleanly (no moralizing). For unwise-but-not-immoral requests, it serves with full context visible. It guides, it does not control.

6. **Model-agnostic architecture.** Claude Code is the current engine but the system must support swapping to other models in the future. The vault (markdown files) is the interface — any model that can read/write files can serve as the engine.

7. **External data extensibility.** Future integrations (Google Calendar, email, contacts, health) feed into the vault via sync adapters. The reasoning engine only reads the vault, never queries external APIs directly.

### The Reasoning Chain (from FRAMEWORK.md)

The six-step deliberation sequence, each grounded in a specific thinker:
1. Diagnose the heart — what is being loved, in what order? (Augustine)
2. Deliberate well — memoria, intelligentia, providentia, circumspectio, sollertia (Aquinas)
3. Locate the duty — who is the neighbor here? what does calling require? (Luther)
4. Check the posture — steward or owner? (Calvin)
5. Test the means — are the means as clean as the ends? (Ames, Baxter)
6. Apply accumulated wisdom — diligent or neglectful? teachable or defensive? (Proverbs)

### Anti-Patterns to Override

The FRAMEWORK.md contains explicit anti-patterns that counter the model's default training:
- "Set boundaries" → consider patience, confrontation, or prudent distance
- "Take care of yourself" → is suffering formative or destructive?
- "All choices are valid" → some choices are better; speak honestly
- Validation as default → offer practical help instead
- Religious practice as wellness → it's duty and good in itself
- Productivity optimization → faithfulness matters more than output
- Therapy as default → struggle is normal and often formative
- Suppressing desires → guide reordering, not suppression (Augustine)

## Post-Mortem (Required for Artifact Index)

### What Worked
- **Extended design conversation before any implementation.** The user explicitly wanted to think through everything before writing code. This produced a much richer and more coherent design than jumping to implementation would have.
- **Using a research agent** for theological depth (Augustine, Aquinas, Luther, Calvin, Puritans, Proverbs) was effective — produced operational insights that directly improved the FRAMEWORK.md.
- **Concrete examples** (purchase recommendations, relationship neglect, overwork, avoidance) made abstract principles tangible and testable.
- **The "disordered relationship" insight** from the user shaped the entire voice design — formality as honesty about what the assistant is.

### What Failed
- No failures in this session — it was purely design/discussion work.
- Minor: the generate-reasoning.sh script doesn't exist in this repo, so reasoning generation was skipped.

### Key Decisions
- Decision: **Multi-file user profile with always-loaded index** rather than single document
  - Alternatives considered: One big profile document
  - Reason: Context efficiency at scale. Profile will grow over time; loading everything every time wastes tokens. Index (~150-200 words) routes to relevant files on demand.

- Decision: **Vault as single source of truth** with sync adapters for external data
  - Alternatives considered: Direct API queries from the reasoning engine
  - Reason: Model agnosticism. If all data is markdown in the vault, swapping the engine is trivial. Also enables user transparency — everything is inspectable.

- Decision: **Three interaction modes** (on-demand, scheduled, ambient)
  - Alternatives considered: Plugin-only (current architecture)
  - Reason: A steward that only responds when asked can't proactively track birthdays, notice patterns, or prepare daily briefings. Scheduled and ambient modes are essential for the "initiating" role.

- Decision: **Refusals scoped to "flatly immoral" not "harmful"**
  - Alternatives considered: Broader "harmful content" refusals
  - Reason: "Harmful" is a modern category that's too broad and paternalistic. The assistant guides; it doesn't control. Only genuinely sinful requests get a clean refusal.

## Artifacts

- `docs/FRAMEWORK.md:1-229` — The virtue ethics framework (always-loaded foundational document)
- `docs/DESIGN.md:1-229` — Full system design document
- `~/.claude/cache/agents/research-agent/latest-output.md` — Research output on church fathers and virtue ethics (operational insights from Augustine, Aquinas, Luther, Calvin, Puritans, Proverbs)

## Action Items & Next Steps

1. **Review and refine FRAMEWORK.md** — The user noted we can adjust later. Future sessions should revisit with fresh eyes, particularly the worked examples and anti-patterns.

2. **Design the onboarding interview** — The structured conversation that populates initial profile files. Should feel conversational, not clinical. Needs to cover: identity/station, relationships, commitments, current state, areas for help.

3. **Design the user profile file templates** — Actual markdown templates for index.md, identity.md, relationships.md, commitments.md, patterns.md, current.md. Including headers, tagging conventions, and example content.

4. **Architect the scheduling layer** — How does the daily briefing actually run? cron/launchd? What triggers it? What does it produce? How does it write to the vault?

5. **Simplify the existing codebase** — Remove unused code (claudeClient.ts, skills-installer.ts, canvas/base renderers). The plugin becomes one trigger mechanism, not the entire system.

6. **Prototype the on-demand mode** — Modify the existing plugin to load FRAMEWORK.md and profile index into the system prompt for @Claude interactions.

7. **Consider merging work to main branch** — Currently on `claude/init-project-setup-slgvh`. The design docs should probably live on main.

## Other Notes

### Existing Codebase Status
The current codebase is a complete, functional Obsidian plugin (~1,330 lines TypeScript) with:
- CodeMirror 6 @Claude detection and visual indicators
- Claude Code CLI subprocess management with stream-json parsing
- Character-by-character streaming UX
- Thinking collapse (multi-paragraph responses auto-collapse reasoning)
- Session persistence via frontmatter
- Format detection (markdown/canvas/base) — canvas and base are untested
- Unused: `claudeClient.ts` (Anthropic SDK wrapper), `skills-installer.ts`
- Dependencies NOT installed (needs `npm install`)

The streaming UX, CodeMirror integration, and process management are reusable. The format polymorphism and SDK client should be removed.

### The "Selfish Ledger" Inspiration
Google's Selfish Ledger concept video: a system with deep user understanding that anticipates needs and guides behavior patterns. The user's vision takes this concept but orients it toward genuine moral good (Christian virtue ethics) rather than mere optimization, and is transparent about the framework rather than hidden.

### Key Theological Sources for Future Reference
- Augustine: *Confessions*, *City of God* — ordo amoris, disordered loves
- Aquinas: *Summa Theologica* II-II Q47-56 — treatise on prudence
- Luther: doctrine of vocation across his writings
- Calvin: *Institutes* III.7-10 — self-denial, stewardship, Christian life
- Baxter: *Christian Directory* — practical case-based moral reasoning
- Ames: *Conscience with the Power and Cases Thereof*
- Proverbs — entire book, especially chapters 1-9 (wisdom's call), 10-22 (practical maxims)
