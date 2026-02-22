"""Tests for vault_writer.py — markdown file writing with YAML frontmatter."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.vault_writer import VaultWriter


class TestVaultWriter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.writer = VaultWriter(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_creates_data_folder(self):
        self.writer.write_data_file(
            folder="weather",
            filename="test.md",
            frontmatter={"type": "test"},
            body="Hello",
        )
        self.assertTrue((Path(self.tmp) / "data" / "weather").is_dir())

    def test_write_creates_file_with_frontmatter(self):
        path = self.writer.write_data_file(
            folder="weather",
            filename="2026-02-21.md",
            frontmatter={"type": "weather-daily", "date": "2026-02-21", "high_f": 55},
            body="# Weather\n\nPartly cloudy.",
        )

        content = path.read_text()
        self.assertTrue(content.startswith("---\n"))
        self.assertIn("type: weather-daily", content)
        self.assertIn("date: '2026-02-21'", content)
        self.assertIn("high_f: 55", content)
        self.assertIn("# Weather", content)
        self.assertIn("Partly cloudy.", content)

    def test_write_idempotent_overwrite(self):
        self.writer.write_data_file(
            folder="test", filename="f.md",
            frontmatter={"v": 1}, body="old",
        )
        self.writer.write_data_file(
            folder="test", filename="f.md",
            frontmatter={"v": 2}, body="new", overwrite=True,
        )

        content = (Path(self.tmp) / "data" / "test" / "f.md").read_text()
        self.assertIn("v: 2", content)
        self.assertIn("new", content)

    def test_write_skip_if_exists(self):
        self.writer.write_data_file(
            folder="test", filename="f.md",
            frontmatter={"v": 1}, body="original",
        )
        self.writer.write_data_file(
            folder="test", filename="f.md",
            frontmatter={"v": 2}, body="updated", overwrite=False,
        )

        content = (Path(self.tmp) / "data" / "test" / "f.md").read_text()
        self.assertIn("v: 1", content)
        self.assertIn("original", content)

    def test_write_no_tmp_file_left(self):
        self.writer.write_data_file(
            folder="test", filename="f.md",
            frontmatter={}, body="",
        )
        data_dir = Path(self.tmp) / "data" / "test"
        tmp_files = list(data_dir.glob("*.tmp"))
        self.assertEqual(len(tmp_files), 0)

    def test_invalid_vault_path(self):
        with self.assertRaises(FileNotFoundError):
            VaultWriter("/nonexistent/vault/path")

    def test_ensure_data_folder(self):
        path = self.writer.ensure_data_folder("calendar")
        self.assertTrue(path.is_dir())
        # Use resolve() on both sides to handle macOS /var -> /private/var symlink
        self.assertEqual(path.resolve(), (Path(self.tmp) / "data" / "calendar").resolve())

    def test_frontmatter_list_values(self):
        path = self.writer.write_data_file(
            folder="test", filename="tags.md",
            frontmatter={"tags": ["data", "weather"], "type": "test"},
            body="body",
        )
        content = path.read_text()
        self.assertIn("- data", content)
        self.assertIn("- weather", content)


class TestVaultWriterUnicode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.writer = VaultWriter(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unicode_body(self):
        path = self.writer.write_data_file(
            folder="test", filename="unicode.md",
            frontmatter={"type": "test"},
            body="Température: 20°C — Humidité: 65%",
        )
        content = path.read_text(encoding="utf-8")
        self.assertIn("Température", content)
        self.assertIn("°C", content)


if __name__ == "__main__":
    unittest.main()
