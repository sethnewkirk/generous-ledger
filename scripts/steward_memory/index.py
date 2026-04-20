from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import re

from .markdown import read_markdown
from .models import RetrievalDocument
from .wikilinks import extract_wikilinks


TOKEN_RE = re.compile(r"[A-Za-z0-9]{2,}")


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _build_document(vault: Path, path: Path) -> RetrievalDocument:
    frontmatter, body = read_markdown(path)
    doc_type = str(frontmatter.get("type") or "markdown")
    title = path.stem
    subjects = [str(item) for item in frontmatter.get("subjects", []) if isinstance(item, str)]
    body_links = extract_wikilinks(body)
    all_links = list(dict.fromkeys(subjects + body_links))
    summary = ""
    if "summary" in frontmatter:
        summary = str(frontmatter["summary"])
    else:
        first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
        summary = first_line[:240]

    return RetrievalDocument(
        path=str(path.relative_to(vault)),
        doc_type=doc_type,
        title=title,
        summary=summary,
        subjects=subjects,
        wikilinks=all_links,
        occurred_at=_string_or_none(frontmatter.get("occurred_at") or frontmatter.get("date")),
        claim_type=_string_or_none(frontmatter.get("claim_type")),
        status=_string_or_none(frontmatter.get("status")),
        source_type=_string_or_none(frontmatter.get("source_type")),
        sensitivity=_string_or_none(frontmatter.get("sensitivity")),
    )


def build_memory_index(vault_path: str) -> Path:
    vault = Path(vault_path).expanduser().resolve()
    documents: list[dict[str, object]] = []

    scan_roots = [
        vault / "memory" / "events",
        vault / "memory" / "claims",
        vault / "profile",
        vault / "data" / "contacts",
        vault / "data" / "tasks",
        vault / "data" / "voice",
        vault / "data" / "calls",
        vault / "diary",
        vault / "reviews",
    ]

    for root in scan_roots:
        if not root.exists():
            continue
        for md_file in sorted(root.rglob("*.md")):
            _, body = read_markdown(md_file)
            document = _build_document(vault, md_file)
            payload = asdict(document)
            payload["tokens"] = _tokens(
                "\n".join(
                    [
                        document.title,
                        document.summary,
                        body,
                        " ".join(document.subjects),
                        " ".join(document.wikilinks),
                    ]
                )
            )
            documents.append(payload)

    index_path = vault / "memory" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "documents": documents,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_path


def load_memory_index(vault_path: str) -> list[dict[str, object]]:
    vault = Path(vault_path).expanduser().resolve()
    index_path = vault / "memory" / "index.json"
    if not index_path.exists():
        build_memory_index(vault_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    return payload.get("documents", [])


def search_memory_index(
    vault_path: str,
    query: str,
    *,
    subjects: list[str] | None = None,
    doc_types: list[str] | None = None,
    since_days: int | None = None,
) -> list[RetrievalDocument]:
    query_tokens = set(_tokens(query))
    subject_filter = set(subjects or [])
    doc_type_filter = set(doc_types or [])
    cutoff = None
    if since_days is not None:
        cutoff = datetime.now() - timedelta(days=since_days)

    results: list[RetrievalDocument] = []
    for raw_doc in load_memory_index(vault_path):
        doc_subjects = set(raw_doc.get("subjects", []))
        if subject_filter and not doc_subjects.intersection(subject_filter):
            continue
        if doc_type_filter and raw_doc.get("doc_type") not in doc_type_filter:
            continue

        occurred_at = raw_doc.get("occurred_at")
        if cutoff and isinstance(occurred_at, str):
            try:
                occurred = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
                if occurred < cutoff:
                    continue
            except ValueError:
                pass

        doc_tokens = set(raw_doc.get("tokens", []))
        score = float(len(query_tokens.intersection(doc_tokens)))
        if not score:
            continue

        result = RetrievalDocument(
            path=str(raw_doc["path"]),
            doc_type=str(raw_doc["doc_type"]),
            title=str(raw_doc["title"]),
            summary=str(raw_doc["summary"]),
            subjects=list(raw_doc.get("subjects", [])),
            wikilinks=list(raw_doc.get("wikilinks", [])),
            occurred_at=raw_doc.get("occurred_at"),
            claim_type=raw_doc.get("claim_type"),
            status=raw_doc.get("status"),
            source_type=raw_doc.get("source_type"),
            sensitivity=raw_doc.get("sensitivity"),
            score=score,
        )
        results.append(result)

    status_rank = {"active": 2, "provisional": 1, "superseded": 0, None: -1}
    results.sort(
        key=lambda doc: (
            status_rank.get(doc.status, -1),
            doc.score,
            doc.occurred_at or "",
        ),
        reverse=True,
    )
    return results
