#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.steward_policy.loader import PolicyRequest, build_policy_packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic steward policy packet.")
    parser.add_argument("--vault", required=True, help="Path to the target vault or repo root")
    parser.add_argument("--surface", choices=["chat", "onboarding", "routine"], required=True)
    parser.add_argument(
        "--workflow",
        choices=["general_chat", "note_chat", "onboarding", "daily", "evening", "weekly", "monthly", "ambient"],
        required=True,
    )
    parser.add_argument("--provider", choices=["codex", "claude"], required=True)
    parser.add_argument("--write-intent", choices=["none", "profile", "memory", "routine_output", "note_writeback"], required=True)
    parser.add_argument(
        "--intent-tag",
        action="append",
        default=[],
        choices=["relationship", "recommendation", "planning", "moral_guidance", "file_writing"],
        help="Optional deterministic enrichment tag",
    )
    args = parser.parse_args()

    packet = build_policy_packet(
        args.vault,
        PolicyRequest(
            surface=args.surface,
            workflow=args.workflow,
            provider=args.provider,
            write_intent=args.write_intent,
            intent_tags=tuple(args.intent_tag),
        ),
    )
    print(packet.markdown, end="")


if __name__ == "__main__":
    main()
