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
    require_clean(w, new)
    planned = [(application, retrom, target)]
    missing = []
    for repo in new[1:]:
        if (w.ROOT / repo["path"]).exists():
            path = w.validate_checkout(repo)
            planned.append((repo, path, w.fetch_default(repo, path)))
        else:
            missing.append(repo)
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
    require_clean(w, new)
    for repo, path, commit in planned:
        w.apply_default(repo, path, commit)
    # Repositories removed from the new catalog are intentionally left on disk.
