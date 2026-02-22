"""
vault_writer.py — Write structured markdown files into the Obsidian vault.

Handles YAML frontmatter serialization and idempotent file writes.
Files are written directly to the vault folder; Obsidian detects
filesystem changes and indexes them automatically.

USAGE:
    from lib.vault_writer import VaultWriter

    writer = VaultWriter("~/Documents/Achaean")
    writer.write_data_file(
        folder="weather",
        filename="2026-02-21.md",
        frontmatter={"type": "weather-daily", "date": "2026-02-21"},
        body="Partly cloudy, high of 45°F.",
    )
"""

import os
import yaml
from pathlib import Path
from datetime import datetime


class VaultWriter:
    """Write markdown files with YAML frontmatter to an Obsidian vault."""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path).expanduser().resolve()
        if not self.vault_path.is_dir():
            raise FileNotFoundError(f"Vault not found: {self.vault_path}")

    def write_data_file(
        self,
        folder: str,
        filename: str,
        frontmatter: dict,
        body: str,
        overwrite: bool = True,
    ) -> Path:
        """Write a markdown file with YAML frontmatter to data/<folder>/<filename>.

        Args:
            folder: Subfolder under data/ (e.g., "weather", "calendar")
            filename: File name (e.g., "2026-02-21.md")
            frontmatter: Dict of YAML frontmatter properties
            body: Markdown body content
            overwrite: If True, replace existing file. If False, skip if exists.

        Returns:
            Path to the written file.
        """
        data_dir = self.vault_path / "data" / folder
        data_dir.mkdir(parents=True, exist_ok=True)

        file_path = data_dir / filename

        if not overwrite and file_path.exists():
            return file_path

        # Serialize frontmatter to YAML
        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()

        content = f"---\n{yaml_str}\n---\n\n{body}\n"

        # Atomic write: write to temp file, then rename
        tmp_path = file_path.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.rename(file_path)

        return file_path

    def ensure_data_folder(self, folder: str) -> Path:
        """Create data/<folder> if it doesn't exist."""
        data_dir = self.vault_path / "data" / folder
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
