from __future__ import annotations

from pathlib import Path
import re
import yaml


def read_markdown(path: str | Path) -> tuple[dict, str]:
    file_path = Path(path)
    if not file_path.exists():
        return {}, ""

    text = file_path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            frontmatter_text = text[4:end]
            body = text[end + 5 :].lstrip("\n")
            data = yaml.safe_load(frontmatter_text) or {}
            if isinstance(data, dict):
                return data, body

    return {}, text


def render_markdown(frontmatter: dict, body: str) -> str:
    yaml_text = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()
    trimmed_body = body.rstrip() + "\n"
    return f"---\n{yaml_text}\n---\n\n{trimmed_body}"


def write_markdown(path: str | Path, frontmatter: dict, body: str) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = render_markdown(frontmatter, body)
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(file_path)
    return file_path


def replace_generated_block(body: str, block_id: str, new_content: str) -> str:
    start_marker = f"<!-- GENERATED:{block_id} START -->"
    end_marker = f"<!-- GENERATED:{block_id} END -->"
    block = f"{start_marker}\n{new_content.rstrip()}\n{end_marker}"
    pattern = re.compile(
        rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
        flags=re.DOTALL,
    )

    if pattern.search(body):
        updated = pattern.sub(block, body)
        return updated.strip() + "\n"

    if body.strip():
        return f"{block}\n\n{body.lstrip()}"
    return block + "\n"

