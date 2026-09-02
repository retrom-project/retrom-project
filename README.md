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

`manifest.yaml` uses JSON syntax, which is valid YAML 1.2. This lets the bootstrap script parse it with Python's standard library before any additional dependencies are installed. Its `gitlink` fields are SSH clone URLs, not root-repository submodules; initialize your GitHub SSH credentials before running `make init`.

Do not use `root` or `sudo` for `make dev` or PFB commands. Retrom rejects those invocations to prevent root-owned generated files and containers.
