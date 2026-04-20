from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.steward_policy.loader import PolicyRequest, build_policy_packet, load_manifest, render_core_markdown


REPO_ROOT = Path(__file__).resolve().parents[3]


class PolicyLoaderTests(unittest.TestCase):
    def test_manifest_module_paths_exist(self) -> None:
        manifest = load_manifest(REPO_ROOT)
        for module in manifest["modules"].values():
            self.assertTrue((REPO_ROOT / module["path"]).exists(), module["path"])

    def test_general_chat_bundle_avoids_routine_modules(self) -> None:
        packet = build_policy_packet(
            REPO_ROOT,
            PolicyRequest(
                surface="chat",
                workflow="general_chat",
                provider="codex",
                write_intent="none",
            ),
        )

        self.assertEqual(packet.fallback_mode, "none")
        self.assertIn("spec.interaction_mode", packet.module_ids)
        self.assertNotIn("spec.daily_briefing", packet.module_ids)

    def test_onboarding_bundle_includes_schema_modules(self) -> None:
        packet = build_policy_packet(
            REPO_ROOT,
            PolicyRequest(
                surface="onboarding",
                workflow="onboarding",
                provider="codex",
                write_intent="profile",
            ),
        )

        self.assertIn("spec.onboarding", packet.module_ids)
        self.assertIn("spec.people_commitment_schemas", packet.module_ids)
        self.assertNotIn("spec.daily_briefing", packet.module_ids)

    def test_generated_core_matches_committed_core(self) -> None:
        manifest = load_manifest(REPO_ROOT)
        expected = render_core_markdown(REPO_ROOT, manifest)
        actual = (REPO_ROOT / manifest["core"]["path"]).read_text(encoding="utf-8")
        self.assertEqual(actual, expected)

    def test_missing_requested_module_uses_workflow_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_root = Path(tmpdir) / "repo"
            shutil.copytree(REPO_ROOT / "docs", sandbox_root / "docs")
            target = sandbox_root / "docs" / "spec" / "note-handoff.md"
            target.unlink()

            packet = build_policy_packet(
                sandbox_root,
                PolicyRequest(
                    surface="chat",
                    workflow="note_chat",
                    provider="codex",
                    write_intent="note_writeback",
                ),
            )

            self.assertEqual(packet.fallback_mode, "workflow")
            self.assertIn("spec.memory_retrieval", packet.module_ids)
            self.assertNotIn("spec.note_handoff", packet.module_ids)


if __name__ == "__main__":
    unittest.main()
