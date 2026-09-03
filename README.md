# retrom-project

This repository bootstraps a complete Retrom development workspace. It records which repositories belong to the workspace, downloads them into `project/`, installs the common dependencies, and forwards local development and PFB commands to Retrom.

The source repositories under `project/` remain independent Git repositories. They are ignored by this repository and are never added as submodules or Git index gitlinks.

## Quick start

```bash
git clone git@github.com:retrom-project/retrom-project.git
cd retrom-project
make init
make install-deps
make dev
```

Standard development is available at `http://localhost:4000`. PFB environments use the shared gateway on `http://localhost:3000` and named addresses such as `http://<pfb-id>.localhost:3000`, so both modes can run at the same time.

Run `make status` to inspect every baseline checkout. `make update` first requires all manifest repositories to be clean, then fetches each manifest `defaultBranch`, switches every baseline checkout to that branch, and fast-forwards it to the latest remote commit. If any repository is dirty, divergent, or has its default branch checked out in another worktree, the update fails before switching any checkout.

Run `make pfb-list` to inspect every PFB development flow below `.worktree/`. The table includes its Retrom branch, creation time, effective status, PFB ID, and stable `http://<pfb-id>.localhost:3000` URL. Effective status is obtained from that PFB's own read-only status command, so a stale candidate is reported as `STALE` even if the owner-local registry still says `RUNNING`.

Each PFB keeps all persistent development state under `.worktree/<name>/project/retrom/.pfb/workspace/`. Its application/runtime source, database/CAS/uploads, materialized dependencies, node_modules, Next output and Go/npm caches are bind-mounted into the container. Rebuild/restart therefore keeps the same data and URL and reuses unchanged dependencies. Put `.worktree/` on a Linux local filesystem; WSL `/mnt/c` and other Windows mounts do not provide the required POSIX permission, SQLite lock, hard-link and fsync semantics.

Legacy PFBs that still use Docker named volumes must be stopped and migrated once from their Retrom worktree:

```bash
make RETROM_DIR="$PWD/.worktree/<name>/project/retrom" \
  pfb-migrate-storage PFB=<name> CONFIRM=<actual-pfb-id>
```

The source volumes remain available after a verified, atomic copy. Compatible migrations continue in the same workspace. For an intentionally incompatible development database/data change, keep the same branch/worktree/PFB and run `pfb-data-reset PFB=<name> CONFIRM=<actual-pfb-id>` while stopped; it archives the old data under `.pfb/retired-data/` and preserves dependency/build caches.

To retire a PFB and remove its source worktrees in one operation, run:

```bash
make pfb-remove PFB=<name>
```

The command first validates the PFB identity and every manifest worktree below `.worktree/<name>/project/`. It stops without changing runtime state if any worktree is dirty. For a clean PFB it displays the actual PFB ID and exact removal list, then requires an interactive `y` before destroying that PFB's containers, worktree-local workspace/retired data, legacy volumes and registry/generated state, and removing its Git worktrees. Local Git branches and the shared gateway are preserved.

## Layout

```text
retrom-project/
├── .codex/             # AI skills and prompts
├── .worktree/          # ignored, isolated PFB worktrees
├── project/            # ignored, baseline child repositories
│   ├── retrom/
│   ├── retrom-runtime/
│   ├── retrom-core/
│   └── retrom-other/
├── manifest.yaml       # repository catalog and dependency graph
├── Makefile            # workspace bootstrap and command forwarding
└── AGENTS.md            # development workflow and ownership rules
```

`manifest.yaml` uses JSON syntax, which is valid YAML 1.2. This lets the bootstrap script parse it with Python's standard library before any additional dependencies are installed. Its `gitlink` fields are SSH clone URLs, not root-repository submodules; initialize your GitHub SSH credentials before running `make init`. A repository may set `shallowClone` to `true` to clone its configured branch and recursive submodules with depth 1. This only affects newly created checkouts; it does not convert an existing full clone into a shallow clone.

Do not use `root` or `sudo` for `make dev` or PFB commands. Retrom rejects those invocations to prevent root-owned generated files and containers.
