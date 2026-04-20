#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.steward_policy.loader import estimate_token_count, load_manifest, render_core_markdown


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    manifest = load_manifest(REPO_ROOT)

    for module_id, module in manifest["modules"].items():
        require((REPO_ROOT / module["path"]).exists(), f"Missing policy module {module_id}: {module['path']}")

    framework_index = (REPO_ROOT / "docs/FRAMEWORK.md").read_text(encoding="utf-8")
    spec_index = (REPO_ROOT / "docs/STEWARD_SPEC.md").read_text(encoding="utf-8")

    for module_id, module in manifest["modules"].items():
        target_index = framework_index if module["layer"] == "framework" else spec_index
        require(module["path"].split("/", 1)[1] in target_index, f"Index missing module path for {module_id}")

    generated_core = render_core_markdown(REPO_ROOT, manifest)
    committed_core = (REPO_ROOT / manifest["core"]["path"]).read_text(encoding="utf-8")
    require(committed_core == generated_core, "docs/STEWARD_CORE.md is out of date. Run scripts/generate_policy_artifacts.py")

    token_estimate = estimate_token_count(committed_core)
    require(token_estimate <= manifest["core"]["hard_token_budget"], "Steward core exceeds hard token budget")

    forbidden_module_titles = [
        manifest["modules"]["spec.daily_briefing"]["title"],
        manifest["modules"]["spec.weekly_review"]["title"],
        manifest["modules"]["spec.note_handoff"]["title"],
    ]
    for title in forbidden_module_titles:
        require(title not in committed_core, f"Workflow-only module leaked into STEWARD_CORE: {title}")


if __name__ == "__main__":
    main()
