"""Local-only Git fixtures for the two-stage workspace commands."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workspace


class SourceCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = workspace.ROOT / "project/retrom/workspace/catalog.py"
        self.w = workspace
        patcher = patch.object(workspace, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.runtime = self.repository("retrom-runtime", "runtime")
        self.app = self.repository("retrom", "application")
        pub = self.publisher(self.app)
        (pub / "workspace").mkdir()
        shutil.copyfile(self.catalog, pub / "workspace/catalog.py")
        self.publish_catalog([self.runtime])
        (self.root / "manifest.yaml").write_text(json.dumps({
            "schemaVersion": 2, "dependencyManifest": "workspace/manifest.yaml",
            "repositories": [self.app],
        }))

    def git(self, path, *args):
        return subprocess.run(["git", "-C", str(path), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def publisher(self, repo):
        return self.root / "publishers" / repo["id"]

    def checkout(self, repo):
        return self.root / repo["path"]

    def repository(self, name, role="core"):
        remote = self.root / "remotes" / (name + ".git")
        publisher = self.root / "publishers" / name
        remote.mkdir(parents=True)
        publisher.mkdir(parents=True)
        self.git(remote, "init", "--bare", "--initial-branch=master")
        self.git(publisher, "init", "--initial-branch=master")
        self.git(publisher, "config", "user.name", "Workspace Test")
        self.git(publisher, "config", "user.email", "test@example.invalid")
        self.git(publisher, "remote", "add", "origin", str(remote))
        (publisher / "file.txt").write_text("initial\n")
        self.git(publisher, "add", ".")
        self.git(publisher, "commit", "-m", "initial")
        self.git(publisher, "push", "origin", "master")
        group = "retrom-core/" if role == "core" else "retrom-other/" if role == "support" else ""
        return {"id": name, "path": f"project/{group}{name}", "role": role,
                "gitlink": str(remote), "defaultBranch": "master", "submodules": False, "dependsOn": []}

    def publish_catalog(self, repositories):
        pub = self.publisher(self.app)
        self.write_catalog(pub, repositories)
        self.git(pub, "add", ".")
        self.git(pub, "commit", "-m", "catalog")
        self.git(pub, "push", "origin", "master")
        return self.git(pub, "rev-parse", "HEAD")

    def write_catalog(self, retrom, repositories):
        repositories = copy.deepcopy(repositories)
        if repositories:
            repositories[0]["dependsOn"] = [repo["id"] for repo in repositories[1:]]
        (retrom / "workspace/manifest.yaml").write_text(json.dumps({
            "schemaVersion": 1, "repositories": repositories,
        }))

    def initialize(self, name=None, ids=None):
        import workspace_sources
        scope = self.root / ".worktree" / name if name else self.root
        workspace_sources.initialize(self.w, scope, scope / "project/retrom", ids)
        return scope
