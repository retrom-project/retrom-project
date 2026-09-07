#!/usr/bin/env python3
"""Destroy one PFB and remove its clean Git worktrees."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
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
    recovery_check: Callable[[str], None] | None = None,
    volume_reader: Callable[[str], list[str]] | None = None,
    volume_remover: Callable[[str, list[str]], None] | None = None,
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
    identifier = str(spec["id"]) if spec is not None else _pfb_id(name)
    if spec is not None:
        _validate_spec_roots(spec, retrom_root, worktrees)
    else:
        (recovery_check or _require_detached_partial_state)(identifier)
    legacy_volumes = (volume_reader or _discover_legacy_volumes)(identifier)
    _require_all_clean(worktrees)
    _print_plan(
        name,
        identifier,
        worktrees,
        legacy_volumes,
        recovering=spec is None,
    )

    ask = prompt or input
    try:
        answer = ask("Type y to destroy this PFB, its persistent data/cache, and remove these worktrees: ")
    except EOFError:
        answer = ""
    if answer.strip().lower() != "y":
        print("PFB removal cancelled")
        return False

    # Recheck after the interactive pause and before the first destructive action.
    _require_all_clean(worktrees)
    if spec is None:
        (recovery_check or _require_detached_partial_state)(identifier)
    if volume_remover is None:
        _require_legacy_volume_plan(identifier, legacy_volumes)
    if destroy is not None:
        destroy(retrom_root, name, identifier)
    elif spec is None:
        _destroy_partial_state(retrom_root)
    else:
        _destroy_pfb(retrom_root, name, identifier)
    (volume_remover or _remove_legacy_volumes)(identifier, legacy_volumes)

    removed: list[Worktree] = []
    for item in sorted(worktrees, key=lambda value: value.repository == "retrom"):
        _deinitialize_submodules(item)
        _remove_worktree(item)
        removed.append(item)

    _remove_empty_scaffolding(workspace_root)
    print(f"removed PFB {name} ({identifier})")
    for item in removed:
        print(f"remove {item.repository:<28} {item.path} (branch preserved: {item.branch})")
    if workspace_root.exists():
        print(f"kept non-empty PFB directory: {workspace_root}")
    return True


def _deinitialize_submodules(item: Worktree) -> None:
    try:
        run_git(item.path, "submodule", "deinit", "--all")
    except subprocess.CalledProcessError as error:
        raise PFBRemoveError(
            f"PFB state was destroyed, but clean submodule deinitialization failed for "
            f"{item.repository}: {_git_error(error)}"
        ) from error


def _remove_worktree(item: Worktree) -> None:
    _require_all_clean([item])
    try:
        run_git(item.baseline, "worktree", "remove", str(item.path))
        return
    except subprocess.CalledProcessError as error:
        if "working trees containing submodules cannot be moved or removed" not in _git_error(error):
            raise PFBRemoveError(
                f"PFB state was destroyed, but worktree removal failed for "
                f"{item.repository}: {_git_error(error)}"
            ) from error
    _require_all_clean([item])
    try:
        run_git(item.baseline, "worktree", "remove", "--force", str(item.path))
    except subprocess.CalledProcessError as error:
        raise PFBRemoveError(
            f"PFB state was destroyed, but clean submodule worktree removal failed for "
            f"{item.repository}: {_git_error(error)}"
        ) from error


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
    manifest = {Path(str(repo["path"])): repo for repo in repositories}
    result = []
    for relative, candidate in _worktree_candidates(workspace_root, manifest):
        if candidate.is_symlink():
            raise PFBRemoveError(f"worktree cannot be a symlink: {candidate}")
        if not candidate.is_dir():
            raise PFBRemoveError(f"worktree path is not a directory: {candidate}")

        repo = manifest.get(relative)
        repository = str(repo["id"]) if repo is not None else _layout_label(relative)
        _require_git_toplevel(candidate, repository, "PFB")
        if repo is not None:
            baseline = _manifest_baseline(root, repo, candidate, repository)
        else:
            baseline = _external_baseline(candidate, workspace_root, repository)
        registered = _registered_worktrees(candidate)
        if candidate not in registered:
            raise PFBRemoveError(f"unregistered Git worktree for {repository}: {candidate}")
        branch = run_git(
            candidate, "symbolic-ref", "--quiet", "--short", "HEAD", check=False
        ).stdout.strip() or "(detached)"
        result.append(Worktree(repository, baseline, candidate, branch))
    return result


def _worktree_candidates(
    workspace_root: Path, manifest: dict[Path, dict[str, object]]
) -> list[tuple[Path, Path]]:
    candidates = {
        relative: workspace_root / relative
        for relative in manifest
        if (workspace_root / relative).exists() or (workspace_root / relative).is_symlink()
    }
    project_root = workspace_root / "project"
    for relative in (Path("project/retrom"), Path("project/retrom-runtime")):
        candidate = workspace_root / relative
        if candidate.exists() or candidate.is_symlink():
            candidates[relative] = candidate
    for group_name in ("retrom-core", "retrom-other"):
        group = project_root / group_name
        if group.is_symlink():
            raise PFBRemoveError(f"PFB repository group cannot be a symlink: {group}")
        if not group.is_dir():
            continue
        for candidate in group.iterdir():
            if candidate.is_symlink():
                raise PFBRemoveError(f"worktree cannot be a symlink: {candidate}")
            if candidate.is_dir() and (candidate / ".git").exists():
                candidates[candidate.relative_to(workspace_root)] = candidate
    return sorted(candidates.items(), key=lambda item: str(item[0]))


def _layout_label(relative: Path) -> str:
    try:
        return relative.relative_to("project").as_posix()
    except ValueError as error:
        raise PFBRemoveError(
            f"non-manifest worktree is outside the PFB project layout: {relative}"
        ) from error


def _manifest_baseline(
    root: Path,
    repo: dict[str, object],
    candidate: Path,
    repository: str,
) -> Path:
    baseline = (root / Path(str(repo["path"]))).resolve(strict=False)
    _require_git_toplevel(baseline, repository, "baseline")
    if _git_common_dir(baseline) != _git_common_dir(candidate):
        raise PFBRemoveError(
            f"PFB worktree does not belong to its manifest baseline {repository}: {candidate}"
        )
    return baseline


def _external_baseline(candidate: Path, workspace_root: Path, repository: str) -> Path:
    common = _git_common_dir(candidate)
    for checkout in _registered_worktrees(candidate):
        if (
            checkout == candidate
            or checkout.is_relative_to(workspace_root)
            or not checkout.is_dir()
        ):
            continue
        completed = run_git(checkout, "rev-parse", "--show-toplevel", check=False)
        if completed.returncode != 0 or Path(completed.stdout.strip()).resolve() != checkout:
            continue
        if _git_common_dir(checkout) == common:
            return checkout
    raise PFBRemoveError(
        f"non-manifest PFB worktree has no registered owner checkout outside this PFB: "
        f"{repository} ({candidate})"
    )


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


def _load_spec(retrom_root: Path, name: str) -> dict[str, object] | None:
    path = retrom_root / ".pfb/spec.json"
    if path.is_symlink():
        raise PFBRemoveError(f"initialized PFB spec cannot be a symlink: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise PFBRemoveError(f"initialized PFB spec is not a file: {path}")
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
            "PFB spec references worktrees outside the discovered PFB inventory: "
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


def _print_plan(
    name: str,
    identifier: str,
    worktrees: list[Worktree],
    legacy_volumes: list[str],
    *,
    recovering: bool,
) -> None:
    print(f"PFB: {name}")
    print(f"PFB ID: {identifier}")
    if recovering:
        print("Recovery: spec is absent and no matching registry entry or container remains")
    print("Clean worktrees to remove:")
    for item in worktrees:
        print(f"  {item.repository:<28} {item.path} [{item.branch}]")
    if legacy_volumes:
        print("Legacy volumes to remove:")
        for volume in legacy_volumes:
            print(f"  {volume}")
    print(
        "PFB containers, worktree-local workspace/retired data and registry state "
        "will also be removed."
    )
    print("Git branches and the shared gateway will be preserved.")


def _discover_legacy_volumes(identifier: str) -> list[str]:
    completed = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"docker exited with {completed.returncode}"
        raise PFBRemoveError(f"cannot discover PFB legacy volumes: {message}")
    pattern = re.compile(
        rf"^retrom-pfb-{re.escape(identifier)}-(?:data|node|runtime-node|go|next|npm)-[0-9a-f]{{12}}$"
    )
    return sorted(name for name in completed.stdout.splitlines() if pattern.fullmatch(name))


def _remove_legacy_volumes(identifier: str, planned: list[str]) -> None:
    _require_legacy_volume_plan(identifier, planned)
    if not planned:
        return
    completed = subprocess.run(
        ["docker", "volume", "rm", *planned],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"docker exited with {completed.returncode}"
        raise PFBRemoveError(f"PFB state was destroyed, but legacy volume removal failed: {message}")


def _require_legacy_volume_plan(identifier: str, planned: list[str]) -> None:
    if _discover_legacy_volumes(identifier) != planned:
        raise PFBRemoveError(
            "PFB legacy volume set changed after confirmation; rerun removal to inspect the new plan"
        )


def _require_detached_partial_state(identifier: str) -> None:
    registry = _registry_path()
    if registry.exists():
        try:
            value = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PFBRemoveError(f"cannot validate PFB recovery registry {registry}: {error}") from error
        entries = value.get("pfbs") if isinstance(value, dict) else None
        if not isinstance(entries, list):
            raise PFBRemoveError(f"cannot validate PFB recovery registry: {registry}")
        if any(isinstance(item, dict) and item.get("id") == identifier for item in entries):
            raise PFBRemoveError(
                f"PFB spec is missing but registry entry still exists for {identifier}"
            )
    compose_project = f"retrom-pfb-{identifier}"
    completed = subprocess.run(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"docker exited with {completed.returncode}"
        raise PFBRemoveError(f"cannot validate PFB recovery containers: {message}")
    if completed.stdout.strip():
        raise PFBRemoveError(
            f"PFB spec is missing but containers still exist for {identifier}"
        )


def _registry_path() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    base = Path(configured) if configured else Path.home() / ".local/state"
    if not base.is_absolute():
        raise PFBRemoveError("XDG_STATE_HOME must be an absolute path")
    return base / "retrom-pfb/registry-v1.json"


def _destroy_partial_state(retrom_root: Path) -> None:
    state_root = retrom_root / ".pfb"
    if state_root.is_symlink():
        raise PFBRemoveError(f"PFB generated state cannot be a symlink: {state_root}")
    if not state_root.exists():
        return
    for directory, _subdirectories, _files in os.walk(state_root):
        path = Path(directory)
        path.chmod(stat.S_IMODE(path.stat().st_mode) | stat.S_IRWXU)
    shutil.rmtree(state_root)


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
