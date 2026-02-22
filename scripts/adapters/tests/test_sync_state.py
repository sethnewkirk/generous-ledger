"""Tests for sync_state.py — persistent adapter state tracking."""

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).parent.parent))
from lib.sync_state import SyncState


class TestSyncState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_dir = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    @patch("lib.sync_state.STATE_DIR")
    def test_get_default(self, mock_dir):
        mock_dir.__truediv__ = lambda self, x: Path(self.tmp) / x
        mock_dir.mkdir = lambda **kw: None
        # Create fresh state with patched dir
        state = SyncState.__new__(SyncState)
        state.adapter_name = "test"
        state.path = self.state_dir / "test.json"
        state._data = {}

        self.assertIsNone(state.get("missing"))
        self.assertEqual(state.get("missing", "fallback"), "fallback")

    @patch("lib.sync_state.STATE_DIR")
    def test_set_and_get(self, mock_dir):
        mock_dir.__truediv__ = lambda self, x: Path(self.tmp) / x
        mock_dir.mkdir = lambda **kw: None

        state = SyncState.__new__(SyncState)
        state.adapter_name = "test"
        state.path = self.state_dir / "test.json"
        state._data = {}

        state.set("key", "value")
        self.assertEqual(state.get("key"), "value")

    @patch("lib.sync_state.STATE_DIR")
    def test_save_and_load(self, mock_dir):
        mock_dir.__truediv__ = lambda self, x: Path(self.tmp) / x
        mock_dir.mkdir = lambda **kw: None

        state = SyncState.__new__(SyncState)
        state.adapter_name = "test"
        state.path = self.state_dir / "test.json"
        state._data = {}

        state.set("token", "abc123")
        state.save()

        # Verify file contents
        saved = json.loads(state.path.read_text())
        self.assertEqual(saved["token"], "abc123")

    @patch("lib.sync_state.STATE_DIR")
    def test_touch_synced(self, mock_dir):
        mock_dir.__truediv__ = lambda self, x: Path(self.tmp) / x
        mock_dir.mkdir = lambda **kw: None

        state = SyncState.__new__(SyncState)
        state.adapter_name = "test"
        state.path = self.state_dir / "test.json"
        state._data = {}

        state.touch_synced()

        self.assertIsNotNone(state.get("last_synced"))
        self.assertTrue(state.path.exists())


if __name__ == "__main__":
    unittest.main()
