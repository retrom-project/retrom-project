"""Resolve bootstrap and branch-owned manifests without falling back across PFBs."""
from __future__ import annotations

import json
import re
import types
from pathlib import Path


class WorkspaceError(RuntimeError):
    pass


def bootstrap(root: Path) -> tuple[dict[str, object], str]:
    try:
        data = json.loads((root / "manifest.yaml").read_text())
        if not isinstance(data, dict) or data.get("schemaVersion") != 2:
            raise ValueError("bootstrap manifest schemaVersion must be 2")
        repositories = data.get("repositories")
        if not isinstance(repositories, list) or len(repositories) != 1:
            raise ValueError("bootstrap must contain only Retrom")
        repo = repositories[0]
        expected = {"id": "retrom", "path": "project/retrom", "role": "application",
                    "submodules": False, "dependsOn": []}
        if not isinstance(repo, dict) or any(repo.get(key) != value for key, value in expected.items()):
            raise ValueError("invalid Retrom bootstrap entry")
        for key in ("gitlink", "defaultBranch"):
            if not isinstance(repo.get(key), str) or not repo[key].strip() or repo[key].startswith("-"):
                raise ValueError(f"bootstrap {key} is required")
        if data.get("dependencyManifest") != "workspace/manifest.yaml":
            raise ValueError("dependencyManifest must be workspace/manifest.yaml")
        return repo, data["dependencyManifest"]
    except (OSError, ValueError) as error:
        raise WorkspaceError(f"cannot read bootstrap {root / 'manifest.yaml'}: {error}") from error


def catalog(retrom_root: Path):
    path = retrom_root / "workspace/catalog.py"
    if not path.is_file():
        raise WorkspaceError(f"missing workspace catalog API: {path}; merge the workspace migration into this Retrom branch")
    # Do not create __pycache__ in the selected checkout during read-only checks.
    module = types.ModuleType("retrom_workspace_catalog")
    module.__file__ = str(path)
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


def dependencies(retrom_root: Path, text: str | None = None) -> list[dict[str, object]]:
    path = retrom_root / "workspace/manifest.yaml"
    try:
        payload = path.read_text() if text is None else text
        return catalog(retrom_root).parse_manifest(payload)
    except (OSError, ValueError) as error:
        raise WorkspaceError(f"cannot read dependency manifest {path}: {error}") from error


def load_manifest(root: Path, retrom_root: Path | None = None) -> list[dict[str, object]]:
    repo, _ = bootstrap(root)
    retrom_root = retrom_root or root / str(repo["path"])
    return [repo, *dependencies(retrom_root)]


def flow_root(root: Path, name: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise WorkspaceError("PFB must be a lowercase name using letters, digits, hyphens or underscores")
    path = root / ".worktree" / name
    if path.resolve() != path.absolute():
        raise WorkspaceError(f"PFB cannot traverse symlinks: {path}")
    return path


def context(root: Path, pfb: str | None, retrom_dir: str | None) -> tuple[Path, Path]:
    scope = flow_root(root, pfb) if pfb else root
    target = scope / "project/retrom"
    if retrom_dir:
        supplied = Path(retrom_dir).absolute()
        if supplied != supplied.resolve():
            raise WorkspaceError("Retrom source cannot traverse symlinks")
        if pfb and supplied != target:
            raise WorkspaceError("PFB and RETROM_DIR select different Retrom worktrees")
        if not pfb and supplied != target:
            relative = supplied.relative_to(root / ".worktree")
            if len(relative.parts) != 3 or relative.parts[1:] != ("project", "retrom"):
                raise WorkspaceError("RETROM_DIR must select a standard PFB Retrom worktree")
            scope = flow_root(root, relative.parts[0])
        target = supplied
    return scope, target
