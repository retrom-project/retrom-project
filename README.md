# retrom-project

This repository bootstraps a complete Retrom development workspace. It first downloads Retrom from the bootstrap manifest, then reads that Retrom checkout’s dependency catalog to prepare the other repositories, install common dependencies, and forward development commands.

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

Run `make status` to inspect baseline checkouts. `make update` is baseline-only:
it checks the current catalog's existing checkouts for dirty state, fetches the
target Retrom commit, reads that commit's dependency catalog without switching
Retrom, then checks the old and new catalogs before applying any branch updates.
New repositories are cloned after the existing checkout preflight. Removed
repositories stay on disk. Dirty, divergent or locally ahead default branches,
and default branches checked out in another worktree, block the update.
A clone failure leaves existing branches untouched; completed new clones can be
reused on retry. Git updates across multiple repositories are not transactional.

Run `make pfb-list` to inspect every PFB development flow below `.worktree/`. The table includes its Retrom branch, creation time, effective status, PFB ID, and stable `http://<pfb-id>.localhost:3000` URL. If Retrom, runtime, any core or supporting repository in that PFB has tracked, untracked or submodule changes, or has commits not contained in any local remote-tracking ref, the effective status is `DIRTY`; otherwise it is obtained from that PFB's read-only status command rather than inferred from the registry. This check is offline and never fetches implicitly.

Each PFB keeps all persistent development state under `.worktree/<name>/project/retrom/.pfb/workspace/`. Its application/runtime source, database/CAS/uploads, materialized dependencies, node_modules, Next output and Go/npm caches are bind-mounted into the container. Rebuild/restart therefore keeps the same data and URL and reuses unchanged dependencies. Put `.worktree/` on a Linux local filesystem; WSL `/mnt/c` and other Windows mounts do not provide the required POSIX permission, SQLite lock, hard-link and fsync semantics.

The ignored root `.pfb/` directory owns the workspace-shared PFB registry, lock and generated Nginx gateway configuration. These project-specific files never use `~/.local/state` or another user-global state directory. A standalone Retrom checkout uses its ignored `.pfb-shared/` directory instead, and all linked Retrom worktrees resolve to the same owner checkout.

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

The command first validates the PFB identity and every registered top-level worktree below `.worktree/<name>/project/`, including historical core/supporting worktrees no longer present in the current manifest. It stops without changing runtime state if any worktree is dirty or has no verified owner checkout outside the PFB. If an earlier destroy was interrupted after removing the spec, rerunning the command is allowed only after it verifies that the matching registry entry and containers are already absent. For a clean PFB it displays the actual PFB ID, exact worktree removal list and any exact-ID legacy Docker volumes, then requires an interactive `y` before destroying that PFB's containers, worktree-local workspace/retired data, legacy volumes and registry/generated state, deinitializing clean submodules, and removing its Git worktrees. Git's required `--force` fallback is used only after a second clean check and only when ordinary removal returns Git's specific “worktree contains submodules” refusal; it never bypasses a dirty-worktree check. Local Git branches and the shared gateway are preserved. Direct Retrom `pfb-destroy` continues to preserve migration-source legacy volumes; their deletion belongs only to this stronger root-workspace cleanup command.

## Layout

```text
retrom-project/
├── .codex/             # AI skills and prompts
├── .pfb/               # ignored, shared PFB registry and gateway state
├── .worktree/          # ignored, isolated PFB worktrees
├── project/            # ignored, baseline child repositories
│   ├── retrom/
│   ├── retrom-runtime/
│   ├── retrom-core/
│   └── retrom-other/
├── manifest.yaml       # Retrom bootstrap entry and dependency-catalog location
├── Makefile            # workspace bootstrap and command forwarding
└── AGENTS.md            # development workflow and ownership rules
```

## Branch-owned repository catalogs

The root `manifest.yaml` (schema version 2) contains only Retrom's clone URL,
default branch and the relative `dependencyManifest` location. The complete
dependency catalog lives in Retrom's tracked `workspace/manifest.yaml` (schema
version 1). Its paths are relative to the selected workspace root, preserving
`project/retrom-runtime`, `project/retrom-core/...` and `project/retrom-other/...`.
Both files use JSON syntax, valid YAML 1.2, with no bootstrap package dependency.
The catalog parser, `workspace/catalog.py`, also lives in Retrom and is checked
by its `make workspace-check` / CI gate.

```bash
# Baseline: clone Retrom first, then all repositories in its current catalog.
make init

# Prepare Retrom plus only the named dependency worktrees for a new PFB.
make init PFB=feat-example REPOS="retrom-runtime butterscotch"
make validate PFB=feat-example
make check PFB=feat-example REPOS="retrom-runtime butterscotch"
make status PFB=feat-example
```

