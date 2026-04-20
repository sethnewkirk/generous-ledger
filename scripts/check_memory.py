#!/usr/bin/env python3

import argparse
import json

from scripts.steward_memory.health import build_memory_health_report, write_memory_health_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a steward memory health report.")
    parser.add_argument("--vault", required=True, help="Path to the target vault")
    parser.add_argument("--since-days", type=int, default=90, help="Inspect recent signal inputs from the last N days")
    parser.add_argument("--stale-days", type=int, default=45, help="Flag active claims older than N days")
    args = parser.parse_args()

    report = build_memory_health_report(
        args.vault,
        since_days=args.since_days,
        stale_days=args.stale_days,
    )
    write_memory_health_report(args.vault, report, stale_days=args.stale_days)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
