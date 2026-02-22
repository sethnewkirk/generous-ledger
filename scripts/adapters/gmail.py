#!/usr/bin/env python3
"""
gmail.py — Sync Gmail messages to vault.

USAGE:
    python3 scripts/adapters/gmail.py [--vault PATH] [--days N]
    python3 scripts/adapters/gmail.py --setup          # First-time OAuth setup

PREREQUISITES:
    1. Use the same Google Cloud project as the Calendar adapter
    2. Enable the Gmail API in Cloud Console
    3. The OAuth client credentials file should already exist at:
       ~/.config/generous-ledger/credentials/google-calendar.json
       (shared with the Calendar adapter)
    4. Run with --setup to authorize Gmail access and get tokens

SETUP GUIDE:
    1. Go to https://console.cloud.google.com/
    2. Select the existing project (same one used for Calendar)
    3. Enable "Gmail API"
    4. Run: python3 scripts/adapters/gmail.py --setup
    5. Follow the browser prompt to authorize Gmail read access
    6. Tokens are saved automatically for future runs

DEPENDENCIES:
    pip install google-auth-oauthlib google-api-python-client pyyaml
"""

from __future__ import annotations

import argparse
import base64
import email.utils
import re
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from lib.vault_writer import VaultWriter
from lib.sync_state import SyncState
from lib.logging_config import setup_logging
from lib.credentials import load_credential, get_config, CREDENTIALS_DIR

# Remove script directory from sys.path to prevent calendar.py from
# shadowing the stdlib calendar module (breaks Google auth imports).
# Python auto-inserts the script's directory as sys.path[0] when running
# directly; this can be an absolute or relative path.
_script_dir = str(Path(__file__).resolve().parent)
sys.path = [p for p in sys.path
            if os.path.realpath(p or '.') != os.path.realpath(_script_dir)]
# Also purge any cached wrong-calendar from sys.modules
if 'calendar' in sys.modules and 'adapters' in getattr(sys.modules['calendar'], '__file__', ''):
    del sys.modules['calendar']

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = CREDENTIALS_DIR / "google-gmail-token.json"

MAX_RESULTS = 50


