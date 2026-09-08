from __future__ import annotations

import subprocess

import workspace_config as config
import workspace_update as updates
from workspace_test_support import SourceCase


class CatalogUpdateTests(SourceCase):
    def test_update_reads_target_manifest_and_clones_new_repository(self):
        self.initialize()
        before_runtime = self.git(self.checkout(self.runtime), "rev-parse", "HEAD")
        core = self.repository("new-core")
        target = self.publish_catalog([self.runtime, core])
        updates.update_workspace(self.w)
        self.assertEqual(self.git(self.checkout(self.app), "rev-parse", "HEAD"), target)
        self.assertTrue(self.checkout(core).exists())
        self.assertEqual(self.git(self.checkout(self.runtime), "rev-parse", "HEAD"), before_runtime)

    def test_dirty_repository_new_to_target_manifest_prevents_all_switches(self):
        self.initialize()
        core = self.repository("new-core")
        self.w.clone_missing([core])
        (self.checkout(core) / "user.txt").write_text("dirty")
        retrom = self.checkout(self.app)
        before = self.git(retrom, "rev-parse", "HEAD")
        self.git(retrom, "switch", "-c", "local-feature")
        self.publish_catalog([self.runtime, core])
        with self.assertRaisesRegex(config.WorkspaceError, "dirty: new-core"):
            updates.update_workspace(self.w)
        self.assertEqual(self.git(retrom, "rev-parse", "HEAD"), before)
        self.assertEqual(self.git(retrom, "branch", "--show-current"), "local-feature")

    def test_removed_dirty_repository_blocks_update_then_is_preserved(self):
        core = self.repository("old-core")
        self.publish_catalog([self.runtime, core])
        self.initialize()
        self.publish_catalog([self.runtime])
        dirt = self.checkout(core) / "user.txt"
        dirt.write_text("dirty")
        with self.assertRaisesRegex(config.WorkspaceError, "dirty: old-core"):
            updates.update_workspace(self.w)
        dirt.unlink()
        updates.update_workspace(self.w)
        self.assertTrue(self.checkout(core).exists())
        self.assertEqual(len(self.w.load_manifest()), 2)

    def test_invalid_target_catalog_preserves_every_checkout(self):
        self.initialize()
        retrom = self.checkout(self.app)
        before = self.git(retrom, "rev-parse", "HEAD")
        self.publish_catalog([])
        with self.assertRaisesRegex(config.WorkspaceError, "non-empty"):
            updates.update_workspace(self.w)
        self.assertEqual(self.git(retrom, "rev-parse", "HEAD"), before)

    def test_default_branch_in_other_worktree_blocks_update_before_new_clone(self):
        self.initialize()
        retrom = self.checkout(self.app)
        before = self.git(retrom, "rev-parse", "HEAD")
        runtime = self.checkout(self.runtime)
        self.git(runtime, "switch", "-c", "owner")
        self.git(runtime, "worktree", "add", str(self.root / "elsewhere"), "master")
        core = self.repository("new-core")
        self.publish_catalog([self.runtime, core])
        with self.assertRaisesRegex(config.WorkspaceError, "another worktree"):
            updates.update_workspace(self.w)
        self.assertEqual(self.git(retrom, "rev-parse", "HEAD"), before)
        self.assertFalse(self.checkout(core).exists())

    def test_unavailable_new_branch_leaves_existing_checkouts_unchanged(self):
        self.initialize()
        retrom = self.checkout(self.app)
        before = self.git(retrom, "rev-parse", "HEAD")
        core = self.repository("new-core")
        core["defaultBranch"] = "missing-maintenance-branch"
        self.publish_catalog([self.runtime, core])
        with self.assertRaises(subprocess.CalledProcessError):
            updates.update_workspace(self.w)
        self.assertEqual(self.git(retrom, "rev-parse", "HEAD"), before)

    def test_locally_ahead_retrom_default_cannot_apply_an_older_catalog(self):
        self.initialize()
        retrom = self.checkout(self.app)
        self.git(retrom, "config", "user.name", "Workspace Test")
        self.git(retrom, "config", "user.email", "test@example.invalid")
        (retrom / "local.txt").write_text("unpublished")
        self.git(retrom, "add", ".")
        self.git(retrom, "commit", "-m", "unpublished default branch")
        self.git(retrom, "switch", "-c", "working")
        with self.assertRaisesRegex(config.WorkspaceError, "unpublished commits"):
            updates.update_workspace(self.w)
        self.assertEqual(self.git(retrom, "branch", "--show-current"), "working")
