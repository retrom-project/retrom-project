# Retrom PFB 操作手册

本手册描述 AI Agent 如何把一次多仓库开发组织到 `retrom-project/.worktree/<pfb>/project/`，并调用 Retrom 已有的 PFB 命令。它不替代根项目或各子仓库的 `AGENTS.md`，也不替代 Retrom 当前文档；发现命令接口变化时，以当前仓库内实现和文档为准，并同步修订本 Skill。

## 1. 认识边界

期望的目录结构如下：

```text
retrom-project/
├── .worktree/
│   └── <pfb>/
│       └── project/
│           ├── retrom/                 # .pfb/workspace 保存该PFB全部持久数据/cache
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

每个 PFB 的数据库/CAS/上传、已物化依赖和构建缓存物理位于 Retrom worktree 的 `.pfb/workspace/`，并与源码一起 bind mount 到开发容器。用户级注册表、共享网关、网络和工具链镜像仍属于主机全局状态。旧版 PFB 的 Docker 命名卷只作为待显式迁移/清理的兼容来源，不再是新运行实例的持久存储。

`.worktree/` 必须放在支持 POSIX owner/mode、SQLite lock、同目录 hard-link 与 fsync 的 Linux 本地文件系统。WSL 用户不得把它放在 `/mnt/c` 等 Windows 文件系统挂载下。

## 2. 只读盘点

从 `retrom-project` 根目录开始，先列出当前 workspace 的全部 PFB 流程：

```bash
make pfb-list
```

输出至少包含 PFB 名称、Retrom 分支、初始化时间、有效状态、实际 PFB ID 和稳定访问 URL。状态由每个 PFB 的只读 `pfb-status` 计算，不以目录是否存在或全局registry缓存代替；status还报告workspace和`providerDevModuleSha256`，不扫描整棵源码，也不存在源码`STALE`。随后针对每个可能涉及的基线仓库检查：

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

若明确需要统一刷新全部基线，可在所有 manifest checkout 都 clean 时运行根项目的 `make update`。该命令先完成全仓 dirty 检查，再 fetch、检查可快进性，最后把所有基线切换并快进到各自 `defaultBranch`；任一仓库 dirty 时不会切换任何仓库。若只需创建涉及少量仓库的 PFB，或需要保留其他基线当前分支，则不要运行全局 update，按下方步骤只 fetch 所需仓库。

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

初始化后检查`.worktree/<pfb>/project/retrom/.pfb/spec.json`，确认每个source root和记录的分支都属于当前PFB worktree。`.pfb/`是生成状态，不应提交。已有旧命名卷时，init后必须先按6.1迁移，不能先运行会创建workspace的build。

## 6. 首次构建与启动

按仓库约束先完成针对性测试，然后运行：

```bash
make -C .worktree/<pfb>/project/retrom pfb-validate PFB=<pfb>
make -C .worktree/<pfb>/project/retrom pfb-build PFB=<pfb>
make -C .worktree/<pfb>/project/retrom pfb-provider-import \
  PFB=<pfb> SOURCE_ROOT=<absolute-verified-provider-base> CONFIRM=<actual-pfb-id>
make -C .worktree/<pfb>/project/retrom pfb-up PFB=<pfb> PFB_SELECT=false
make -C .worktree/<pfb>/project/retrom pfb-status PFB=<pfb> FORMAT=json
```

从 status 输出记录实际 PFB ID。默认访问稳定的 PFB 专属地址：

```text
http://<actual-pfb-id>.localhost:3000
```

只有用户明确要求让裸 `http://localhost:3000` 指向当前 PFB 时，才执行选择操作或以选择模式启动。共享网关绑定 `127.0.0.1:3000`；标准 `make dev` 使用 `127.0.0.1:4000`，两者可以同时运行。

上述`pfb-provider-import`只适用于新workspace；`SOURCE_ROOT`必须包含已经完整验证的`active.json + installed/`，app必须停止。导入器验证来源和staging，执行upgrade-only检查，幂等保留同一bundle，最后才原子切换active；它不读取archive、不联网。已有旧命名卷时跳过此命令并按6.1先迁移。

PFB直接bind mount Retrom/runtime源码及`.pfb/workspace/`。`pfb-build`只在缺失或工具链/package/API生成输入变化时准备开发镜像、Node/Go依赖和生成代码；它绝不构建Provider archive、runtime candidate或core。`pfb-up`固定Compose`--no-build`，`pfb-restart`只restart app，不切换数据库或要求重新上传游戏。

