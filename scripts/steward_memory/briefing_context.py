from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path

from .markdown import read_markdown


MAX_PROFILE_CHARS = 2200
MAX_PROFILE_LINES = 60
MAX_DATA_CHARS = 1200
MAX_DATA_LINES = 24


@dataclass(frozen=True)
class DataSourceSpec:
    folder: str
    label: str
    limit: int
    since_days: int | None = None


DAILY_SOURCES = [
    DataSourceSpec("calendar", "Calendar", 2, since_days=7),
    DataSourceSpec("weather", "Weather", 2, since_days=7),
    DataSourceSpec("finance", "Finance", 1, since_days=14),
    DataSourceSpec("email", "Email", 3, since_days=2),
    DataSourceSpec("messages", "Messages", 3, since_days=2),
    DataSourceSpec("tasks", "Tasks", 4, since_days=14),
    DataSourceSpec("calls", "Calls", 4, since_days=14),
    DataSourceSpec("voice", "Voice", 4, since_days=14),
]

EVENING_SOURCES = [
    DataSourceSpec("calendar", "Calendar", 2, since_days=2),
    DataSourceSpec("weather", "Weather", 1, since_days=2),
    DataSourceSpec("finance", "Finance", 1, since_days=14),
    DataSourceSpec("email", "Email", 4, since_days=2),
    DataSourceSpec("messages", "Messages", 4, since_days=2),
    DataSourceSpec("tasks", "Tasks", 4, since_days=14),
    DataSourceSpec("calls", "Calls", 4, since_days=14),
    DataSourceSpec("voice", "Voice", 4, since_days=14),
]

WEEKLY_SOURCES = [
    DataSourceSpec("calendar", "Calendar", 3, since_days=14),
    DataSourceSpec("finance", "Finance", 2, since_days=30),
    DataSourceSpec("email", "Email", 4, since_days=7),
    DataSourceSpec("messages", "Messages", 4, since_days=7),
    DataSourceSpec("tasks", "Tasks", 5, since_days=14),
    DataSourceSpec("calls", "Calls", 4, since_days=14),
    DataSourceSpec("voice", "Voice", 4, since_days=14),
]

MONTHLY_SOURCES = [
    DataSourceSpec("calendar", "Calendar", 4, since_days=45),
    DataSourceSpec("finance", "Finance", 3, since_days=45),
    DataSourceSpec("email", "Email", 4, since_days=14),
    DataSourceSpec("messages", "Messages", 4, since_days=14),
    DataSourceSpec("tasks", "Tasks", 5, since_days=30),
    DataSourceSpec("calls", "Calls", 4, since_days=30),
    DataSourceSpec("voice", "Voice", 4, since_days=30),
]

AMBIENT_SOURCES = [
    DataSourceSpec("email", "Email", 2, since_days=2),
    DataSourceSpec("messages", "Messages", 2, since_days=2),
    DataSourceSpec("tasks", "Tasks", 3, since_days=14),
]


def _safe_excerpt(body: str, *, max_chars: int, max_lines: int) -> str:
    kept_lines: list[str] = []
    current_chars = 0
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        prospective = current_chars + len(line) + 1
        if kept_lines and prospective > max_chars:
            break
        kept_lines.append(line)
        current_chars = prospective
        if len(kept_lines) >= max_lines:
            break

    excerpt = "\n".join(kept_lines).strip()
    if len(excerpt) > max_chars:
        excerpt = excerpt[: max_chars - 3].rstrip() + "..."
    return excerpt


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def _date_from_text(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    for parser in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text, parser).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _next_occurrence(event_date: date, today: date) -> date:
    occurrence = event_date.replace(year=today.year)
    if occurrence < today:
        occurrence = occurrence.replace(year=today.year + 1)
    return occurrence


def _recent_markdown_files(vault: Path, folder: str, *, limit: int, since_days: int | None) -> list[Path]:
    root = vault / "data" / folder
    if not root.exists():
        return []

    cutoff = None
    if since_days is not None:
        cutoff = datetime.now() - timedelta(days=since_days)

    files: list[Path] = []
    for path in root.rglob("*.md"):
        if cutoff is not None:
            modified = datetime.fromtimestamp(path.stat().st_mtime)
            if modified < cutoff:
                continue
        files.append(path)

    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[:limit]


