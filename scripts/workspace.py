#!/usr/bin/env python3
"""Manage the repositories that form a Retrom development workspace."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import workspace_config as config

ROOT = Path(__file__).resolve().parents[1]

WorkspaceError = config.WorkspaceError


def run_git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def load_manifest(retrom_root: Path | None = None, *, root: Path | None = None) -> list[dict[str, object]]:
    return config.load_manifest(root or ROOT, retrom_root)


def validate_repositories(repositories: list[object]) -> None:
    try:
        config.catalog(ROOT / "project/retrom").validate_repositories(repositories)
    except ValueError as error:
        raise WorkspaceError(str(error)) from error


def normalize_git_url(url: str) -> str:
    value = url.strip().rstrip("/")
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        value = f"{host}/{path}"
    elif "://" in value:
        parsed = urlparse(value)
        value = f"{parsed.hostname or ''}/{parsed.path.lstrip('/')}"
    if value.endswith(".git"):
        value = value[:-4]
    return value.lower()


def validate_checkout(repo: dict[str, object], root: Path | None = None) -> Path:
    path = (root or ROOT) / str(repo["path"])
    if not path.exists():
        raise WorkspaceError(f"missing checkout {repo['id']}: {path}")
    result = run_git(path, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise WorkspaceError(f"not a Git checkout {repo['id']}: {path}")
    if Path(result.stdout.strip()).resolve() != path.resolve():
        raise WorkspaceError(f"checkout is not rooted at the declared path {repo['id']}: {path}")
    origin = run_git(path, "remote", "get-url", "origin", check=False)
    if origin.returncode != 0:
        raise WorkspaceError(f"checkout has no origin remote {repo['id']}: {path}")
    if normalize_git_url(origin.stdout) != normalize_git_url(str(repo["gitlink"])):
        raise WorkspaceError(
            f"origin mismatch for {repo['id']}: {origin.stdout.strip()} != {repo['gitlink']}"
        )
    return path


def clone_missing(repositories: list[dict[str, object]]) -> None:
    for repo in repositories:
        path = ROOT / str(repo["path"])
        if path.exists():
            validate_checkout(repo)
            print(f"ready  {repo['id']:<28} {repo['path']}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "git",
            "clone",
            "--branch",
            str(repo["defaultBranch"]),
            "--single-branch",
        ]
        if repo.get("shallowClone", False):
            command.extend(["--depth", "1"])
        if repo["submodules"]:
            command.append("--recurse-submodules")
            if repo.get("shallowClone", False):
                command.append("--shallow-submodules")
        command.extend([str(repo["gitlink"]), str(path)])
        print(f"clone  {repo['id']:<28} {repo['gitlink']}")
        subprocess.run(command, cwd=ROOT, check=True)


def check_workspace(repositories: list[dict[str, object]]) -> None:
    for repo in repositories:
        path = validate_checkout(repo)
        print(f"ready  {repo['id']:<28} {path.relative_to(ROOT)}")


def update_repositories(repositories: list[dict[str, object]]) -> None:
    checkouts = [(repo, validate_checkout(repo)) for repo in repositories]
    dirty = [
        f"{repo['id']} ({path.relative_to(ROOT)})"
        for repo, path in checkouts
        if run_git(path, "status", "--porcelain=v1", "-z").stdout
    ]
    if dirty:
        raise WorkspaceError(
            "make update requires every manifest checkout to be clean; dirty: "
            + ", ".join(dirty)
        )

    targets = [(repo, path, fetch_default(repo, path)) for repo, path in checkouts]
    for repo, path, commit in targets:
        _validate_default_branch_update(path, str(repo["defaultBranch"]), commit)
    for repo, path, commit in targets:
        apply_default(repo, path, commit)


def fetch_default(repo: dict[str, object], path: Path) -> str:
    branch = str(repo["defaultBranch"])
    remote_ref = f"refs/remotes/origin/{branch}"
    print(f"fetch  {repo['id']:<28} origin/{branch}")
    run_git(path, "fetch", "--prune", "origin", f"+refs/heads/{branch}:{remote_ref}")
    return run_git(path, "rev-parse", "--verify", remote_ref).stdout.strip()


def apply_default(repo: dict[str, object], path: Path, commit: str) -> None:
    branch = str(repo["defaultBranch"])
    if _local_branch_exists(path, branch):
        run_git(path, "switch", branch)
    else:
        run_git(path, "branch", branch, commit)
        run_git(path, "branch", "--set-upstream-to", f"origin/{branch}", branch)
        run_git(path, "switch", branch)
    run_git(path, "merge", "--ff-only", commit)
    initialize_submodules(repo, path)
    head = run_git(path, "rev-parse", "--short=10", "HEAD").stdout.strip()
    print(f"update {repo['id']:<28} {branch} {head}")


def initialize_submodules(repo: dict[str, object], path: Path) -> None:
    if repo["submodules"]:
        run_git(path, "submodule", "sync", "--recursive")
        args = ["submodule", "update", "--init", "--recursive"]
        if repo.get("shallowClone", False):
            args.extend(["--depth", "1"])
        run_git(path, *args)


def _validate_default_branch_update(path: Path, branch: str, commit: str | None = None) -> None:
    if not _local_branch_exists(path, branch):
        return
    target_ref = f"refs/heads/{branch}"
    for worktree, checked_out_ref in _worktree_branches(path):
        if checked_out_ref == target_ref and worktree.resolve() != path.resolve():
            raise WorkspaceError(
                f"default branch {branch} is checked out in another worktree: {worktree}"
            )

    remote_ref = commit or f"refs/remotes/origin/{branch}"
    local_is_ancestor = run_git(
        path, "merge-base", "--is-ancestor", target_ref, remote_ref, check=False
    ).returncode == 0
    remote_is_ancestor = run_git(
        path, "merge-base", "--is-ancestor", remote_ref, target_ref, check=False
    ).returncode == 0
    if not local_is_ancestor and not remote_is_ancestor:
        raise WorkspaceError(
            f"default branch has diverged from origin/{branch}: {path.relative_to(ROOT)}"
        )


def _local_branch_exists(path: Path, branch: str) -> bool:
    return run_git(
        path, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False
    ).returncode == 0


def _worktree_branches(path: Path) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    worktree: Path | None = None
    for line in run_git(path, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            worktree = Path(line.removeprefix("worktree "))
        elif line.startswith("branch ") and worktree is not None:
            result.append((worktree, line.removeprefix("branch ")))
    return result


def show_status(repositories: list[dict[str, object]]) -> None:
    print(f"{'repository':<29} {'branch':<34} {'HEAD':<12} state")
    for repo in repositories:
        path = ROOT / str(repo["path"])
        if not path.exists():
            print(f"{str(repo['id']):<29} {'-':<34} {'-':<12} missing")
            continue
        path = validate_checkout(repo)
        branch = run_git(path, "branch", "--show-current").stdout.strip() or "(detached)"
        head = run_git(path, "rev-parse", "--short=10", "HEAD").stdout.strip()
        dirty = bool(run_git(path, "status", "--porcelain=v1").stdout)
        print(f"{str(repo['id']):<29} {branch:<34} {head:<12} {'dirty' if dirty else 'clean'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("validate", "init", "check", "update", "status"),
        help="operation to perform",
    )
    parser.add_argument("--pfb")
    parser.add_argument("--retrom-dir")
    parser.add_argument("--repos", nargs="+", help="exact repository IDs to prepare/check; no implicit dependency expansion")
    return parser.parse_args()


def main() -> int:
    import workspace_sources as sources
    import workspace_update as updates

    args = parse_args()
    try:
        scope, retrom = config.context(ROOT, args.pfb, args.retrom_dir)
        if args.command == "update" and (scope != ROOT or args.repos):
            raise WorkspaceError("update is baseline-only and requires the complete manifest")
        if args.command in {"init", "update"}:
            with sources.locked(ROOT):
                if args.command == "init":
                    sources.initialize(sys.modules[__name__], scope, retrom, args.repos)
                else:
                    updates.update_workspace(sys.modules[__name__])
            return 0
        repositories = sources.selected(load_manifest(retrom), args.repos)
        print(f"manifest: {retrom / 'workspace/manifest.yaml'}")
        if args.command == "validate":
            print(f"manifest valid: {len(repositories)} repositories")
        elif args.command == "check":
            for repo in repositories:
                print(f"ready  {repo['id']:<28} {validate_checkout(repo, scope)}")
        elif args.command == "status":
            sources.status(sys.modules[__name__], scope, repositories)
    except (WorkspaceError, subprocess.CalledProcessError, OSError, ValueError) as error:
        print(f"workspace error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
