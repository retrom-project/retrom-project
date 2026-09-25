"""Plan baseline updates using the manifest in the target Retrom commit."""
from __future__ import annotations

import workspace_config as config


def require_clean(w, repositories: list[dict]) -> None:
    dirty = []
    for repo in repositories:
        if not (w.ROOT / repo["path"]).exists():
            continue
        path = w.validate_checkout(repo)
        if w.run_git(path, "status", "--porcelain=v1", "-z").stdout:
            dirty.append(repo["id"])
    if dirty:
        raise config.WorkspaceError("make update requires every manifest checkout to be clean; dirty: " + ", ".join(dirty))


def inspect_target_checkouts(w, repositories: list[dict], previous: list[dict]):
    previous_by_path = {repo["path"]: repo for repo in previous}
    existing = []
    dirty = []
    for repo in repositories:
        if not (w.ROOT / repo["path"]).exists():
            continue
        path = w.validate_checkout_path(repo)
        origin = w.run_git(path, "remote", "get-url", "origin", check=False)
        if origin.returncode:
            raise config.WorkspaceError(f"checkout has no origin remote {repo['id']}: {path}")
        current_url = origin.stdout.strip()
        source = "origin"
        previous_repo = previous_by_path.get(repo["path"])
        if previous_repo is not None and previous_repo["id"] != repo["id"]:
            raise config.WorkspaceError(f"checkout path changed owner: {repo['path']}")
        if w.normalize_git_url(current_url) != w.normalize_git_url(repo["gitlink"]):
            source = next((
                name for name in w.run_git(path, "remote").stdout.splitlines()
                if name != "origin" and w.normalize_git_url(
                    w.run_git(path, "remote", "get-url", name).stdout
                ) == w.normalize_git_url(repo["gitlink"])
            ), None)
            if source is None:
                raise config.WorkspaceError(
                    f"origin mismatch for {repo['id']}: {current_url} != {repo['gitlink']}; "
                    "no configured remote matches the target catalog"
                )
        if w.run_git(path, "status", "--porcelain=v1", "-z").stdout:
            dirty.append(repo["id"])
        existing.append((repo, path, source, current_url))
    if dirty:
        raise config.WorkspaceError(
            "make update requires every manifest checkout to be clean; dirty: "
            + ", ".join(dirty)
        )
    return existing


def update_workspace(w) -> None:
    old = w.load_manifest()
    require_clean(w, old)
    application, manifest_path = config.bootstrap(w.ROOT)
    retrom = w.validate_checkout(application)
    target = w.fetch_default(application, retrom)
    payload = w.run_git(retrom, "show", f"{target}:{manifest_path}").stdout
    new = [application, *config.dependencies(retrom, payload)]
    # Validate both catalogs before cloning, switching or advancing any checkout.
    require_clean(w, old)
    existing = inspect_target_checkouts(w, new, old)
    planned = [(application, retrom, target)]
    missing = [repo for repo in new[1:] if not (w.ROOT / repo["path"]).exists()]
    for repo, path, source, current_url in existing[1:]:
        commit = w.fetch_default(repo, path, source)
        if source != "origin" and w.run_git(
            path, "merge-base", "HEAD", commit, check=False
        ).returncode:
            raise config.WorkspaceError(f"target remote has unrelated history: {repo['id']}")
        planned.append((repo, path, commit))
    for repo, path, commit in planned:
        branch = repo["defaultBranch"]
        w._validate_default_branch_update(path, branch, commit)
        if w._local_branch_exists(path, branch) and w.run_git(
            path, "merge-base", "--is-ancestor", branch, commit, check=False
        ).returncode:
            raise config.WorkspaceError(f"default branch has unpublished commits: {repo['id']} {branch}")
    # New repositories may be materialized after every existing checkout passes.
    # A clone failure leaves existing branches untouched and is safe to retry.
    w.clone_missing(missing)
    require_clean(w, old)
    refreshed = {entry[0]["path"]: entry for entry in inspect_target_checkouts(w, new, old)}
    if any(refreshed[entry[0]["path"]] != entry for entry in existing):
        raise config.WorkspaceError("checkout remotes changed during update preflight")
    for repo, path, source, current_url in existing:
        if source != "origin":
            w.run_git(path, "remote", "set-url", "origin", repo["gitlink"])
            print(f"origin {repo['id']:<28} {current_url} -> {repo['gitlink']}")
    require_clean(w, new)
    for repo, path, commit in planned:
        w.apply_default(repo, path, commit)
    # Repositories removed from the new catalog are intentionally left on disk.