def _render_doc_section(vault: Path, rel_path: str, *, max_chars: int, max_lines: int) -> str:
    frontmatter, body = read_markdown(vault / rel_path)
    excerpt = _safe_excerpt(body, max_chars=max_chars, max_lines=max_lines)
    lines = [f"### {rel_path}"]
    summary = str(frontmatter.get("summary") or "").strip()
    if summary:
        lines.append(f"- Summary: {summary}")
    for key in ("date", "last_synced", "status", "priority", "deadline", "source_type"):
        value = frontmatter.get(key)
        if value not in (None, "", []):
            lines.append(f"- {key}: {value}")
    if excerpt:
        lines.append("```md")
        lines.append(excerpt)
        lines.append("```")
    else:
        lines.append("- No body content.")
    return "\n".join(lines)


def _render_profile_sections(vault: Path) -> list[str]:
    sections: list[str] = []
    for rel_path, heading in (
        ("profile/index.md", "## Profile Index"),
        ("profile/current.md", "## Current State"),
        ("profile/patterns.md", "## Pattern Snapshot"),
    ):
        target = vault / rel_path
        if not target.exists():
            continue
        sections.append(heading)
        sections.append(_render_doc_section(vault, rel_path, max_chars=MAX_PROFILE_CHARS, max_lines=MAX_PROFILE_LINES))
    return sections


def _render_commitments(vault: Path) -> str:
    commitment_dir = vault / "profile" / "commitments"
    if not commitment_dir.exists():
        return "## Priority Commitments\n- No commitment files found."

    rows: list[tuple[int, str, str]] = []
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    status_rank = {"blocked": 0, "in-progress": 1, "ongoing": 2, "not-started": 3, "completed": 4, "abandoned": 5}
    for path in commitment_dir.glob("*.md"):
        frontmatter, _ = read_markdown(path)
        status = str(frontmatter.get("status") or "")
        priority = str(frontmatter.get("priority") or "")
        deadline = str(frontmatter.get("deadline") or "none")
        if status not in {"blocked", "in-progress", "ongoing", "not-started"} and priority != "high":
            continue
        score = priority_rank.get(priority, 9) * 10 + status_rank.get(status, 9)
        title = str(frontmatter.get("title") or path.stem)
        line = f"- [[{path.stem}]] — status: {status or 'unknown'}; priority: {priority or 'unknown'}; deadline: {deadline}"
        rows.append((score, title.lower(), line))

    rows.sort(key=lambda item: (item[0], item[1]))
    if not rows:
        return "## Priority Commitments\n- No active or high-priority commitments."
    return "## Priority Commitments\n" + "\n".join(item[2] for item in rows[:10])


def _render_upcoming_dates(vault: Path, *, horizon_days: int = 7) -> str:
    people_dir = vault / "profile" / "people"
    if not people_dir.exists():
        return "## Upcoming Birthdays And Anniversaries\n- No people files found."

    today = date.today()
    upcoming: list[tuple[date, str]] = []
    for path in people_dir.glob("*.md"):
        frontmatter, _ = read_markdown(path)
        for field, label in (("birthday", "Birthday"), ("anniversary", "Anniversary")):
            raw_value = frontmatter.get(field)
            parsed = _date_from_text(raw_value)
            if not parsed:
                continue
            occurrence = _next_occurrence(parsed, today)
            delta = (occurrence - today).days
            if 0 <= delta <= horizon_days:
                upcoming.append(
                    (
                        occurrence,
                        f"- [[{path.stem}]] — {label.lower()} in {delta} day{'s' if delta != 1 else ''} ({occurrence.isoformat()})",
                    )
                )

    upcoming.sort(key=lambda item: item[0])
    if not upcoming:
        return "## Upcoming Birthdays And Anniversaries\n- No birthdays or anniversaries in the next 7 days."
    return "## Upcoming Birthdays And Anniversaries\n" + "\n".join(item[1] for item in upcoming)


