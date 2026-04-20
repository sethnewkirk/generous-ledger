#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.steward_policy.loader import load_manifest, render_core_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate derived steward policy artifacts.")
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repo root")
    args = parser.parse_args()

    root = Path(args.root)
    manifest = load_manifest(root)
    core_path = root / manifest["core"]["path"]
    core_path.write_text(render_core_markdown(root, manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
