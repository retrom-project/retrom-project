# Retrom PFB 操作手册

本手册描述 AI Agent 如何把一次多仓库开发组织到 `retrom-project/.worktree/<pfb>/project/`，并调用 Retrom 已有的 PFB 命令。它不替代根项目或各子仓库的 `AGENTS.md`，也不替代 Retrom 当前文档；发现命令接口变化时，以当前仓库内实现和文档为准，并同步修订本 Skill。

## 1. 认识边界

期望的目录结构如下：

```text
retrom-project/
├── .worktree/
│   └── <pfb>/
│       └── project/
│           ├── retrom/
│           ├── retrom-runtime/
│           ├── retrom-core/<core-repository>/
│           └── retrom-other/<support-repository>/
├── project/
│   ├── retrom/                         # 基线 checkout
│   ├── retrom-runtime/                 # 基线 checkout
│   ├── retrom-core/<core-repository>/  # 基线 checkout
│   └── retrom-other/<support-repository>/
└── manifest.yaml
```

根仓库只管理环境元数据，`project/` 和 `.worktree/` 中的源码由各自子仓库管理。当前 PFB 命令消费已有 worktree，但不创建、切换或删除 Git worktree。Agent 负责先准备目录，再从 `.worktree/<pfb>/project/retrom/` 调用 PFB。

物理上位于用户级状态目录或 Docker 中的内容包括 PFB 注册表、共享网关、网络、镜像、命名卷和缓存。它们可能由命令正常创建或更新，因此本工作流保证的是源代码与构建输入的工作区隔离，以及运行时资源的 PFB 逻辑隔离。

## 2. 只读盘点

从 `retrom-project` 根目录开始，针对每个可能涉及的基线仓库检查：

```bash
git -C project/retrom worktree list --porcelain
git -C project/retrom branch --show-current
git -C project/retrom status --short

git -C project/retrom-runtime worktree list --porcelain
git -C project/retrom-runtime branch --show-current
git -C project/retrom-runtime status --short
```

对每个 core 仓库使用 `project/retrom-core/<repository>` 执行同类检查，对 supporting repository 使用 `project/retrom-other/<repository>`。记录基线 checkout 已有的未提交修改，后续不得覆盖或归因给本次 PFB 工作。

检查 `.worktree/<pfb>/project/` 是否已存在：

- 若不存在，按下一节准备所需 worktree。
- 若存在，逐个确认其 Git toplevel、当前分支、状态和所属基线仓库。
- 若路径对应错误分支、错误仓库或无关脏状态，停止复用并向用户说明，不要自行清空。

## 3. 准备 worktree

每个新 PFB 开发分支的基准都固定为 `manifest.yaml` 对应仓库 `defaultBranch` 的最新远端提交。`project/` 下的 checkout 仅用于管理共享 Git 仓库和 worktree；不得使用其当前分支、`HEAD` 或工作区内容作为 PFB 分支基准。

下面的尖括号是占位符，执行前必须替换成 manifest 或已确认的值。先把根目录保存为绝对路径，避免 `git -C` 导致相对路径落到错误位置：

```bash
RETROM_PROJECT_ROOT="$(pwd -P)"
PFB_WORKSPACE="$RETROM_PROJECT_ROOT/.worktree/<pfb>"
mkdir -p "$PFB_WORKSPACE/project/retrom-core" "$PFB_WORKSPACE/project/retrom-other"
```

针对每个待纳入的仓库：

1. 从 manifest 找到其 `path`、`gitlink` 和 `defaultBranch`。
2. 确认仓库中用于该 `gitlink` 的远端；通常是 `origin`，但不要仅凭名称猜测，应用 `git remote -v` 核对 URL。
3. 显式抓取 manifest 的默认分支，并解析刚抓取到的远端 ref：

```bash
git -C "$RETROM_PROJECT_ROOT/<manifest-path>" fetch <manifest-remote> \
  +refs/heads/<manifest-default-branch>:refs/remotes/<manifest-remote>/<manifest-default-branch>
git -C "$RETROM_PROJECT_ROOT/<manifest-path>" rev-parse --verify \
  refs/remotes/<manifest-remote>/<manifest-default-branch>
```

