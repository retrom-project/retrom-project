from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import workspace_config as config
import workspace_sources as sources
from workspace_test_support import SourceCase


class SourceTests(SourceCase):
    def test_fresh_bootstrap_downloads_retrom_then_its_dependencies(self):
        self.assertFalse(self.checkout(self.app).exists())
        self.initialize()
        self.w.check_workspace(self.w.load_manifest())
        self.assertEqual([r["id"] for r in self.w.load_manifest()], ["retrom", "retrom-runtime"])

    def test_two_pfb_catalogs_and_source_worktrees_are_isolated(self):
        a = self.initialize("feature-a")
        b = self.initialize("feature-b")
        x = self.repository("core-x")
        y = self.repository("core-y")
        self.write_catalog(a / "project/retrom", [self.runtime, x])
        self.write_catalog(b / "project/retrom", [self.runtime, y])
        self.initialize("feature-a")
        self.initialize("feature-b")
        self.assertTrue((a / x["path"]).exists())
        self.assertFalse((a / y["path"]).exists())
        self.assertTrue((b / y["path"]).exists())
        self.assertFalse((b / x["path"]).exists())
        self.assertEqual(len(self.w.load_manifest()), 2)
        for scope, core in ((a, x), (b, y)):
            repos = self.w.load_manifest(scope / "project/retrom")
            self.assertEqual([r["id"] for r in repos], ["retrom", "retrom-runtime", core["id"]])
            self.assertEqual(self.git(scope / core["path"], "branch", "--show-current"), "feat/" + scope.name)
        self.assertEqual(self.git(self.checkout(self.app), "status", "--porcelain"), "")

    def test_missing_or_invalid_pfb_manifest_never_uses_baseline_catalog(self):
        scope = self.initialize("feature")
        path = scope / "project/retrom/workspace/manifest.yaml"
        path.unlink()
        with self.assertRaisesRegex(config.WorkspaceError, "cannot read dependency manifest"):
            self.w.load_manifest(scope / "project/retrom")
        path.write_text("[]")
        with self.assertRaisesRegex(config.WorkspaceError, "schemaVersion"):
            self.w.load_manifest(scope / "project/retrom")

    def test_partial_init_uses_latest_remote_without_switching_dirty_owner(self):
        core = self.repository("core-x")
        other = self.repository("core-y")
        self.publish_catalog([self.runtime, core, other])
        self.initialize(ids=["retrom-runtime", "core-x"])
        owner = self.checkout(core)
        self.git(owner, "switch", "-c", "local-owner")
        (owner / "local.txt").write_text("user change")
        pub = self.publisher(core)
        (pub / "file.txt").write_text("new remote revision")
        self.git(pub, "add", ".")
        self.git(pub, "commit", "-m", "new core")
        self.git(pub, "push", "origin", "master")
        scope = self.initialize("feature", ["retrom-runtime", "core-x"])
        self.assertEqual(self.git(scope / core["path"], "rev-parse", "HEAD"), self.git(pub, "rev-parse", "HEAD"))
        self.assertEqual(self.git(owner, "branch", "--show-current"), "local-owner")
        self.assertEqual((owner / "local.txt").read_text(), "user change")
        self.assertFalse(self.checkout(other).exists())

    def test_source_context_rejects_conflicting_or_escaping_pfb_roots(self):
        for name in ("../escape", "feature/other", ".."):
            with self.assertRaises(config.WorkspaceError):
                config.context(self.root, name, None)
        with self.assertRaises(config.WorkspaceError):
            config.context(self.root, "a", str(self.root / ".worktree/b/project/retrom"))
        scope, retrom = config.context(self.root, None, str(self.root / ".worktree/a/project/retrom"))
        self.assertEqual(scope, self.root / ".worktree/a")
        self.assertEqual(retrom, scope / "project/retrom")

    def test_bootstrap_rejects_extra_core_entry(self):
        path = self.root / "manifest.yaml"
        data = json.loads(path.read_text())
        data["repositories"].append(self.runtime)
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(config.WorkspaceError, "only Retrom"):
            self.initialize()

    def test_invalid_selection_does_not_clone_dependencies(self):
        with self.assertRaisesRegex(config.WorkspaceError, "unknown repository"):
            self.initialize(ids=["typo"])
        self.assertFalse(self.checkout(self.runtime).exists())

    def test_parallel_cli_initialization_shares_owners_without_conflicts(self):
        script_root = Path(__file__).parent
        target = self.root / "scripts"
        target.mkdir()
        for path in script_root.glob("workspace*.py"):
            shutil.copyfile(path, target / path.name)
        processes = [subprocess.Popen(
            [sys.executable, str(target / "workspace.py"), "init", "--pfb", name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) for name in ("parallel-a", "parallel-b")]
        for process in processes:
            output, error = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, output + error)
        for name in ("parallel-a", "parallel-b"):
            scope = self.root / ".worktree" / name
            self.assertEqual(self.git(scope / "project/retrom-runtime", "branch", "--show-current"), "codex/" + name)
        self.assertEqual(self.git(self.checkout(self.app), "status", "--porcelain"), "")

    def test_cleanup_uses_pfb_catalog_and_discovers_legacy_worktrees(self):
        from pfb_remove import _discover_worktrees, load_pfb_repositories
        scope = self.initialize("feature")
        core = self.repository("new-core")
        self.write_catalog(scope / "project/retrom", [self.runtime, core])
        self.initialize("feature")
        repos = load_pfb_repositories(self.root, scope)
        self.assertEqual([r["id"] for r in repos], ["retrom", "retrom-runtime", "new-core"])
        (scope / "project/retrom/workspace/manifest.yaml").unlink()
        repos = load_pfb_repositories(self.root, scope)
        self.assertEqual([r["id"] for r in repos], ["retrom"])
        worktrees = _discover_worktrees(self.root, scope, repos)
        self.assertEqual({w.path for w in worktrees}, {scope / r["path"] for r in (self.app, self.runtime, core)})
