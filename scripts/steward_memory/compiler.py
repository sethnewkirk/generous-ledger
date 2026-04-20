from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .catalog import SubjectCatalog, load_subject_catalog, resolve_subjects
from .health import build_memory_health_report, write_memory_health_report
from .index import build_memory_index
from .markdown import read_markdown, replace_generated_block, write_markdown
from .models import ClaimCandidate, CompileReport, SignalEnvelope, SubjectRef
from .wikilinks import as_wikilink, normalize_lookup_key, replace_titles_with_wikilinks, safe_title_fragment, short_hash


SYSTEM_NOTE_ROOTS = {
    ".obsidian",
    "bases",
    "data",
    "diary",
    "docs",
    "memory",
    "node_modules",
    "profile",
    "reviews",
    "scripts",
    "src",
    "templates",
}

OBLIGATION_KEYWORDS = (
    "follow up",
    "follow-up",
    "reply",
    "respond",
    "send",
    "call",
    "text",
    "schedule",
    "remember to",
    "need to",
    "needs to",
    "must",
    "should",
    "owe",
    "promised",
    "deadline",
    "due",
    "finish",
    "complete",
)
DEFERRAL_KEYWORDS = (
    "defer",
    "deferred",
    "deferral",
    "reschedule",
    "rescheduled",
    "postpone",
    "postponed",
    "push to",
    "pushed to",
    "move to tomorrow",
    "move to next week",
    "not yet",
    "later",
    "tomorrow instead",
)
RELATIONSHIP_KEYWORDS = (
    "birthday",
    "anniversary",
    "married",
    "engaged",
    "friend",
    "family",
    "relationship",
)
MAYBE_KEYWORDS = ("maybe", "might", "consider", "perhaps", "possibly", "tentative")
REQUEST_KEYWORDS = (
    "can you",
    "could you",
    "would you",
    "please",
    "let me know",
    "are you able",
    "when can",
    "should we",
)
FOLLOW_UP_PHRASES = (
    "follow up",
    "reply",
    "respond",
    "send",
    "call back",
    "text back",
    "schedule",
)

