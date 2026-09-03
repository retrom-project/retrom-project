---
name: retrom-pfb-workflow
description: 指导 AI Agent 在 retrom-project 的命名 PFB worktree 目录下组织 Retrom、retrom-runtime 与 core fork 的多仓库开发，并执行 PFB 的初始化、构建、启动和验证。当用户要求使用 PFB、隔离功能分支开发、在 .worktree 下联调或避免直接修改 project/ 中的基线 checkout 时使用；纯只读分析或用户明确要求直接修改基线工程时不自动套用。
---

# Retrom PFB Workflow

## 目标

把一次功能开发所需的仓库 checkout 放在同一个 `.worktree/<pfb>/project/` 目录内，并从其中的 `retrom/` 操作 PFB。该目录镜像根项目的 `project/` 布局，让源代码修改、构建输入和联调上下文都指向同一个 PFB，避免误改 `retrom-project/project/` 下的基线 checkout。

本 Skill 是工作流指导，不是访问控制。用户可以明确要求修改基线工程；不要把本 Skill 当成拒绝该请求的理由。

## 开始前

1. 找到包含 `manifest.yaml` 和基线 `project/retrom/`、`project/retrom-runtime/` 等仓库的 `retrom-project` 根目录。
2. 确认 PFB 名称、涉及的仓库和各仓库的开发分支名称。先从根项目运行 `make pfb-list` 盘点已有流程，再运行只读的 `git worktree list --porcelain`、`git branch --show-current` 和 `git status --short` 了解相关仓库现状。
3. 从 `manifest.yaml` 读取每个仓库的 `path`、`gitlink` 和 `defaultBranch`。新建 PFB worktree 前先更新对应远端的 `defaultBranch`，并且只以它的最新远端提交作为开发分支基准；不得以 `project/` 中基线 checkout 当前所在的分支或 `HEAD` 作为基准。
4. 若 PFB 名称、开发分支名称或应纳入的仓库会实质改变结果，且无法从用户请求与仓库约定可靠推断，先向用户确认。基准分支不需要猜测，它固定来自 manifest 的 `defaultBranch`。
5. 使用已有且匹配的 `.worktree/<pfb>/project/`；不要静默复用分支错误、来源不明或带有无关改动的 worktree。
6. 编辑每个仓库前，读取该仓库适用的 `AGENTS.md`。处理 core fork 时也读取 `retrom-fork.json` 和仓库规定的候选构建接口。

## 隔离原则

- 进入 `.worktree/<pfb>/project/` 后再开展开发；所有待修改文件必须位于其子仓库中。
- `project/` checkout 只作为 Git worktree 的管理入口和对象库使用，不是 PFB 开发分支的代码基准。即使它当前处于其他分支、detached HEAD 或落后于远端，也必须从 manifest `defaultBranch` 的最新远端提交创建 PFB 开发分支。
- 在每次编辑前核对目标文件的规范化绝对路径确实位于 `.worktree/<pfb>/project/` 下。
- 将 PFB 的 `RUNTIME_ROOT` 和 `CORE_ROOTS` 只指向该 PFB 目录里的 worktree，不要指向根目录下的基线仓库。
- 保留基线 checkout 中已有的用户改动。必要时在开发前后对基线仓库运行只读的 `git status --short`，用结果证明没有新增工作区修改。
- Git worktree 仍共享对象库、refs 和部分 Git 元数据；“隔离”主要指工作文件与 PFB 构建输入隔离，不代表 Git 仓库在物理上完全独立。
- PFB 的应用源码和持久运行状态都归当前 worktree 所有：Retrom 的 `.pfb/workspace/` 保存数据库/CAS/上传、已物化依赖、node_modules、Next、Go 与 npm cache，并 bind mount 到开发容器。共享网关、Docker 网络/工具链镜像以及用户级注册表仍是主机全局状态；不要把这些全局资源误称为 worktree 私有。
- worktree 与 `.pfb/workspace/` 必须位于支持 POSIX owner/mode、SQLite lock、hard-link 与 fsync 的 Linux 本地文件系统；不要在 WSL `/mnt/c` 等 Windows 文件系统挂载下创建 PFB。

