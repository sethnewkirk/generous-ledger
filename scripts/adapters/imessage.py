#!/usr/bin/env python3
"""
imessage.py — Sync iMessage conversations to vault.

USAGE:
    python3 scripts/adapters/imessage.py [--vault PATH] [--days N]

PREREQUISITES:
    1. Full Disk Access must be granted to Terminal (or whichever app runs python3)
       System Settings > Privacy & Security > Full Disk Access > Terminal
    2. No API keys or OAuth needed — reads directly from local SQLite database

DATA SOURCE:
    ~/Library/Messages/chat.db (macOS iMessage database, read-only access)

OUTPUT:
    data/messages/YYYY-MM-DD.md — One file per day in the vault
    Known contacts get full conversation detail.
    Unknown contacts get count-only summary.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import struct
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from lib.vault_writer import VaultWriter
from lib.sync_state import SyncState
from lib.logging_config import setup_logging
from lib.credentials import get_config

# Core Data epoch: 2001-01-01 00:00:00 UTC
CORE_DATA_EPOCH = 978307200

CHAT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def open_chat_db() -> sqlite3.Connection:
    """Open chat.db in read-only mode.

    Returns:
        SQLite connection in read-only mode.

    Raises:
        SystemExit: If the database is not found or not readable.
    """
    if not CHAT_DB_PATH.exists():
        print(f"ERROR: iMessage database not found at {CHAT_DB_PATH}")
        print("This adapter only works on macOS with iMessage configured.")
        sys.exit(1)

    db_uri = f"file:{CHAT_DB_PATH}?mode=ro"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        conn.row_factory = sqlite3.Row
        # Quick sanity check
        conn.execute("SELECT COUNT(*) FROM message LIMIT 1")
        return conn
    except sqlite3.OperationalError as e:
        error_msg = str(e).lower()
        if "unable to open" in error_msg or "authorization denied" in error_msg:
            print(f"ERROR: Cannot read {CHAT_DB_PATH}")
            print()
            print("Full Disk Access is required. Grant it to your terminal app:")
            print("  System Settings > Privacy & Security > Full Disk Access")
            print("  Enable access for Terminal (or iTerm, etc.)")
            print()
            print("After granting access, restart your terminal and try again.")
            sys.exit(1)
        raise


def convert_timestamp(raw: int | float | None) -> datetime | None:
    """Convert a Core Data timestamp to a local datetime.

    iMessage timestamps are nanoseconds since 2001-01-01 (Core Data epoch).
    Older messages may use seconds instead. This function handles both.

    Args:
        raw: Raw timestamp value from the database.

    Returns:
        datetime in local time, or None if the value is missing/invalid.
    """
    if raw is None or raw == 0:
        return None

    # Defensive: if value > 1e12, treat as nanoseconds; otherwise seconds
    if raw > 1e12:
        unix_ts = (raw / 1e9) + CORE_DATA_EPOCH
    else:
        unix_ts = raw + CORE_DATA_EPOCH

    try:
        return datetime.fromtimestamp(unix_ts)
    except (OSError, ValueError, OverflowError):
        return None


def decode_attributed_body(blob: bytes | None) -> str:
    """Extract plain text from an attributedBody binary blob.

    The attributedBody column contains an NSKeyedArchiver/streamtyped blob.
    We try multiple strategies to extract readable text from it.

    Args:
        blob: Raw bytes from the attributedBody column.

    Returns:
        Extracted text, or empty string on failure.
    """
    if not blob:
        return ""

    try:
        raw = bytes(blob)
    except (TypeError, ValueError):
        return ""

    # Strategy 1: Look for NSString marker and extract text after it
    # The pattern is: NSString followed by a length byte and then the text
    for marker in [b"NSString", b"NSDictionary"]:
        idx = raw.find(marker)
        if idx == -1:
            continue

        # Skip past the marker and look for text
        after = raw[idx + len(marker):]
        # Find the start of readable text: skip control bytes until we hit
        # a printable ASCII or UTF-8 character
        text_start = 0
        for i, byte in enumerate(after):
            if 0x20 <= byte < 0x7F or byte >= 0xC0:
                text_start = i
                break

        if text_start > 0:
            # Extract until we hit a run of control characters
            candidate = after[text_start:]
            # Find the end: look for null bytes or runs of non-printable chars
            end = len(candidate)
            null_idx = candidate.find(b"\x00")
            if null_idx > 0:
                end = null_idx

            try:
                text = candidate[:end].decode("utf-8", errors="replace").strip()
                # Clean up replacement characters and control chars
                text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]+", "", text)
                if len(text) > 1:
                    return text
            except Exception:
                continue

    # Strategy 2: Decode as streamtyped — find readable text between control chars
    # Look for the longest run of printable text in the blob
    try:
        decoded = raw.decode("utf-8", errors="replace")
        # Find runs of printable characters (including common punctuation and spaces)
        runs = re.findall(r"[\x20-\x7E\u00A0-\uFFFF]{2,}", decoded)
        if runs:
            # Filter out known metadata strings
            skip_patterns = {
                "NSString", "NSDictionary", "NSMutableString",
                "NSObject", "NSAttributedString", "NSMutableAttributedString",
                "streamtyped", "NSValue", "NSNumber",
            }
            candidates = [
                r for r in runs
                if r not in skip_patterns and len(r) > 1
            ]
            if candidates:
                # Return the longest candidate as the most likely message text
                return max(candidates, key=len).strip()
    except Exception:
        pass

    return ""


def fetch_messages(conn: sqlite3.Connection, days: int) -> list[dict]:
    """Fetch recent messages from chat.db.

    Args:
        conn: SQLite connection to chat.db.
        days: Number of days to look back.

    Returns:
        List of message dicts with keys: handle_id, text, is_from_me,
        timestamp, service, chat_id, chat_display_name, is_group.
    """
    # Calculate the cutoff timestamp in Core Data nanoseconds
    cutoff_dt = datetime.now() - timedelta(days=days)
    cutoff_unix = cutoff_dt.timestamp()
    cutoff_core_data_ns = int((cutoff_unix - CORE_DATA_EPOCH) * 1e9)

    query = """
        SELECT
            m.ROWID,
            m.text,
            m.attributedBody,
            m.is_from_me,
            m.date AS msg_date,
            m.associated_message_type,
            m.service,
            h.id AS handle_id,
            c.ROWID AS chat_rowid,
            c.chat_identifier,
            c.display_name AS chat_display_name,
            c.style AS chat_style
        FROM message m
        LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        LEFT JOIN chat c ON c.ROWID = cmj.chat_id
        LEFT JOIN handle h ON h.ROWID = m.handle_id
        WHERE m.date > ?
          AND m.associated_message_type = 0
        ORDER BY m.date ASC
    """

    rows = conn.execute(query, (cutoff_core_data_ns,)).fetchall()
    messages: list[dict] = []

    for row in rows:
        # Extract text, falling back to attributedBody
        text = row["text"] or ""
        if not text.strip():
            text = decode_attributed_body(row["attributedBody"])

        if not text.strip():
            continue  # Skip messages with no extractable text

        timestamp = convert_timestamp(row["msg_date"])
        is_group = (row["chat_style"] or 0) == 43  # 43 = group chat

        messages.append({
            "handle_id": row["handle_id"] or "",
            "text": text.strip(),
            "is_from_me": bool(row["is_from_me"]),
            "timestamp": timestamp,
            "service": row["service"] or "iMessage",
            "chat_id": row["chat_identifier"] or "",
            "chat_display_name": row["chat_display_name"] or "",
            "is_group": is_group,
        })

    return messages


# ---------------------------------------------------------------------------
# Contact matching
# ---------------------------------------------------------------------------

def normalize_phone(phone: str) -> str:
    """Normalize a phone number by stripping everything except digits.

    Keeps leading +1 as just the digits for US numbers.

    Args:
        phone: Raw phone string.

    Returns:
        Digits-only string.
    """
    digits = re.sub(r"[^\d]", "", phone)
    # US numbers: strip leading 1 if 11 digits
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def load_known_contacts(vault_path: str) -> dict[str, str]:
    """Scan profile/people/*.md for phone numbers and emails in YAML frontmatter.

    Returns:
        Dict mapping normalized identifier (phone digits or lowercase email)
        to person name.
    """
    import yaml

    people_dir = Path(vault_path).expanduser().resolve() / "profile" / "people"
    contacts: dict[str, str] = {}

    if not people_dir.is_dir():
        return contacts

    for md_file in people_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
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

        # Phone numbers
        phones = fm.get("phone", [])
        if isinstance(phones, (str, int)):
            phones = [str(phones)]
        for phone in phones:
            normalized = normalize_phone(str(phone))
            if len(normalized) >= 7:
                contacts[normalized] = name

        # Email addresses
        emails = fm.get("email", [])
        if isinstance(emails, str):
            emails = [emails]
        for addr in emails:
            if isinstance(addr, str) and "@" in addr:
                contacts[addr.strip().lower()] = name

    return contacts


def match_contact(handle_id: str, known_contacts: dict[str, str]) -> str | None:
    """Match a handle ID against known contacts.

    Handle IDs can be phone numbers (+15551234567) or emails.

    Args:
        handle_id: The iMessage handle identifier.
        known_contacts: Dict from load_known_contacts.

    Returns:
        Contact name if matched, None otherwise.
    """
    if not handle_id:
        return None

    # Try email match
    if "@" in handle_id:
        return known_contacts.get(handle_id.strip().lower())

    # Try phone match
    normalized = normalize_phone(handle_id)
    return known_contacts.get(normalized)


# ---------------------------------------------------------------------------
# Grouping and formatting
# ---------------------------------------------------------------------------

def group_messages_by_conversation(
    messages: list[dict],
    known_contacts: dict[str, str],
) -> tuple[dict[str, list[dict]], int, int]:
    """Group messages by conversation and split into known/unknown.

    For direct messages, the key is the handle_id.
    For group chats, the key is the chat_id.

    Returns:
        Tuple of:
        - Dict mapping conversation key to list of messages (known contacts only)
        - Count of unknown conversations
        - Count of unknown messages
    """
    by_conversation: dict[str, list[dict]] = {}

    for msg in messages:
        if msg["is_group"]:
            key = msg["chat_id"] or msg["handle_id"] or "unknown-group"
        else:
            key = msg["handle_id"] or "unknown"
        by_conversation.setdefault(key, []).append(msg)

    known_conversations: dict[str, list[dict]] = {}
    unknown_conversation_count = 0
    unknown_message_count = 0

    for key, msgs in by_conversation.items():
        # For group chats, check if any participants are known
        is_known = False
        for msg in msgs:
            if msg["is_group"]:
                # Group chat: consider known if it has a display name or
                # any participant is a known contact
                if msg["chat_display_name"]:
                    is_known = True
                    break
                if not msg["is_from_me"] and match_contact(msg["handle_id"], known_contacts):
                    is_known = True
                    break
            else:
                # Direct message: check the handle
                handle = msg["handle_id"] if not msg["is_from_me"] else key
                if match_contact(handle, known_contacts):
                    is_known = True
                    break

        if is_known:
            known_conversations[key] = msgs
        else:
            unknown_conversation_count += 1
            unknown_message_count += len(msgs)

    return known_conversations, unknown_conversation_count, unknown_message_count


def format_conversation(
    key: str,
    messages: list[dict],
    known_contacts: dict[str, str],
) -> str:
    """Format a single conversation as markdown.

    Args:
        key: Conversation identifier (handle_id or chat_id).
        messages: List of message dicts in this conversation.
        known_contacts: Known contact lookup dict.

    Returns:
        Markdown string for this conversation.
    """
    lines: list[str] = []

    # Determine conversation header
    first_msg = messages[0]
    if first_msg["is_group"]:
        display_name = first_msg["chat_display_name"] or key
        lines.append(f"## {display_name} (group)")
    else:
        contact_name = match_contact(key, known_contacts)
        display_name = contact_name or key
        lines.append(f"## {display_name}")

    # Show handle ID for reference
    if not first_msg["is_group"]:
        lines.append(f"*{key}*")
    lines.append("")

    # Format each message
    for msg in messages:
        ts = msg["timestamp"]
        time_str = ts.strftime("%H:%M") if ts else "??:??"
        service = msg["service"]

        if msg["is_from_me"]:
            sender = "You"
        elif msg["is_group"]:
            sender = match_contact(msg["handle_id"], known_contacts) or msg["handle_id"]
        else:
            sender = match_contact(key, known_contacts) or key

        service_tag = f" [{service}]" if service.lower() != "imessage" else ""
        lines.append(f"- **{time_str}** {sender}{service_tag}: {msg['text']}")

    lines.append("")
    return "\n".join(lines)


def format_day(
    date_str: str,
    messages: list[dict],
    known_contacts: dict[str, str],
) -> tuple[dict, str]:
    """Format a day's messages into frontmatter and body.

    Returns:
        Tuple of (frontmatter_dict, body_string).
    """
    known_convos, unknown_convo_count, unknown_msg_count = (
        group_messages_by_conversation(messages, known_contacts)
    )

    total_conversations = len(known_convos) + unknown_convo_count
    total_messages = sum(len(msgs) for msgs in known_convos.values()) + unknown_msg_count

    frontmatter = {
        "type": "imessage-daily",
        "date": date_str,
        "conversation_count": total_conversations,
        "message_count": total_messages,
        "known_contact_conversations": len(known_convos),
        "source": "imessage-local",
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "messages"],
    }

    body_lines: list[str] = [f"# Messages — {date_str}", ""]

    if not messages:
        body_lines.append("No messages for this day.")
        return frontmatter, "\n".join(body_lines)

    # Known conversations: full detail
    if known_convos:
        # Sort by earliest message timestamp
        sorted_convos = sorted(
            known_convos.items(),
            key=lambda item: min(
                (m["timestamp"] for m in item[1] if m["timestamp"]),
                default=datetime.min,
            ),
        )

        for key, msgs in sorted_convos:
            body_lines.append(format_conversation(key, msgs, known_contacts))
            body_lines.append("---")
            body_lines.append("")

    # Unknown conversations: count-only summary
    if unknown_convo_count > 0:
        body_lines.append(
            f"*{unknown_convo_count} other conversation(s) "
            f"with {unknown_msg_count} message(s)*"
        )
        body_lines.append("")

    return frontmatter, "\n".join(body_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sync iMessage conversations to vault")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    parser.add_argument("--days", type=int, default=1, help="Days to look back (default: 1)")
    args = parser.parse_args()

    logger = setup_logging("imessage")
    state = SyncState("imessage")

    vault_path = args.vault or get_config().get("vault_path", "~/Documents/Achaean")

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # Load known contacts from profile/people/ files
    known_contacts = load_known_contacts(vault_path)
    if known_contacts:
        logger.info(f"Loaded {len(known_contacts)} known contact identifier(s)")
    else:
        logger.info("No known contacts found in profile/people/")

    logger.info(f"Fetching iMessage conversations for past {args.days} day(s)")

    # Open the iMessage database
    conn = open_chat_db()

    try:
        messages = fetch_messages(conn, args.days)
    except Exception as e:
        logger.error(f"Failed to query iMessage database: {e}")
        sys.exit(1)
    finally:
        conn.close()

    logger.info(f"Fetched {len(messages)} messages")

    # Group messages by date
    by_date: dict[str, list[dict]] = {}
    for msg in messages:
        if msg["timestamp"]:
            msg_date = msg["timestamp"].strftime("%Y-%m-%d")
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
        frontmatter, body = format_day(day_str, day_messages, known_contacts)
        filename = f"{day_str}.md"

        path = writer.write_data_file(
            folder="messages",
            filename=filename,
            frontmatter=frontmatter,
            body=body,
            overwrite=True,
        )
        logger.info(f"Wrote {path} ({len(day_messages)} messages)")
        files_written += 1

    state.touch_synced()
    logger.info(f"Done. {files_written} message file(s) written.")


if __name__ == "__main__":
    main()
