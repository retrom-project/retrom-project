from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("pfb_remove.py")
SCRIPTS_PATH = str(MODULE_PATH.parent)
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)
SPEC = importlib.util.spec_from_file_location("pfb_remove_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
pfb_remove = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pfb_remove
SPEC.loader.exec_module(pfb_remove)


class PFBRemoveTests(unittest.TestCase):
    def setUp(self) -> None:
        volume_reader = mock.patch.object(pfb_remove, "_discover_legacy_volumes", return_value=[])
        volume_reader.start()
        self.addCleanup(volume_reader.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.name = "alpha"
        self.flow_root = self.root / ".worktree/alpha"
        self.repositories = [
            {"id": "retrom", "path": "project/retrom"},
            {"id": "retrom-runtime", "path": "project/retrom-runtime"},
        ]
        self.worktrees = {
            str(repo["id"]): self._create_worktree(repo) for repo in self.repositories
        }
        spec = {
            "schemaVersion": 1,
            "name": self.name,
            "id": pfb_remove._pfb_id(self.name),
            "retrom": {
                "root": str(self.worktrees["retrom"]),
                "branch": "feat/alpha-retrom",
            },
            "runtime": {
                "mode": "branch",
                "root": str(self.worktrees["retrom-runtime"]),
                "branch": "feat/alpha-retrom-runtime",
            },
            "cores": [],
        }
        spec_path = self.worktrees["retrom"] / ".pfb/spec.json"
        spec_path.parent.mkdir()
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_confirmed_removal_destroys_pfb_and_preserves_branches(self, _geteuid: mock.Mock) -> None:
        calls = []

        def destroy(retrom_root: Path, name: str, identifier: str) -> None:
            calls.append((retrom_root, name, identifier))
            shutil.rmtree(retrom_root / ".pfb")

        removed = pfb_remove.remove_pfb(
            self.name,
            root=self.root,
            repositories=self.repositories,
            prompt=lambda _message: "y",
            destroy=destroy,
        )

        self.assertTrue(removed)
        self.assertEqual(
            calls,
            [(self.worktrees["retrom"], self.name, pfb_remove._pfb_id(self.name))],
        )
        self.assertFalse(self.flow_root.exists())
        for repo in self.repositories:
            baseline = self.root / str(repo["path"])
            branch = f"feat/alpha-{repo['id']}"
            self.assertEqual(
                self._run("git", "-C", str(baseline), "branch", "--list", branch).stdout.strip(),
                f"{branch}",
            )
            self.assertNotIn(
                str(self.worktrees[str(repo["id"])]),
                self._run("git", "-C", str(baseline), "worktree", "list", "--porcelain").stdout,
            )

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_dirty_worktree_fails_before_prompt_or_destroy(self, _geteuid: mock.Mock) -> None:
        (self.worktrees["retrom-runtime"] / "tracked.txt").write_text(
            "changed\n", encoding="utf-8"
        )
        prompt = mock.Mock(return_value="y")
        destroy = mock.Mock()

        with self.assertRaisesRegex(pfb_remove.PFBRemoveError, "retrom-runtime"):
            pfb_remove.remove_pfb(
                self.name,
                root=self.root,
                repositories=self.repositories,
                prompt=prompt,
                destroy=destroy,
            )

        prompt.assert_not_called()
        destroy.assert_not_called()
        self.assertTrue(self.worktrees["retrom"].exists())
        self.assertTrue(self.worktrees["retrom-runtime"].exists())

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_non_y_confirmation_cancels_without_changes(self, _geteuid: mock.Mock) -> None:
        destroy = mock.Mock()

        removed = pfb_remove.remove_pfb(
            self.name,
            root=self.root,
            repositories=self.repositories,
            prompt=lambda _message: "n",
            destroy=destroy,
        )

        self.assertFalse(removed)
        destroy.assert_not_called()
        self.assertTrue(self.worktrees["retrom"].exists())
        self.assertTrue(self.worktrees["retrom-runtime"].exists())

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_worktree_changed_during_prompt_is_rechecked(self, _geteuid: mock.Mock) -> None:
        destroy = mock.Mock()

        def prompt(_message: str) -> str:
            (self.worktrees["retrom"] / "tracked.txt").write_text(
                "changed while prompting\n", encoding="utf-8"
            )
            return "y"

        with self.assertRaisesRegex(pfb_remove.PFBRemoveError, "retrom"):
            pfb_remove.remove_pfb(
                self.name,
                root=self.root,
                repositories=self.repositories,
                prompt=prompt,
                destroy=destroy,
            )

        destroy.assert_not_called()
        self.assertTrue(self.worktrees["retrom"].exists())
        self.assertTrue(self.worktrees["retrom-runtime"].exists())

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_spec_for_another_identity_is_rejected(self, _geteuid: mock.Mock) -> None:
        spec_path = self.worktrees["retrom"] / ".pfb/spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["id"] = pfb_remove._pfb_id("other")
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        destroy = mock.Mock()

        with self.assertRaisesRegex(pfb_remove.PFBRemoveError, "identity"):
            pfb_remove.remove_pfb(
                self.name,
                root=self.root,
                repositories=self.repositories,
                prompt=lambda _message: "y",
                destroy=destroy,
            )

        destroy.assert_not_called()

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_non_manifest_layout_worktrees_are_validated_and_removed(
        self, _geteuid: mock.Mock
    ) -> None:
        core = self._create_non_manifest_worktree(
            "j2me-web", "project/retrom-core/j2me-web", "feat/alpha-j2me"
        )
        support = self._create_non_manifest_worktree(
            "miniJVM", "project/retrom-other/miniJVM", "feat/alpha-minijvm"
        )
        spec_path = self.worktrees["retrom"] / ".pfb/spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["cores"] = [
            {
                "id": "j2me",
                "mode": "branch",
                "root": str(core),
                "branch": "feat/alpha-j2me",
            }
        ]
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        removed = pfb_remove.remove_pfb(
            self.name,
            root=self.root,
            repositories=self.repositories,
            prompt=lambda _message: "y",
            destroy=lambda retrom_root, _name, _identifier: shutil.rmtree(
                retrom_root / ".pfb"
            ),
        )

        self.assertTrue(removed)
        self.assertFalse(core.exists())
        self.assertFalse(support.exists())
        self.assertFalse(self.flow_root.exists())

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_dirty_non_manifest_worktree_fails_before_destroy(
        self, _geteuid: mock.Mock
    ) -> None:
        support = self._create_non_manifest_worktree(
            "miniJVM", "project/retrom-other/miniJVM", "feat/alpha-minijvm"
        )
        (support / "tracked.txt").write_text("changed\n", encoding="utf-8")
        destroy = mock.Mock()

        with self.assertRaisesRegex(pfb_remove.PFBRemoveError, "retrom-other/miniJVM"):
            pfb_remove.remove_pfb(
                self.name,
                root=self.root,
                repositories=self.repositories,
                prompt=lambda _message: "y",
                destroy=destroy,
            )

        destroy.assert_not_called()
        self.assertTrue(support.exists())

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_missing_spec_recovers_only_after_detached_state_check(
        self, _geteuid: mock.Mock
    ) -> None:
        spec_path = self.worktrees["retrom"] / ".pfb/spec.json"
        spec_path.unlink()
        recovery_check = mock.Mock()
        destroy = mock.Mock(side_effect=lambda root, _name, _identifier: shutil.rmtree(root / ".pfb"))

        removed = pfb_remove.remove_pfb(
            self.name,
            root=self.root,
            repositories=self.repositories,
            prompt=lambda _message: "y",
            destroy=destroy,
            recovery_check=recovery_check,
        )

        self.assertTrue(removed)
        self.assertEqual(
            recovery_check.call_args_list,
            [mock.call(pfb_remove._pfb_id(self.name))] * 2,
        )
        destroy.assert_called_once()
        self.assertFalse(self.flow_root.exists())

    def test_partial_state_removal_handles_read_only_go_cache(self) -> None:
        module = self.worktrees["retrom"] / ".pfb/workspace/go-cache/mod/module@v1"
        module.mkdir(parents=True)
        (module / "module.go").write_text("package module\n", encoding="utf-8")
        module.chmod(0o555)

        pfb_remove._destroy_partial_state(self.worktrees["retrom"])

        self.assertFalse((self.worktrees["retrom"] / ".pfb").exists())

    def test_recovery_registry_is_owned_by_workspace(self) -> None:
        self.assertEqual(
            pfb_remove._registry_path(self.root),
            self.root / ".pfb/registry-v1.json",
        )

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_clean_initialized_submodule_is_deinitialized_before_removal(
        self, _geteuid: mock.Mock
    ) -> None:
        self._add_submodule(self.worktrees["retrom-runtime"])

        removed = pfb_remove.remove_pfb(
            self.name,
            root=self.root,
            repositories=self.repositories,
            prompt=lambda _message: "y",
            destroy=lambda retrom_root, _name, _identifier: shutil.rmtree(
                retrom_root / ".pfb"
            ),
        )

        self.assertTrue(removed)
        self.assertFalse(self.flow_root.exists())

    @mock.patch.object(pfb_remove.os, "geteuid", return_value=1000)
    def test_confirmed_removal_deletes_exact_planned_legacy_volumes(
        self, _geteuid: mock.Mock
    ) -> None:
        identifier = pfb_remove._pfb_id(self.name)
        volumes = [f"retrom-pfb-{identifier}-data-0123456789ab"]
        remove_volumes = mock.Mock()

        removed = pfb_remove.remove_pfb(
            self.name,
            root=self.root,
            repositories=self.repositories,
            prompt=lambda _message: "y",
            destroy=lambda retrom_root, _name, _identifier: shutil.rmtree(
                retrom_root / ".pfb"
            ),
            volume_reader=lambda _identifier: volumes,
            volume_remover=remove_volumes,
        )

        self.assertTrue(removed)
        remove_volumes.assert_called_once_with(identifier, volumes)

    def _create_worktree(self, repo: dict[str, object]) -> Path:
        baseline = self.root / str(repo["path"])
        baseline.mkdir(parents=True)
        self._run("git", "init", "--initial-branch=master", str(baseline))
        self._run("git", "-C", str(baseline), "config", "user.name", "PFB Test")
        self._run(
            "git", "-C", str(baseline), "config", "user.email", "pfb-test@example.invalid"
        )
        (baseline / ".gitignore").write_text(".pfb/\n", encoding="utf-8")
        (baseline / "tracked.txt").write_text("initial\n", encoding="utf-8")
        self._run("git", "-C", str(baseline), "add", ".gitignore", "tracked.txt")
        self._run("git", "-C", str(baseline), "commit", "-m", "initial")
        target = self.flow_root / str(repo["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        branch = f"feat/alpha-{repo['id']}"
        self._run(
            "git",
            "-C",
            str(baseline),
            "worktree",
            "add",
            "-b",
            branch,
            str(target),
            "HEAD",
        )
        return target.resolve()

    def _create_non_manifest_worktree(
        self, name: str, target_relative: str, branch: str
    ) -> Path:
        baseline = self.root / "external" / name
        baseline.mkdir(parents=True)
        self._run("git", "init", "--initial-branch=master", str(baseline))
        self._run("git", "-C", str(baseline), "config", "user.name", "PFB Test")
        self._run(
            "git", "-C", str(baseline), "config", "user.email", "pfb-test@example.invalid"
        )
        (baseline / "tracked.txt").write_text("initial\n", encoding="utf-8")
        self._run("git", "-C", str(baseline), "add", "tracked.txt")
        self._run("git", "-C", str(baseline), "commit", "-m", "initial")
        target = self.flow_root / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            "git", "-C", str(baseline), "worktree", "add", "-b", branch, str(target), "HEAD"
        )
        return target.resolve()

    def _add_submodule(self, worktree: Path) -> None:
        source = self.root / "external/submodule"
        source.mkdir(parents=True)
        self._run("git", "init", "--initial-branch=main", str(source))
        self._run("git", "-C", str(source), "config", "user.name", "PFB Test")
        self._run(
            "git", "-C", str(source), "config", "user.email", "pfb-test@example.invalid"
        )
        (source / "module.txt").write_text("module\n", encoding="utf-8")
        self._run("git", "-C", str(source), "add", "module.txt")
        self._run("git", "-C", str(source), "commit", "-m", "module")
        self._run(
            "git",
            "-c",
            "protocol.file.allow=always",
            "-C",
            str(worktree),
            "submodule",
            "add",
            str(source),
            "vendor/submodule",
        )
        self._run("git", "-C", str(worktree), "commit", "-am", "add submodule")

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(arguments, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