## 执行工作流

当任务涉及创建 worktree、初始化 PFB、运行或清理 PFB 时，先完整阅读 [PFB 操作手册](references/workflow.md)，再按其中对应阶段执行。

遵循以下默认选择：

- 仅创建任务需要的仓库 worktree；Retrom 本身始终位于 `.worktree/<pfb>/project/retrom/`。
- 需要统一刷新全部基线 checkout 时可运行根项目的 `make update`；它只在全部 manifest 仓库 clean 时执行，并会把所有基线切换、快进到各自 `defaultBranch`。只需准备单个 PFB 仓库或需要保留基线当前分支时，显式 fetch 该仓库的 manifest 默认分支，不要运行全局 update。
- 有 core worktree 时，同时提供该 PFB 的 `.worktree/<pfb>/project/retrom-runtime/`，因为当前 PFB 规范要求 core 与 runtime 配套。
- 默认以 `PFB_SELECT=false` 启动，使用 PFB 专属的 `http://<actual-pfb-id>.localhost:3000` 地址，避免改变裸 `localhost:3000` 当前选中的 PFB。只有用户明确需要裸地址时才选择它。
- 源码改变后先停止正在运行的 PFB，再增量构建和启动；未变化的 core/runtime candidate、工具链镜像与依赖 cache 应直接复用。只在构建输入未变化时使用 restart。
- 兼容数据库 migration 使用当前 `.pfb/workspace/` 原地升级。若当前分支明确引入不兼容开发数据变更，必须停止同一 PFB，并在启动前用 exact PFB ID 执行 `pfb-data-reset`；它可恢复地归档 `home/data/dev-state`、保留依赖/cache。禁止通过新分支、新 worktree 或新 PFB 规避数据清理。
- 先运行各仓库 `AGENTS.md` 要求的针对性检查，再执行与风险相称的 PFB validate、build、up 和 verify。

## 权限与清理边界

- 用户要求“使用 PFB 开发”时，可以把更新 manifest `defaultBranch`、从其最新远端提交创建所需 worktree，以及运行 PFB 命令视为正常实施步骤；不要从基线 checkout 的当前分支派生 PFB 开发分支。
- 不要自动提交、推送、合并或删除分支，除非用户请求包含这些操作。
- 旧命名卷版 PFB 只允许在当前 PFB 停止态执行一次 `pfb-migrate-storage PFB=<name> CONFIRM=<actual-id>`；只迁移该 PFB 当前 state 指向的数据卷及其缓存，校验后原子发布 workspace并保留源卷。不得扫描后猜选其他 PFB 的卷，也不得借迁移影响其他正在运行的 worktree。
- `pfb-destroy` 不会删除 Git worktree，但会删除该 Retrom worktree 的 `.pfb/workspace/`、retired data与遗留卷。用户明确要求将 PFB 与 worktree 一并下线时，优先从根项目运行 `make pfb-remove PFB=<name>`：它会先验证全部 manifest worktree 均 clean，显示实际 ID 与精确路径，并只在交互输入 `y` 后销毁 PFB、通过 Git 移除 worktree。不得绕过其检查使用强制或递归文件删除；该命令保留 Git 分支与共享网关。
- 标准 `make dev` 监听 `localhost:4000`，PFB 共享网关监听 `localhost:3000`，两者可以并行运行。处理其他冲突时只停止任务范围内明确属于当前 PFB 的进程；不要擅自终止基线工程或其他 PFB。

## 交付说明

最终向用户报告：

- PFB 逻辑名称、实际 ID、工作区根目录和访问地址；
- 纳入的仓库、对应分支以及是否存在未提交修改；
- 已执行的构建、测试和验证及其结果；
- 是否写入了 `.worktree/<pfb>/` 之外的主机全局 PFB/Docker 状态；
- 基线 checkout 是否保持原状，以及未完成或需用户决定的事项。
