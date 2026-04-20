"""Tests for voice_notes.py — import normalization for voice transcripts."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from voice_notes import format_voice_note, iter_voice_items


class TestVoiceNotesAdapter(unittest.TestCase):
    def test_format_voice_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "note.txt"
            source.write_text("transcript", encoding="utf-8")
            filename, fm, body = format_voice_note(
                source,
                {
                    "title": "Walking thought",
                    "recorded_at": "2026-04-16T10:15:00",
                    "summary": "Idea about follow-up",
                    "transcript": "Need to call Max tomorrow",
                    "subjects": ["[[Max]]"],
                    "source_app": "test",
                },
            )
            self.assertTrue(filename.endswith(".md"))
            self.assertEqual(fm["type"], "voice-note")
            self.assertEqual(fm["title"], "Walking thought")
            self.assertIn("[[Max]]", fm["subjects"])
            self.assertIn("Need to call Max tomorrow", body)

    def test_iter_voice_items_reads_json_md_and_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("plain transcript", encoding="utf-8")
            (root / "b.json").write_text(
                json.dumps({"title": "JSON Note", "recorded_at": "2026-04-16T09:00:00", "transcript": "json body"}),
                encoding="utf-8",
            )
            (root / "c.md").write_text(
                "---\ntitle: Markdown Note\nrecorded_at: 2026-04-16T08:00:00\n---\n\nmarkdown body",
                encoding="utf-8",
            )

            items = iter_voice_items(root)
            self.assertEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main()
