from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("pfb_list.py")
SPEC = importlib.util.spec_from_file_location("pfb_list_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
pfb_list = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pfb_list
SPEC.loader.exec_module(pfb_list)


class PFBListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.registry = self.root / "state/registry-v1.json"
        self.registry.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_initialized_flow_reports_live_status_and_creation_time(self) -> None:
        retrom = self._create_retrom_worktree("alpha", "feat/alpha")
        identifier = pfb_list.pfb_id("alpha")
        spec = {
            "schemaVersion": 1,
            "name": "alpha",
            "id": identifier,
            "hostMode": "LOCALHOST_SHARED_GATEWAY_V1",
            "retrom": {"root": str(retrom), "branch": "feat/alpha"},
            "runtime": {"mode": "formal"},
            "cores": [],
        }
        spec_path = retrom / ".pfb/spec.json"
        spec_path.parent.mkdir()
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        os.utime(spec_path, (1_700_000_000, 1_700_000_000))
        self._write_registry([self._registry_entry(identifier, "alpha", retrom)])

        flows = pfb_list.discover_flows(
            self.root,
            state_file=self.registry,
            status_reader=lambda _root, _name: "STALE",
        )

        self.assertEqual(len(flows), 1)
        self.assertEqual(flows[0].branch, "feat/alpha")
        self.assertEqual(flows[0].created_at, "2023-11-14T22:13:20Z")
        self.assertEqual(flows[0].status, "STALE")
        self.assertEqual(flows[0].pfb_id, identifier)
        self.assertEqual(flows[0].url, f"http://{identifier}.localhost:3000")

    def test_prepared_and_missing_flows_remain_visible(self) -> None:
        prepared = self._create_retrom_worktree("prepared", "feat/prepared")
        missing = self.root / ".worktree/missing/project/retrom"
        missing_id = pfb_list.pfb_id("missing")
        self._write_registry([self._registry_entry(missing_id, "missing", missing)])

        flows = pfb_list.discover_flows(
            self.root,
            state_file=self.registry,
            status_reader=lambda _root, _name: self.fail("status should not be called"),
        )
        by_name = {flow.name: flow for flow in flows}

        self.assertEqual(by_name["prepared"].status, "PREPARED")
        self.assertEqual(by_name["prepared"].branch, "feat/prepared")
        self.assertEqual(by_name["missing"].status, "MISSING")
        self.assertEqual(by_name["missing"].branch, "-")
        self.assertEqual(by_name["missing"].pfb_id, missing_id)
        self.assertTrue(prepared.is_dir())

    def test_table_contains_required_fields(self) -> None:
        flow = pfb_list.PFBFlow(
            name="alpha",
            branch="feat/alpha",
            created_at="2023-11-14T22:13:20Z",
            status="RUNNING",
            pfb_id="alpha-8ed3f6ad685b",
            url="http://alpha-8ed3f6ad685b.localhost:3000",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            pfb_list.print_flows([flow])

        value = output.getvalue()
        for expected in ("BRANCH", "CREATED (UTC)", "STATUS", "PFB ID", "URL", "feat/alpha"):
            self.assertIn(expected, value)

    def test_worktree_symlink_cannot_escape_workspace(self) -> None:
        outside = self.root / "outside"
        (outside / "project/retrom").mkdir(parents=True)
        worktrees = self.root / ".worktree"
        worktrees.mkdir()
        (worktrees / "escape").symlink_to(outside, target_is_directory=True)
        self._write_registry([])

        flows = pfb_list.discover_flows(
            self.root,
            state_file=self.registry,
            status_reader=lambda _root, _name: self.fail("status should not be called"),
        )

        self.assertEqual(flows, [])

    def _create_retrom_worktree(self, name: str, branch: str) -> Path:
        root = self.root / ".worktree" / name / "project/retrom"
        root.mkdir(parents=True)
        self._run("git", "init", f"--initial-branch={branch}", str(root))
        self._run("git", "-C", str(root), "config", "user.name", "PFB Test")
        self._run("git", "-C", str(root), "config", "user.email", "pfb-test@example.invalid")
        (root / "README.md").write_text("test\n", encoding="utf-8")
        self._run("git", "-C", str(root), "add", "README.md")
        self._run("git", "-C", str(root), "commit", "-m", "initial")
        return root.resolve()

    def _registry_entry(self, identifier: str, name: str, root: Path) -> dict[str, str]:
        return {
            "id": identifier,
            "name": name,
            "retromRoot": str(root),
            "composeProject": f"retrom-pfb-{identifier}",
            "status": "RUNNING",
        }

    def _write_registry(self, entries: list[dict[str, str]]) -> None:
        self.registry.write_text(json.dumps({"pfbs": entries}), encoding="utf-8")

    def _run(self, *arguments: str) -> None:
        subprocess.run(arguments, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
