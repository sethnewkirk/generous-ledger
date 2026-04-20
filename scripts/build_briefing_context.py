#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.steward_memory.briefing_context import build_briefing_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bounded context for steward briefing runs.")
    parser.add_argument("--vault", required=True, help="Path to the target vault")
    parser.add_argument(
        "--workflow",
        choices=["daily", "evening", "weekly", "monthly", "ambient"],
        required=True,
        help="Briefing workflow",
    )
    parser.add_argument("--note", default="", help="Relative note path relevant to the workflow")
    args = parser.parse_args()

    print(
        build_briefing_context(
            args.vault,
            workflow=args.workflow,
            note_relative_path=args.note or None,
        ),
        end="",
    )


if __name__ == "__main__":
    main()