4. 使用符合该仓库约定的 PFB 开发分支名，从这个远端 ref 创建 worktree：

```bash
git -C "$RETROM_PROJECT_ROOT/<manifest-path>" worktree add \
  -b <new-development-branch> \
  "$PFB_WORKSPACE/<manifest-path>" \
  refs/remotes/<manifest-remote>/<manifest-default-branch>
```

例如，manifest 中 Retrom 的 `defaultBranch` 为 `master` 时，应先抓取并从 `refs/remotes/origin/master` 创建其 PFB 开发分支；基线 `project/retrom` 当前检出了什么分支不影响结果。

其余仓库采用同样模式。core 分支还必须符合当前 fork/branch policy；不要为了绕过校验临时更改策略。若目标开发分支已存在于本地或其他 worktree，先确认它确实属于同一个 PFB。恢复已有 PFB 可以继续使用其原开发分支；不要为了追随新主线而静默重建、变基或覆盖已有工作。

创建后对每个目录执行：

```bash
git -C "$PFB_WORKSPACE/project/retrom" rev-parse --show-toplevel
git -C "$PFB_WORKSPACE/project/retrom" branch --show-current
git -C "$PFB_WORKSPACE/project/retrom" status --short
```

对 runtime 和 core 重复检查，并用 `realpath` 确认所有 toplevel 都是 `.worktree/<pfb>/project/` 的子路径。不要仅依赖相似的字符串前缀。

对每个新建 worktree 记录创建时的 base commit，并确认它等于创建前解析的 `refs/remotes/<manifest-remote>/<manifest-default-branch>`。这能证明 PFB 来自 manifest 主线的最新抓取结果，而不是基线 checkout 当前分支。

## 4. 阅读仓库约束

进入 PFB 工作区后，在编辑前读取：

- 根项目的 `AGENTS.md`；
- `.worktree/<pfb>/project/retrom/AGENTS.md`；
- `.worktree/<pfb>/project/retrom-runtime/AGENTS.md`（若纳入 runtime）；
- 每个 core worktree 适用的 `AGENTS.md` 与 `retrom-fork.json`；
- core 的 `.github/rpg-runtime/build-candidate.sh` 及其相关说明（若构建 core candidate）。

PFB 接口的权威说明位于当前 Retrom worktree 的：

- `README.md` 中的 PFB 章节；
- `docs/backend-api-and-operations.md` 的 PFB 操作章节；
- `docs/project-acceptance.md` 中的 `ACC-PFB-*` 验收项。

## 5. 初始化 PFB

以下命令均从项目根目录调用，但把 `make -C` 指向 PFB 内的 Retrom worktree。路径参数使用规范化绝对路径。

仅修改 Retrom：

```bash
make -C .worktree/<pfb>/project/retrom pfb-init PFB=<pfb>
```

同时修改 runtime：

```bash
make -C .worktree/<pfb>/project/retrom pfb-init \
  PFB=<pfb> \
  RUNTIME_ROOT=<absolute-path-to-.worktree/<pfb>/project/retrom-runtime>
```

同时修改一个 core：

```bash
make -C .worktree/<pfb>/project/retrom pfb-init \
  PFB=<pfb> \
  RUNTIME_ROOT=<absolute-path-to-.worktree/<pfb>/project/retrom-runtime> \
  CORE_ROOTS='{"<core_id>":"<absolute-path-to-.worktree/<pfb>/project/retrom-core/<core-repository>>"}'
```

多个 core 使用同一个合法 JSON object。`core_id` 必须匹配当前 PFB 规范，并与 fork 配置一致。只要存在 core，就必须同时提供 runtime root。

初始化后检查 `.worktree/<pfb>/project/retrom/.pfb/spec.json`，确认每个 source root 和记录的分支都属于当前 PFB worktree。`.pfb/` 是生成状态，不应提交。

