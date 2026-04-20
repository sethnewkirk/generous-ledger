#!/usr/bin/env python3
"""
contacts.py — Sync Apple Contacts into the vault.

USAGE:
    python3 scripts/adapters/contacts.py [--vault PATH]

PREREQUISITES:
    1. macOS with Contacts configured
    2. Automation permission for osascript / terminal to read Contacts
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from lib.credentials import get_config
from lib.logging_config import setup_logging
from lib.macos_jxa import MacOSBridgeError, run_jxa_json
from lib.sync_state import SyncState
from lib.vault_writer import VaultWriter


def _safe_fragment(text: str, fallback: str = "Contact") -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return " ".join(words[:6]) or fallback


def _contact_filename(contact: dict) -> str:
    base = _safe_fragment(contact.get("name") or contact.get("organization") or "Contact")
    ident = str(contact.get("id") or base)
    suffix = ident[-8:] if len(ident) >= 8 else ident
    return f"{base} {suffix}.md".strip()


def fetch_contacts() -> list[dict]:
    script = r"""
function callOr(fn, fallback) {
  try { return fn(); } catch (error) { return fallback; }
}

function isoDate(value) {
  if (!value) { return ""; }
  try { return value.toISOString(); } catch (error) { return ""; }
}

var Contacts = Application("Contacts");
var people = Contacts.people();
var output = [];

for (var i = 0; i < people.length; i++) {
  var person = people[i];
  var firstName = callOr(function () { return person.firstName(); }, "");
  var lastName = callOr(function () { return person.lastName(); }, "");
  var organization = callOr(function () { return person.organization(); }, "");
  var displayName = [firstName, lastName].join(" ").trim() || organization || callOr(function () { return person.name(); }, "");
  var emails = callOr(function () {
    return person.emails().map(function (email) {
      return callOr(function () { return email.value(); }, "");
    }).filter(Boolean);
  }, []);
  var phones = callOr(function () {
    return person.phones().map(function (phone) {
      return callOr(function () { return phone.value(); }, "");
    }).filter(Boolean);
  }, []);
  var urls = callOr(function () {
    return person.urls().map(function (url) {
      return callOr(function () { return url.value(); }, "");
    }).filter(Boolean);
  }, []);
  output.push({
    id: callOr(function () { return person.id(); }, ""),
    name: displayName,
    first_name: firstName,
    last_name: lastName,
    organization: organization,
    nickname: callOr(function () { return person.nickname(); }, ""),
    note: callOr(function () { return person.note(); }, ""),
    emails: emails,
    phones: phones,
    urls: urls,
    birthday: isoDate(callOr(function () { return person.birthday(); }, null))
  });
}

JSON.stringify(output);
"""
    raw = run_jxa_json(script, app_name="Contacts", timeout=300)
    return [item for item in raw if isinstance(item, dict) and (item.get("name") or item.get("organization"))]


def format_contact(contact: dict) -> tuple[dict, str]:
    name = str(contact.get("name") or contact.get("organization") or "Unknown Contact").strip()
    emails = [str(item).strip().lower() for item in contact.get("emails", []) if str(item).strip()]
    phones = [str(item).strip() for item in contact.get("phones", []) if str(item).strip()]
    urls = [str(item).strip() for item in contact.get("urls", []) if str(item).strip()]
    birthday = str(contact.get("birthday") or "")
    if "T" in birthday:
        birthday = birthday.split("T", 1)[0]

    frontmatter = {
        "type": "contact-entry",
        "contact_id": str(contact.get("id") or ""),
        "name": name,
        "organization": str(contact.get("organization") or ""),
        "nickname": str(contact.get("nickname") or ""),
        "birthday": birthday,
        "emails": emails,
        "phones": phones,
        "urls": urls,
        "source": "apple-contacts",
        "last_synced": datetime.now().isoformat(),
        "tags": ["data", "contacts"],
    }

    body_lines = [f"# Contact — {name}", ""]
    if frontmatter["organization"]:
        body_lines.append(f"- Organization: {frontmatter['organization']}")
    if frontmatter["nickname"]:
        body_lines.append(f"- Nickname: {frontmatter['nickname']}")
    if birthday:
        body_lines.append(f"- Birthday: {birthday}")
    if emails:
        body_lines.append(f"- Emails: {', '.join(emails)}")
    if phones:
        body_lines.append(f"- Phones: {', '.join(phones)}")
    if urls:
        body_lines.append(f"- URLs: {', '.join(urls)}")
    note = str(contact.get("note") or "").strip()
    if note:
        body_lines.extend(["", "## Notes", "", note])

    return frontmatter, "\n".join(body_lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="Sync Apple Contacts to vault")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    args = parser.parse_args()

    logger = setup_logging("contacts")
    state = SyncState("contacts")
    vault_path = args.vault or get_config().get("vault_path", "~/Documents/Achaean")

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)

    try:
        contacts = fetch_contacts()
    except MacOSBridgeError as exc:
        logger.error(f"Failed to fetch Contacts: {exc}")
        sys.exit(1)

    logger.info(f"Fetched {len(contacts)} contact(s)")
    writer.clear_data_folder("contacts")
    for contact in contacts:
        frontmatter, body = format_contact(contact)
        writer.write_data_file("contacts", _contact_filename(contact), frontmatter, body, overwrite=True)

    state.touch_synced()
    logger.info("Done. Contacts written.")


if __name__ == "__main__":
    main()
