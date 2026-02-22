#!/usr/bin/env python3
"""
finance.py — Sync YNAB budget summaries to vault.

USAGE:
    python3 scripts/adapters/finance.py [--vault PATH]

PREREQUISITES:
    1. Get a YNAB Personal Access Token at: https://app.ynab.com/settings/developer
    2. Save it to: ~/.config/generous-ledger/credentials/ynab.json
       Format: {"token": "your-token-here"}
    3. Run the adapter

SECURITY:
    This adapter writes ONLY aggregated summaries (category totals, budget status).
    Individual transactions, account numbers, and balances are NEVER written to the vault.
"""

from __future__ import annotations

import argparse
import sys
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

sys.path.append(str(Path(__file__).parent))

from lib.vault_writer import VaultWriter
from lib.sync_state import SyncState
from lib.logging_config import setup_logging
from lib.credentials import load_credential, get_config

YNAB_BASE = "https://api.ynab.com/v1"


def ynab_request(endpoint: str, token: str) -> dict:
    """Make an authenticated request to the YNAB API."""
    url = f"{YNAB_BASE}{endpoint}"
    req = Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_default_budget_id(token: str) -> str:
    """Get the first (default) budget ID."""
    data = ynab_request("/budgets", token)
    budgets = data.get("data", {}).get("budgets", [])
    if not budgets:
        raise ValueError("No budgets found in YNAB account")
    return budgets[0]["id"]


def get_month_summary(token: str, budget_id: str, month: str) -> dict:
    """Get budget month summary.

    Args:
        token: YNAB API token
        budget_id: Budget ID
        month: Month in YYYY-MM-01 format
    """
    return ynab_request(f"/budgets/{budget_id}/months/{month}", token)


def get_categories(token: str, budget_id: str) -> list[dict]:
    """Get all budget categories with current month activity."""
    data = ynab_request(f"/budgets/{budget_id}/categories", token)
    groups = data.get("data", {}).get("category_groups", [])

    categories = []
    for group in groups:
        if group.get("hidden", False) or group["name"] in ("Internal Master Category", "Credit Card Payments"):
            continue
        for cat in group.get("categories", []):
            if cat.get("hidden", False) or cat.get("deleted", False):
                continue
            categories.append({
                "group": group["name"],
                "name": cat["name"],
                "budgeted": cat.get("budgeted", 0) / 1000,  # YNAB uses milliunits
                "activity": abs(cat.get("activity", 0)) / 1000,
                "balance": cat.get("balance", 0) / 1000,
            })

    return categories


def format_weekly_summary(categories: list[dict], week_start: date) -> tuple[dict, str]:
    """Format category data into a weekly vault file."""
    week_end = week_start + timedelta(days=6)
    week_num = week_start.isocalendar()[1]

    total_budgeted = sum(c["budgeted"] for c in categories)
    total_activity = sum(c["activity"] for c in categories)

    over_budget = [
        c["name"] for c in categories
        if c["activity"] > c["budgeted"] > 0
    ]

    frontmatter = {
        "type": "finance-weekly",
        "week": f"{week_start.year}-W{week_num:02d}",
        "period_start": week_start.isoformat(),
        "period_end": week_end.isoformat(),
        "total_budgeted": round(total_budgeted, 2),
        "total_spent": round(total_activity, 2),
        "over_budget_categories": over_budget[:5],  # cap at 5
        "source": "ynab",
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "finance"],
    }

    body_lines = [
        f"# Budget Summary — Week of {week_start.isoformat()}",
        "",
        f"**Total budgeted:** ${total_budgeted:,.2f}",
        f"**Total spent:** ${total_activity:,.2f}",
        "",
    ]

    if over_budget:
        body_lines.append("## Over Budget")
        body_lines.append("")
        for cat in categories:
            if cat["name"] in over_budget:
                over_by = cat["activity"] - cat["budgeted"]
                pct = (cat["activity"] / cat["budgeted"] * 100) if cat["budgeted"] > 0 else 0
                body_lines.append(
                    f"- **{cat['name']}**: ${cat['activity']:,.2f} / ${cat['budgeted']:,.2f} "
                    f"(+${over_by:,.2f}, {pct:.0f}%)"
                )
        body_lines.append("")

    body_lines.append("## By Category Group")
    body_lines.append("")

    # Group categories
    groups = {}
    for cat in categories:
        groups.setdefault(cat["group"], []).append(cat)

    for group_name, cats in sorted(groups.items()):
        group_total = sum(c["activity"] for c in cats)
        if group_total == 0:
            continue
        body_lines.append(f"### {group_name} (${group_total:,.2f})")
        body_lines.append("")
        for cat in sorted(cats, key=lambda c: c["activity"], reverse=True):
            if cat["activity"] == 0:
                continue
            status = ""
            if cat["budgeted"] > 0 and cat["activity"] > cat["budgeted"]:
                status = " **OVER**"
            body_lines.append(
                f"- {cat['name']}: ${cat['activity']:,.2f} / ${cat['budgeted']:,.2f}{status}"
            )
        body_lines.append("")

    return frontmatter, "\n".join(body_lines)


def main():
    parser = argparse.ArgumentParser(description="Sync YNAB budget summaries to vault")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    args = parser.parse_args()

    logger = setup_logging("finance")
    state = SyncState("finance")

    vault_path = args.vault or get_config().get("vault_path", "~/Documents/Achaean")

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    try:
        creds = load_credential("ynab")
        token = creds["token"]
    except (FileNotFoundError, KeyError) as e:
        logger.error(f"YNAB credentials not found: {e}")
        logger.error('Create ~/.config/generous-ledger/credentials/ynab.json with: {"token": "your-token"}')
        sys.exit(1)

    logger.info("Fetching YNAB budget data")

    try:
        budget_id = get_default_budget_id(token)
        categories = get_categories(token, budget_id)
    except (URLError, ValueError) as e:
        logger.error(f"Failed to fetch YNAB data: {e}")
        sys.exit(1)

    logger.info(f"Fetched {len(categories)} categories")

    # Write weekly summary
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_num = today.isocalendar()[1]

    frontmatter, body = format_weekly_summary(categories, week_start)
    filename = f"{today.year}-W{week_num:02d}.md"

    path = writer.write_data_file(
        folder="finance",
        filename=filename,
        frontmatter=frontmatter,
        body=body,
        overwrite=True,
    )
    logger.info(f"Wrote {path}")

    state.touch_synced()
    logger.info("Done. Finance summary written.")


if __name__ == "__main__":
    main()
