from __future__ import annotations

from pathlib import Path

from .catalog import SubjectCatalog, get_subject_by_title, load_subject_catalog
from .index import search_memory_index
from .markdown import read_markdown
from .models import RetrievalDocument, RetrievalResult
from .wikilinks import extract_wikilinks, path_to_wikilink


def _load_document(vault: Path, rel_path: str) -> RetrievalDocument:
    frontmatter, body = read_markdown(vault / rel_path)
    return RetrievalDocument(
        path=rel_path,
        doc_type=str(frontmatter.get("type") or "markdown"),
        title=Path(rel_path).stem,
        summary=next((line.strip() for line in body.splitlines() if line.strip()), ""),
        subjects=[str(item) for item in frontmatter.get("subjects", []) if isinstance(item, str)],
        wikilinks=extract_wikilinks(body),
        occurred_at=frontmatter.get("occurred_at") or frontmatter.get("date"),
        claim_type=frontmatter.get("claim_type"),
        status=frontmatter.get("status"),
        source_type=frontmatter.get("source_type"),
        sensitivity=frontmatter.get("sensitivity"),
    )


def _append_if_present(documents: list[RetrievalDocument], seen: set[str], vault: Path, rel_path: str) -> None:
    if rel_path in seen:
        return
    target = vault / rel_path
    if not target.exists():
        return
    seen.add(rel_path)
    documents.append(_load_document(vault, rel_path))


def _subject_profile_path(subject) -> str:
    return subject.path


def retrieve_context(
    vault_path: str,
    workflow: str,
    *,
    subject_titles: list[str] | None = None,
    since_days: int = 30,
) -> RetrievalResult:
    vault = Path(vault_path).expanduser().resolve()
    catalog = load_subject_catalog(vault_path)
    subjects = [subject for title in (subject_titles or []) if (subject := get_subject_by_title(catalog, title))]
    subject_links = [subject.wikilink for subject in subjects]

    documents: list[RetrievalDocument] = []
    seen: set[str] = set()

    _append_if_present(documents, seen, vault, "profile/index.md")
    if workflow in {"daily-briefing", "meeting-prep", "incoming-message", "incoming-email"}:
        _append_if_present(documents, seen, vault, "profile/current.md")
    if workflow in {"weekly-review", "monthly-review"}:
        _append_if_present(documents, seen, vault, "profile/patterns.md")

    for subject in subjects:
        _append_if_present(documents, seen, vault, _subject_profile_path(subject))

    direct_docs = search_memory_index(
        vault_path,
        " ".join(subject_titles or [workflow]),
        subjects=subject_links or None,
        doc_types=["memory-claim", "memory-event", "person", "commitment", "profile"],
        since_days=since_days,
    )

    for doc in direct_docs:
        if doc.path not in seen:
            seen.add(doc.path)
            documents.append(doc)

    # Graph expansion through direct link neighborhoods before broad fallback search.
    neighborhood_links = set(subject_links)
    for doc in documents:
        neighborhood_links.update(doc.wikilinks)
        neighborhood_links.update(doc.subjects)

    for link in sorted(neighborhood_links):
        graph_docs = search_memory_index(
            vault_path,
            link.replace("[[", "").replace("]]", ""),
            subjects=[link],
            since_days=since_days,
        )
        for doc in graph_docs[:3]:
            if doc.path not in seen:
                seen.add(doc.path)
                documents.append(doc)

    used_search_fallback = False
    if not subjects or len(documents) < 4:
        fallback = search_memory_index(vault_path, " ".join(subject_titles or [workflow]), since_days=since_days)
        for doc in fallback[:8]:
            if doc.path not in seen:
                seen.add(doc.path)
                documents.append(doc)
                used_search_fallback = True

    return RetrievalResult(
        workflow=workflow,
        subject_titles=subject_titles or [],
        documents=documents,
        used_search_fallback=used_search_fallback,
    )
