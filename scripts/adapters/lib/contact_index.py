"""Helpers for loading known contact identifiers from profile and synced contact data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import yaml


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d]", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _read_frontmatter(md_file: Path) -> tuple[dict, str]:
    text = md_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    try:
        frontmatter = yaml.safe_load(text[3:end]) or {}
    except Exception:
        return {}, text
    if not isinstance(frontmatter, dict):
        return {}, text
    return frontmatter, text[end + 3 :]


def _iter_values(value) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, (int, float)):
        yield str(value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (str, int, float)):
                yield str(item)


def _register_contact_points(mapping: dict[str, str], name: str, *, emails=(), phones=(), body: str = "") -> None:
    for addr in emails:
        if "@" in addr:
            mapping[addr.strip().lower()] = name

    for phone in phones:
        normalized = normalize_phone(phone)
        if len(normalized) >= 7:
            mapping[normalized] = name

    for match in EMAIL_RE.finditer(body):
        mapping.setdefault(match.group(0).lower(), name)


def load_contact_identifier_map(vault_path: str) -> dict[str, str]:
    vault = Path(vault_path).expanduser().resolve()
    mapping: dict[str, str] = {}

    people_dir = vault / "profile" / "people"
    if people_dir.is_dir():
        for md_file in sorted(people_dir.glob("*.md")):
            frontmatter, body = _read_frontmatter(md_file)
            name = str(frontmatter.get("name") or md_file.stem)
            _register_contact_points(
                mapping,
                name,
                emails=list(_iter_values(frontmatter.get("email", []))),
                phones=list(_iter_values(frontmatter.get("phone", []))),
                body=body,
            )

    contacts_dir = vault / "data" / "contacts"
    if contacts_dir.is_dir():
        for md_file in sorted(contacts_dir.glob("*.md")):
            frontmatter, body = _read_frontmatter(md_file)
            if str(frontmatter.get("type") or "") != "contact-entry":
                continue
            name = str(frontmatter.get("name") or md_file.stem)
            _register_contact_points(
                mapping,
                name,
                emails=list(_iter_values(frontmatter.get("emails", []))),
                phones=list(_iter_values(frontmatter.get("phones", []))),
                body=body,
            )

    return mapping


def load_email_contacts(vault_path: str) -> dict[str, str]:
    return {identifier: name for identifier, name in load_contact_identifier_map(vault_path).items() if "@" in identifier}


def load_message_contacts(vault_path: str) -> dict[str, str]:
    return load_contact_identifier_map(vault_path)
