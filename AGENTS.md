# Retrom workspace guide

## Purpose and ownership

This repository manages the Retrom development environment, not the source history of Retrom or its dependencies. Root-level Git owns only the workspace metadata, documentation, scripts, and `.codex/` resources.

Everything cloned below `project/` is an independent Git repository and is ignored by root Git. Never stage child repositories in this repository, convert them to submodules, or use the root repository to commit child source changes. Commit, push, merge, tag, and inspect history from the relevant child repository.

Before editing a child repository, read every applicable `AGENTS.md` in that repository. Preserve pre-existing dirty state and unrelated user changes.

## Dependency layout

```text
retrom
└── retrom-runtime
    └── ...
```

Baseline checkouts live at:

- `project/retrom`
- `project/retrom-runtime`
- `project/retrom-core/<repository>` for cores consumed directly by the runtime
- `project/retrom-other/<repository>` for supporting repositories that are not cores

Nested Git submodules remain owned by their parent child repository. Root `manifest.yaml` only bootstraps Retrom. Read dependency paths, clone URLs, maintenance branches and edges from the selected Retrom checkout’s `workspace/manifest.yaml`. In a PFB, edit and commit that PFB’s Retrom catalog with the integration changes; never add dependencies to the shared root bootstrap or substitute another PFB’s catalog.

## Workspace commands

- `make init` clones Retrom first, then its declared dependencies. `make init PFB=<name> REPOS="<ids>"` prepares selected source worktrees from that PFB’s catalog, preserving existing worktrees and baseline working files.
- `make check` validates catalog checkouts and origins. `PFB=<name>` selects the PFB catalog and paths; `REPOS` selects exact IDs without expanding dependencies.
- `make update` is baseline-only. It reads the target Retrom commit’s catalog before switching checkouts, checks existing repositories in both old and new catalogs, and validates default branches before cloning additions or applying updates. Removed repositories remain on disk. Never use this global operation to prepare a single PFB.
- `make status` reports child branches, commits, and dirty state.
- `make install-deps` installs Retrom and retrom-runtime dependencies.
- `make dev` forwards to Retrom and serves the standard development stack at `http://localhost:4000`.
- `make pfb-list` reports every PFB flow's Retrom branch, creation time, effective status, PFB ID, and stable URL.
- `make pfb-remove PFB=<name>` validates that all registered top-level worktrees in that PFB's standard project layout are clean and have a verified owner checkout outside the PFB, including historical repositories no longer in the manifest. It can resume a partial destroy with a missing spec only after proving the matching registry entry and containers are absent. It asks for an interactive `y`, destroys the PFB (including `.pfb/workspace/`, retired data and exact-ID legacy volumes), deinitializes clean submodules, and removes its Git worktrees while preserving branches and the shared gateway. Direct Retrom `pfb-destroy` still preserves migration-source legacy volumes. If ordinary Git removal returns the specific submodule-worktree refusal, one `--force` fallback is allowed only after a second clean check; force must never bypass dirty-state validation.
- `make pfb-<action>` forwards the corresponding PFB command to Retrom. `pfb-build` prepares only the dev toolchain/dependencies; daily `up/restart` never builds an image, Provider archive, or core. PFB uses port 3000.

Run development, PFB, and initialization commands as the current non-root user. Never use `sudo`; Retrom intentionally rejects root/sudo dev and PFB invocations.

## PFB development

PFB source isolation mirrors the baseline layout below `.worktree/<pfb>/project/`:

```text
.worktree/<pfb>/project/
├── retrom/
├── retrom-runtime/
├── retrom-core/<repository>/
└── retrom-other/<repository>/
```

Use `make init PFB=<name> REPOS="<ids>"` to prepare sources, or `git worktree add` from the corresponding baseline repository when explicit branch names are needed. All source edits, builds, tests, and PFB inputs for the feature belong in that named worktree. Keep `RUNTIME_ROOT` and `CORE_ROOTS` pointed at repositories inside the same PFB tree.

Each initialized Retrom PFB owns persistent runtime state below its own `.pfb/workspace/`. Source, database/CAS/uploads, base/loose dev providers, node_modules, Next and Go caches are bind-mounted into the development container, so restarting that container must retain them and keep the same PFB ID/URL. Web edits use HMR; Go edits need only `pfb-restart`; runtime adapter edits are rebuilt by the provider watcher and need one restart to reload the revision. Core builds are always explicit. Keep the entire worktree on a Linux local filesystem with POSIX permissions, SQLite locking, hard-link, and fsync semantics; do not place it under WSL `/mnt/c` or another Windows filesystem mount.

For a legacy named-volume PFB, stop only that PFB and run its `pfb-migrate-storage` command with the exact PFB ID; migration must remain scoped to that PFB, verify the copy, publish atomically, and retain the old volumes. Compatible database migrations run in place. When a branch intentionally introduces an incompatible development database/data change, stop the existing PFB and use `pfb-data-reset` with the exact ID; it archives the old `data/` below `.pfb/workspace/reset-backups/` and preserves provider/dependency/build caches, ID and URL. Report the archive path.

Use the `retrom-pfb-workflow` skill under `.codex/skills/` for the complete workflow. A new PFB imports an already verified Provider base explicitly; a legacy PFB migrates its old named volumes once. Neither daily lifecycle builds Provider archives. The isolation is a working-file boundary, not an access-control mechanism: a user may explicitly ask to edit a baseline checkout.

Use `make pfb-list` for the initial PFB inventory. It combines `.worktree/` metadata with every top-level repository's Git status and each initialized PFB's read-only status command; any Retrom/runtime/core/supporting repository with working-tree changes or commits absent from all local remote-tracking refs makes the PFB status `DIRTY`. The check remains offline and never fetches implicitly. Do not infer current runtime state from directory presence or the workspace-local `.pfb/registry-v1.json` alone. The ignored root `.pfb/` also owns the generated shared gateway configuration; do not move those project-specific files back into a user-global state directory.

Use `make pfb-remove PFB=<name>` when the user explicitly requests complete PFB cleanup. Its all-worktree clean preflight happens before PFB runtime destruction; never bypass it with manual forced Git removal or recursive filesystem deletion. The unified command itself may use its documented, second-clean-checked `--force` fallback only for Git's specific submodule-worktree limitation. The prompt's resolved ID and path list are the destructive-action confirmation boundary and include the worktree-local workspace/retired data that will be removed.

The root Makefile can target a PFB Retrom worktree with an override, for example:

```bash
make RETROM_DIR="$PWD/.worktree/<pfb>/project/retrom" pfb-status PFB=<pfb>
```

## Change boundaries

Changes to the Retrom bootstrap entry, root `Makefile`, root docs, bootstrap scripts, or `.codex/` belong to this root repository. Dependency catalog changes belong to Retrom’s `workspace/manifest.yaml` and must be reviewed and committed in that repository. Changes below `project/` or `.worktree/` belong exclusively to their child repositories. Verify both scopes independently before reporting or committing work.