## 6. 首次构建与启动

按仓库约束先完成针对性测试，然后运行：

```bash
make -C .worktree/<pfb>/project/retrom pfb-validate PFB=<pfb>
make -C .worktree/<pfb>/project/retrom pfb-build PFB=<pfb>
make -C .worktree/<pfb>/project/retrom pfb-up PFB=<pfb> PFB_SELECT=false
make -C .worktree/<pfb>/project/retrom pfb-status PFB=<pfb> FORMAT=json
```

从 status 输出记录实际 PFB ID。默认访问稳定的 PFB 专属地址：

```text
http://<actual-pfb-id>.localhost:3000
```

只有用户明确要求让裸 `http://localhost:3000` 指向当前 PFB 时，才执行选择操作或以选择模式启动。共享网关绑定 `127.0.0.1:3000`；标准 `make dev` 使用 `127.0.0.1:4000`，两者可以同时运行。

## 7. 开发迭代

源码可以保持未提交状态；PFB 会把被跟踪和未跟踪文件内容及模式纳入候选指纹。每次编辑仍要确保目标绝对路径位于 `.worktree/<pfb>/project/`。

源码改变后，已有 candidate lock 会过期。若 PFB 正在运行，使用以下顺序：

```bash
make -C .worktree/<pfb>/project/retrom pfb-down PFB=<pfb>
make -C .worktree/<pfb>/project/retrom pfb-build PFB=<pfb>
make -C .worktree/<pfb>/project/retrom pfb-up PFB=<pfb> PFB_SELECT=false
```

当 source root、分支、工具链或配置发生变化时，在 build 前再次运行 `pfb-validate`。`pfb-restart` 只适用于构建输入未变化、无需重新生成 candidate 的场景。

运行中可用以下命令检查状态和陈旧候选：

```bash
make -C .worktree/<pfb>/project/retrom pfb-status PFB=<pfb> FORMAT=json
```

不要通过修改 `.pfb/` 内部状态或 Docker 标签绕过 stale 检查。

## 8. 联调与验证

验证范围至少覆盖本次改动涉及的仓库测试和 PFB 端到端行为。构建并启动成功后运行：

```bash
make -C .worktree/<pfb>/project/retrom pfb-verify PFB=<pfb>
```

根据任务检查稳定 PFB URL、runtime launch URL、core candidate 选择和浏览器行为。保存命令结果、失败原因以及 PFB evidence 位置；不要把生成 evidence 提交到源码仓库。

## 9. 停止与清理

临时停止当前 PFB：

```bash
make -C .worktree/<pfb>/project/retrom pfb-down PFB=<pfb>
```

只有用户要求销毁 PFB 状态时，先通过 status 得到实际 ID，再使用准确确认值：

```bash
make -C .worktree/<pfb>/project/retrom pfb-status PFB=<pfb> FORMAT=json
make -C .worktree/<pfb>/project/retrom pfb-destroy PFB=<pfb> CONFIRM=<actual-pfb-id>
```

`pfb-destroy` 清理当前 PFB 的容器、卷、注册记录和 `.pfb/` 状态，但不会移除 Git worktree 或分支。

只有用户进一步要求清理源码 worktree 时才执行 Git 清理：

1. 对每个 worktree 运行 `git status --short`，若有修改则停止并报告。
2. 确认目标是 `.worktree/<pfb>/project/` 下的精确仓库路径。
3. 从对应基线仓库使用 `git worktree remove <exact-path>`。
4. 不使用递归文件删除代替 Git worktree removal，不自动删除分支。

## 10. 完成检查

交付前重新检查：

```bash
git -C .worktree/<pfb>/project/retrom status --short
git -C project/retrom status --short
```

对所有纳入的 runtime/core 仓库重复检查。报告 PFB 工作区中的预期修改，并将基线的最终状态与开始时记录比较。若 PFB 命令正常更新了用户级注册表、共享网关或 Docker 资源，也要明确说明这些是工作流允许的主机全局副作用。
