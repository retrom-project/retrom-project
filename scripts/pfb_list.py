#!/usr/bin/env python3
"""List PFB development flows that belong to this Retrom workspace."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
PFB_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,22}[a-z0-9])?$")
NON_SLUG = re.compile(r"[^a-z0-9]+")
CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f-\x9f]")


class PFBListError(RuntimeError):
    pass


@dataclass(frozen=True)
class PFBFlow:
    name: str
    branch: str
    created_at: str
    status: str
    pfb_id: str
    url: str


def registry_path() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    base = Path(configured) if configured else Path.home() / ".local/state"
    if not base.is_absolute():
        raise PFBListError("XDG_STATE_HOME must be an absolute path")
    return base / "retrom-pfb/registry-v1.json"


def pfb_id(name: str) -> str:
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PFBListError(f"invalid PFB name: {name!r}") from error
    if not 1 <= len(encoded) <= 128 or CONTROL_OR_SPACE.search(name):
        raise PFBListError(f"invalid PFB name: {name!r}")
    suffix = hashlib.sha256(encoded).hexdigest()[:12]
    slug = NON_SLUG.sub("-", name.lower()).strip("-") or "pfb"
    slug = slug[:11].rstrip("-") or "pfb"
    value = f"{slug}-{suffix}"
    if PFB_ID.fullmatch(value) is None:
        raise PFBListError(f"invalid PFB id derived from {name!r}")
    return value


def discover_flows(
    root: Path = ROOT,
    *,
    state_file: Path | None = None,
    status_reader: Callable[[Path, str], str] | None = None,
) -> list[PFBFlow]:
    worktree_root = root / ".worktree"
    status_reader = status_reader or live_status
    registry = _load_registry(state_file or registry_path())
    registered = _workspace_registry_entries(registry, worktree_root)
    retrom_roots = set(registered)
    if worktree_root.is_dir():
        for flow_root in worktree_root.iterdir():
            if flow_root.is_dir():
                retrom_root = (flow_root / "project/retrom").resolve(strict=False)
                if _is_workspace_retrom_root(retrom_root, worktree_root):
                    retrom_roots.add(retrom_root)

    flows = []
    for retrom_root in sorted(retrom_roots, key=lambda value: str(value)):
        entry = registered.get(retrom_root)
        flow_root = retrom_root.parent.parent
        fallback_name = flow_root.name
        spec_path = retrom_root / ".pfb/spec.json"
        spec = _load_optional_object(spec_path)
        name = _string_field(spec, "name") or _string_field(entry, "name") or fallback_name
        identifier = _string_field(spec, "id") or _string_field(entry, "id") or pfb_id(name)
        if PFB_ID.fullmatch(identifier) is None:
            identifier = pfb_id(name)
        branch = _git_branch(retrom_root) or _spec_branch(spec) or "-"
        created_source = spec_path if spec_path.is_file() else flow_root
        created_at = _creation_time(created_source) if created_source.exists() else "-"
        status = _flow_status(retrom_root, name, spec, entry, status_reader)
        flows.append(
            PFBFlow(
                name=name,
                branch=branch,
                created_at=created_at,
                status=status,
                pfb_id=identifier,
                url=f"http://{identifier}.localhost:3000",
            )
        )
    return sorted(flows, key=lambda flow: flow.name)


def live_status(retrom_root: Path, name: str) -> str:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.pfb.cli",
            "status",
            "--root",
            str(retrom_root),
            "--pfb",
            name,
            "--format",
            "json",
        ],
        cwd=retrom_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return "ERROR"
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return "ERROR"
    status = value.get("status") if isinstance(value, dict) else None
    return status if isinstance(status, str) and status else "ERROR"


def print_flows(flows: list[PFBFlow]) -> None:
    if not flows:
        print("no PFB development flows found")
        return
    headers = ("PFB", "BRANCH", "CREATED (UTC)", "STATUS", "PFB ID", "URL")
    rows = [
        (flow.name, flow.branch, flow.created_at, flow.status, flow.pfb_id, flow.url)
        for flow in flows
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print(_table_line(headers, widths))
    for row in rows:
        print(_table_line(row, widths))


def _table_line(values: tuple[str, ...], widths: list[int]) -> str:
    padded = [
        value.ljust(widths[index]) if index < len(values) - 1 else value
        for index, value in enumerate(values)
    ]
    return "  ".join(padded)


def _load_registry(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"pfbs": []}
    value = _load_object(path)
    if not isinstance(value.get("pfbs"), list):
        raise PFBListError(f"invalid PFB registry: {path}")
    return value


def _workspace_registry_entries(
    registry: dict[str, object], worktree_root: Path
) -> dict[Path, dict[str, object]]:
    result = {}
    canonical_root = worktree_root.resolve(strict=False)
    for value in registry["pfbs"]:
        if not isinstance(value, dict) or not isinstance(value.get("retromRoot"), str):
            raise PFBListError("invalid PFB registry entry")
        retrom_root = Path(value["retromRoot"]).resolve(strict=False)
        if _is_workspace_retrom_root(retrom_root, canonical_root):
            result[retrom_root] = value
    return result


def _is_workspace_retrom_root(retrom_root: Path, worktree_root: Path) -> bool:
    try:
        relative = retrom_root.relative_to(worktree_root.resolve(strict=False))
    except ValueError:
        return False
    return len(relative.parts) == 3 and relative.parts[1:] == ("project", "retrom")


def _flow_status(
    retrom_root: Path,
    name: str,
    spec: dict[str, object] | None,
    entry: dict[str, object] | None,
    status_reader: Callable[[Path, str], str],
) -> str:
    if not retrom_root.is_dir():
        return "MISSING"
    if spec is None:
        return "PREPARED"
    if entry is None:
        return "UNREGISTERED"
    return status_reader(retrom_root, name)


def _load_optional_object(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    return _load_object(path)


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PFBListError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise PFBListError(f"expected JSON object: {path}")
    return value


def _git_branch(root: Path) -> str | None:
    if not root.is_dir():
        return None
    completed = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _creation_time(path: Path) -> str:
    timestamp = path.stat().st_mtime
    value = datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")
    return value.replace("+00:00", "Z")


def _string_field(value: dict[str, object] | None, field: str) -> str | None:
    item = value.get(field) if value is not None else None
    return item if isinstance(item, str) and item else None


def _spec_branch(spec: dict[str, object] | None) -> str | None:
    retrom = spec.get("retrom") if spec is not None else None
    return _string_field(retrom, "branch") if isinstance(retrom, dict) else None


def main() -> int:
    try:
        print_flows(discover_flows())
    except (OSError, PFBListError, subprocess.TimeoutExpired) as error:
        print(f"PFB list error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
