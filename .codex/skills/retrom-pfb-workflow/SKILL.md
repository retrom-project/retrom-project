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
2. 确认 PFB 名称、涉及的仓库、各仓库目标分支或基准 ref。先运行只读的 `git worktree list --porcelain`、`git branch --show-current` 和 `git status --short` 了解现状。
3. 若 PFB 名称、分支基准或应纳入的仓库会实质改变结果，且无法从用户请求与仓库状态可靠推断，先向用户确认。
4. 使用已有且匹配的 `.worktree/<pfb>/project/`；不要静默复用分支错误、来源不明或带有无关改动的 worktree。
5. 编辑每个仓库前，读取该仓库适用的 `AGENTS.md`。处理 core fork 时也读取 `retrom-fork.json` 和仓库规定的候选构建接口。

## 隔离原则

- 进入 `.worktree/<pfb>/project/` 后再开展开发；所有待修改文件必须位于其子仓库中。
- 在每次编辑前核对目标文件的规范化绝对路径确实位于 `.worktree/<pfb>/project/` 下。
- 将 PFB 的 `RUNTIME_ROOT` 和 `CORE_ROOTS` 只指向该 PFB 目录里的 worktree，不要指向根目录下的基线仓库。
- 保留基线 checkout 中已有的用户改动。必要时在开发前后对基线仓库运行只读的 `git status --short`，用结果证明没有新增工作区修改。
- Git worktree 仍共享对象库、refs 和部分 Git 元数据；“隔离”主要指工作文件与 PFB 构建输入隔离，不代表 Git 仓库在物理上完全独立。
- PFB 的容器、卷和缓存按 PFB 逻辑隔离，但共享网关、Docker 网络/镜像以及用户级注册表属于主机全局状态。不要声称所有运行时状态都存放在 `.worktree/<pfb>/` 内。

## 执行工作流

当任务涉及创建 worktree、初始化 PFB、运行或清理 PFB 时，先完整阅读 [PFB 操作手册](references/workflow.md)，再按其中对应阶段执行。

遵循以下默认选择：

- 仅创建任务需要的仓库 worktree；Retrom 本身始终位于 `.worktree/<pfb>/project/retrom/`。
- 有 core worktree 时，同时提供该 PFB 的 `.worktree/<pfb>/project/retrom-runtime/`，因为当前 PFB 规范要求 core 与 runtime 配套。
- 默认以 `PFB_SELECT=false` 启动，使用 PFB 专属的 `http://<actual-pfb-id>.localhost:3000` 地址，避免改变裸 `localhost:3000` 当前选中的 PFB。只有用户明确需要裸地址时才选择它。
- 源码改变后先停止正在运行的 PFB，再重新构建和启动；只在构建输入未变化时使用 restart。
- 先运行各仓库 `AGENTS.md` 要求的针对性检查，再执行与风险相称的 PFB validate、build、up 和 verify。

## 权限与清理边界

- 用户要求“使用 PFB 开发”时，可以把创建所需 worktree 和运行 PFB 命令视为正常实施步骤；但不要猜测会改变开发方向的基准分支。
- 不要自动提交、推送、合并或删除分支，除非用户请求包含这些操作。
- `pfb-destroy` 不会删除 Git worktree。不要用递归删除清理 worktree；只有用户明确要求清理、且已确认目标路径和工作区状态后，才使用 Git 的 worktree removal 流程。
- 标准 `make dev` 监听 `localhost:4000`，PFB 共享网关监听 `localhost:3000`，两者可以并行运行。处理其他冲突时只停止任务范围内明确属于当前 PFB 的进程；不要擅自终止基线工程或其他 PFB。

## 交付说明

最终向用户报告：

- PFB 逻辑名称、实际 ID、工作区根目录和访问地址；
- 纳入的仓库、对应分支以及是否存在未提交修改；
- 已执行的构建、测试和验证及其结果；
- 是否写入了 `.worktree/<pfb>/` 之外的主机全局 PFB/Docker 状态；
- 基线 checkout 是否保持原状，以及未完成或需用户决定的事项。
