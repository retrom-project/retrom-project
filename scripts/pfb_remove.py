#!/usr/bin/env python3
"""Destroy one PFB and remove its clean Git worktrees."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from workspace import WorkspaceError, load_manifest, run_git


ROOT = Path(__file__).resolve().parents[1]
CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f-\x9f]")
NON_SLUG = re.compile(r"[^a-z0-9]+")
PFB_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,22}[a-z0-9])?$")


class PFBRemoveError(RuntimeError):
    pass


@dataclass(frozen=True)
class Worktree:
    repository: str
    baseline: Path
    path: Path
    branch: str


def remove_pfb(
    name: str,
    *,
    root: Path = ROOT,
    repositories: list[dict[str, object]] | None = None,
    prompt: Callable[[str], str] | None = None,
    destroy: Callable[[Path, str, str], None] | None = None,
) -> bool:
    if os.geteuid() == 0:
        raise PFBRemoveError("PFB commands must run as the current non-root user; do not use sudo")

    workspace_root = _flow_root(root, name)
    repositories = repositories if repositories is not None else load_manifest()
    worktrees = _discover_worktrees(root, workspace_root, repositories)
    retrom_root = workspace_root / "project/retrom"
    if not any(item.path == retrom_root for item in worktrees):
        raise PFBRemoveError(f"missing Retrom worktree: {retrom_root}")

    spec = _load_spec(retrom_root, name)
    identifier = str(spec["id"])
    _validate_spec_roots(spec, retrom_root, worktrees)
    _require_all_clean(worktrees)
    _print_plan(name, identifier, worktrees)

    ask = prompt or input
    try:
        answer = ask("Type y to destroy this PFB and remove these worktrees: ")
    except EOFError:
        answer = ""
    if answer.strip().lower() != "y":
        print("PFB removal cancelled")
        return False

    # Recheck after the interactive pause and before the first destructive action.
    _require_all_clean(worktrees)
    destroy_action = destroy or _destroy_pfb
    destroy_action(retrom_root, name, identifier)

    removed: list[Worktree] = []
    for item in sorted(worktrees, key=lambda value: value.repository == "retrom"):
        try:
            run_git(item.baseline, "worktree", "remove", str(item.path))
        except subprocess.CalledProcessError as error:
            raise PFBRemoveError(
                f"PFB state was destroyed, but worktree removal failed for "
                f"{item.repository}: {_git_error(error)}"
            ) from error
        removed.append(item)

    _remove_empty_scaffolding(workspace_root)
    print(f"removed PFB {name} ({identifier})")
    for item in removed:
        print(f"remove {item.repository:<28} {item.path} (branch preserved: {item.branch})")
    if workspace_root.exists():
        print(f"kept non-empty PFB directory: {workspace_root}")
    return True


def _flow_root(root: Path, name: str) -> Path:
    if not name:
        raise PFBRemoveError("PFB is required; use make pfb-remove PFB=<name>")
    if name in {".", ".."} or Path(name).name != name:
        raise PFBRemoveError(f"PFB must be a single directory name: {name!r}")
    worktree_root = (root / ".worktree").resolve(strict=False)
    candidate = worktree_root / name
    if candidate.is_symlink():
        raise PFBRemoveError(f"PFB workspace cannot be a symlink: {candidate}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise PFBRemoveError(f"PFB workspace does not exist: {candidate}") from error
    if resolved.parent != worktree_root:
        raise PFBRemoveError(f"PFB must name a direct child of {worktree_root}: {name!r}")
    if not resolved.is_dir():
        raise PFBRemoveError(f"PFB workspace is not a directory: {resolved}")
    return resolved


def _discover_worktrees(
    root: Path,
    workspace_root: Path,
    repositories: list[dict[str, object]],
) -> list[Worktree]:
    result = []
    for repo in repositories:
        repository = str(repo["id"])
        relative = Path(str(repo["path"]))
        baseline = (root / relative).resolve(strict=False)
        candidate = workspace_root / relative
        if candidate.is_symlink():
            raise PFBRemoveError(f"worktree cannot be a symlink: {candidate}")
        if not candidate.exists():
            continue
        if not candidate.is_dir():
            raise PFBRemoveError(f"worktree path is not a directory: {candidate}")

        _require_git_toplevel(baseline, repository, "baseline")
        _require_git_toplevel(candidate, repository, "PFB")
        if _git_common_dir(baseline) != _git_common_dir(candidate):
            raise PFBRemoveError(
                f"PFB worktree does not belong to its manifest baseline {repository}: {candidate}"
            )
        registered = _registered_worktrees(baseline)
        if candidate not in registered:
            raise PFBRemoveError(f"unregistered Git worktree for {repository}: {candidate}")
        branch = run_git(
            candidate, "symbolic-ref", "--quiet", "--short", "HEAD", check=False
        ).stdout.strip() or "(detached)"
        result.append(Worktree(repository, baseline, candidate, branch))
    return result


def _require_git_toplevel(path: Path, repository: str, kind: str) -> None:
    if not path.is_dir():
        raise PFBRemoveError(f"missing {kind} checkout for {repository}: {path}")
    completed = run_git(path, "rev-parse", "--show-toplevel", check=False)
    if completed.returncode != 0:
        raise PFBRemoveError(f"not a Git checkout for {repository}: {path}")
    if Path(completed.stdout.strip()).resolve() != path:
        raise PFBRemoveError(f"Git checkout is not rooted at {path}")


def _git_common_dir(path: Path) -> Path:
    completed = run_git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(completed.stdout.strip()).resolve()


def _registered_worktrees(path: Path) -> set[Path]:
    result = set()
    for line in run_git(path, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            result.add(Path(line.removeprefix("worktree ")).resolve())
    return result


def _load_spec(retrom_root: Path, name: str) -> dict[str, object]:
    path = retrom_root / ".pfb/spec.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PFBRemoveError(f"cannot read initialized PFB spec {path}: {error}") from error
    expected_id = _pfb_id(name)
    if (
        not isinstance(value, dict)
        or value.get("schemaVersion") != 1
        or value.get("name") != name
        or value.get("id") != expected_id
    ):
        raise PFBRemoveError(f"PFB spec identity does not match {name!r}: {path}")
    retrom = value.get("retrom")
    if not isinstance(retrom, dict) or not isinstance(retrom.get("root"), str):
        raise PFBRemoveError(f"PFB spec has no valid Retrom root: {path}")
    if Path(str(retrom["root"])).resolve() != retrom_root:
        raise PFBRemoveError(f"PFB spec points at a different Retrom worktree: {path}")
    return value


def _pfb_id(name: str) -> str:
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PFBRemoveError(f"invalid PFB name: {name!r}") from error
    if not 1 <= len(encoded) <= 128 or CONTROL_OR_SPACE.search(name):
        raise PFBRemoveError(f"invalid PFB name: {name!r}")
    suffix = hashlib.sha256(encoded).hexdigest()[:12]
    slug = NON_SLUG.sub("-", name.lower()).strip("-") or "pfb"
    slug = slug[:11].rstrip("-") or "pfb"
    value = f"{slug}-{suffix}"
    if PFB_ID.fullmatch(value) is None:
        raise PFBRemoveError(f"invalid PFB id derived from {name!r}")
    return value


def _validate_spec_roots(
    spec: dict[str, object], retrom_root: Path, worktrees: list[Worktree]
) -> None:
    known = {item.path for item in worktrees}
    expected_roots = {retrom_root}
    runtime = spec.get("runtime")
    if isinstance(runtime, dict) and runtime.get("mode") == "branch":
        expected_roots.add(_branch_root(runtime, "runtime"))
    cores = spec.get("cores")
    if not isinstance(cores, list):
        raise PFBRemoveError("PFB spec has no valid cores list")
    for index, core in enumerate(cores):
        if not isinstance(core, dict):
            raise PFBRemoveError(f"PFB spec core {index} is invalid")
        expected_roots.add(_branch_root(core, f"core {index}"))
    unknown = expected_roots - known
    if unknown:
        raise PFBRemoveError(
            "PFB spec references worktrees outside the manifest inventory: "
            + ", ".join(str(path) for path in sorted(unknown, key=str))
        )


def _branch_root(value: dict[str, object], label: str) -> Path:
    root = value.get("root")
    if not isinstance(root, str):
        raise PFBRemoveError(f"PFB spec {label} has no valid root")
    return Path(root).resolve()


def _require_all_clean(worktrees: list[Worktree]) -> None:
    dirty = []
    for item in worktrees:
        completed = run_git(
            item.path,
            "status",
            "--porcelain=v1",
            "-z",
            "--ignore-submodules=none",
        )
        if completed.stdout:
            dirty.append(f"{item.repository} ({item.path})")
    if dirty:
        raise PFBRemoveError(
            "all PFB worktrees must be clean before removal; dirty: " + ", ".join(dirty)
        )


def _print_plan(name: str, identifier: str, worktrees: list[Worktree]) -> None:
    print(f"PFB: {name}")
    print(f"PFB ID: {identifier}")
    print("Clean worktrees to remove:")
    for item in worktrees:
        print(f"  {item.repository:<28} {item.path} [{item.branch}]")
    print("PFB containers, volumes, registry state and generated .pfb data will also be removed.")
    print("Git branches and the shared gateway will be preserved.")


def _destroy_pfb(retrom_root: Path, name: str, identifier: str) -> None:
    completed = subprocess.run(
        [
            "make",
            "-C",
            str(retrom_root),
            "pfb-destroy",
            f"PFB={name}",
            f"CONFIRM={identifier}",
        ],
        check=False,
    )
    if completed.returncode != 0:
        raise PFBRemoveError(
            f"Retrom pfb-destroy failed with exit code {completed.returncode}; no worktrees were removed"
        )


def _remove_empty_scaffolding(workspace_root: Path) -> None:
    directories = [path for path in workspace_root.rglob("*") if path.is_dir() and not path.is_symlink()]
    for path in sorted(directories, key=lambda value: len(value.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass
    try:
        workspace_root.rmdir()
    except OSError:
        pass


def _git_error(error: subprocess.CalledProcessError) -> str:
    stderr = error.stderr.strip() if isinstance(error.stderr, str) else ""
    return stderr or f"git exited with {error.returncode}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pfb", required=True, help="logical PFB name")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        remove_pfb(args.pfb)
    except (PFBRemoveError, WorkspaceError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = _git_error(error)
        else:
            message = str(error)
        print(f"pfb-remove error: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
