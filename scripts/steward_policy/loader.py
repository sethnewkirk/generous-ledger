from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal


PolicySurface = Literal["chat", "onboarding", "routine"]
PolicyWorkflow = Literal["general_chat", "note_chat", "onboarding", "daily", "evening", "weekly", "monthly", "ambient"]
PolicyWriteIntent = Literal["none", "profile", "memory", "routine_output", "note_writeback"]
PolicyIntentTag = Literal["relationship", "recommendation", "planning", "moral_guidance", "file_writing"]
PolicyFallbackMode = Literal["none", "workflow", "core_only"]


@dataclass(frozen=True)
class PolicyRequest:
    surface: PolicySurface
    workflow: PolicyWorkflow
    provider: str
    write_intent: PolicyWriteIntent
    intent_tags: tuple[PolicyIntentTag, ...] = ()


@dataclass(frozen=True)
class PolicyPacket:
    markdown: str
    module_ids: tuple[str, ...]
    module_paths: tuple[str, ...]
    fallback_mode: PolicyFallbackMode
    token_estimate: int


def _repo_path(vault_or_repo_path: str | Path, relative_path: str) -> Path:
    return Path(vault_or_repo_path) / relative_path


def load_manifest(vault_or_repo_path: str | Path) -> dict:
    manifest_path = _repo_path(vault_or_repo_path, "docs/policy/manifest.json")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def estimate_token_count(markdown: str) -> int:
    trimmed = markdown.strip()
    if not trimmed:
        return 0
    return int((len(trimmed.split()) * 1.33) + 0.9999)


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _strip_title(markdown: str) -> str:
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def render_core_markdown(vault_or_repo_path: str | Path, manifest: dict | None = None) -> str:
    manifest = manifest or load_manifest(vault_or_repo_path)
    sections = [
        "# Steward Core",
        "",
        "This is a generated always-on policy artifact assembled from the canonical framework and spec modules listed in `docs/policy/manifest.json`.",
    ]

    for module_id in manifest["core"]["module_ids"]:
        module = manifest["modules"][module_id]
        body = _strip_title(_repo_path(vault_or_repo_path, module["path"]).read_text(encoding="utf-8"))
        sections.extend(["", f"## {module['title']}", "", body])

    return "\n".join(sections).strip() + "\n"


def _build_requested_module_ids(manifest: dict, request: PolicyRequest, use_fallback_workflow: bool) -> list[str]:
    workflow_key = "fallback_workflow" if use_fallback_workflow else "workflow"
    ids = [
        *manifest["core"]["module_ids"],
        *manifest["bundles"]["surface"].get(request.surface, []),
        *manifest["bundles"][workflow_key].get(request.workflow, []),
    ]

    if not use_fallback_workflow:
        ids.extend(manifest["bundles"]["write_intent"].get(request.write_intent, []))
        for tag in request.intent_tags:
            ids.extend(manifest["bundles"]["intent_tags"].get(tag, []))

    return _unique_preserving_order(ids)


def _read_extra_modules(vault_or_repo_path: str | Path, manifest: dict, module_ids: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for module_id in module_ids:
        module = manifest["modules"].get(module_id)
        if not module:
            raise FileNotFoundError(f"Unknown policy module: {module_id}")
        module_path = _repo_path(vault_or_repo_path, module["path"])
        if not module_path.exists():
            raise FileNotFoundError(f"Missing policy module file: {module['path']}")
        texts[module_id] = module_path.read_text(encoding="utf-8")
    return texts


def _load_core_markdown(vault_or_repo_path: str | Path, manifest: dict) -> str:
    core_path = _repo_path(vault_or_repo_path, manifest["core"]["path"])
    if core_path.exists():
        return core_path.read_text(encoding="utf-8")
    return render_core_markdown(vault_or_repo_path, manifest)


def _render_policy_packet(core_markdown: str, manifest: dict, module_ids: list[str], module_texts: dict[str, str]) -> str:
    extra_module_ids = [module_id for module_id in module_ids if module_id not in manifest["core"]["module_ids"]]
    sections = ["<POLICY_PACKET>", core_markdown.strip()]

    for module_id in extra_module_ids:
        module = manifest["modules"][module_id]
        body = module_texts.get(module_id)
        if not body:
            continue
        sections.extend([
            "",
            f'<POLICY_MODULE id="{module_id}" path="{module["path"]}">',
            body.strip(),
            "</POLICY_MODULE>",
        ])

    sections.append("</POLICY_PACKET>")
    return "\n".join(sections)


def build_policy_packet(vault_or_repo_path: str | Path, request: PolicyRequest) -> PolicyPacket:
    manifest = load_manifest(vault_or_repo_path)
    core_markdown = _load_core_markdown(vault_or_repo_path, manifest)
    module_ids = _build_requested_module_ids(manifest, request, use_fallback_workflow=False)
    fallback_mode: PolicyFallbackMode = "none"

    try:
        module_texts = _read_extra_modules(
            vault_or_repo_path,
            manifest,
            [module_id for module_id in module_ids if module_id not in manifest["core"]["module_ids"]],
        )
    except FileNotFoundError:
        try:
            module_ids = _build_requested_module_ids(manifest, request, use_fallback_workflow=True)
            module_texts = _read_extra_modules(
                vault_or_repo_path,
                manifest,
                [module_id for module_id in module_ids if module_id not in manifest["core"]["module_ids"]],
            )
            fallback_mode = "workflow"
        except FileNotFoundError:
            module_ids = list(manifest["core"]["module_ids"])
            module_texts = {}
            fallback_mode = "core_only"

    markdown = _render_policy_packet(core_markdown, manifest, module_ids, module_texts)
    module_paths = tuple([manifest["core"]["path"], *[manifest["modules"][module_id]["path"] for module_id in module_ids]])
    return PolicyPacket(
        markdown=markdown,
        module_ids=tuple(module_ids),
        module_paths=module_paths,
        fallback_mode=fallback_mode,
        token_estimate=estimate_token_count(markdown),
    )
