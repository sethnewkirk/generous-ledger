from __future__ import annotations

import hashlib
import re
from pathlib import Path


WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def title_from_path(path: str | Path) -> str:
    return Path(path).stem


def as_wikilink(title: str, alias: str | None = None) -> str:
    title = title.strip()
    if alias and alias.strip() and alias.strip() != title:
        return f"[[{title}|{alias.strip()}]]"
    return f"[[{title}]]"


def path_to_wikilink(path: str | Path, alias: str | None = None) -> str:
    return as_wikilink(title_from_path(path), alias=alias)


def extract_wikilinks(text: str) -> list[str]:
    links: list[str] = []
    for match in WIKILINK_RE.finditer(text):
        target = match.group(1).strip()
        if target:
            links.append(target)
    return links


def normalize_lookup_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def replace_titles_with_wikilinks(text: str, titles_to_links: dict[str, str]) -> str:
    output = text
    for title in sorted(titles_to_links.keys(), key=len, reverse=True):
        pattern = re.compile(rf"(?<!\[\[)\b{re.escape(title)}\b(?![^\[]*\]\])", re.IGNORECASE)
        output = pattern.sub(titles_to_links[title], output)
    return output


def safe_title_fragment(text: str, max_words: int = 8) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return "Memory"
    return " ".join(word.capitalize() for word in words[:max_words])


def short_hash(*parts: str, length: int = 8) -> str:
    joined = "||".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:length]

