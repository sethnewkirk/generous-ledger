import json
import tempfile
import unittest
from pathlib import Path

from scripts.steward_memory.compiler import compile_memory
from scripts.steward_memory.health import build_memory_health_report
from scripts.steward_memory.retrieval import retrieve_context


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _profile_person(name: str) -> str:
    return f"""---
type: person
name: {name}
role: friend
circle: friends
birthday:
anniversary:
contact_frequency: weekly
status: active
tags: [person]
last_updated: 2026-04-16
---
<!-- GENERATED:STEWARD_MEMORY_PERSON START -->
## Steward Summary

- No compiled summary yet.
<!-- GENERATED:STEWARD_MEMORY_PERSON END -->

## Notes
"""


def _profile_commitment(title: str) -> str:
    return f"""---
type: commitment
title: {title}
category: work
status: in-progress
priority: high
deadline:
timeframe:
stakeholder:
tags: [commitment]
last_updated: 2026-04-16
---
<!-- GENERATED:STEWARD_MEMORY_COMMITMENT START -->
## Steward Summary

- No compiled summary yet.
<!-- GENERATED:STEWARD_MEMORY_COMMITMENT END -->

## Details
"""


def _profile_current() -> str:
    return """---
type: profile
last_updated: 2026-04-16
---
<!-- GENERATED:STEWARD_MEMORY_CURRENT START -->
## Steward Digest

- No compiled digest yet.
<!-- GENERATED:STEWARD_MEMORY_CURRENT END -->

## This Week
"""


def _profile_patterns() -> str:
    return """---
type: profile
last_updated: 2026-04-16
---
<!-- GENERATED:STEWARD_MEMORY_PATTERNS START -->
## Active Pattern Claims

- No active pattern claims.
<!-- GENERATED:STEWARD_MEMORY_PATTERNS END -->

## Growth Trajectories
"""


def _profile_index() -> str:
    return """---
type: profile
last_updated: 2026-04-16
---

## Core Identity

Test user.
"""


class StewardMemoryCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)
        _write(self.vault / "profile" / "index.md", _profile_index())
        _write(self.vault / "profile" / "current.md", _profile_current())
        _write(self.vault / "profile" / "patterns.md", _profile_patterns())
        _write(self.vault / "profile" / "people" / "Max.md", _profile_person("Max"))
        _write(
            self.vault / "profile" / "commitments" / "Quarterly Planning.md",
            _profile_commitment("Quarterly Planning"),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _claim_frontmatters(self) -> list[dict]:
        claim_dir = self.vault / "memory" / "claims"
        if not claim_dir.exists():
            return []
        results = []
        for path in claim_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            end = text.find("\n---\n", 4)
            self.assertNotEqual(end, -1)
            import yaml

            results.append(yaml.safe_load(text[4:end]))
        return results

    def test_message_request_creates_event_obligation_and_profile_links(self) -> None:
        _write(
            self.vault / "data" / "messages" / "2026-04-16.md",
            """---
type: imessage-daily
date: 2026-04-16
last_synced: 2026-04-16T09:30:00
---
# Messages — 2026-04-16

## Max

*max@example.com*

- **09:15** Max: Can you send the revised outline tonight?
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertEqual(report.events_created, 1)
        self.assertEqual(report.claims_created, 1)

        claims = self._claim_frontmatters()
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["claim_type"], "obligation")
        self.assertEqual(claims[0]["status"], "active")
        self.assertIn("[[Max]]", claims[0]["subjects"])

        event_files = list((self.vault / "memory" / "events").glob("*.md"))
        self.assertEqual(len(event_files), 1)
        event_text = event_files[0].read_text(encoding="utf-8")
        self.assertIn("[[Max]]", event_text)

        person_text = (self.vault / "profile" / "people" / "Max.md").read_text(encoding="utf-8")
        self.assertIn("Open Obligations", person_text)
        self.assertIn("Follow up with [[Max]]", person_text)

    def test_calendar_event_with_known_person_creates_event_without_claim(self) -> None:
        _write(
            self.vault / "data" / "calendar" / "2026-04-16.md",
            """---
type: calendar-day
date: 2026-04-16
last_synced: 2026-04-16T08:00:00
---
# Calendar — 2026-04-16

- **09:00** — Coffee with Max
  - With: Max
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertEqual(report.events_created, 1)
        self.assertEqual(report.claims_created, 0)
        self.assertEqual(len(list((self.vault / "memory" / "claims").glob("*.md"))), 0)

    def test_repeated_deferrals_generate_pattern_claim_and_update_patterns_profile(self) -> None:
        _write(
            self.vault / "Planning Notes.md",
            """---
date: 2026-04-16
---
- [ ] Defer [[Quarterly Planning]] until later
- [ ] Reschedule [[Quarterly Planning]] for next week
- [ ] Postpone [[Quarterly Planning]] again
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertGreaterEqual(report.claims_created, 2)

        claims = self._claim_frontmatters()
        pattern_claims = [claim for claim in claims if claim.get("claim_type") == "pattern"]
        self.assertEqual(len(pattern_claims), 1)
        self.assertEqual(pattern_claims[0]["status"], "active")
        self.assertIn("[[Quarterly Planning]]", pattern_claims[0]["summary"])

        patterns_text = (self.vault / "profile" / "patterns.md").read_text(encoding="utf-8")
        self.assertIn("Active Pattern Claims", patterns_text)
        self.assertIn("[[Quarterly Planning]]", patterns_text)

    def test_structured_obligation_from_note_updates_commitment_page(self) -> None:
        _write(
            self.vault / "Work Notes.md",
            """---
date: 2026-04-16
---
Obligation[quarterly-plan]: [[Quarterly Planning]] finish the first draft by Friday
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertEqual(report.claims_created, 1)

        claims = self._claim_frontmatters()
        self.assertEqual(claims[0]["claim_type"], "obligation")
        self.assertEqual(claims[0]["status"], "active")
        self.assertIn("[[Quarterly Planning]]", claims[0]["subjects"])

        commitment_text = (self.vault / "profile" / "commitments" / "Quarterly Planning.md").read_text(encoding="utf-8")
        self.assertIn("Open Obligations", commitment_text)
        self.assertIn("[[Quarterly Planning]] finish the first draft by Friday.", commitment_text)

    def test_conflicting_structured_claims_supersede_by_slot(self) -> None:
        _write(
            self.vault / "Preferences A.md",
            """---
date: 2026-04-15
---
Preference[meeting-time]: [[Max]] prefers morning meetings
""",
        )
        _write(
            self.vault / "Preferences B.md",
            """---
date: 2026-04-16
---
Preference[meeting-time]: [[Max]] prefers afternoon meetings
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertEqual(report.claims_created, 2)
        self.assertEqual(report.claims_superseded, 1)

        claims = self._claim_frontmatters()
        active = [claim for claim in claims if claim.get("status") == "active"]
        superseded = [claim for claim in claims if claim.get("status") == "superseded"]
        self.assertEqual(len(active), 1)
        self.assertEqual(len(superseded), 1)
        self.assertIn("afternoon meetings", active[0]["summary"])
        self.assertIn("morning meetings", superseded[0]["summary"])

    def test_general_prose_note_without_links_is_not_promoted(self) -> None:
        _write(
            self.vault / "Reading Notes.md",
            """---
date: 2026-04-16
---
I must not assume that people understand what I mean.
Relationships carry obligations, not just benefits.
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertEqual(report.events_created, 0)
        self.assertEqual(report.claims_created, 0)

    def test_retrieval_prefers_linked_context_before_fallback_search(self) -> None:
        _write(
            self.vault / "Meeting Prep.md",
            """---
date: 2026-04-16
---
Obligation[send-outline]: [[Max]] send the revised outline before the meeting
""",
        )
        compile_memory(str(self.vault), since_days=30)

        result = retrieve_context(
            str(self.vault),
            "meeting-prep",
            subject_titles=["Max"],
            since_days=30,
        )

        paths = [document.path for document in result.documents]
        self.assertIn("profile/index.md", paths)
        self.assertIn("profile/current.md", paths)
        self.assertIn("profile/people/Max.md", paths)
        self.assertTrue(any(path.startswith("memory/claims/") for path in paths))
        self.assertFalse(result.used_search_fallback)

    def test_task_entry_becomes_obligation_claim(self) -> None:
        _write(
            self.vault / "data" / "tasks" / "Send Outline task-123.md",
            """---
type: task-entry
task_id: task-123
title: Send [[Max]] the outline
list_name: Work
due_at: 2026-04-18T09:00:00
last_synced: 2026-04-16T09:30:00
tags: [data, tasks]
---

## Notes

Need the revised version.
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertEqual(report.claims_created, 1)
        claims = self._claim_frontmatters()
        self.assertEqual(claims[0]["claim_type"], "obligation")
        self.assertIn("[[Max]]", claims[0]["summary"])

    def test_voice_note_with_structured_idea_becomes_claim(self) -> None:
        _write(
            self.vault / "data" / "voice" / "Walking Thought 1234abcd.md",
            """---
type: voice-note
voice_note_id: voice-123
title: Walking Thought
recorded_at: 2026-04-16T07:15:00
summary: Thought about helping [[Max]]
subjects: ["[[Max]]"]
last_synced: 2026-04-16T07:20:00
tags: [data, voice]
---

## Transcript

Idea[encouragement]: [[Max]] might benefit from a direct encouragement note this week
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertEqual(report.claims_created, 1)
        claims = self._claim_frontmatters()
        self.assertEqual(claims[0]["claim_type"], "idea")
        self.assertEqual(claims[0]["status"], "provisional")
        self.assertIn("[[Max]]", claims[0]["summary"])

    def test_compile_writes_health_report_for_unresolved_signal_and_unlinked_contact(self) -> None:
        _write(
            self.vault / "data" / "contacts" / "Sam Carter 1234abcd.md",
            """---
type: contact-entry
name: Sam Carter
emails: [sam@example.com]
phones: ["+1 (555) 010-1234"]
tags: [data, contacts]
last_synced: 2026-04-16T09:00:00
---

# Contact — Sam Carter
""",
        )
        _write(
            self.vault / "data" / "calls" / "Sam Carter 20260416.md",
            """---
type: call-entry
contact_name: Sam Carter
handle: +15550101234
direction: missed
occurred_at: 2026-04-16T08:30:00
summary: Missed call from Sam Carter
last_synced: 2026-04-16T08:31:00
tags: [data, calls]
---

# Call — Sam Carter
""",
        )

        report = compile_memory(str(self.vault), since_days=30)
        self.assertTrue(report.health_report_written)
        self.assertGreaterEqual(report.unresolved_signals, 1)
        self.assertEqual(report.unlinked_contacts, 1)

        health_payload = json.loads((self.vault / "memory" / "health-report.json").read_text(encoding="utf-8"))
        self.assertEqual(health_payload["summary"]["unlinked_contacts"], 1)
        self.assertEqual(health_payload["summary"]["active_contacts"], 1)
        self.assertGreaterEqual(health_payload["summary"]["unresolved_signals"], 1)
        self.assertTrue((self.vault / "memory" / "health-report.md").exists())

    def test_health_report_flags_stale_and_conflicting_active_claims(self) -> None:
        _write(
            self.vault / "memory" / "claims" / "Max Preference A.md",
            """---
type: memory-claim
claim_slot: preference::max::meeting-time
claim_type: preference
status: active
summary: "[[Max]] prefers morning meetings."
subjects: ["[[Max]]"]
last_updated: 2026-01-01
---

## Statement
[[Max]] prefers morning meetings.
""",
        )
        _write(
            self.vault / "memory" / "claims" / "Max Preference B.md",
            """---
type: memory-claim
claim_slot: preference::max::meeting-time
claim_type: preference
status: active
summary: "[[Max]] prefers afternoon meetings."
subjects: ["[[Max]]"]
last_updated: 2026-01-02
---

## Statement
[[Max]] prefers afternoon meetings.
""",
        )

        health_report = build_memory_health_report(str(self.vault), signals=[], stale_days=30)
        self.assertEqual(health_report["summary"]["conflicting_active_claim_slots"], 1)
        self.assertEqual(health_report["summary"]["stale_active_claims"], 2)

    def test_dormant_contacts_are_not_reported_as_unlinked(self) -> None:
        _write(
            self.vault / "data" / "contacts" / "Dormant Person 1234abcd.md",
            """---
type: contact-entry
name: Dormant Person
emails: [dormant@example.com]
tags: [data, contacts]
last_synced: 2026-04-16T09:00:00
---

# Contact — Dormant Person
""",
        )

        health_report = build_memory_health_report(str(self.vault), signals=[], stale_days=30)
        self.assertEqual(health_report["summary"]["total_contacts"], 1)
        self.assertEqual(health_report["summary"]["active_contacts"], 0)
        self.assertEqual(health_report["summary"]["unlinked_contacts"], 0)

    def test_contact_suggestions_do_not_merge_on_first_name_only(self) -> None:
        _write(self.vault / "profile" / "people" / "Caleb Morell.md", _profile_person("Caleb Morell"))
        _write(
            self.vault / "data" / "contacts" / "Caleb Angell 1234abcd.md",
            """---
type: contact-entry
name: Caleb Angell
tags: [data, contacts]
last_synced: 2026-04-16T09:00:00
---

# Contact — Caleb Angell
""",
        )
        _write(
            self.vault / "data" / "calls" / "Caleb Angell 20260416.md",
            """---
type: call-entry
contact_name: Caleb Angell
handle: +15550101234
direction: missed
occurred_at: 2026-04-16T08:30:00
summary: Missed call from Caleb Angell
last_synced: 2026-04-16T08:31:00
tags: [data, calls]
---

# Call — Caleb Angell
""",
        )

        compile_memory(str(self.vault), since_days=30)
        payload = json.loads((self.vault / "memory" / "health-report.json").read_text(encoding="utf-8"))
        unlinked = payload["unlinked_contacts"]
        self.assertEqual(len(unlinked), 1)
        self.assertEqual(unlinked[0]["name"], "Caleb Angell")
        self.assertEqual(unlinked[0]["suggestions"], [])


if __name__ == "__main__":
    unittest.main()
