#!/usr/bin/env python3
"""Manage the repositories that form a Retrom development workspace."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.yaml"
ALLOWED_ROLES = {"application", "runtime", "core", "support"}


class WorkspaceError(RuntimeError):
    pass


def run_git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_manifest() -> list[dict[str, object]]:
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkspaceError(f"cannot read {MANIFEST}: {error}") from error

    if data.get("schemaVersion") != 1:
        raise WorkspaceError("manifest schemaVersion must be 1")
    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise WorkspaceError("manifest repositories must be a non-empty list")
    validate_repositories(repositories)
    return repositories


def validate_repositories(repositories: list[object]) -> None:
    ids: set[str] = set()
    paths: set[str] = set()

    for index, value in enumerate(repositories):
        if not isinstance(value, dict):
            raise WorkspaceError(f"repositories[{index}] must be an object")
        repo = value
        required = {
            "id": str,
            "path": str,
            "role": str,
            "gitlink": str,
            "defaultBranch": str,
            "submodules": bool,
            "dependsOn": list,
        }
        for field, expected_type in required.items():
            if field not in repo or not isinstance(repo[field], expected_type):
                raise WorkspaceError(
                    f"repositories[{index}].{field} must be {expected_type.__name__}"
                )

        repo_id = str(repo["id"])
        repo_path = str(repo["path"])
        if not repo_id or repo_id in ids:
            raise WorkspaceError(f"duplicate or empty repository id: {repo_id!r}")
        if not repo_path or repo_path in paths:
            raise WorkspaceError(f"duplicate or empty repository path: {repo_path!r}")
        ids.add(repo_id)
        paths.add(repo_path)

        relative = Path(repo_path)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("project",):
            raise WorkspaceError(f"repository path must stay under project/: {repo_path}")
        if str(repo["role"]) not in ALLOWED_ROLES:
            raise WorkspaceError(f"unsupported role for {repo_id}: {repo['role']}")
        if not str(repo["gitlink"]).strip() or not str(repo["defaultBranch"]).strip():
            raise WorkspaceError(f"gitlink and defaultBranch are required for {repo_id}")
        dependencies = repo["dependsOn"]
        if any(not isinstance(item, str) or not item for item in dependencies):
            raise WorkspaceError(f"dependsOn must contain repository ids for {repo_id}")

    by_id = {str(repo["id"]): repo for repo in repositories if isinstance(repo, dict)}
    for repo_id, repo in by_id.items():
        unknown = set(repo["dependsOn"]) - set(by_id)
        if unknown:
            raise WorkspaceError(f"unknown dependencies for {repo_id}: {sorted(unknown)}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(repo_id: str) -> None:
        if repo_id in visiting:
            raise WorkspaceError(f"dependency cycle includes {repo_id}")
        if repo_id in visited:
            return
        visiting.add(repo_id)
        for dependency in by_id[repo_id]["dependsOn"]:
            visit(str(dependency))
        visiting.remove(repo_id)
        visited.add(repo_id)

    for repo_id in by_id:
        visit(repo_id)


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


def validate_checkout(repo: dict[str, object]) -> Path:
    path = ROOT / str(repo["path"])
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
        if repo["submodules"]:
            command.append("--recurse-submodules")
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

    for repo, path in checkouts:
        branch = str(repo["defaultBranch"])
        remote_ref = f"refs/remotes/origin/{branch}"
        refspec = f"+refs/heads/{branch}:{remote_ref}"
        print(f"fetch  {repo['id']:<28} origin/{branch}")
        run_git(path, "fetch", "--prune", "origin", refspec)
        run_git(path, "rev-parse", "--verify", remote_ref)

    for repo, path in checkouts:
        branch = str(repo["defaultBranch"])
        _validate_default_branch_update(path, branch)

    for repo, path in checkouts:
        branch = str(repo["defaultBranch"])
        remote_ref = f"refs/remotes/origin/{branch}"
        if _local_branch_exists(path, branch):
            run_git(path, "switch", branch)
        else:
            run_git(path, "switch", "--track", "-c", branch, remote_ref)
        run_git(path, "merge", "--ff-only", remote_ref)
        if repo["submodules"]:
            run_git(path, "submodule", "sync", "--recursive")
            run_git(path, "submodule", "update", "--init", "--recursive")
        head = run_git(path, "rev-parse", "--short=10", "HEAD").stdout.strip()
        print(f"update {repo['id']:<28} {branch} {head}")


def _validate_default_branch_update(path: Path, branch: str) -> None:
    if not _local_branch_exists(path, branch):
        return
    target_ref = f"refs/heads/{branch}"
    for worktree, checked_out_ref in _worktree_branches(path):
        if checked_out_ref == target_ref and worktree.resolve() != path.resolve():
            raise WorkspaceError(
                f"default branch {branch} is checked out in another worktree: {worktree}"
            )

    remote_ref = f"refs/remotes/origin/{branch}"
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        repositories = load_manifest()
        if args.command == "validate":
            print(f"manifest valid: {len(repositories)} repositories")
        elif args.command == "init":
            clone_missing(repositories)
        elif args.command == "check":
            check_workspace(repositories)
        elif args.command == "update":
            update_repositories(repositories)
        elif args.command == "status":
            show_status(repositories)
    except (WorkspaceError, subprocess.CalledProcessError) as error:
        print(f"workspace error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
