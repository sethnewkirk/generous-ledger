#!/usr/bin/env python3
"""
tasks.py — Sync Apple Reminders tasks into the vault.

USAGE:
    python3 scripts/adapters/tasks.py [--vault PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from lib.credentials import get_config
from lib.logging_config import setup_logging
from lib.macos_jxa import MacOSBridgeError, run_jxa_json
from lib.sync_state import SyncState
from lib.vault_writer import VaultWriter


def _safe_fragment(text: str, fallback: str = "Task") -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return " ".join(words[:8]) or fallback


def _task_filename(task: dict) -> str:
    base = _safe_fragment(str(task.get("title") or "Task"))
    ident = str(task.get("task_id") or base)
    suffix = ident[-8:] if len(ident) >= 8 else ident
    return f"{base} {suffix}.md"


def fetch_tasks() -> list[dict]:
    script = r"""
function callOr(fn, fallback) {
  try { return fn(); } catch (error) { return fallback; }
}

function isoDate(value) {
  if (!value) { return ""; }
  try { return value.toISOString(); } catch (error) { return ""; }
}

var Reminders = Application("Reminders");
var lists = Reminders.lists();
var output = [];

for (var i = 0; i < lists.length; i++) {
  var list = lists[i];
  var reminders = callOr(function () { return list.reminders(); }, []);
  for (var j = 0; j < reminders.length; j++) {
    var reminder = reminders[j];
    if (callOr(function () { return reminder.completed(); }, false)) {
      continue;
    }
    output.push({
      task_id: callOr(function () { return reminder.id(); }, ""),
      title: callOr(function () { return reminder.name(); }, ""),
      notes: callOr(function () { return reminder.body(); }, ""),
      list_name: callOr(function () { return list.name(); }, ""),
      due_date: isoDate(callOr(function () { return reminder.dueDate(); }, null)),
      creation_date: isoDate(callOr(function () { return reminder.creationDate(); }, null)),
      modification_date: isoDate(callOr(function () { return reminder.modificationDate(); }, null)),
      priority: callOr(function () { return reminder.priority(); }, 0),
      flagged: callOr(function () { return reminder.flagged(); }, false)
    });
  }
}

JSON.stringify(output);
"""
    raw = run_jxa_json(script, app_name="Reminders", timeout=600)
    return [item for item in raw if isinstance(item, dict) and str(item.get("title") or "").strip()]


def format_task(task: dict) -> tuple[dict, str]:
    due = str(task.get("due_date") or "")
    due_date = due.split("T", 1)[0] if "T" in due else due
    frontmatter = {
        "type": "task-entry",
        "task_id": str(task.get("task_id") or ""),
        "title": str(task.get("title") or "").strip(),
        "list_name": str(task.get("list_name") or "").strip(),
        "due_date": due_date,
        "due_at": due,
        "priority": int(task.get("priority") or 0),
        "flagged": bool(task.get("flagged") or False),
        "completed": False,
        "source": "apple-reminders",
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "tasks"],
    }

    body_lines = [f"# Task — {frontmatter['title']}", ""]
    if frontmatter["list_name"]:
        body_lines.append(f"- List: {frontmatter['list_name']}")
    if due_date:
        body_lines.append(f"- Due: {due}")
    if frontmatter["priority"]:
        body_lines.append(f"- Priority: {frontmatter['priority']}")
    if frontmatter["flagged"]:
        body_lines.append("- Flagged: true")

    notes = str(task.get("notes") or "").strip()
    if notes:
        body_lines.extend(["", "## Notes", "", notes])
    return frontmatter, "\n".join(body_lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="Sync Apple Reminders tasks to vault")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    args = parser.parse_args()

    logger = setup_logging("tasks")
    state = SyncState("tasks")
    vault_path = args.vault or get_config().get("vault_path", "~/Documents/Achaean")

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)

    try:
        tasks = fetch_tasks()
    except MacOSBridgeError as exc:
        logger.error(f"Failed to fetch Reminders: {exc}")
        sys.exit(1)

    logger.info(f"Fetched {len(tasks)} open task(s)")
    writer.clear_data_folder("tasks")
    for task in tasks:
        frontmatter, body = format_task(task)
        writer.write_data_file("tasks", _task_filename(task), frontmatter, body, overwrite=True)

    state.touch_synced()
    logger.info("Done. Tasks written.")


if __name__ == "__main__":
    main()
