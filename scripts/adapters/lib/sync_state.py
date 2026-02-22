"""
sync_state.py — Track sync tokens and last-synced timestamps.

State is stored in ~/.config/generous-ledger/state/ so adapters can
perform incremental syncs (only fetching what changed since last run).

USAGE:
    from lib.sync_state import SyncState

    state = SyncState("calendar")
    token = state.get("sync_token")        # None if not set
    state.set("sync_token", "abc123")
    state.set("last_synced", "2026-02-21T06:00:00")
    state.save()
"""

import json
from pathlib import Path
from datetime import datetime


STATE_DIR = Path.home() / ".config" / "generous-ledger" / "state"


class SyncState:
    """Persistent key-value state for a specific adapter."""

    def __init__(self, adapter_name: str):
        self.adapter_name = adapter_name
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.path = STATE_DIR / f"{adapter_name}.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, default=str),
            encoding="utf-8",
        )

    def touch_synced(self) -> None:
        """Record the current time as last_synced and save."""
        self.set("last_synced", datetime.now().isoformat())
        self.save()
