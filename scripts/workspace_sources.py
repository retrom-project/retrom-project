"""Serialized source preparation for baseline and PFB worktrees."""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path

import workspace_config as config


@contextmanager
def locked(root: Path):
    if os.geteuid() == 0:
        raise config.WorkspaceError("source initialization/update must run as the current non-root user")
    directory = root / ".pfb"
    directory.mkdir(exist_ok=True, mode=0o700)
    with (directory / "sources.lock").open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def selected(repositories: list[dict], ids: list[str] | None) -> list[dict]:
    if ids is None:
        return repositories
    unknown = set(ids) - {repo["id"] for repo in repositories}
    if unknown:
        raise config.WorkspaceError(f"unknown repository IDs: {sorted(unknown)}")
    return [repo for repo in repositories if repo["id"] in {"retrom", *ids}]


def initialize(w, scope: Path, retrom: Path, ids: list[str] | None) -> None:
    application, _ = config.bootstrap(w.ROOT)
    w.clone_missing([application])
    if scope != w.ROOT:
        prepare_worktree(w, scope, application)
    repositories = selected(w.load_manifest(retrom), ids)
    print(f"manifest: {retrom / 'workspace/manifest.yaml'}")
    w.clone_missing(repositories)
    if scope != w.ROOT:
        for repo in repositories[1:]:
            prepare_worktree(w, scope, repo)


def prepare_worktree(w, scope: Path, repo: dict) -> None:
    owner = w.validate_checkout(repo)
    target = scope / repo["path"]
    prefix = "feat" if repo["role"] in {"core", "support"} else "codex"
    branch = f"{prefix}/{scope.name}"
    if target.exists():
        w.validate_checkout(repo, scope)
        owner_common = w.run_git(owner, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
        target_common = w.run_git(target, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
        if owner_common != target_common:
            raise config.WorkspaceError(f"PFB worktree has a different owner: {target}")
        # Existing branches are owned by the PFB and may have an explicitly chosen name.
        if w.run_git(target, "symbolic-ref", "--quiet", "HEAD", check=False).returncode:
            raise config.WorkspaceError(f"PFB worktree is detached: {target}")
        return
    commit = w.fetch_default(repo, owner)
    target.parent.mkdir(parents=True, exist_ok=True)
    w.run_git(owner, "worktree", "add", "-b", branch, str(target), commit)
    w.initialize_submodules(repo, target)
    print(f"worktree {repo['id']:<26} {target} {branch} {commit}")


def status(w, scope: Path, repositories: list[dict]) -> None:
    print(f"{'repository':<29} {'branch':<34} {'HEAD':<12} state")
    for repo in repositories:
        if not (scope / repo["path"]).exists():
            print(f"{repo['id']:<29} {'-':<34} {'-':<12} missing")
            continue
        path = w.validate_checkout(repo, scope)
        branch = w.run_git(path, "branch", "--show-current").stdout.strip() or "(detached)"
        head = w.run_git(path, "rev-parse", "--short=10", "HEAD").stdout.strip()
        state = "dirty" if w.run_git(path, "status", "--porcelain=v1").stdout else "clean"
        print(f"{repo['id']:<29} {branch:<34} {head:<12} {state}")
