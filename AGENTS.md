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
- `make pfb-<action>` forwards the corresponding PFB command to Retrom. PFB uses port 3000.

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

Use the `retrom-pfb-workflow` skill under `.codex/skills/` for the complete workflow. The isolation is a working-file boundary, not an access-control mechanism: a user may explicitly ask to edit a baseline checkout.

Use `make pfb-list` for the initial PFB inventory. It combines `.worktree/` metadata with each initialized PFB's read-only status command; do not infer current runtime state from directory presence or the owner-local registry alone.

The root Makefile can target a PFB Retrom worktree with an override, for example:

```bash
make RETROM_DIR="$PWD/.worktree/<pfb>/project/retrom" pfb-status PFB=<pfb>
```

## Change boundaries

Changes to `manifest.yaml`, the root `Makefile`, root docs, bootstrap scripts, or `.codex/` belong to this root repository. Changes below `project/` or `.worktree/` belong exclusively to their child repositories. Verify both scopes independently before reporting or committing work.
