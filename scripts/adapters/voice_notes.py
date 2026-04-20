#!/usr/bin/env python3
"""
voice_notes.py — Normalize imported voice note transcripts into the vault.

USAGE:
    python3 scripts/adapters/voice_notes.py [--vault PATH] [--import-path PATH]
"""

from __future__ import annotations

import argparse
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


def _safe_fragment(text: str, fallback: str = "Voice Note") -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return " ".join(words[:8]) or fallback


def _frontmatter_from_markdown(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    import yaml

    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        data = {}
    body = text[end + 5 :].lstrip("\n")
    return data, body


def _normalize_voice_item(source_path: Path) -> dict | None:
    if source_path.suffix.lower() == ".json":
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
        return None

    if source_path.suffix.lower() == ".md":
        frontmatter, body = _frontmatter_from_markdown(source_path.read_text(encoding="utf-8"))
        return {
            "title": frontmatter.get("title") or source_path.stem,
            "recorded_at": frontmatter.get("recorded_at") or datetime.fromtimestamp(source_path.stat().st_mtime).isoformat(),
            "summary": frontmatter.get("summary") or "",
            "transcript": body.strip(),
            "subjects": frontmatter.get("subjects", []),
            "source_app": frontmatter.get("source_app") or "imported-markdown",
        }

    if source_path.suffix.lower() == ".txt":
        return {
            "title": source_path.stem,
            "recorded_at": datetime.fromtimestamp(source_path.stat().st_mtime).isoformat(),
            "summary": "",
            "transcript": source_path.read_text(encoding="utf-8").strip(),
            "subjects": [],
            "source_app": "imported-text",
        }

    return None


def iter_voice_items(import_path: Path) -> list[tuple[Path, dict]]:
    items: list[tuple[Path, dict]] = []
    for source_path in sorted(import_path.glob("*")):
        if not source_path.is_file() or source_path.suffix.lower() not in {".json", ".md", ".txt"}:
            continue
        payload = _normalize_voice_item(source_path)
        if not payload or not str(payload.get("transcript") or "").strip():
            continue
        items.append((source_path, payload))
    return items


def format_voice_note(source_path: Path, payload: dict) -> tuple[str, dict, str]:
    title = str(payload.get("title") or source_path.stem).strip()
    recorded_at = str(payload.get("recorded_at") or datetime.fromtimestamp(source_path.stat().st_mtime).isoformat())
    subjects = payload.get("subjects", [])
    if isinstance(subjects, str):
        subjects = [subjects]
    subjects = [str(item).strip() for item in subjects if str(item).strip()]
    summary = str(payload.get("summary") or "").strip()
    transcript = str(payload.get("transcript") or "").strip()

    filename = f"{_safe_fragment(title)} {source_path.stem[-8:]}.md"
    frontmatter = {
        "type": "voice-note",
        "voice_note_id": source_path.stem,
        "title": title,
        "recorded_at": recorded_at,
        "subjects": subjects,
        "source_import_path": str(source_path),
        "source_app": str(payload.get("source_app") or "import"),
        "summary": summary,
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "voice"],
    }

    body_lines = [f"# Voice Note — {title}", ""]
    if summary:
        body_lines.extend(["## Summary", "", summary, ""])
    body_lines.extend(["## Transcript", "", transcript])
    return filename, frontmatter, "\n".join(body_lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="Normalize imported voice note transcripts")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    parser.add_argument("--import-path", help="Folder containing .json/.md/.txt voice transcripts")
    args = parser.parse_args()

    logger = setup_logging("voice-notes")
    state = SyncState("voice_notes")
    config = get_config()
    vault_path = args.vault or config.get("vault_path", "~/Documents/Achaean")
    default_import = config.get("adapters", {}).get("voice_notes", {}).get("import_path", "~/Documents/Achaean/inbox/voice")
    import_path = Path(args.import_path or default_import).expanduser().resolve()

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)

    if not import_path.exists():
        logger.info(f"Voice import path not found at {import_path}; nothing to do.")
        state.touch_synced()
        return

    items = iter_voice_items(import_path)
    logger.info(f"Found {len(items)} voice note import(s)")
    writer.clear_data_folder("voice")
    for source_path, payload in items:
        filename, frontmatter, body = format_voice_note(source_path, payload)
        writer.write_data_file("voice", filename, frontmatter, body, overwrite=True)

    state.touch_synced()
    logger.info("Done. Voice notes written.")


if __name__ == "__main__":
    main()
