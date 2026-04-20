from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import re

from .catalog import ambiguous_aliases, get_subject_by_title, load_subject_catalog, suggest_subjects
from .markdown import read_markdown, write_markdown
from .models import SignalEnvelope


HIGH_VALUE_UNRESOLVED_SOURCES = {"calendar", "email", "message", "call", "task", "voice"}
ACTIVE_CONTACT_SOURCES = {"calendar", "email", "message", "call"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"[^\d]", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _clean_name_key(value: str) -> str | None:
    key = " ".join(token for token in re.split(r"[^a-z0-9]+", value.lower()) if token)
    if not key:
        return None
    if len(key.split()) > 5:
        return None
    return key


def _signal_hints(signal: SignalEnvelope) -> list[str]:
    hints = list(signal.subject_hints)
    if signal.summary:
        hints.append(signal.summary)
    return _unique_strings(hints)


def _suggestion_links(hints: list[str], catalog) -> list[str]:
    suggestions: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        for subject in suggest_subjects(hint, catalog, limit=3):
            if subject.wikilink not in seen:
                seen.add(subject.wikilink)
                suggestions.append(subject.wikilink)
    return suggestions


def _contact_match_keys(frontmatter: dict) -> set[str]:
    keys: set[str] = set()

    def add_name(value: str) -> None:
        name_key = _clean_name_key(value)
        if name_key:
            keys.add(f"name:{name_key}")

    def add_identifier(value: str) -> None:
        value = value.strip()
        if not value:
            return
        if "@" in value:
            keys.add(f"email:{value.lower()}")
        phone = _normalize_phone(value)
        if len(phone) >= 7:
            keys.add(f"phone:{phone}")

    add_name(str(frontmatter.get("name") or ""))
    add_name(str(frontmatter.get("nickname") or ""))
    add_name(str(frontmatter.get("organization") or ""))
    for key in ("emails", "phones", "aliases"):
        values = frontmatter.get(key, [])
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            add_name(value)
            add_identifier(value)
    return keys


def _signal_match_keys(signal: SignalEnvelope) -> set[str]:
    keys: set[str] = set()

    def add_name(value: str) -> None:
        name_key = _clean_name_key(value)
        if name_key:
            keys.add(f"name:{name_key}")

    def add_identifier(value: str) -> None:
        cleaned = value.strip()
        if not cleaned:
            return
        if "@" in cleaned:
            keys.add(f"email:{cleaned.lower()}")
        phone = _normalize_phone(cleaned)
        if len(phone) >= 7:
            keys.add(f"phone:{phone}")

    if signal.source_type == "calendar":
        participants = signal.metadata.get("participants", [])
        if isinstance(participants, list):
            for participant in participants:
                if isinstance(participant, str):
                    add_name(participant)
                    add_identifier(participant)
    elif signal.source_type == "email":
        sender = str(signal.metadata.get("sender") or "").strip()
        add_name(sender)
        add_identifier(sender)
    elif signal.source_type == "message":
        sender = str(signal.metadata.get("sender") or "").strip()
        conversation = str(signal.metadata.get("conversation") or "").strip()
        add_name(sender)
        add_identifier(sender)
        add_name(conversation)
        add_identifier(conversation)
    elif signal.source_type == "call":
        handle = str(signal.metadata.get("handle") or "").strip()
        add_identifier(handle)
        for hint in signal.subject_hints:
            add_name(hint)
            add_identifier(hint)

    return keys


def _active_contact_keys(signals: list[SignalEnvelope]) -> set[str]:
    active_keys: set[str] = set()
    for signal in signals:
        if signal.source_type not in ACTIVE_CONTACT_SOURCES:
            continue
        active_keys.update(_signal_match_keys(signal))
    return active_keys


def _load_documents(vault: Path, subdir: str) -> list[dict[str, object]]:
    directory = vault / "memory" / subdir
    documents: list[dict[str, object]] = []
    if not directory.exists():
        return documents
    for md_file in sorted(directory.glob("*.md")):
        frontmatter, body = read_markdown(md_file)
        documents.append({"path": str(md_file.relative_to(vault)), "frontmatter": frontmatter, "body": body})
    return documents


def _unresolved_signals(signals: list[SignalEnvelope], catalog) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for signal in signals:
        if signal.subjects:
            continue
        if signal.source_type not in HIGH_VALUE_UNRESOLVED_SOURCES:
            continue
        hints = _signal_hints(signal)
        if not hints:
            continue
        items.append(
            {
                "source_type": signal.source_type,
                "source_ref": signal.source_ref,
                "raw_path": signal.raw_path,
                "summary": signal.summary,
                "occurred_at": signal.occurred_at,
                "hints": hints,
                "suggestions": _suggestion_links(hints, catalog),
            }
        )
    return items


def _unlinked_contacts(vault: Path, catalog, active_contact_keys: set[str]) -> tuple[list[dict[str, object]], int]:
    contacts_dir = vault / "data" / "contacts"
    if not contacts_dir.exists():
        return [], 0

    items: list[dict[str, object]] = []
    active_total = 0
    for md_file in sorted(contacts_dir.glob("*.md")):
        frontmatter, _ = read_markdown(md_file)
        if str(frontmatter.get("type") or "") != "contact-entry":
            continue

        contact_keys = _contact_match_keys(frontmatter)
        is_active = bool(contact_keys.intersection(active_contact_keys))
        if not is_active:
            continue
        active_total += 1

        profile_target = str(frontmatter.get("profile_target") or "").strip()
        if profile_target.startswith("[[") and profile_target.endswith("]]"):
            target_title = profile_target[2:-2].split("|", 1)[0]
            if get_subject_by_title(catalog, target_title):
                continue

        name = str(frontmatter.get("name") or md_file.stem).strip()
        if get_subject_by_title(catalog, name):
            continue

        hints = [name]
        for key in ("nickname", "organization"):
            value = str(frontmatter.get(key) or "").strip()
            if value:
                hints.append(value)
        for key in ("emails", "phones"):
            raw_values = frontmatter.get(key, [])
            if isinstance(raw_values, str):
                raw_values = [raw_values]
            if isinstance(raw_values, list):
                for value in raw_values:
                    if isinstance(value, str) and value.strip():
                        hints.append(value.strip())

        items.append(
            {
                "path": str(md_file.relative_to(vault)),
                "name": name,
                "profile_target": profile_target,
                "hints": _unique_strings(hints),
                "suggestions": _suggestion_links(hints, catalog),
            }
        )
    return items, active_total


def _orphan_documents(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for document in documents:
        frontmatter = document["frontmatter"]
        subjects = [str(item) for item in frontmatter.get("subjects", []) if isinstance(item, str)]
        if subjects:
            continue
        items.append(
            {
                "path": document["path"],
                "summary": str(frontmatter.get("summary") or ""),
                "type": str(frontmatter.get("type") or ""),
                "status": str(frontmatter.get("status") or ""),
            }
        )
    return items


def _stale_active_claims(documents: list[dict[str, object]], *, stale_days: int) -> list[dict[str, object]]:
    cutoff = datetime.now() - timedelta(days=stale_days)
    items: list[dict[str, object]] = []
    for document in documents:
        frontmatter = document["frontmatter"]
        status = str(frontmatter.get("status") or "")
        if status not in {"active", "provisional"}:
            continue
        last_updated = str(frontmatter.get("last_updated") or "")
        if not last_updated:
            continue
        try:
            updated_at = datetime.fromisoformat(last_updated)
        except ValueError:
            continue
        if updated_at >= cutoff:
            continue
        items.append(
            {
                "path": document["path"],
                "summary": str(frontmatter.get("summary") or ""),
                "status": status,
                "last_updated": last_updated,
            }
        )
    return items


def _conflicting_active_claim_slots(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for document in documents:
        frontmatter = document["frontmatter"]
        status = str(frontmatter.get("status") or "")
        if status not in {"active", "provisional"}:
            continue
        claim_slot = str(frontmatter.get("claim_slot") or "").strip()
        if not claim_slot:
            continue
        grouped[claim_slot].append(
            {
                "path": document["path"],
                "summary": str(frontmatter.get("summary") or ""),
                "status": status,
            }
        )

    conflicts: list[dict[str, object]] = []
    for claim_slot, records in grouped.items():
        if len(records) > 1:
            conflicts.append({"claim_slot": claim_slot, "claims": records})
    return conflicts


def build_memory_health_report(
    vault_path: str,
    *,
    signals: list[SignalEnvelope] | None = None,
    since_days: int = 90,
    stale_days: int = 45,
) -> dict[str, object]:
    if signals is None:
        from .compiler import collect_signals

        signals = collect_signals(vault_path, since_days=since_days)

    vault = Path(vault_path).expanduser().resolve()
    catalog = load_subject_catalog(vault_path)
    claim_docs = _load_documents(vault, "claims")
    event_docs = _load_documents(vault, "events")
    alias_conflicts = ambiguous_aliases(catalog)
    active_contact_keys = _active_contact_keys(signals)
    unlinked_contacts, active_contacts = _unlinked_contacts(vault, catalog, active_contact_keys)
    total_contacts = sum(
        1
        for path in (vault / "data" / "contacts").glob("*.md")
        if path.is_file()
    ) if (vault / "data" / "contacts").exists() else 0

    report = {
        "generated_at": _now_iso(),
        "summary": {
            "signals_scanned": len(signals),
            "total_contacts": total_contacts,
            "active_contacts": active_contacts,
            "unresolved_signals": 0,
            "unlinked_contacts": 0,
            "ambiguous_aliases": 0,
            "orphan_events": 0,
            "orphan_claims": 0,
            "stale_active_claims": 0,
            "conflicting_active_claim_slots": 0,
        },
        "unresolved_signals": _unresolved_signals(signals, catalog),
        "unlinked_contacts": unlinked_contacts,
        "ambiguous_aliases": [
            {
                "alias": alias,
                "subjects": [subject.wikilink for subject in subjects],
            }
            for alias, subjects in sorted(alias_conflicts.items())
        ],
        "orphan_events": _orphan_documents(event_docs),
        "orphan_claims": _orphan_documents(claim_docs),
        "stale_active_claims": _stale_active_claims(claim_docs, stale_days=stale_days),
        "conflicting_active_claim_slots": _conflicting_active_claim_slots(claim_docs),
    }

    summary = report["summary"]
    for key in (
        "unresolved_signals",
        "unlinked_contacts",
        "ambiguous_aliases",
        "orphan_events",
        "orphan_claims",
        "stale_active_claims",
        "conflicting_active_claim_slots",
    ):
        summary[key] = len(report[key])  # type: ignore[index]

    return report


def _render_section(title: str, items: list[str], empty_text: str) -> str:
    lines = [f"## {title}"]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append(f"- {empty_text}")
    return "\n".join(lines)


def _render_report_markdown(report: dict[str, object], *, stale_days: int) -> str:
    summary = report["summary"]
    unresolved_lines = [
        f"`{item['source_type']}` {item['source_ref']} — {item['summary']} | hints: {', '.join(item['hints'])}"
        + (f" | suggestions: {', '.join(item['suggestions'])}" if item["suggestions"] else "")
        for item in report["unresolved_signals"]  # type: ignore[index]
    ]
    contact_lines = [
        f"{item['name']} ({item['path']})"
        + (f" | suggestions: {', '.join(item['suggestions'])}" if item["suggestions"] else "")
        for item in report["unlinked_contacts"]  # type: ignore[index]
    ]
    alias_lines = [
        f"`{item['alias']}` -> {', '.join(item['subjects'])}"
        for item in report["ambiguous_aliases"]  # type: ignore[index]
    ]
    orphan_event_lines = [
        f"{item['path']} — {item['summary'] or '(no summary)'}"
        for item in report["orphan_events"]  # type: ignore[index]
    ]
    orphan_claim_lines = [
        f"{item['path']} — {item['summary'] or '(no summary)'}"
        for item in report["orphan_claims"]  # type: ignore[index]
    ]
    stale_lines = [
        f"{item['path']} — last updated {item['last_updated']} — {item['summary'] or '(no summary)'}"
        for item in report["stale_active_claims"]  # type: ignore[index]
    ]
    conflict_lines = [
        f"`{item['claim_slot']}` -> {', '.join(claim['path'] for claim in item['claims'])}"
        for item in report["conflicting_active_claim_slots"]  # type: ignore[index]
    ]

    return "\n\n".join(
        [
            "# Memory Health Report",
            _render_section(
                "Summary",
                [
                    f"Signals scanned: {summary['signals_scanned']}",
                    f"Total contacts synced: {summary['total_contacts']}",
                    f"Active contacts: {summary['active_contacts']}",
                    f"Unresolved signals: {summary['unresolved_signals']}",
                    f"Unlinked active contacts: {summary['unlinked_contacts']}",
                    f"Ambiguous aliases: {summary['ambiguous_aliases']}",
                    f"Orphan events: {summary['orphan_events']}",
                    f"Orphan claims: {summary['orphan_claims']}",
                    f"Stale active claims (> {stale_days} days): {summary['stale_active_claims']}",
                    f"Conflicting active claim slots: {summary['conflicting_active_claim_slots']}",
                ],
                "No summary available.",
            ),
            _render_section("Unresolved Signals", unresolved_lines, "No unresolved high-value signals."),
            _render_section("Unlinked Active Contacts", contact_lines, "No unlinked active contacts."),
            _render_section("Ambiguous Aliases", alias_lines, "No ambiguous aliases."),
            _render_section("Orphan Events", orphan_event_lines, "No orphan events."),
            _render_section("Orphan Claims", orphan_claim_lines, "No orphan claims."),
            _render_section("Stale Active Claims", stale_lines, "No stale active claims."),
            _render_section("Conflicting Active Claim Slots", conflict_lines, "No conflicting active claim slots."),
        ]
    ).rstrip() + "\n"


def write_memory_health_report(
    vault_path: str,
    report: dict[str, object],
    *,
    stale_days: int = 45,
) -> tuple[Path, Path]:
    vault = Path(vault_path).expanduser().resolve()
    memory_dir = vault / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    json_path = memory_dir / "health-report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    markdown_path = memory_dir / "health-report.md"
    write_markdown(
        markdown_path,
        {
            "type": "memory-health-report",
            "generated_at": report["generated_at"],
            "tags": ["memory", "health"],
            "last_updated": datetime.now().date().isoformat(),
        },
        _render_report_markdown(report, stale_days=stale_days),
    )
    return json_path, markdown_path