`REPOS` is an exact selection of repository IDs; it does not expand dependency
edges. Retrom is always included. Omit `REPOS` to prepare/check all catalog entries.
For development containers, include `retrom-runtime` and the core/supporting
repositories needed by the task. `init` prepares source only; it does not initialize
or start a PFB container. Follow the PFB skill for runtime setup and core builds.

PFB initialization first creates the Retrom worktree, then reads **that worktree's**
catalog. Each new source branch starts at the freshly fetched maintenance branch
commit; an existing owner's checkout branch and dirty files are preserved.
New Retrom/runtime branches use `codex/<pfb>`; core/support branches use `feat/<pfb>`.
Existing worktrees must have the correct Git owner and an attached branch and are
reused without switching or resetting them. An existing branch with the proposed
new name is not silently reused. Explicit custom branches can still be prepared
with `git worktree add` before running `init`.

Add or change a core entry in `.worktree/<pfb>/project/retrom/workspace/manifest.yaml`
and commit it with that PFB's Retrom integration changes. Re-run `make init PFB=...`
with the desired `REPOS` to prepare added source worktrees. Other PFBs and the
baseline continue using their own catalogs. Keep feature branches and absolute
local paths out of the catalog; it records maintenance branches, while runtime
release locks continue to pin production artifacts independently.

`RETROM_DIR` may explicitly select the baseline or a standard PFB Retrom worktree.
When both it and `PFB` are supplied, they must select the same worktree. Source
initialization and baseline updates serialize through the ignored root
`.pfb/sources.lock`; ordinary editing and read-only commands do not take this lock.

An older PFB without `workspace/manifest.yaml` must merge the Retrom workspace
migration before using source init/validate/check/status. These commands never
fall back to the baseline catalog. Existing `pfb-list`, lifecycle commands and
`pfb-remove` continue to work; cleanup discovers registered historical worktrees
through Git even when that PFB predates the catalog. The root bootstrap file keeps
the name `manifest.yaml`, preserving existing shared gateway/state discovery.

Publish the Retrom migration before the root bootstrap migration, so a fresh clone
can obtain the catalog and parser from Retrom's remote maintenance branch. Changes
in these two repositories must be committed independently. Later dependency
changes belong only in the relevant Retrom integration branch.

Initialize GitHub SSH credentials before cloning. `gitlink` fields are clone URLs,
not submodules. `shallowClone: true` selects depth 1 for new clones and recursive
submodules; it does not convert existing full clones.

Do not use `root` or `sudo` for `make dev` or PFB commands. Retrom rejects those invocations to prevent root-owned generated files and containers.

## Core and supporting repositories

Retrom’s dependency catalog tracks retrom-runtime, the maintained core repositories
and their supporting forks. Core entries come from the runtime's `provider-sources.json`
and the workspace's maintained core forks. EmulatorJS archives are tracked by
the runtime's `src/providers/emulatorjs/source-catalog.ts`; the individual cores
inside those prebuilt archives do not each require a workspace checkout.

The J2ME source chain uses these repositories, all on the `main` maintenance branch:

| Repository | Workspace path | Dependencies in this workspace |
| --- | --- | --- |
| [j2me-web](https://github.com/retrom-project/j2me-web) | `project/retrom-core/j2me-web` | miniJVM, freej2meOnMinijvm, freej2me-plus |
| [miniJVM](https://github.com/retrom-project/miniJVM) | `project/retrom-other/miniJVM` | None |
| [freej2meOnMinijvm](https://github.com/retrom-project/freej2meOnMinijvm) | `project/retrom-other/freej2meOnMinijvm` | miniJVM, freej2me-plus |
| [freej2me-plus](https://github.com/retrom-project/freej2me-plus) | `project/retrom-other/freej2me-plus` | None |

The J2ME build script and maintenance documentation own the fixed dependency
commits. Its historical `xxxsen` URLs do not change the workspace's canonical
`retrom-project` clone URLs. TinySoundFont, FFmpeg and the SoundFont asset remain
pinned downloads managed by the J2ME build script; nested Git submodules remain
managed by their parent core repository.

WASM-4, TIC-80 and FAKE-08 use `retrom-project/wasm4`, `retrom-project/TIC-80`
and `retrom-project/fake-08`. The dependency catalog selects their Retrom maintenance
branches, `retrom/gca2600db8de4`, `retrom/g4aba09c98f1e` and
`retrom/g814991a2571a`; the fork `main` / `master` branches remain upstream mirrors.
Manifest branches select development checkouts. Runtime consumption continues
to use immutable core releases and fixed build inputs from the child repositories.