def get_gmail_service():
    """Build and return a Gmail API service object.

    Handles OAuth 2.0 token refresh automatically.
    Reuses the same client config as the Calendar adapter.
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
            # Reuse the same Google Cloud project client config as Calendar
            client_config = load_credential("google-calendar")
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save tokens for next run
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Contact matching
# ---------------------------------------------------------------------------

def load_known_contacts(vault_path: str) -> dict[str, str]:
    """Scan profile/people/*.md for email addresses in YAML frontmatter.

    Returns:
        Dict mapping email address (lowercase) to person name.
    """
    import yaml

    people_dir = Path(vault_path).expanduser().resolve() / "profile" / "people"
    contacts: dict[str, str] = {}

    if not people_dir.is_dir():
        return contacts

    for md_file in people_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        # Extract YAML frontmatter between --- delimiters
        if not text.startswith("---"):
            continue
        end = text.find("---", 3)
        if end == -1:
            continue
        try:
            fm = yaml.safe_load(text[3:end])
        except Exception:
            continue
        if not isinstance(fm, dict):
            continue

        name = fm.get("name", md_file.stem)

        # Check for email in frontmatter (single value or list)
        emails = fm.get("email", [])
        if isinstance(emails, str):
            emails = [emails]
        for addr in emails:
            if isinstance(addr, str) and "@" in addr:
                contacts[addr.strip().lower()] = name

        # Also scan body for email-like patterns in contact info
        body = text[end + 3:]
        for match in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", body):
            addr = match.group(0).lower()
            if addr not in contacts:
                contacts[addr] = name

    return contacts


# ---------------------------------------------------------------------------
# Message fetching
# ---------------------------------------------------------------------------

def fetch_message_ids(service, query: str, max_results: int = MAX_RESULTS) -> list[str]:
    """Fetch message IDs matching a Gmail search query.

    Returns:
        List of message ID strings.
    """
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return [m["id"] for m in result.get("messages", [])]


def fetch_messages(service, days: int, known_contacts: dict[str, str]) -> list[dict]:
    """Fetch messages from Gmail using two queries, deduplicating by ID.

    Query 1: category:primary newer_than:Nd -from:noreply
    Query 2: from:(<known contacts>) newer_than:Nd

    Args:
        service: Gmail API service object.
        days: Number of days to look back.
        known_contacts: Dict mapping email -> name.

    Returns:
        List of full message dicts.
    """
    # Query 1: Primary inbox, excluding noreply
    primary_query = f"category:primary newer_than:{days}d -from:noreply"
    primary_ids = fetch_message_ids(service, primary_query)

    # Query 2: Known contacts (may catch messages outside primary)
    contact_ids: list[str] = []
    if known_contacts:
        # Build OR query for known contact emails
        email_list = " OR ".join(known_contacts.keys())
        contact_query = f"from:({email_list}) newer_than:{days}d"
        contact_ids = fetch_message_ids(service, contact_query)

    # Deduplicate by message ID
    seen: set[str] = set()
    unique_ids: list[str] = []
    for msg_id in primary_ids + contact_ids:
        if msg_id not in seen:
            seen.add(msg_id)
            unique_ids.append(msg_id)

    # Fetch full message content for each unique ID
    messages: list[dict] = []
    for msg_id in unique_ids:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )
        messages.append(msg)

    return messages


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------

def get_header(msg: dict, name: str) -> str:
    """Extract a header value from a Gmail message dict."""
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def extract_sender_email(from_header: str) -> str:
    """Extract bare email address from a From header value."""
    _, addr = email.utils.parseaddr(from_header)
    return addr.lower()


def extract_sender_name(from_header: str) -> str:
    """Extract display name from a From header value, falling back to email."""
    name, addr = email.utils.parseaddr(from_header)
    return name if name else addr


def extract_body_text(payload: dict) -> str:
    """Recursively extract plain text body from a Gmail message payload.

    Prefers text/plain parts. Falls back to text/html with tag stripping.
    """
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    # Recurse into multipart
    parts = payload.get("parts", [])
    # First pass: look for text/plain
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        # Recurse into nested multipart
        nested = extract_body_text(part)
        if nested:
            return nested

    # Second pass: fall back to text/html with tag stripping
    for part in parts:
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                return strip_html_tags(html)

    # Top-level text/html fallback
    if mime_type == "text/html" and body_data:
        html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        return strip_html_tags(html)

    return ""


def strip_html_tags(html: str) -> str:
    """Rough HTML-to-text conversion for email bodies."""
    # Remove style and script blocks
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace <br> and block elements with newlines
    text = re.sub(r"<br[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_message(msg: dict, known_contacts: dict[str, str]) -> dict:
    """Parse a Gmail API message into a structured dict.

    Returns:
        Dict with keys: id, thread_id, from_name, from_email, subject,
        date, date_str, labels, body, is_unread, is_known_contact.
    """
    from_header = get_header(msg, "From")
    from_email = extract_sender_email(from_header)
    from_name = extract_sender_name(from_header)
    subject = get_header(msg, "Subject") or "(no subject)"
    date_header = get_header(msg, "Date")
    labels = msg.get("labelIds", [])
    body = extract_body_text(msg.get("payload", {}))

    # Parse date
    parsed_date = None
    if date_header:
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_header)
        except Exception:
            pass

    return {
        "id": msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "from_name": from_name,
        "from_email": from_email,
        "subject": subject,
        "date": parsed_date,
        "date_str": parsed_date.strftime("%Y-%m-%d %H:%M") if parsed_date else "",
        "labels": labels,
        "body": body.strip(),
        "is_unread": "UNREAD" in labels,
        "is_known_contact": from_email in known_contacts,
        "contact_name": known_contacts.get(from_email, ""),
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def group_by_sender(messages: list[dict]) -> dict[str, list[dict]]:
    """Group parsed messages by sender email, preserving thread order."""
    by_sender: dict[str, list[dict]] = {}
    for msg in messages:
        key = msg["from_email"]
        by_sender.setdefault(key, []).append(msg)
    # Sort each sender's messages by date
    for msgs in by_sender.values():
        msgs.sort(key=lambda m: m["date"] or datetime.min)
    return by_sender


def format_message(msg: dict) -> str:
    """Format a single parsed message as markdown."""
    lines: list[str] = []

    status = " (unread)" if msg["is_unread"] else ""
    contact_tag = f" [known contact: {msg['contact_name']}]" if msg["is_known_contact"] else ""

    lines.append(f"### {msg['subject']}{status}{contact_tag}")
    lines.append(f"- **From:** {msg['from_name']} <{msg['from_email']}>")
    lines.append(f"- **Date:** {msg['date_str']}")

    label_display = [l for l in msg["labels"] if not l.startswith("CATEGORY_")]
    if label_display:
        lines.append(f"- **Labels:** {', '.join(label_display)}")

    lines.append("")
    if msg["body"]:
        lines.append(msg["body"])
    else:
        lines.append("*(no text content)*")
    lines.append("")

    return "\n".join(lines)


def format_day(date_str: str, messages: list[dict]) -> tuple[dict, str]:
    """Format a day's messages into frontmatter and body.

    Returns:
        Tuple of (frontmatter_dict, body_string).
    """
    unread_count = sum(1 for m in messages if m["is_unread"])
    known_count = sum(1 for m in messages if m["is_known_contact"])

    frontmatter = {
        "type": "email-daily",
        "date": date_str,
        "message_count": len(messages),
        "unread_count": unread_count,
        "known_contact_messages": known_count,
        "source": "gmail",
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "email"],
    }

    body_lines: list[str] = [f"# Email — {date_str}", ""]

    if not messages:
        body_lines.append("No messages for this day.")
        return frontmatter, "\n".join(body_lines)

    # Group by sender
    by_sender = group_by_sender(messages)

    # Sort senders: known contacts first, then by most recent message
    def sender_sort_key(item: tuple[str, list[dict]]) -> tuple[int, str]:
        sender_email, msgs = item
        is_known = 0 if msgs[0]["is_known_contact"] else 1
        # Sort by most recent message date descending
        latest = max((m["date"] for m in msgs if m["date"]), default=datetime.min)
        return (is_known, latest.isoformat() if latest != datetime.min else "")

    sorted_senders = sorted(by_sender.items(), key=sender_sort_key)

    for sender_email, msgs in sorted_senders:
        sender_name = msgs[0]["from_name"]
        contact_label = ""
        if msgs[0]["is_known_contact"]:
            contact_label = f" — known contact"

        body_lines.append(f"## {sender_name}{contact_label}")
        body_lines.append("")

        for msg in msgs:
            body_lines.append(format_message(msg))

        body_lines.append("---")
        body_lines.append("")

    return frontmatter, "\n".join(body_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sync Gmail messages to vault")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    parser.add_argument("--days", type=int, default=1, help="Days to look back (default: 1)")
    parser.add_argument("--setup", action="store_true", help="Run first-time OAuth setup")
    args = parser.parse_args()

    logger = setup_logging("gmail")
    state = SyncState("gmail")

    if args.setup:
        logger.info("Running first-time OAuth setup for Gmail...")
        try:
            service = get_gmail_service()
        except FileNotFoundError as e:
            logger.error(str(e))
            logger.error("To set up Gmail:")
            logger.error("  1. Go to https://console.cloud.google.com/apis/credentials")
            logger.error("  2. Enable the Gmail API")
            logger.error("  3. Create OAuth 2.0 credentials (Desktop app)")
            logger.error("  4. Download JSON and save to: %s/google-calendar.json", CREDENTIALS_DIR)
            logger.error("  5. Run --setup again")
            sys.exit(1)
        logger.info("Setup complete. Token saved to %s", TOKEN_FILE)
        return

    vault_path = args.vault or get_config().get("vault_path", "~/Documents/Achaean")

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # Load known contacts from profile/people/ files
    known_contacts = load_known_contacts(vault_path)
    if known_contacts:
        logger.info(f"Loaded {len(known_contacts)} known contact email(s)")
    else:
        logger.info("No known contacts found in profile/people/")

    logger.info(f"Fetching Gmail messages for past {args.days} day(s)")

    try:
        service = get_gmail_service()
        raw_messages = fetch_messages(service, args.days, known_contacts)
    except FileNotFoundError as e:
        logger.error(f"Credentials not found: {e}")
        logger.error("Run with --setup first, or see docstring for setup instructions.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to fetch Gmail messages: {e}")
        sys.exit(1)

    logger.info(f"Fetched {len(raw_messages)} messages")

    # Parse all messages
    parsed = [parse_message(msg, known_contacts) for msg in raw_messages]

    # Group by date
    by_date: dict[str, list[dict]] = {}
    for msg in parsed:
        if msg["date"]:
            msg_date = msg["date"].strftime("%Y-%m-%d")
        else:
            msg_date = date.today().isoformat()
        by_date.setdefault(msg_date, []).append(msg)

    files_written = 0

    # Write a file for each day in the range
    today = date.today()
    for i in range(args.days):
        day = today - timedelta(days=i)
        day_str = day.isoformat()

        day_messages = by_date.get(day_str, [])
        frontmatter, body = format_day(day_str, day_messages)
        filename = f"{day_str}.md"

        path = writer.write_data_file(
            folder="email",
            filename=filename,
            frontmatter=frontmatter,
            body=body,
            overwrite=True,
        )
        logger.info(f"Wrote {path} ({len(day_messages)} messages)")
        files_written += 1

    state.touch_synced()
    logger.info(f"Done. {files_written} email file(s) written.")


if __name__ == "__main__":
    main()