def _render_compile_snapshot(vault: Path) -> str:
    compile_report = vault / "memory" / "compile-report.json"
    if not compile_report.exists():
        return "## Memory Compile Snapshot\n- No compile report found."

    try:
        payload = json.loads(compile_report.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "## Memory Compile Snapshot\n- Compile report unreadable."

    lines = [
        "## Memory Compile Snapshot",
        f"- Signals seen: {payload.get('signals_seen', 0)}",
        f"- Promoted signals: {payload.get('promoted_signals', 0)}",
        f"- Active contact gaps: {payload.get('unlinked_contacts', 0)}",
    ]
    return "\n".join(lines)


def _render_data_sources(vault: Path, sources: list[DataSourceSpec]) -> list[str]:
    sections = ["## Recent Source Files"]
    for spec in sources:
        sections.append(f"### {spec.label}")
        files = _recent_markdown_files(vault, spec.folder, limit=spec.limit, since_days=spec.since_days)
        if not files:
            sections.append(f"- No recent {spec.folder} files.")
            continue
        for path in files:
            sections.append(
                _render_doc_section(
                    vault,
                    _relative(path, vault),
                    max_chars=MAX_DATA_CHARS,
                    max_lines=MAX_DATA_LINES,
                )
            )
    return sections


def _render_recent_notes(vault: Path, relative_root: str, heading: str, *, limit: int, since_days: int | None = None) -> list[str]:
    root = vault / relative_root
    sections = [heading]
    if not root.exists():
        sections.append(f"- No files found under {relative_root}.")
        return sections

    cutoff = None
    if since_days is not None:
        cutoff = datetime.now() - timedelta(days=since_days)

    files: list[Path] = []
    for path in root.rglob("*.md"):
        if cutoff is not None and datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
            continue
        files.append(path)

    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    if not files:
        sections.append(f"- No recent files under {relative_root}.")
        return sections

    for path in files[:limit]:
        sections.append(_render_doc_section(vault, _relative(path, vault), max_chars=MAX_DATA_CHARS, max_lines=MAX_DATA_LINES))
    return sections


def build_briefing_context(vault_path: str, *, workflow: str, note_relative_path: str | None = None) -> str:
    vault = Path(vault_path).expanduser().resolve()
    lines = [
        f"# {workflow.title()} Briefing Context",
        f"- Date: {date.today().isoformat()}",
    ]
    if note_relative_path:
        lines.append(f"- Target note: {note_relative_path}")

    lines.append(_render_compile_snapshot(vault))
    lines.extend(_render_profile_sections(vault))
    lines.append(_render_commitments(vault))
    lines.append(_render_upcoming_dates(vault))

    if workflow == "evening":
        if note_relative_path and (vault / note_relative_path).exists():
            lines.append("## Today's Daily Note")
            lines.append(_render_doc_section(vault, note_relative_path, max_chars=MAX_PROFILE_CHARS, max_lines=MAX_PROFILE_LINES))
        lines.extend(_render_data_sources(vault, EVENING_SOURCES))
    elif workflow == "daily":
        lines.extend(_render_data_sources(vault, DAILY_SOURCES))
    elif workflow == "weekly":
        lines.extend(_render_recent_notes(vault, "diary", "## Recent Diary Entries", limit=3, since_days=10))
        lines.extend(_render_recent_notes(vault, "reviews", "## Recent Review Notes", limit=4, since_days=21))
        lines.extend(_render_data_sources(vault, WEEKLY_SOURCES))
    elif workflow == "monthly":
        lines.extend(_render_recent_notes(vault, "diary", "## Recent Diary Entries", limit=4, since_days=35))
        lines.extend(_render_recent_notes(vault, "reviews", "## Recent Review Notes", limit=6, since_days=45))
        lines.extend(_render_data_sources(vault, MONTHLY_SOURCES))
    else:
        if note_relative_path and (vault / note_relative_path).exists():
            lines.append("## Changed File")
            lines.append(_render_doc_section(vault, note_relative_path, max_chars=MAX_PROFILE_CHARS, max_lines=MAX_PROFILE_LINES))
        lines.extend(_render_data_sources(vault, AMBIENT_SOURCES))

    return "\n\n".join(lines).strip() + "\n"
