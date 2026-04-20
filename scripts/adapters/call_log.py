#!/usr/bin/env python3
"""
call_log.py — Normalize imported call log exports into the vault.

USAGE:
    python3 scripts/adapters/call_log.py [--vault PATH] [--import-path PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from lib.credentials import get_config
from lib.logging_config import setup_logging
from lib.sync_state import SyncState
from lib.vault_writer import VaultWriter


def _safe_fragment(text: str, fallback: str = "Call") -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return " ".join(words[:8]) or fallback


def _load_entries(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("calls", [])
        return [item for item in payload if isinstance(item, dict)]

    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    return []


def iter_call_entries(import_path: Path) -> list[dict]:
    entries: list[dict] = []
    for source_path in sorted(import_path.glob("*")):
        if not source_path.is_file() or source_path.suffix.lower() not in {".json", ".csv"}:
            continue
        for entry in _load_entries(source_path):
            normalized = {
                "source_file": str(source_path),
                "occurred_at": str(entry.get("occurred_at") or entry.get("timestamp") or ""),
                "contact_name": str(entry.get("contact_name") or entry.get("name") or ""),
                "handle": str(entry.get("handle") or entry.get("phone") or entry.get("email") or ""),
                "direction": str(entry.get("direction") or "unknown"),
                "duration_seconds": int(float(entry.get("duration_seconds") or entry.get("duration") or 0)),
                "summary": str(entry.get("summary") or entry.get("notes") or ""),
                "source_app": str(entry.get("source_app") or "import"),
            }
            if normalized["occurred_at"]:
                entries.append(normalized)
    return entries


def format_call(entry: dict) -> tuple[str, dict, str]:
    contact = entry["contact_name"] or entry["handle"] or "Unknown Caller"
    occurred_at = entry["occurred_at"]
    timestamp = occurred_at.replace(":", "").replace("-", "").replace("T", " ").replace("Z", "")
    filename = f"{_safe_fragment(contact)} {timestamp[:15].strip() or 'Call'}.md"
    frontmatter = {
        "type": "call-entry",
        "contact_name": contact,
        "handle": entry["handle"],
        "direction": entry["direction"],
        "occurred_at": occurred_at,
        "duration_seconds": entry["duration_seconds"],
        "summary": entry["summary"],
        "source_import_path": entry["source_file"],
        "source_app": entry["source_app"],
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "calls"],
    }

    body_lines = [f"# Call — {contact}", ""]
    body_lines.append(f"- Direction: {entry['direction']}")
    body_lines.append(f"- Occurred At: {occurred_at}")
    if entry["handle"]:
        body_lines.append(f"- Handle: {entry['handle']}")
    if entry["duration_seconds"]:
        body_lines.append(f"- Duration Seconds: {entry['duration_seconds']}")
    if entry["summary"]:
        body_lines.extend(["", "## Notes", "", entry["summary"]])
    return filename, frontmatter, "\n".join(body_lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="Normalize imported call logs")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    parser.add_argument("--import-path", help="Folder containing call log .json/.csv exports")
    args = parser.parse_args()

    logger = setup_logging("call-log")
    state = SyncState("call_log")
    config = get_config()
    vault_path = args.vault or config.get("vault_path", "~/Documents/Achaean")
    default_import = config.get("adapters", {}).get("call_log", {}).get("import_path", "~/Documents/Achaean/inbox/calls")
    import_path = Path(args.import_path or default_import).expanduser().resolve()

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)

    if not import_path.exists():
        logger.info(f"Call log import path not found at {import_path}; nothing to do.")
        state.touch_synced()
        return

    entries = iter_call_entries(import_path)
    logger.info(f"Found {len(entries)} call log entr{('y' if len(entries) == 1 else 'ies')}")
    writer.clear_data_folder("calls")
    for entry in entries:
        filename, frontmatter, body = format_call(entry)
        writer.write_data_file("calls", filename, frontmatter, body, overwrite=True)

    state.touch_synced()
    logger.info("Done. Call logs written.")


if __name__ == "__main__":
    main()