TASK_RE = re.compile(r"^\s*[-*]\s+\[(?P<done>[ xX])\]\s+(?P<text>.+)$")
STRUCTURED_CLAIM_RE = re.compile(
    r"^\s*(?P<type>Obligation|Fact|Preference|Pattern|Idea)\s*(?:\[(?P<slot>[^\]]+)\])?\s*:\s*(?P<text>.+)$",
    re.IGNORECASE,
)
CALENDAR_EVENT_RE = re.compile(r"^- \*\*(?P<time>[^*]+)\*\* — (?P<summary>.+)$")
CALENDAR_WITH_RE = re.compile(r"^\s+- With:\s+(?P<names>.+)$")
MESSAGE_SECTION_RE = re.compile(r"^## (?P<title>.+)$")
MESSAGE_LINE_RE = re.compile(r"^- \*\*(?P<time>\d{2}:\d{2})\*\* (?P<sender>[^:]+): (?P<text>.+)$")
EMAIL_SENDER_RE = re.compile(r"^## (?P<sender>.+)$")
EMAIL_SUBJECT_RE = re.compile(r"^### (?P<subject>.+)$")
FRONTMATTER_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _today_iso() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_read(path: Path) -> tuple[dict, str]:
    return read_markdown(path)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    candidates = [
        raw,
        raw.replace("Z", "+00:00"),
        f"{raw}T00:00:00" if FRONTMATTER_DATE_RE.match(raw) else "",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _iso_from_file_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _within_cutoff(timestamp: str | None, cutoff: datetime | None) -> bool:
    if cutoff is None:
        return True
    parsed = _parse_datetime(timestamp)
    if parsed is None:
        return True
    return parsed >= cutoff


def _normalize_line(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed


def _strip_markdown_artifacts(text: str) -> str:
    cleaned = re.sub(r"\[(?:x| )\]\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    return _normalize_line(cleaned)


def _looks_like_obligation(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in OBLIGATION_KEYWORDS)


def _looks_like_deferral(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in DEFERRAL_KEYWORDS)


def _looks_relationship_relevant(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in RELATIONSHIP_KEYWORDS)


def _looks_provisional(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in MAYBE_KEYWORDS)


def _looks_like_request(text: str) -> bool:
    lowered = text.lower()
    return "?" in text or any(keyword in lowered for keyword in REQUEST_KEYWORDS)


def _sentence(text: str) -> str:
    cleaned = _strip_markdown_artifacts(text).rstrip(".")
    if not cleaned:
        return ""
    return f"{cleaned}."


def _relative_path(vault: Path, path: Path) -> str:
    return str(path.resolve().relative_to(vault.resolve()))


def _subject_wikilinks(subjects: list[SubjectRef]) -> list[str]:
    return [subject.wikilink for subject in subjects]


def _subjects_from_frontmatter(frontmatter: dict, catalog: SubjectCatalog) -> list[SubjectRef]:
    raw_subjects = frontmatter.get("subjects", [])
    if isinstance(raw_subjects, str):
        raw_subjects = [raw_subjects]

    subjects: list[SubjectRef] = []
    seen: set[str] = set()
    for raw in raw_subjects if isinstance(raw_subjects, list) else []:
        if not isinstance(raw, str):
            continue
        title = raw.strip()
        if title.startswith("[[") and title.endswith("]]"):
            title = title[2:-2].split("|", 1)[0]
        resolved = resolve_subjects(title, catalog)
        for subject in resolved:
            if subject.path not in seen:
                seen.add(subject.path)
                subjects.append(subject)
    return subjects


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


def _format_section(title: str, bullets: list[str], empty_text: str) -> str:
    lines = [f"## {title}"]
    if bullets:
        lines.extend(f"- {bullet}" for bullet in bullets)
    else:
        lines.append(f"- {empty_text}")
    return "\n".join(lines)


def _memory_event_title(signal: SignalEnvelope) -> str:
    timestamp = _parse_datetime(signal.occurred_at or signal.captured_at)
    prefix = timestamp.strftime("%Y-%m-%d %H%M") if timestamp else _today_iso()
    subject_fragment = signal.subjects[0].title if signal.subjects else safe_title_fragment(signal.summary, max_words=5)
    return f"{prefix} {subject_fragment} {short_hash(signal.signal_id)}"


def _memory_claim_title(candidate: ClaimCandidate) -> str:
    subject_fragment = candidate.subjects[0].title if candidate.subjects else safe_title_fragment(candidate.statement, max_words=4)
    type_fragment = candidate.claim_type.title()
    return f"{subject_fragment} {type_fragment} {short_hash(candidate.claim_slot, candidate.statement)}"


def _render_event_body(signal: SignalEnvelope) -> str:
    sections = [
        "## Summary",
        signal.summary,
        "",
        "## Related Subjects",
    ]
    if signal.subjects:
        sections.extend(f"- {subject.wikilink}" for subject in signal.subjects)
    else:
        sections.append("- None linked")
    sections.extend(["", "## Source"])
    sections.append(f"- Type: `{signal.source_type}`")
    sections.append(f"- Reference: `{signal.source_ref}`")
    sections.append(f"- Raw Path: `{signal.raw_path}`")
    if signal.excerpt:
        sections.extend(["", "## Retained Excerpt", f"> {signal.excerpt.replace(chr(10), chr(10) + '> ')}"])
    return "\n".join(sections).rstrip() + "\n"


def _render_claim_body(candidate: ClaimCandidate, related_claims: list[str] | None = None) -> str:
    sections = [
        "## Statement",
        candidate.statement,
        "",
        "## Related Subjects",
    ]
    if candidate.subjects:
        sections.extend(f"- {subject.wikilink}" for subject in candidate.subjects)
    else:
        sections.append("- None linked")
    sections.extend(["", "## Supporting Events"])
    if candidate.supporting_event_wikilinks:
        sections.extend(f"- {link}" for link in candidate.supporting_event_wikilinks)
    else:
        sections.append("- None linked")
    if related_claims:
        sections.extend(["", "## Related Claims"])
        sections.extend(f"- {link}" for link in related_claims)
    if candidate.notes:
        sections.extend(["", "## Notes"])
        sections.extend(f"- {note}" for note in candidate.notes)
    return "\n".join(sections).rstrip() + "\n"


def _existing_claim_records(vault: Path) -> dict[str, list[dict[str, object]]]:
    records: dict[str, list[dict[str, object]]] = defaultdict(list)
    claims_dir = vault / "memory" / "claims"
    if not claims_dir.exists():
        return records

    for md_file in sorted(claims_dir.glob("*.md")):
        frontmatter, body = read_markdown(md_file)
        claim_slot = str(frontmatter.get("claim_slot") or "").strip()
        if not claim_slot:
            continue
        records[claim_slot].append(
            {
                "path": md_file,
                "frontmatter": frontmatter,
                "body": body,
            }
        )
    return records


def _note_paths(vault: Path) -> list[Path]:
    note_paths: list[Path] = []
    for md_file in sorted(vault.rglob("*.md")):
        rel_parts = md_file.relative_to(vault).parts
        if not rel_parts:
            continue
        if rel_parts[0] in SYSTEM_NOTE_ROOTS:
            continue
        note_paths.append(md_file)
    return note_paths


def _build_signal(
    *,
    signal_id: str,
    source_type: str,
    source_ref: str,
    captured_at: str,
    occurred_at: str | None,
    subjects: list[SubjectRef],
    sensitivity: str,
    retention_policy: str,
    raw_path: str,
    summary: str,
    excerpt: str | None,
    full_text: str,
    subject_hints: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> SignalEnvelope:
    excerpt_text = None
    if excerpt:
        excerpt_text = excerpt.strip()
        if len(excerpt_text) > 280:
            excerpt_text = excerpt_text[:277].rstrip() + "..."

    return SignalEnvelope(
        signal_id=signal_id,
        source_type=source_type,
        source_ref=source_ref,
        captured_at=captured_at,
        occurred_at=occurred_at,
        time_range=None,
        subjects=subjects,
        sensitivity=sensitivity,  # type: ignore[arg-type]
        retention_policy=retention_policy,  # type: ignore[arg-type]
        raw_path=raw_path,
        summary=_normalize_line(summary),
        excerpt=excerpt_text,
        full_text=full_text.strip(),
        subject_hints=_merge_unique_strings(subject_hints or []),
        metadata=metadata or {},
    )


def _collect_calendar_signals(vault: Path, catalog: SubjectCatalog, cutoff: datetime | None) -> list[SignalEnvelope]:
    signals: list[SignalEnvelope] = []
    calendar_dir = vault / "data" / "calendar"
    if not calendar_dir.exists():
        return signals

    for md_file in sorted(calendar_dir.glob("*.md")):
        frontmatter, body = _safe_read(md_file)
        day = str(frontmatter.get("date") or md_file.stem)
        if not _within_cutoff(day, cutoff):
            continue
        lines = body.splitlines()
        for index, line in enumerate(lines):
            match = CALENDAR_EVENT_RE.match(line)
            if not match:
                continue
            time_fragment = match.group("time").strip()
            summary = match.group("summary").strip()
            participants: list[str] = []
            if index + 1 < len(lines):
                with_match = CALENDAR_WITH_RE.match(lines[index + 1])
                if with_match:
                    participants = [name.strip() for name in with_match.group("names").split(",") if name.strip()]

            occurred_at = day if "all day" in time_fragment.lower() else f"{day}T{time_fragment}:00"
            raw_path = _relative_path(vault, md_file)
            subjects = resolve_subjects("\n".join([summary, *participants]), catalog)
            summary_text = summary
            if participants:
                summary_text = f"{summary} with {', '.join(participants)}"
            signals.append(
                _build_signal(
                    signal_id=short_hash(raw_path, str(index), summary_text, occurred_at),
                    source_type="calendar",
                    source_ref=f"{raw_path}#L{index + 1}",
                    captured_at=str(frontmatter.get("last_synced") or _iso_from_file_mtime(md_file)),
                    occurred_at=occurred_at,
                    subjects=subjects,
                    sensitivity="personal",
                    retention_policy="summary_only",
                    raw_path=raw_path,
                    summary=summary_text,
                    excerpt=line.strip(),
                    full_text="\n".join(filter(None, [summary, ", ".join(participants)])),
                    subject_hints=[summary, *participants],
                    metadata={"participants": participants, "all_day": "all day" in time_fragment.lower()},
                )
            )
    return signals


def _collect_email_signals(vault: Path, catalog: SubjectCatalog, cutoff: datetime | None) -> list[SignalEnvelope]:
    signals: list[SignalEnvelope] = []
    email_dir = vault / "data" / "email"
    if not email_dir.exists():
        return signals

    for md_file in sorted(email_dir.glob("*.md")):
        frontmatter, body = _safe_read(md_file)
        day = str(frontmatter.get("date") or md_file.stem)
        if not _within_cutoff(day, cutoff):
            continue

        sender = ""
        lines = body.splitlines()
        index = 0
        while index < len(lines):
            sender_match = EMAIL_SENDER_RE.match(lines[index])
            if sender_match:
                sender = re.sub(r"\s+\[known contact:.*\]$", "", sender_match.group("sender")).strip()
                index += 1
                continue

            subject_match = EMAIL_SUBJECT_RE.match(lines[index])
            if not subject_match:
                index += 1
                continue

            subject = re.sub(r"\s+\(unread\)$", "", subject_match.group("subject")).strip()
            meta_lines: list[str] = []
            body_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].startswith("- **"):
                meta_lines.append(lines[index].strip())
                index += 1
            if index < len(lines) and not lines[index].strip():
                index += 1
            while index < len(lines) and not EMAIL_SENDER_RE.match(lines[index]) and not EMAIL_SUBJECT_RE.match(lines[index]):
                body_lines.append(lines[index])
                index += 1

            meta_text = "\n".join(meta_lines)
            body_text = "\n".join(body_lines).strip()
            date_match = re.search(r"- \*\*Date:\*\* (?P<date>.+)", meta_text)
            occurred_at = date_match.group("date").strip() if date_match else day
            raw_path = _relative_path(vault, md_file)
            subjects = resolve_subjects("\n".join(filter(None, [sender, subject, body_text])), catalog)
            summary = f"Email from {sender or 'unknown sender'}: {subject}"
            signals.append(
                _build_signal(
                    signal_id=short_hash(raw_path, sender, subject, occurred_at),
                    source_type="email",
                    source_ref=f"{raw_path}#{subject}",
                    captured_at=str(frontmatter.get("last_synced") or _iso_from_file_mtime(md_file)),
                    occurred_at=occurred_at,
                    subjects=subjects,
                    sensitivity="sensitive",
                    retention_policy="excerpt_ok",
                    raw_path=raw_path,
                    summary=summary,
                    excerpt=body_text or meta_text,
                    full_text="\n".join(filter(None, [summary, meta_text, body_text])),
                    subject_hints=[sender, subject],
                    metadata={"sender": sender, "subject": subject},
                )
            )
    return signals


def _collect_message_signals(vault: Path, catalog: SubjectCatalog, cutoff: datetime | None) -> list[SignalEnvelope]:
    signals: list[SignalEnvelope] = []
    messages_dir = vault / "data" / "messages"
    if not messages_dir.exists():
        return signals

    for md_file in sorted(messages_dir.glob("*.md")):
        frontmatter, body = _safe_read(md_file)
        day = str(frontmatter.get("date") or md_file.stem)
        if not _within_cutoff(day, cutoff):
            continue

        conversation = ""
        lines = body.splitlines()
        for index, line in enumerate(lines):
            section_match = MESSAGE_SECTION_RE.match(line)
            if section_match:
                conversation = section_match.group("title").replace(" (group)", "").strip()
                continue
            message_match = MESSAGE_LINE_RE.match(line)
            if not message_match:
                continue
            sender = message_match.group("sender").strip()
            text = message_match.group("text").strip()
            occurred_at = f"{day}T{message_match.group('time')}:00"
            raw_path = _relative_path(vault, md_file)
            subjects = resolve_subjects("\n".join(filter(None, [conversation, sender, text])), catalog)
            summary = f"Message in {conversation or 'conversation'}: {text}"
            signals.append(
                _build_signal(
                    signal_id=short_hash(raw_path, conversation, sender, occurred_at, text),
                    source_type="message",
                    source_ref=f"{raw_path}#L{index + 1}",
                    captured_at=str(frontmatter.get("last_synced") or _iso_from_file_mtime(md_file)),
                    occurred_at=occurred_at,
                    subjects=subjects,
                    sensitivity="sensitive",
                    retention_policy="excerpt_ok",
                    raw_path=raw_path,
                    summary=summary,
                    excerpt=text,
                    full_text="\n".join(filter(None, [conversation, sender, text])),
                    subject_hints=[conversation, sender],
                    metadata={"conversation": conversation, "sender": sender},
                )
            )
    return signals


def _note_occurrence(frontmatter: dict, note_path: Path) -> str:
    raw_date = frontmatter.get("date")
    if isinstance(raw_date, str) and raw_date.strip():
        return raw_date.strip()
    return _iso_from_file_mtime(note_path)


def _collect_note_signals(vault: Path, catalog: SubjectCatalog, cutoff: datetime | None) -> list[SignalEnvelope]:
    signals: list[SignalEnvelope] = []
    for note_path in _note_paths(vault):
        frontmatter, body = _safe_read(note_path)
        occurred_at = _note_occurrence(frontmatter, note_path)
        if not _within_cutoff(occurred_at, cutoff):
            continue

        rel_path = _relative_path(vault, note_path)
        captured_at = _iso_from_file_mtime(note_path)
        lines = body.splitlines()
        for index, line in enumerate(lines):
            structured_match = STRUCTURED_CLAIM_RE.match(line)
            task_match = TASK_RE.match(line)
            has_explicit_link = "[[" in line
            if not structured_match and not task_match:
                if not (has_explicit_link and (_looks_like_obligation(line) or _looks_relationship_relevant(line))):
                    continue
            if task_match and not structured_match and not has_explicit_link:
                continue

            metadata: dict[str, object] = {"note_title": note_path.stem}
            text = line.strip()
            if structured_match:
                claim_type = structured_match.group("type").lower()
                claim_text = structured_match.group("text").strip()
                slot_hint = structured_match.group("slot")
                metadata["structured_type"] = claim_type
                metadata["structured_slot"] = slot_hint.strip() if slot_hint else None
                text = claim_text
            elif task_match:
                metadata["structured_type"] = "obligation"
                metadata["task_done"] = task_match.group("done").lower() == "x"
                text = task_match.group("text").strip()

            subjects = resolve_subjects("\n".join(filter(None, [note_path.stem, text])), catalog)
            if not subjects and not structured_match:
                continue

            signals.append(
                _build_signal(
                    signal_id=short_hash(rel_path, str(index), text),
                    source_type="note",
                    source_ref=f"{rel_path}#L{index + 1}",
                    captured_at=captured_at,
                    occurred_at=occurred_at,
                    subjects=subjects,
                    sensitivity="personal",
                    retention_policy="excerpt_ok",
                    raw_path=rel_path,
                    summary=text,
                    excerpt=line.strip(),
                    full_text=text,
                    subject_hints=[note_path.stem, text],
                    metadata=metadata,
                )
            )
    return signals


def _collect_task_signals(vault: Path, catalog: SubjectCatalog, cutoff: datetime | None) -> list[SignalEnvelope]:
    signals: list[SignalEnvelope] = []
    tasks_dir = vault / "data" / "tasks"
    if not tasks_dir.exists():
        return signals

    for md_file in sorted(tasks_dir.glob("*.md")):
        frontmatter, body = _safe_read(md_file)
        if str(frontmatter.get("type") or "") != "task-entry":
            continue
        occurred_at = str(frontmatter.get("due_at") or frontmatter.get("due_date") or frontmatter.get("last_synced") or _iso_from_file_mtime(md_file))
        if not _within_cutoff(occurred_at, cutoff):
            continue

        title = str(frontmatter.get("title") or md_file.stem).strip()
        notes = body.strip()
        subjects = _merge_subject_lists(
            _subjects_from_frontmatter(frontmatter, catalog),
            resolve_subjects("\n".join(filter(None, [title, notes])), catalog),
        )
        raw_path = _relative_path(vault, md_file)
        signals.append(
            _build_signal(
                signal_id=short_hash(raw_path, str(frontmatter.get("task_id") or title)),
                source_type="task",
                source_ref=f"{raw_path}#{frontmatter.get('task_id') or title}",
                captured_at=str(frontmatter.get("last_synced") or _iso_from_file_mtime(md_file)),
                occurred_at=occurred_at,
                subjects=subjects,
                sensitivity="personal",
                retention_policy="summary_only",
                raw_path=raw_path,
                summary=title,
                excerpt=notes,
                full_text="\n".join(filter(None, [title, notes])),
                subject_hints=[title],
                metadata={
                    "task_id": frontmatter.get("task_id"),
                    "list_name": frontmatter.get("list_name"),
                    "due_at": frontmatter.get("due_at"),
                    "priority": frontmatter.get("priority"),
                    "flagged": frontmatter.get("flagged"),
                },
            )
        )
    return signals


def _collect_voice_signals(vault: Path, catalog: SubjectCatalog, cutoff: datetime | None) -> list[SignalEnvelope]:
    signals: list[SignalEnvelope] = []
    voice_dir = vault / "data" / "voice"
    if not voice_dir.exists():
        return signals

    for md_file in sorted(voice_dir.glob("*.md")):
        frontmatter, body = _safe_read(md_file)
        if str(frontmatter.get("type") or "") != "voice-note":
            continue
        occurred_at = str(frontmatter.get("recorded_at") or frontmatter.get("last_synced") or _iso_from_file_mtime(md_file))
        if not _within_cutoff(occurred_at, cutoff):
            continue
        title = str(frontmatter.get("title") or md_file.stem).strip()
        summary = str(frontmatter.get("summary") or title).strip()
        base_subjects = _subjects_from_frontmatter(frontmatter, catalog)
        raw_path = _relative_path(vault, md_file)
        created_structured = False
        for index, line in enumerate(body.splitlines()):
            structured_match = STRUCTURED_CLAIM_RE.match(line)
            task_match = TASK_RE.match(line)
            if not structured_match and not task_match:
                continue

            metadata: dict[str, object] = {"title": title}
            text = line.strip()
            if structured_match:
                metadata["structured_type"] = structured_match.group("type").lower()
                slot_hint = structured_match.group("slot")
                metadata["structured_slot"] = slot_hint.strip() if slot_hint else None
                text = structured_match.group("text").strip()
            elif task_match:
                metadata["structured_type"] = "obligation"
                metadata["task_done"] = task_match.group("done").lower() == "x"
                text = task_match.group("text").strip()

            subjects = _merge_subject_lists(
                base_subjects,
                resolve_subjects("\n".join(filter(None, [title, text])), catalog),
            )
            signals.append(
                _build_signal(
                    signal_id=short_hash(raw_path, str(frontmatter.get("voice_note_id") or title), str(index), text),
                    source_type="voice",
                    source_ref=f"{raw_path}#L{index + 1}",
                    captured_at=str(frontmatter.get("last_synced") or _iso_from_file_mtime(md_file)),
                    occurred_at=occurred_at,
                    subjects=subjects,
                    sensitivity="personal",
                    retention_policy="excerpt_ok",
                    raw_path=raw_path,
                    summary=text,
                    excerpt=line.strip(),
                    full_text=text,
                    subject_hints=[title, text],
                    metadata=metadata,
                )
            )
            created_structured = True

        if created_structured:
            continue

        subjects = _merge_subject_lists(
            base_subjects,
            resolve_subjects("\n".join(filter(None, [title, summary, body])), catalog),
        )
        signals.append(
            _build_signal(
                signal_id=short_hash(raw_path, str(frontmatter.get("voice_note_id") or title)),
                source_type="voice",
                source_ref=f"{raw_path}#{frontmatter.get('voice_note_id') or title}",
                captured_at=str(frontmatter.get("last_synced") or _iso_from_file_mtime(md_file)),
                occurred_at=occurred_at,
                subjects=subjects,
                sensitivity="personal",
                retention_policy="excerpt_ok",
                raw_path=raw_path,
                summary=summary,
                excerpt=body,
                full_text="\n".join(filter(None, [title, summary, body])),
                subject_hints=[title, *[str(item) for item in frontmatter.get("subjects", []) if isinstance(item, str)]],
                metadata={"title": title},
            )
        )
    return signals


def _collect_call_signals(vault: Path, catalog: SubjectCatalog, cutoff: datetime | None) -> list[SignalEnvelope]:
    signals: list[SignalEnvelope] = []
    calls_dir = vault / "data" / "calls"
    if not calls_dir.exists():
        return signals

    for md_file in sorted(calls_dir.glob("*.md")):
        frontmatter, body = _safe_read(md_file)
        if str(frontmatter.get("type") or "") != "call-entry":
            continue
        occurred_at = str(frontmatter.get("occurred_at") or frontmatter.get("last_synced") or _iso_from_file_mtime(md_file))
        if not _within_cutoff(occurred_at, cutoff):
            continue
        contact = str(frontmatter.get("contact_name") or frontmatter.get("handle") or md_file.stem).strip()
        direction = str(frontmatter.get("direction") or "unknown").strip()
        summary = str(frontmatter.get("summary") or f"{direction.title()} call with {contact}").strip()
        subjects = _merge_subject_lists(
            _subjects_from_frontmatter(frontmatter, catalog),
            resolve_subjects("\n".join(filter(None, [contact, summary, body])), catalog),
        )
        raw_path = _relative_path(vault, md_file)
        signals.append(
            _build_signal(
                signal_id=short_hash(raw_path, occurred_at, contact, direction),
                source_type="call",
                source_ref=f"{raw_path}#{occurred_at}",
                captured_at=str(frontmatter.get("last_synced") or _iso_from_file_mtime(md_file)),
                occurred_at=occurred_at,
                subjects=subjects,
                sensitivity="sensitive",
                retention_policy="summary_only",
                raw_path=raw_path,
                summary=summary,
                excerpt=body,
                full_text="\n".join(filter(None, [contact, direction, summary, body])),
                subject_hints=[contact, str(frontmatter.get("handle") or "").strip()],
                metadata={
                    "direction": direction,
                    "duration_seconds": frontmatter.get("duration_seconds"),
                    "handle": frontmatter.get("handle"),
                },
            )
        )
    return signals


def _merge_subject_lists(*groups: list[SubjectRef]) -> list[SubjectRef]:
    merged: list[SubjectRef] = []
    seen: set[str] = set()
    for group in groups:
        for subject in group:
            if subject.path not in seen:
                seen.add(subject.path)
                merged.append(subject)
    return merged


def collect_signals(vault_path: str, *, since_days: int = 90) -> list[SignalEnvelope]:
    vault = Path(vault_path).expanduser().resolve()
    cutoff = datetime.now() - timedelta(days=since_days) if since_days > 0 else None
    catalog = load_subject_catalog(vault_path)
    signals = [
        * _collect_calendar_signals(vault, catalog, cutoff),
        * _collect_email_signals(vault, catalog, cutoff),
        * _collect_message_signals(vault, catalog, cutoff),
        * _collect_task_signals(vault, catalog, cutoff),
        * _collect_voice_signals(vault, catalog, cutoff),
        * _collect_call_signals(vault, catalog, cutoff),
        * _collect_note_signals(vault, catalog, cutoff),
    ]
    signals.sort(key=lambda signal: signal.occurred_at or signal.captured_at)
    return signals


def _should_promote(signal: SignalEnvelope) -> bool:
    text = "\n".join(filter(None, [signal.summary, signal.full_text]))
    structured_type = str(signal.metadata.get("structured_type") or "").strip().lower()
    if structured_type:
        if structured_type == "obligation" and signal.metadata.get("task_done"):
            return False
        return True
    if signal.source_type == "task":
        return True
    if signal.source_type == "voice":
        return bool(signal.subjects) or _looks_like_obligation(text) or _looks_relationship_relevant(text)
    if signal.source_type == "call":
        return bool(signal.subjects) or _looks_like_request(text)
    if _looks_like_obligation(text):
        return True
    if signal.subjects and signal.source_type in {"calendar", "email", "message"}:
        return True
    if signal.subjects and _looks_relationship_relevant(text):
        return True
    return False


def _link_known_subjects(text: str, subjects: list[SubjectRef]) -> str:
    replacements = {subject.title: subject.wikilink for subject in subjects}
    return replace_titles_with_wikilinks(text, replacements)


def _structured_slot(candidate_type: str, slot_hint: str | None, subjects: list[SubjectRef], statement: str) -> str:
    if slot_hint:
        subject_prefix = "::".join(normalize_lookup_key(subject.title) for subject in subjects) or "general"
        return f"{candidate_type}::{subject_prefix}::{normalize_lookup_key(slot_hint)}"
    subject_prefix = "::".join(normalize_lookup_key(subject.title) for subject in subjects) or "general"
    statement_key = normalize_lookup_key(statement)[:120] or short_hash(statement)
    return f"{candidate_type}::{subject_prefix}::{statement_key}"


def _obligation_statement(signal: SignalEnvelope) -> str:
    primary = signal.subjects[0].wikilink if signal.subjects else None
    cleaned = _strip_markdown_artifacts(signal.summary)
    if signal.source_type == "task":
        list_name = str(signal.metadata.get("list_name") or "").strip()
        if primary:
            return f"{primary}: {cleaned}."
        if list_name:
            return f"[{list_name}] {cleaned}."
        return _sentence(cleaned)
    if signal.source_type == "note":
        return _sentence(_link_known_subjects(cleaned, signal.subjects))
    if signal.source_type in {"message", "email"} and primary:
        return f"Follow up with {primary} about {_sentence(cleaned)[:-1].lower()}."
    if signal.source_type == "call" and primary:
        return f"Follow up with {primary} after the call regarding {_sentence(cleaned)[:-1].lower()}."
    if signal.source_type == "calendar" and primary:
        return f"Prepare for or follow up on {_link_known_subjects(cleaned, signal.subjects)}."
    return _sentence(_link_known_subjects(cleaned, signal.subjects))


def _derive_claim_candidates(signal: SignalEnvelope, event_wikilink: str) -> list[ClaimCandidate]:
    candidates: list[ClaimCandidate] = []
    structured_type = str(signal.metadata.get("structured_type") or "").strip().lower()
    base_text = _strip_markdown_artifacts(signal.summary)
    linked_text = _link_known_subjects(base_text, signal.subjects)
    status = "provisional" if _looks_provisional(signal.full_text or signal.summary) else "active"

    if structured_type in {"fact", "preference", "pattern", "idea"}:
        statement = _sentence(linked_text)
        if statement:
            candidates.append(
                ClaimCandidate(
                    claim_type=structured_type,  # type: ignore[arg-type]
                    claim_slot=_structured_slot(
                        structured_type,
                        signal.metadata.get("structured_slot"),
                        signal.subjects,
                        statement,
                    ),
                    statement=statement,
                    subjects=signal.subjects,
                    supporting_event_wikilinks=[event_wikilink],
                    status=status,  # type: ignore[arg-type]
                    confidence=0.65 if status == "provisional" else 0.85,
                    valid_from=signal.occurred_at or signal.captured_at,
                )
            )
        return candidates

    if (
        structured_type == "obligation"
        or signal.source_type == "task"
        or _looks_like_obligation(signal.summary)
        or any(phrase in (signal.full_text or signal.summary).lower() for phrase in FOLLOW_UP_PHRASES)
        or (
        signal.source_type in {"message", "email"}
        and signal.subjects
        and _looks_like_request(signal.full_text or signal.summary)
        )
    ):
        statement = _obligation_statement(signal)
        if statement:
            candidates.append(
                ClaimCandidate(
                    claim_type="obligation",
                    claim_slot=_structured_slot(
                        "obligation",
                        signal.metadata.get("structured_slot"),
                        signal.subjects,
                        statement,
                    ),
                    statement=statement,
                    subjects=signal.subjects,
                    supporting_event_wikilinks=[event_wikilink],
                    status=status,  # type: ignore[arg-type]
                    confidence=0.6 if status == "provisional" else 0.82,
                    valid_from=signal.occurred_at or signal.captured_at,
                )
            )
    return candidates


def _merge_claim_candidates(candidates: list[ClaimCandidate]) -> list[ClaimCandidate]:
    merged: dict[tuple[str, str], ClaimCandidate] = {}
    for candidate in candidates:
        key = (candidate.claim_slot, candidate.statement)
        if key not in merged:
            merged[key] = candidate
            continue
        existing = merged[key]
        existing.subjects = list({subject.path: subject for subject in [*existing.subjects, *candidate.subjects]}.values())
        existing.supporting_event_wikilinks = _merge_unique_strings(
            existing.supporting_event_wikilinks,
            candidate.supporting_event_wikilinks,
        )
        existing.notes = _merge_unique_strings(existing.notes, candidate.notes)
        existing.confidence = max(existing.confidence, candidate.confidence)
        if existing.status != "active":
            existing.status = candidate.status
        existing.valid_from = existing.valid_from or candidate.valid_from
    return list(merged.values())


def _derive_pattern_claims(promoted_signals: list[tuple[SignalEnvelope, str]]) -> list[ClaimCandidate]:
    grouped: dict[str, list[tuple[SignalEnvelope, str]]] = defaultdict(list)
    for signal, event_link in promoted_signals:
        if not _looks_like_deferral("\n".join(filter(None, [signal.summary, signal.full_text]))):
            continue
        if signal.subjects:
            subject = signal.subjects[0]
            grouped[f"{subject.path}::repeated-deferral"].append((signal, event_link))
        else:
            grouped[f"{safe_title_fragment(signal.summary)}::repeated-deferral"].append((signal, event_link))

    candidates: list[ClaimCandidate] = []
    for key, items in grouped.items():
        if len(items) < 3:
            continue
        signal, _ = items[-1]
        subject = signal.subjects[0] if signal.subjects else None
        if subject and subject.kind == "commitment":
            statement = f"Progress on {subject.wikilink} has been deferred repeatedly across recent signals."
        elif subject:
            statement = f"Follow-through related to {subject.wikilink} has been deferred repeatedly across recent signals."
        else:
            statement = "A recurring area of follow-through has been deferred repeatedly across recent signals."
        candidates.append(
            ClaimCandidate(
                claim_type="pattern",
                claim_slot=f"pattern::{key}",
                statement=statement,
                subjects=signal.subjects[:1],
                supporting_event_wikilinks=[event_link for _, event_link in items[-5:]],
                status="active",
                confidence=0.78,
                valid_from=items[0][0].occurred_at or items[0][0].captured_at,
                notes=[f"Derived from {len(items)} recent deferral signals."],
            )
        )
    return candidates


def _ensure_event_file(vault: Path, signal: SignalEnvelope) -> tuple[str, bool]:
    title = _memory_event_title(signal)
    event_path = vault / "memory" / "events" / f"{title}.md"
    event_wikilink = as_wikilink(title)
    if event_path.exists():
        return event_wikilink, False

    frontmatter = {
        "type": "memory-event",
        "event_id": short_hash(signal.signal_id, title, length=12),
        "signal_id": signal.signal_id,
        "source_type": signal.source_type,
        "source_ref": signal.source_ref,
        "captured_at": signal.captured_at,
        "occurred_at": signal.occurred_at or "",
        "sensitivity": signal.sensitivity,
        "retention_policy": signal.retention_policy,
        "raw_path": signal.raw_path,
        "subjects": _subject_wikilinks(signal.subjects),
        "summary": signal.summary,
        "tags": ["memory", "event", signal.source_type],
        "last_updated": _today_iso(),
    }
    write_markdown(event_path, frontmatter, _render_event_body(signal))
    return event_wikilink, True


def _update_existing_claim(path: Path, frontmatter: dict, body: str, candidate: ClaimCandidate) -> bool:
    new_subjects = _merge_unique_strings([str(item) for item in frontmatter.get("subjects", []) if isinstance(item, str)], _subject_wikilinks(candidate.subjects))
    new_events = _merge_unique_strings(
        [str(item) for item in frontmatter.get("supporting_events", []) if isinstance(item, str)],
        candidate.supporting_event_wikilinks,
    )
    changed = False

    if new_subjects != frontmatter.get("subjects", []):
        frontmatter["subjects"] = new_subjects
        changed = True
    if new_events != frontmatter.get("supporting_events", []):
        frontmatter["supporting_events"] = new_events
        changed = True
    if candidate.confidence > float(frontmatter.get("confidence", 0)):
        frontmatter["confidence"] = round(candidate.confidence, 2)
        changed = True
    if frontmatter.get("status") != candidate.status:
        frontmatter["status"] = candidate.status
        changed = True
    if not frontmatter.get("valid_from") and candidate.valid_from:
        frontmatter["valid_from"] = candidate.valid_from
        changed = True
    if changed:
        frontmatter["last_updated"] = _today_iso()
        related_claims = [str(item) for item in frontmatter.get("related_claims", []) if isinstance(item, str)]
        write_markdown(path, frontmatter, _render_claim_body(candidate, related_claims))
    return changed


def _supersede_claim(path: Path, frontmatter: dict, body: str, new_claim_link: str) -> bool:
    existing_related = [str(item) for item in frontmatter.get("related_claims", []) if isinstance(item, str)]
    related_claims = _merge_unique_strings(existing_related, [new_claim_link])
    if frontmatter.get("status") == "superseded" and frontmatter.get("valid_to"):
        return False
    frontmatter["status"] = "superseded"
    frontmatter["valid_to"] = _today_iso()
    frontmatter["related_claims"] = related_claims
    frontmatter["last_updated"] = _today_iso()
    write_markdown(path, frontmatter, body)
    return True


def _write_new_claim(vault: Path, candidate: ClaimCandidate, related_claims: list[str] | None = None) -> str:
    title = _memory_claim_title(candidate)
    claim_path = vault / "memory" / "claims" / f"{title}.md"
    frontmatter = {
        "type": "memory-claim",
        "claim_id": short_hash(candidate.claim_slot, candidate.statement, length=12),
        "claim_slot": candidate.claim_slot,
        "claim_type": candidate.claim_type,
        "status": candidate.status,
        "confidence": round(candidate.confidence, 2),
        "valid_from": candidate.valid_from or "",
        "valid_to": candidate.valid_to or "",
        "subjects": _subject_wikilinks(candidate.subjects),
        "supporting_events": candidate.supporting_event_wikilinks,
        "related_claims": related_claims or [],
        "summary": candidate.statement,
        "tags": ["memory", "claim", candidate.claim_type],
        "last_updated": _today_iso(),
    }
    write_markdown(claim_path, frontmatter, _render_claim_body(candidate, related_claims))
    return as_wikilink(title)


def _upsert_claims(vault: Path, candidates: list[ClaimCandidate], report: CompileReport) -> None:
    existing = _existing_claim_records(vault)
    for candidate in candidates:
        records = existing.get(candidate.claim_slot, [])
        exact_match = None
        active_records: list[dict[str, object]] = []
        for record in records:
            frontmatter = record["frontmatter"]
            if frontmatter.get("status") in {"active", "provisional"}:
                active_records.append(record)
            if str(frontmatter.get("summary") or "").strip() == candidate.statement:
                exact_match = record

        if exact_match is not None:
            if _update_existing_claim(
                exact_match["path"],  # type: ignore[arg-type]
                exact_match["frontmatter"],  # type: ignore[arg-type]
                exact_match["body"],  # type: ignore[arg-type]
                candidate,
            ):
                report.claims_updated += 1
            continue

        provisional_title = _memory_claim_title(candidate)
        new_claim_link = as_wikilink(provisional_title)
        related_claims = [as_wikilink(Path(record["path"]).stem) for record in active_records]  # type: ignore[arg-type]

        for record in active_records:
            if _supersede_claim(
                record["path"],  # type: ignore[arg-type]
                record["frontmatter"],  # type: ignore[arg-type]
                record["body"],  # type: ignore[arg-type]
                new_claim_link,
            ):
                report.claims_superseded += 1

        _write_new_claim(vault, candidate, related_claims=related_claims)
        report.claims_created += 1
        existing = _existing_claim_records(vault)


def _load_memory_documents(vault: Path, subdir: str) -> list[dict[str, object]]:
    directory = vault / "memory" / subdir
    documents: list[dict[str, object]] = []
    if not directory.exists():
        return documents
    for md_file in sorted(directory.glob("*.md")):
        frontmatter, body = read_markdown(md_file)
        documents.append({"path": md_file, "frontmatter": frontmatter, "body": body})
    return documents


def _project_subject_file(subject: SubjectRef, claims: list[dict[str, object]], events: list[dict[str, object]]) -> None:
    subject_path = Path(subject.path)
    frontmatter, body = read_markdown(subject_path)
    subject_link = subject.wikilink

    subject_claims = [
        claim
        for claim in claims
        if subject_link in [str(item) for item in claim["frontmatter"].get("subjects", []) if isinstance(item, str)]
        and claim["frontmatter"].get("status") in {"active", "provisional"}
    ]
    subject_events = [
        event
        for event in events
        if subject_link in [str(item) for item in event["frontmatter"].get("subjects", []) if isinstance(item, str)]
    ]

    subject_claims.sort(key=lambda item: str(item["frontmatter"].get("last_updated") or ""), reverse=True)
    subject_events.sort(key=lambda item: str(item["frontmatter"].get("occurred_at") or ""), reverse=True)

    summary_bullets = [
        f"{claim['frontmatter'].get('summary')} ({as_wikilink(Path(claim['path']).stem)})"
        for claim in subject_claims
        if claim["frontmatter"].get("claim_type") in {"fact", "preference", "idea"}
    ][:5]
    obligation_bullets = [
        f"{claim['frontmatter'].get('summary')} ({as_wikilink(Path(claim['path']).stem)})"
        for claim in subject_claims
        if claim["frontmatter"].get("claim_type") == "obligation"
    ][:6]
    linked_memory_bullets = [
        f"{as_wikilink(Path(event['path']).stem)} — {event['frontmatter'].get('summary')}"
        for event in subject_events[:6]
    ]
    evidence_bullets = [
        f"{event['frontmatter'].get('occurred_at') or event['frontmatter'].get('captured_at')}: {as_wikilink(Path(event['path']).stem)}"
        for event in subject_events[:6]
    ]

    generated = "\n\n".join(
        [
            _format_section("Steward Summary", summary_bullets, "No compiled summary yet."),
            _format_section("Open Obligations", obligation_bullets, "No active obligations."),
            _format_section("Linked Memory", linked_memory_bullets, "No linked memory yet."),
            _format_section("Evidence Trail", evidence_bullets, "No evidence trail yet."),
        ]
    )

    block_id = f"STEWARD_MEMORY_{subject.kind.upper()}"
    updated_body = replace_generated_block(body, block_id, generated)
    frontmatter["last_updated"] = _today_iso()
    write_markdown(subject_path, frontmatter, updated_body)


def _project_current_file(vault: Path, claims: list[dict[str, object]], events: list[dict[str, object]]) -> None:
    current_path = vault / "profile" / "current.md"
    if not current_path.exists():
        return
    frontmatter, body = read_markdown(current_path)
    active_claims = [
        claim
        for claim in claims
        if claim["frontmatter"].get("status") in {"active", "provisional"}
    ]
    active_obligations = [
        claim
        for claim in active_claims
        if claim["frontmatter"].get("claim_type") == "obligation"
    ]
    recent_events = sorted(
        events,
        key=lambda item: str(item["frontmatter"].get("occurred_at") or ""),
        reverse=True,
    )[:8]

    generated = "\n\n".join(
        [
            _format_section(
                "Steward Digest",
                [
                    f"{claim['frontmatter'].get('summary')} ({as_wikilink(Path(claim['path']).stem)})"
                    for claim in active_claims
                    if claim["frontmatter"].get("claim_type") in {"fact", "preference", "idea"}
                ][:6],
                "No compiled digest yet.",
            ),
            _format_section(
                "Active Obligations",
                [
                    f"{claim['frontmatter'].get('summary')} ({as_wikilink(Path(claim['path']).stem)})"
                    for claim in active_obligations[:8]
                ],
                "No active obligations.",
            ),
            _format_section(
                "Recent High-Signal Events",
                [
                    f"{as_wikilink(Path(event['path']).stem)} — {event['frontmatter'].get('summary')}"
                    for event in recent_events
                ],
                "No recent high-signal events.",
            ),
        ]
    )
    updated_body = replace_generated_block(body, "STEWARD_MEMORY_CURRENT", generated)
    frontmatter["last_updated"] = _today_iso()
    write_markdown(current_path, frontmatter, updated_body)


def _project_patterns_file(vault: Path, claims: list[dict[str, object]]) -> None:
    patterns_path = vault / "profile" / "patterns.md"
    if not patterns_path.exists():
        return
    frontmatter, body = read_markdown(patterns_path)
    pattern_claims = [
        claim
        for claim in claims
        if claim["frontmatter"].get("claim_type") == "pattern"
        and claim["frontmatter"].get("status") in {"active", "provisional"}
    ]
    pattern_claims.sort(key=lambda item: str(item["frontmatter"].get("last_updated") or ""), reverse=True)
    generated = "\n\n".join(
        [
            _format_section(
                "Active Pattern Claims",
                [
                    f"{claim['frontmatter'].get('summary')} ({as_wikilink(Path(claim['path']).stem)})"
                    for claim in pattern_claims[:8]
                ],
                "No active pattern claims.",
            ),
            _format_section(
                "Pattern Evidence",
                [
                    f"{', '.join(str(item) for item in claim['frontmatter'].get('supporting_events', []))}"
                    for claim in pattern_claims[:6]
                ],
                "No linked pattern evidence.",
            ),
        ]
    )
    updated_body = replace_generated_block(body, "STEWARD_MEMORY_PATTERNS", generated)
    frontmatter["last_updated"] = _today_iso()
    write_markdown(patterns_path, frontmatter, updated_body)


def _project_profile_surfaces(vault_path: str) -> None:
    vault = Path(vault_path).expanduser().resolve()
    catalog = load_subject_catalog(vault_path)
    claims = _load_memory_documents(vault, "claims")
    events = _load_memory_documents(vault, "events")
    for subject in catalog.by_title.values():
        subject_path = vault / subject.path
        if subject_path.exists():
            _project_subject_file(
                SubjectRef(subject.kind, subject.title, str(subject_path), subject.wikilink),
                claims,
                events,
            )
    _project_current_file(vault, claims, events)
    _project_patterns_file(vault, claims)


def compile_memory(vault_path: str, *, since_days: int = 90) -> CompileReport:
    vault = Path(vault_path).expanduser().resolve()
    report = CompileReport()
    signals = collect_signals(vault_path, since_days=since_days)
    report.signals_seen = len(signals)

    promoted_signals: list[tuple[SignalEnvelope, str]] = []
    claim_candidates: list[ClaimCandidate] = []

    for signal in signals:
        if not _should_promote(signal):
            continue
        report.promoted_signals += 1
        event_wikilink, created = _ensure_event_file(vault, signal)
        if created:
            report.events_created += 1
        promoted_signals.append((signal, event_wikilink))
        claim_candidates.extend(_derive_claim_candidates(signal, event_wikilink))

    claim_candidates.extend(_derive_pattern_claims(promoted_signals))
    merged_candidates = _merge_claim_candidates(claim_candidates)
    _upsert_claims(vault, merged_candidates, report)
    _project_profile_surfaces(vault_path)
    build_memory_index(vault_path)
    report.index_rebuilt = True
    health_report = build_memory_health_report(vault_path, signals=signals, since_days=since_days)
    write_memory_health_report(vault_path, health_report)
    report.health_report_written = True
    summary = health_report["summary"]
    report.unresolved_signals = int(summary.get("unresolved_signals", 0))
    report.unlinked_contacts = int(summary.get("unlinked_contacts", 0))
    report.ambiguous_aliases = int(summary.get("ambiguous_aliases", 0))
    report.orphan_events = int(summary.get("orphan_events", 0))
    report.orphan_claims = int(summary.get("orphan_claims", 0))
    report.stale_active_claims = int(summary.get("stale_active_claims", 0))
    report.conflicting_active_claim_slots = int(summary.get("conflicting_active_claim_slots", 0))

    compile_report_path = vault / "memory" / "compile-report.json"
    compile_report_path.parent.mkdir(parents=True, exist_ok=True)
    compile_report_path.write_text(
        json.dumps(
            {
                "generated_at": _now_iso(),
                "signals_seen": report.signals_seen,
                "promoted_signals": report.promoted_signals,
                "events_created": report.events_created,
                "claims_created": report.claims_created,
                "claims_updated": report.claims_updated,
                "claims_superseded": report.claims_superseded,
                "health_report_written": report.health_report_written,
                "unresolved_signals": report.unresolved_signals,
                "unlinked_contacts": report.unlinked_contacts,
                "ambiguous_aliases": report.ambiguous_aliases,
                "orphan_events": report.orphan_events,
                "orphan_claims": report.orphan_claims,
                "stale_active_claims": report.stale_active_claims,
                "conflicting_active_claim_slots": report.conflicting_active_claim_slots,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile vault signals into steward memory events and claims.")
    parser.add_argument("--vault", required=True, help="Path to the target vault")
    parser.add_argument("--since-days", type=int, default=90, help="Only scan signals from the last N days")
    args = parser.parse_args()

    report = compile_memory(args.vault, since_days=args.since_days)
    print(
        json.dumps(
            {
                "signals_seen": report.signals_seen,
                "promoted_signals": report.promoted_signals,
                "events_created": report.events_created,
                "claims_created": report.claims_created,
                "claims_updated": report.claims_updated,
                "claims_superseded": report.claims_superseded,
                "index_rebuilt": report.index_rebuilt,
                "health_report_written": report.health_report_written,
                "unresolved_signals": report.unresolved_signals,
                "unlinked_contacts": report.unlinked_contacts,
                "ambiguous_aliases": report.ambiguous_aliases,
                "orphan_events": report.orphan_events,
                "orphan_claims": report.orphan_claims,
                "stale_active_claims": report.stale_active_claims,
                "conflicting_active_claim_slots": report.conflicting_active_claim_slots,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
