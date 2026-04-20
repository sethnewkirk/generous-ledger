import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.steward_memory.briefing_context import build_briefing_context


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class BriefingContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name)

        _write(
            self.vault / "profile" / "index.md",
            """---
type: profile
last_updated: 2026-04-16
---

## Core Identity

Test user.
""",
        )
        _write(
            self.vault / "profile" / "current.md",
            """---
type: profile
last_updated: 2026-04-16
---

## This Week

- Call father [stated]
""",
        )
        _write(
            self.vault / "profile" / "patterns.md",
            """---
type: profile
last_updated: 2026-04-16
---

## Active Pattern Claims

- No active pattern claims.
""",
        )

        upcoming_birthday = (date.today() + timedelta(days=2)).isoformat()
        _write(
            self.vault / "profile" / "people" / "Max.md",
            f"""---
type: person
name: Max
role: friend
circle: friends
birthday: {upcoming_birthday}
anniversary:
contact_frequency: weekly
status: active
tags: [person]
last_updated: 2026-04-16
---

## Notes

Friend from church.
""",
        )
        _write(
            self.vault / "profile" / "commitments" / "Drop Classes.md",
            """---
type: commitment
title: Drop Classes
category: education
status: blocked
priority: high
deadline: 2026-04-20
timeframe:
stakeholder:
tags: [commitment]
last_updated: 2026-04-16
---

## Details

Need to call professor.
""",
        )
        _write(
            self.vault / "memory" / "compile-report.json",
            """{
  "signals_seen": 3,
  "promoted_signals": 1,
  "unlinked_contacts": 0
}""",
        )
        _write(
            self.vault / "data" / "calendar" / "2026-04-16.md",
            """---
type: calendar-day
date: 2026-04-16
last_synced: 2026-04-16T08:00:00
summary: Coffee with Max at 09:00
---

# Calendar — 2026-04-16

- **09:00** Coffee with Max
""",
        )
        _write(
            self.vault / "01_personal" / "2026-04-16.md",
            "# Existing Note\n",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_daily_context_includes_note_targets_commitments_and_recent_sources(self) -> None:
        context = build_briefing_context(
            str(self.vault),
            workflow="daily",
            note_relative_path="01_personal/2026-04-16.md",
        )

        self.assertIn("Target note: 01_personal/2026-04-16.md", context)
        self.assertIn("[[Drop Classes]]", context)
        self.assertIn("Birthday", context)
        self.assertIn("data/calendar/2026-04-16.md", context)
        self.assertIn("Signals seen: 3", context)

    def test_evening_context_includes_today_note_excerpt(self) -> None:
        context = build_briefing_context(
            str(self.vault),
            workflow="evening",
            note_relative_path="01_personal/2026-04-16.md",
        )

        self.assertIn("## Today's Daily Note", context)
        self.assertIn("Existing Note", context)

