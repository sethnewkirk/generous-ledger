from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .markdown import read_markdown
from .models import SubjectRef
from .wikilinks import as_wikilink, extract_wikilinks, normalize_lookup_key


SYSTEM_PROFILE_FILES = {"index", "identity", "patterns", "current"}


@dataclass
class SubjectCatalog:
    by_title: dict[str, SubjectRef]
    aliases: dict[str, list[SubjectRef]]


def _register_subject(
    by_title: dict[str, SubjectRef],
    aliases: dict[str, list[SubjectRef]],
    subject: SubjectRef,
    *extra_aliases: str,
) -> None:
    by_title[normalize_lookup_key(subject.title)] = subject
    for alias in (subject.title, *extra_aliases):
        key = normalize_lookup_key(alias)
        if not key:
            continue
        aliases.setdefault(key, [])
        if subject not in aliases[key]:
            aliases[key].append(subject)


def load_subject_catalog(vault_path: str) -> SubjectCatalog:
    vault = Path(vault_path).expanduser().resolve()
    by_title: dict[str, SubjectRef] = {}
    aliases: dict[str, list[SubjectRef]] = {}

    for md_file in sorted((vault / "profile" / "people").glob("*.md")):
        frontmatter, _ = read_markdown(md_file)
        title = str(frontmatter.get("name") or md_file.stem).strip()
        subject = SubjectRef("person", title, str(md_file.relative_to(vault)), as_wikilink(md_file.stem))
        _register_subject(by_title, aliases, subject, md_file.stem)

    for md_file in sorted((vault / "profile" / "commitments").glob("*.md")):
        frontmatter, _ = read_markdown(md_file)
        title = str(frontmatter.get("title") or md_file.stem).strip()
        subject = SubjectRef("commitment", title, str(md_file.relative_to(vault)), as_wikilink(md_file.stem))
        _register_subject(by_title, aliases, subject, md_file.stem)

    for md_file in sorted((vault / "profile").glob("*.md")):
        if md_file.stem in SYSTEM_PROFILE_FILES:
            continue
        subject = SubjectRef("domain", md_file.stem, str(md_file.relative_to(vault)), as_wikilink(md_file.stem))
        _register_subject(by_title, aliases, subject, md_file.stem)

    contacts_dir = vault / "data" / "contacts"
    if contacts_dir.is_dir():
        for md_file in sorted(contacts_dir.glob("*.md")):
            frontmatter, _ = read_markdown(md_file)
            if str(frontmatter.get("type") or "") != "contact-entry":
                continue

            target_subject = None
            profile_target = str(frontmatter.get("profile_target") or "").strip()
            if profile_target.startswith("[[") and profile_target.endswith("]]"):
                target_title = profile_target[2:-2].split("|", 1)[0]
                target_subject = by_title.get(normalize_lookup_key(target_title))

            if target_subject is None:
                target_subject = by_title.get(normalize_lookup_key(str(frontmatter.get("name") or md_file.stem)))

            if target_subject is None:
                continue

            extra_aliases: list[str] = []
            for key in ("nickname", "organization"):
                value = str(frontmatter.get(key) or "").strip()
                if value:
                    extra_aliases.append(value)
            for key in ("emails", "phones", "aliases"):
                values = frontmatter.get(key, [])
                if isinstance(values, str):
                    values = [values]
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, str) and value.strip():
                            extra_aliases.append(value.strip())

            _register_subject(by_title, aliases, target_subject, *extra_aliases)

    return SubjectCatalog(by_title=by_title, aliases=aliases)


def get_subject_by_title(catalog: SubjectCatalog, title: str) -> SubjectRef | None:
    return catalog.by_title.get(normalize_lookup_key(title))


def ambiguous_aliases(catalog: SubjectCatalog) -> dict[str, list[SubjectRef]]:
    return {
        alias: subjects
        for alias, subjects in catalog.aliases.items()
        if len({subject.path for subject in subjects}) > 1
    }


def suggest_subjects(text: str, catalog: SubjectCatalog, *, limit: int = 5) -> list[SubjectRef]:
    query = normalize_lookup_key(text)
    if not query:
        return []

    query_tokens = {token for token in re.split(r"[^a-z0-9]+", query) if token}
    scored: dict[str, tuple[int, SubjectRef]] = {}

    for alias, subjects in catalog.aliases.items():
        alias_tokens = {token for token in re.split(r"[^a-z0-9]+", alias) if token}
        overlap = len(query_tokens.intersection(alias_tokens))
        for subject in subjects:
            score = 0
            title_key = normalize_lookup_key(subject.title)
            if title_key == query:
                score += 120
            elif alias == query:
                score += 100
            elif overlap >= 2:
                score += 70 + overlap * 10
            elif overlap == 1 and len(query_tokens) == 1 and len(alias_tokens) == 1 and next(iter(query_tokens)) == next(iter(alias_tokens)):
                score += 50
            else:
                continue
            if score <= 0:
                continue
            existing = scored.get(subject.path)
            if existing is None or score > existing[0]:
                scored[subject.path] = (score, subject)

    ordered = sorted(scored.values(), key=lambda item: (item[0], item[1].title), reverse=True)
    return [subject for _, subject in ordered[:limit]]


def resolve_subjects(text: str, catalog: SubjectCatalog) -> list[SubjectRef]:
    subjects: list[SubjectRef] = []
    seen: set[str] = set()

    for target in extract_wikilinks(text):
        subject = get_subject_by_title(catalog, target)
        if subject and subject.path not in seen:
            seen.add(subject.path)
            subjects.append(subject)

    lowered_text = text.lower()
    for alias_key, alias_subjects in sorted(catalog.aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if not alias_key:
            continue
        pattern = re.compile(rf"\b{re.escape(alias_key)}\b", re.IGNORECASE)
        if not pattern.search(lowered_text):
            continue
        for subject in alias_subjects:
            if subject.path not in seen:
                seen.add(subject.path)
                subjects.append(subject)

    return subjects
