"""Tests for tasks.py — formatting Reminder tasks into vault entries."""

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from tasks import format_task


class TestTasksAdapter(unittest.TestCase):
    def test_format_task_basic(self):
        fm, body = format_task(
            {
                "task_id": "task-123",
                "title": "Send Max the outline",
                "list_name": "Work",
                "due_date": "2026-04-18T09:00:00",
                "priority": 5,
                "flagged": True,
                "notes": "Need the revised version.",
            }
        )

        self.assertEqual(fm["type"], "task-entry")
        self.assertEqual(fm["title"], "Send Max the outline")
        self.assertEqual(fm["list_name"], "Work")
        self.assertEqual(fm["due_date"], "2026-04-18")
        self.assertTrue(fm["flagged"])
        self.assertIn("Priority: 5", body)
        self.assertIn("Need the revised version.", body)


if __name__ == "__main__":
    unittest.main()
