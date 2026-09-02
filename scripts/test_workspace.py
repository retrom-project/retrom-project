from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("workspace.py")
SPEC = importlib.util.spec_from_file_location("workspace_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


class WorkspaceCloneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.original_root = workspace.ROOT
        workspace.ROOT = self.root

    def tearDown(self) -> None:
        workspace.ROOT = self.original_root
        self.temporary.cleanup()

    def test_shallow_clone_includes_shallow_submodules(self) -> None:
        repository = {
            "id": "sample",
            "path": "project/sample",
            "role": "core",
            "gitlink": "git@example.invalid:sample.git",
            "defaultBranch": "main",
            "submodules": True,
            "shallowClone": True,
            "dependsOn": [],
        }

        with patch.object(workspace.subprocess, "run") as run:
            workspace.clone_missing([repository])

        run.assert_called_once_with(
            [
                "git",
                "clone",
                "--branch",
                "main",
                "--single-branch",
                "--depth",
                "1",
                "--recurse-submodules",
                "--shallow-submodules",
                "git@example.invalid:sample.git",
                str(self.root / "project/sample"),
            ],
            cwd=self.root,
            check=True,
        )


class WorkspaceUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.original_root = workspace.ROOT
        workspace.ROOT = self.root

    def tearDown(self) -> None:
        workspace.ROOT = self.original_root
        self.temporary.cleanup()

    def test_dirty_repository_prevents_every_checkout_switch_and_fetch(self) -> None:
        first, first_publisher, first_repo = self._create_repository("first")
        _, _, second_repo = self._create_repository("second")
        self._git(first_repo, "switch", "-c", "feature/first")
        before_remote = self._git(first_repo, "rev-parse", "refs/remotes/origin/master")
        latest_remote = self._publish(first_publisher, "remote update")
        (second_repo / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")

        with self.assertRaisesRegex(
            workspace.WorkspaceError, "every manifest checkout to be clean"
        ):
            workspace.update_repositories([first, self._repo("second", second_repo)])

        self.assertEqual(self._git(first_repo, "branch", "--show-current"), "feature/first")
        self.assertEqual(
            self._git(first_repo, "rev-parse", "refs/remotes/origin/master"),
            before_remote,
        )
        self.assertNotEqual(before_remote, latest_remote)

    def test_update_switches_to_default_branch_and_fast_forwards(self) -> None:
        repo, publisher, checkout = self._create_repository("sample")
        self._git(checkout, "switch", "-c", "feature/sample")
        latest_remote = self._publish(publisher, "latest")

        workspace.update_repositories([repo])

        self.assertEqual(self._git(checkout, "branch", "--show-current"), "master")
        self.assertEqual(self._git(checkout, "rev-parse", "HEAD"), latest_remote)
        self.assertEqual(self._git(checkout, "status", "--porcelain=v1"), "")

    def test_update_keeps_shallow_submodule_depth(self) -> None:
        repo, publisher, checkout = self._create_repository("sample")
        repo["submodules"] = True
        repo["shallowClone"] = True
        self._publish(publisher, "latest")

        with patch.object(workspace, "run_git", wraps=workspace.run_git) as run_git:
            workspace.update_repositories([repo])

        run_git.assert_any_call(
            checkout,
            "submodule",
            "update",
            "--init",
            "--recursive",
            "--depth",
            "1",
        )

    def test_diverged_default_branch_fails_before_switch(self) -> None:
        repo, publisher, checkout = self._create_repository("sample")
        (checkout / "local.txt").write_text("local\n", encoding="utf-8")
        self._git(checkout, "add", "local.txt")
        self._git(checkout, "commit", "-m", "local default commit")
        self._git(checkout, "switch", "-c", "feature/sample")
        self._publish(publisher, "remote commit")

        with self.assertRaisesRegex(workspace.WorkspaceError, "has diverged"):
            workspace.update_repositories([repo])

        self.assertEqual(self._git(checkout, "branch", "--show-current"), "feature/sample")

    def _create_repository(
        self, name: str
    ) -> tuple[dict[str, object], Path, Path]:
        remote = self.root / "remotes" / f"{name}.git"
        publisher = self.root / "publishers" / name
        checkout = self.root / "project" / name
        remote.parent.mkdir(parents=True, exist_ok=True)
        publisher.parent.mkdir(parents=True, exist_ok=True)
        checkout.parent.mkdir(parents=True, exist_ok=True)
        self._run("git", "init", "--bare", "--initial-branch=master", str(remote))
        self._run("git", "clone", str(remote), str(publisher))
        self._configure(publisher)
        self._publish(publisher, "initial")
        self._run("git", "clone", str(remote), str(checkout))
        self._configure(checkout)
        return self._repo(name, checkout, remote), publisher, checkout

    def _publish(self, publisher: Path, message: str) -> str:
        target = publisher / "history.txt"
        previous = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(previous + message + "\n", encoding="utf-8")
        self._git(publisher, "add", "history.txt")
        self._git(publisher, "commit", "-m", message)
        self._git(publisher, "push", "origin", "master")
        return self._git(publisher, "rev-parse", "HEAD")

    def _repo(
        self, name: str, checkout: Path, remote: Path | None = None
    ) -> dict[str, object]:
        origin = remote or Path(self._git(checkout, "remote", "get-url", "origin"))
        return {
            "id": name,
            "path": str(checkout.relative_to(self.root)),
            "role": "core",
            "gitlink": str(origin),
            "defaultBranch": "master",
            "submodules": False,
            "dependsOn": [],
        }

    def _configure(self, root: Path) -> None:
        self._git(root, "config", "user.name", "Workspace Test")
        self._git(root, "config", "user.email", "workspace-test@example.invalid")

    def _git(self, root: Path, *arguments: str) -> str:
        return self._run("git", "-C", str(root), *arguments).stdout.strip()

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            arguments,
            check=True,
            capture_output=True,
            text=True,
        )


class ManifestTests(unittest.TestCase):
    def test_shallow_clone_must_be_boolean(self) -> None:
        repository = {
            "id": "sample",
            "path": "project/sample",
            "role": "core",
            "gitlink": "git@example.invalid:sample.git",
            "defaultBranch": "main",
            "submodules": True,
            "shallowClone": 1,
            "dependsOn": [],
        }

        with self.assertRaisesRegex(
            workspace.WorkspaceError, "shallowClone must be bool"
        ):
            workspace.validate_repositories([repository])

    def test_clone_links_use_ssh(self) -> None:
        manifest_path = MODULE_PATH.parents[1] / "manifest.yaml"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for repository in manifest["repositories"]:
            with self.subTest(repository=repository["id"]):
                self.assertRegex(repository["gitlink"], r"^git@github\.com:.+\.git$")


if __name__ == "__main__":
    unittest.main()
