#!/usr/bin/env python3
"""
calendar.py — Sync Google Calendar events to vault.

USAGE:
    python3 scripts/adapters/calendar.py [--vault PATH] [--days N]
    python3 scripts/adapters/calendar.py --setup          # First-time OAuth setup

PREREQUISITES:
    1. Create a Google Cloud project and enable the Calendar API
    2. Create OAuth 2.0 credentials (Desktop app type)
    3. Download credentials.json and save to:
       ~/.config/generous-ledger/credentials/google-calendar.json
    4. Run with --setup to authorize and get tokens

SETUP GUIDE:
    1. Go to https://console.cloud.google.com/
    2. Create a new project (or use existing)
    3. Enable "Google Calendar API"
    4. Go to Credentials > Create Credentials > OAuth client ID
    5. Choose "Desktop app" as application type
    6. Download the JSON and save it as google-calendar.json in credentials dir
    7. Run: python3 scripts/adapters/calendar.py --setup
    8. Follow the browser prompt to authorize
    9. Tokens are saved automatically for future runs

DEPENDENCIES:
    pip install google-auth-oauthlib google-api-python-client
"""

from __future__ import annotations

import argparse
import sys
import json
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.vault_writer import VaultWriter
from lib.sync_state import SyncState
from lib.logging_config import setup_logging
from lib.credentials import load_credential, save_credential, get_config, CREDENTIALS_DIR

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE = CREDENTIALS_DIR / "google-calendar-token.json"


def get_calendar_service():
    """Build and return a Google Calendar API service object.

    Handles OAuth 2.0 token refresh automatically.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("ERROR: Required packages not installed.")
        print("Run: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    creds = None

    # Load existing token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Refresh or re-authorize if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = load_credential("google-calendar")
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save tokens for next run
        TOKEN_FILE.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def fetch_events(service, days: int = 7) -> list[dict]:
    """Fetch upcoming events from Google Calendar.

    Args:
        service: Google Calendar API service object.
        days: Number of days to look ahead.

    Returns:
        List of event dicts.
    """
    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days)).isoformat() + "Z"

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return events_result.get("items", [])


def group_events_by_date(events: list[dict]) -> dict[str, list[dict]]:
    """Group events by their start date."""
    by_date = {}
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date", ""))
        # Extract just the date portion
        event_date = start[:10]
        by_date.setdefault(event_date, []).append(event)
    return by_date


def format_event(event: dict) -> str:
    """Format a single event as a markdown list item."""
    start = event["start"].get("dateTime", event["start"].get("date", ""))
    summary = event.get("summary", "(no title)")
    location = event.get("location", "")

    # Extract time if it's a timed event (not all-day)
    if "T" in start:
        time_str = start[11:16]  # HH:MM
        line = f"- **{time_str}** — {summary}"
    else:
        line = f"- *(all day)* — {summary}"

    if location:
        line += f" ({location})"

    # Add attendees if present
    attendees = event.get("attendees", [])
    if attendees:
        names = [
            a.get("displayName", a.get("email", ""))
            for a in attendees
            if not a.get("self", False)
        ]
        if names and len(names) <= 5:
            line += f"\n  - With: {', '.join(names)}"

    return line


def format_day(date_str: str, events: list[dict]) -> tuple[dict, str]:
    """Format a day's events into frontmatter and body.

    Returns:
        Tuple of (frontmatter_dict, body_string).
    """
    # Check for time conflicts
    timed_events = [
        e for e in events if "T" in e["start"].get("dateTime", "")
    ]
    has_conflicts = False
    for i, e1 in enumerate(timed_events):
        for e2 in timed_events[i + 1 :]:
            end1 = e1.get("end", {}).get("dateTime", "")
            start2 = e2["start"].get("dateTime", "")
            if end1 and start2 and end1 > start2:
                has_conflicts = True
                break

    frontmatter = {
        "type": "calendar-day",
        "date": date_str,
        "event_count": len(events),
        "has_conflicts": has_conflicts,
        "source": "google-calendar",
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "calendar"],
    }

    body_lines = [f"# Calendar — {date_str}", ""]
    for event in events:
        body_lines.append(format_event(event))
    body_lines.append("")

    if has_conflicts:
        body_lines.append("**Note:** Scheduling conflict detected.")

    return frontmatter, "\n".join(body_lines)


def main():
    parser = argparse.ArgumentParser(description="Sync Google Calendar to vault")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    parser.add_argument("--days", type=int, default=7, help="Days to look ahead (default: 7)")
    parser.add_argument("--setup", action="store_true", help="Run first-time OAuth setup")
    args = parser.parse_args()

    logger = setup_logging("calendar")
    state = SyncState("calendar")

    if args.setup:
        logger.info("Running first-time OAuth setup...")
        service = get_calendar_service()
        logger.info("Setup complete. Token saved.")
        return

    vault_path = args.vault or get_config().get("vault_path", "~/Documents/Achaean")

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"Fetching calendar events for next {args.days} days")

    try:
        service = get_calendar_service()
        events = fetch_events(service, args.days)
    except FileNotFoundError as e:
        logger.error(f"Credentials not found: {e}")
        logger.error("Run with --setup first, or see docstring for setup instructions.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to fetch calendar: {e}")
        sys.exit(1)

    logger.info(f"Fetched {len(events)} events")

    grouped = group_events_by_date(events)
    files_written = 0

    # Also write empty files for days with no events (within range)
    today = date.today()
    for i in range(args.days):
        day = today + timedelta(days=i)
        day_str = day.isoformat()

        day_events = grouped.get(day_str, [])
        frontmatter, body = format_day(day_str, day_events)
        filename = f"{day_str}.md"

        path = writer.write_data_file(
            folder="calendar",
            filename=filename,
            frontmatter=frontmatter,
            body=body,
            overwrite=True,
        )
        logger.info(f"Wrote {path} ({len(day_events)} events)")
        files_written += 1

    state.touch_synced()
    logger.info(f"Done. {files_written} calendar files written.")


if __name__ == "__main__":
    main()
