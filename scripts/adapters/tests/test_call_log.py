"""Tests for call_log.py — import normalization for call entries."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from call_log import format_call, iter_call_entries


class TestCallLogAdapter(unittest.TestCase):
    def test_format_call(self):
        filename, fm, body = format_call(
            {
                "source_file": "/tmp/calls.json",
                "occurred_at": "2026-04-16T12:00:00",
                "contact_name": "Max",
                "handle": "+15551234567",
                "direction": "incoming",
                "duration_seconds": 180,
                "summary": "Discussed quarterly planning",
                "source_app": "test",
            }
        )

        self.assertTrue(filename.endswith(".md"))
        self.assertEqual(fm["type"], "call-entry")
        self.assertEqual(fm["direction"], "incoming")
        self.assertIn("Discussed quarterly planning", body)

    def test_iter_call_entries_reads_json_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "calls.json").write_text(
                json.dumps([{"occurred_at": "2026-04-16T12:00:00", "contact_name": "Max", "direction": "incoming"}]),
                encoding="utf-8",
            )
            with (root / "calls.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["occurred_at", "contact_name", "direction"])
                writer.writeheader()
                writer.writerow({"occurred_at": "2026-04-16T13:00:00", "contact_name": "Kate", "direction": "missed"})

            entries = iter_call_entries(root)
            self.assertEqual(len(entries), 2)
            names = {entry["contact_name"] for entry in entries}
            self.assertIn("Max", names)
            self.assertIn("Kate", names)


if __name__ == "__main__":
    unittest.main()
