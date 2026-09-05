# Retrom workspace guide

## Purpose and ownership

This repository manages the Retrom development environment, not the source history of Retrom or its dependencies. Root-level Git owns only the workspace metadata, documentation, scripts, and `.codex/` resources.

Everything cloned below `project/` is an independent Git repository and is ignored by root Git. Never stage child repositories in this repository, convert them to submodules, or use the root repository to commit child source changes. Commit, push, merge, tag, and inspect history from the relevant child repository.

Before editing a child repository, read every applicable `AGENTS.md` in that repository. Preserve pre-existing dirty state and unrelated user changes.

## Dependency layout

```text
retrom
└── retrom-runtime
    ├── Player
    ├── mkxp-z-libretro-emscripten
    ├── OnscripterYuri
    ├── kirikiroid2-web
    ├── Butterscotch
    └── tyranoscript
```

Baseline checkouts live at:

- `project/retrom`
- `project/retrom-runtime`
- `project/retrom-core/<repository>` for cores consumed directly by the runtime
- `project/retrom-other/<repository>` for supporting repositories that are not cores

Nested Git submodules remain owned by their parent child repository. The authoritative repository list, default clone branch, clone URL, and dependency edges are in `manifest.yaml`.

## Workspace commands

- `make init` validates existing checkouts and clones only missing repositories.
- `make check` validates every checkout and its origin.
- `make update` requires every manifest checkout to be clean, fetches every manifest `defaultBranch`, switches all baseline checkouts to their declared default, and fast-forwards them. The all-repository dirty preflight must finish before any checkout is switched.
- `make status` reports child branches, commits, and dirty state.
- `make install-deps` installs Retrom and retrom-runtime dependencies.
- `make dev` forwards to Retrom and serves the standard development stack at `http://localhost:4000`.
- `make pfb-list` reports every PFB flow's Retrom branch, creation time, effective status, PFB ID, and stable URL.
- `make pfb-remove PFB=<name>` validates that all of that PFB's manifest worktrees are clean, asks for an interactive `y`, destroys the PFB (including `.pfb/workspace/` and retired data), and removes its Git worktrees while preserving branches and the shared gateway.
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

Create those directories with `git worktree add` from the corresponding baseline repository. All source edits, builds, tests, and PFB inputs for the feature belong in that named worktree. Keep `RUNTIME_ROOT` and `CORE_ROOTS` pointed at repositories inside the same PFB tree.

Each initialized Retrom PFB owns persistent runtime state below its own `.pfb/workspace/`. Source, database/CAS/uploads, base/loose dev providers, node_modules, Next and Go caches are bind-mounted into the development container, so restarting that container must retain them and keep the same PFB ID/URL. Web edits use HMR; Go edits need only `pfb-restart`; runtime adapter edits are rebuilt by the provider watcher and need one restart to reload the revision. Core builds are always explicit. Keep the entire worktree on a Linux local filesystem with POSIX permissions, SQLite locking, hard-link, and fsync semantics; do not place it under WSL `/mnt/c` or another Windows filesystem mount.

For a legacy named-volume PFB, stop only that PFB and run its `pfb-migrate-storage` command with the exact PFB ID; migration must remain scoped to that PFB, verify the copy, publish atomically, and retain the old volumes. Compatible database migrations run in place. When a branch intentionally introduces an incompatible development database/data change, stop the existing PFB and use `pfb-data-reset` with the exact ID; it archives the old `data/` below `.pfb/workspace/reset-backups/` and preserves provider/dependency/build caches, ID and URL. Report the archive path.

Use the `retrom-pfb-workflow` skill under `.codex/skills/` for the complete workflow. A new PFB imports an already verified Provider base explicitly; a legacy PFB migrates its old named volumes once. Neither daily lifecycle builds Provider archives. The isolation is a working-file boundary, not an access-control mechanism: a user may explicitly ask to edit a baseline checkout.

Use `make pfb-list` for the initial PFB inventory. It combines `.worktree/` metadata with each initialized PFB's read-only status command; do not infer current runtime state from directory presence or the owner-local registry alone.

Use `make pfb-remove PFB=<name>` when the user explicitly requests complete PFB cleanup. Its all-worktree clean preflight happens before PFB runtime destruction; never bypass it with forced Git removal or recursive filesystem deletion. The prompt's resolved ID and path list are the destructive-action confirmation boundary and include the worktree-local workspace/retired data that will be removed.

The root Makefile can target a PFB Retrom worktree with an override, for example:

```bash
make RETROM_DIR="$PWD/.worktree/<pfb>/project/retrom" pfb-status PFB=<pfb>
```

## Change boundaries

Changes to `manifest.yaml`, the root `Makefile`, root docs, bootstrap scripts, or `.codex/` belong to this root repository. Changes below `project/` or `.worktree/` belong exclusively to their child repositories. Verify both scopes independently before reporting or committing work.