### 6.1 旧命名卷迁移

若已有PFB在workspace缺失时仍存在legacy data volume，init后、build前只对当前任务管理的PFB执行：

```bash
make -C .worktree/<pfb>/project/retrom pfb-down PFB=<pfb>
make -C .worktree/<pfb>/project/retrom pfb-migrate-storage \
  PFB=<pfb> CONFIRM=<actual-pfb-id>
```

迁移器优先只读旧state当前`dataCompatibilityDigest`指向的数据卷，并选择同一PFB最新的Node/runtime-node/Next/Go缓存卷；所有内容先进入同文件系统staging，每个源/目标的普通文件与symlink指纹一致后才原子重命名为`.pfb/workspace/`。旧卷不会删除；不要手工删除、改名或迁移其他PFB的卷。迁移后先执行SQLite integrity检查，再build/up。

## 7. 开发迭代

源码可以保持未提交状态；每次编辑仍要确保目标绝对路径位于`.worktree/<pfb>/project/`。源码变化不产生候选锁或stale：

- Web变化由Next HMR直接加载；
- Go变化执行`pfb-restart`；
- runtime adapter变化先用`pfb-status`等待`providerDevModuleSha256`改变，再执行一次`pfb-restart`；
- Dockerfile/Compose/entrypoint、package lock、Go module或API生成输入变化时，才`pfb-down → pfb-build → pfb-up`；
- core只在明确需要时执行`pfb-core-build PFB=<pfb> CORE=<id>`，不能把它塞进普通build。

相同工具链输入的第二次`pfb-build`不应再次构建镜像或运行`npm ci`。不要为了“干净环境”删除workspace，这会丢失用户上传和DB。

数据库 migration兼容时继续使用上述同一workspace原地升级。若本次分支明确引入不兼容的开发期schema或数据语义，在`pfb-up`前执行：

```bash
make -C .worktree/<pfb>/project/retrom pfb-data-reset \
  PFB=<pfb> CONFIRM=<actual-pfb-id>
```

该命令只允许停止态运行，把`data`原子移动到`.pfb/workspace/reset-backups/<UTC时间>/`，建立空目录并保留provider/Node/Next/Go cache；随后仍在同一branch/worktree/PFB ID/URL上up。Agent必须报告归档路径。禁止用新建branch、checkout或PFB规避这一步；也不要把兼容migration误判为必须reset。

运行中可用以下命令检查健康、workspace与开发 Provider 模块内容摘要：

```bash
make -C .worktree/<pfb>/project/retrom pfb-status PFB=<pfb> FORMAT=json
```

不要手工修改`.pfb/`内部状态、dev descriptor或Docker标签绕过验证。

## 8. 联调与验证

验证范围至少覆盖本次改动涉及的仓库测试和 PFB 端到端行为。构建并启动成功后运行：

```bash
make -C .worktree/<pfb>/project/retrom pfb-verify PFB=<pfb>
```

根据任务检查稳定PFB URL、runtime launch URL、开发模块内容摘要、显式core选择和浏览器行为。保存命令结果、失败原因以及PFB evidence位置；不要把生成evidence提交到源码仓库。

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

`pfb-destroy`清理当前PFB的容器、`.pfb/workspace/`、reset backup、注册记录和其他`.pfb/`状态，但不会移除Git worktree、分支或迁移前旧命名卷。

用户明确要求将 PFB 和源码 worktree 一并下线时，从根项目使用统一清理入口：

```bash
make pfb-remove PFB=<pfb>
```

该命令在产生任何销毁副作用前，先验证 PFB 名称、由名称派生的实际 ID、spec 中的 source root、manifest 基线仓库归属，以及该 PFB 下全部 manifest worktree 的状态。只要任一 worktree 有 tracked、untracked 或 submodule 改动，命令就直接失败，PFB 不会被停止或销毁。全部 clean 后，命令显示实际 PFB ID、分支和精确移除路径；只有操作者交互输入 `y` 才会继续。确认后它调用 Retrom 的 `pfb-destroy`，再逐个执行 Git worktree removal，并保留本地分支和共享网关。

不要向该入口传 `CONFIRM`；内部确认值来自已经校验的 spec。`CONFIRM=<actual-pfb-id>` 仍只是直接调用底层 `pfb-destroy` 时的接口。

只有在统一入口不可用、且用户仍明确要求手工清理源码 worktree 时，才执行以下 Git 清理：

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
