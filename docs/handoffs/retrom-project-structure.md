# Retrom 结构重构交接（2026-09-20）

这是 `retrom-project` 工作区的状态交接，覆盖固定基线 `82834ba` 到 Retrom `28504499` 的 59 个提交及当前未收口工作树。采样时间为 **2026-09-20 12:58（北京时间）**。它不修改 Retrom 的产品、API、事务或验收合同。

**整体重构尚未完成，goal 当前为 PAUSED。** 环境、基线盘点、共享 Model 和部分 Adapter/门禁改造已有可审查提交；领域事务、统一生命周期、前端与最终验收仍有大量工作。按原 RF 完整退出条件，22 项目前均没有最终完成证据；这不否定已经通过验证的局部成果，也不能把 59 个提交换算成完成率。

配套的 [机器可读状态清单](retrom-project-structure-state.json) 保存 22 项状态、59 个提交、127 个待处理路径及工作字节 SHA-256、5 个暂存删除项、17 项未批准例外和验证绑定。本文是可直接接手的摘要，原始日志只是补充证据。

## 1. 工作区、分支与授权

| 项目 | 交接状态 |
| --- | --- |
| 根仓库 | `retrom-project`；分支 `codex/add-user-facing-instruction`；本文提交前 HEAD `26422b5e` |
| Retrom PFB | `.worktree/retrom-project-structure/project/retrom`；分支 `refactor/retrom-project-structure`；HEAD `28504499b37f14d15818df677f0c8e3083aba663` |
| runtime PFB | 同一 PFB 的 `project/retrom-runtime`；同名重构分支；HEAD `3ba27985a23f00663546164ac28491b57ec07862`；工作树干净 |
| 开发基线 | 创建 PFB 前已经 fetch origins；Retrom 当时快进至 `82834bade1648da3067ebda1b1fc89c18577fd6a`，runtime 至 `3ba2798`。本次文档任务未再次 fetch 或更新基线 |
| PFB | 名称 `retrom-project-structure`；ID `retrom-proj-e20ec94170f0` |
| 稳定入口 | http://retrom-proj-e20ec94170f0.localhost:3000 |
| 当前容器 | `retrom-pfb-retrom-proj-e20ec94170f0-app-1`；只读检查为 running / healthy；这不代表已重新完成浏览器产品验收 |
| 工具链 | 最近验证使用 Go 1.26.5、golangci-lint 2.11.4、Node 24.18.0；在现有开发容器中以 UID 1000 运行 |
| 提交策略 | 完成功能/修复即提交；开发期间至少每小时提交独立可审查成果；自动化 ID 为 `retrom`；没有成果不造空提交 |
| 模型策略 | 常规测试整理、lint 盘点、清单与文档审计用 Sol；资源协议、事务/生命周期、来源证明用较强模型，并对关键证明做独立审查 |
| 私有样本 | 用户已明确“暂无，先完成重构和公开测试，保留缺失验收项”；不重复询问，不将缺失项记为 PASS |

源请求包已解压至工作区 `td/retrom-baseline-refactor-82834ba`。接手时阅读其 README、00–07 合同及相关 RF 文档，同时以各仓库 AGENTS 和正式契约核对冲突。包含 **22 工作项、22 冻结决策、102 具名验证场景、16 永久门禁**，没有授权重新选择架构。它是本地实施输入；产品源码、工具和正式文档不能依赖其路径。

根仓库只拥有工作区元数据、脚本和文档。Retrom/runtime/core 的源码及提交始终归各自子仓库。本文和 JSON 提交在根仓库；未把子仓库源码或 Git 对象纳入根仓库。原根目录两个未跟踪 ZIP/Zone.Identifier 项也不属于此任务。

## 2. 已提交的主要成果

| 成果 | 提交证据 | 已完成范围与边界 |
| --- | --- | --- |
| 真实旧基线与全量盘点 | `8f8c99f4`、`d7097086` 及之前的 census 提交 | 实际执行归档的 82834ba，冻结 461 schema 对象、14 migrations、目录/存档/receipt/CAS 行为；业务写根、SQL、消费者盘点闭合。当前登记 246 operations / 584 policies；原 census 时 policies 为 581 |
| Model 与类型归属 | `1a262d35`、`1979169a`、`0bca6452` | 共享值、Provider/Launch 封闭数据、窄 BIOS facts 和大量 Service re-export 已迁移；不能等同于所有领域 port/事务完成 |
| Provider envelope 兼容 | `0e5db8ca` | 82 个当前 binding、164 个公开 envelope 验证；不证明每个核心的真实可玩性 |
| Digest 协调能力 | `f3924347` | 可取消、进程共享的 256 槽 digest lock Adapter；**还未接入发布/引用/GC 全链** |
| 外部能力与资源边界 | `43b73ec9`、`fecc5b75`、`6cd37e1b`、`d8ca8806`、`85b2fac3`、`95bc3c74` | 密码执行/词表、firmware facts、ZIP 命名、native probes、维护锁、显式诊断、有界引擎探测等分批迁移 |
| DAT 获取与生命周期 | `f3c12490` | 19 文件；DATCatalogSource + Adapter + CatalogService/composition；13 个实际调用点；原读取、取消、错误树及 Close-before-write 顺序保留 |
| 导入/启动 integration 测试 | `d5175272` 至 `218c279a` | 分真实业务阶段提取；原断言、SQL/HTTP/配置、ctx、时间和测试控制保留；两个包原有 55 条 lint 已清零 |
| 架构门禁与来源证明 | `5470153e`、`b6ff2da2`、`2e98c03b`、`28504499`，及早期扫描器提交 | 有限资源签名、真实构造/消费者来源、固定模块校验、外部方法、错误 guard；真实执行反例修复了 receiver/global/range/guard 误判 |

`28504499` 标题带 RF19，但变更实际在 `internal/testkit/architecture`，属于 RF21 门禁进展，不能拿提交标题宣告 RF19 维护领域完成。全部 59 个提交及时间见配套 JSON。

## 3. RF01–RF22 未完成矩阵

下面的“已做”包括局部已提交能力；每一行的完整退出仍待证明。各领域对应的操作和策略定义在 Retrom 的 `quality/architecture/operations.json`、`policies.json`、`test-cases.json`，盘点说明在 `baseline-census.json`。

| 工作项 | 当前状态与已做内容 | 主要剩余工作 |
| --- | --- | --- |
| **RF01 基线冻结与全量盘点** | 盘点闭合；完整退出待验证。固定基线、真实旧源码 characterization、包/类型/写根/消费者盘点；登记 246 个操作。 | 把逐操作测试、证据、所有权和原 Case 映射补齐，取得当前源码的 RF01 point 退出证据。 |
| **RF02 统一组装、资源所有权和后台生命周期** | 局部接线；核心生命周期未迁。部分 composition、锁、诊断、detector 显式注入。 | 实现 Application 的 BUILT/STARTING/RUNNING/STOPPING/STOPPED、统一 Worker registry、重复 Start/Shutdown 和一次释放。 |
| **RF03 共享 Model、窄端口及类型真实归属** | 部分生产实现。共享 blob/metadata/netplay/clock、Provider/Launch 值和窄 BIOS facts 已迁移；最新报告 re-export 为 0。 | 关闭全部类型/端口消费者图；提交 RPG ports；清除具体跨 Service 依赖和嵌套 writer，不能用新门面隐藏依赖。 |
| **RF04 纯 Capability 与外部 I/O 分离** | 部分实现；重要批次未提交。Hasher、blocklist、firmware facts、ZIP 命名、native probes、process lock、diagnostics、有界引擎探测和 DAT 获取已分离。 | 先收口 B2/RPG，再完成 7z worker/SDK、materializer、剩余 cleanup 与流缓存；D22 锁还需产品接线。 |
| **RF05 值命令与原子事务公共机制** | 登记/计划；事务机制未闭环。operations/policies schema、静态合同、246 operations/584 policies；锁 Adapter 前置。 | 实际值命令替换 Repo 业务回调；ID 在 writer 外准备，取写权后一次 admission clock，重读权限/来源/lease，原子写入与逐阶段回滚。 |
| **RF06 HTTP/WebSocket 边界、错误与幂等回放** | 盘点与局部边界迁移。receipt autocommit、路由和错误回放边界已盘点。 | StoredReply、codec、全部 route port 与原子幂等回放；解决领域提交后另写 receipt 的窗口。 |
| **RF07 账户、会话与身份安全用例** | 领域盘点；能力前置已做。15 类身份/账户操作；密码执行和 blocklist 获取已分离。 | 迁移 Initialize/Authenticate/Renew/ChangePassword/Link/Admin/Recover/RateLimit 命令，补权限新鲜度和事务 UUID 的安全回归。 |
| **RF08 存档：流式协议与业务提交完整样板** | 盘点/计划。5 类 save 操作和合同已登记。 | 实现纯值 SaveCommand、Stager 与流关闭所有权、完整原子提交、取消/恢复/故障矩阵。 |
| **RF09 上传与内容准备流水线** | 盘点/计划。11 类 upload 操作，含续租、恢复重排、取消对账。 | 迁移 Create/AcceptPart/Finalize/Cancel/Claim/Finish；临时文件和 Reader 留在 Adapter，消费转移进入所属导入事务。 |
| **RF10 Launch、预览、配置、授权与隔离** | 盘点与局部共享值迁移。14 类 Launch/隔离事务；Provider/Launch 值、BIOS facts 及部分配置测试。 | 迁移 Launch/Preview/Netplay/Variant/Config/Play/Screenshot/Validation/Isolation；补预览文件闭包、回放、权限与执行防护。 |
| **RF11 Runtime、BIOS、DAT 与内容验证能力** | 部分能力实现；事务未迁完。Provider 严格值、BIOS facts、firmware source、DAT CatalogService 及真实调用方。 | 实现 ActivateProvider/ProjectCatalog/Install/ReplaceFirmware/SyncDATRequirements 的原子命令和故障矩阵；公开 DAT 已有验证，私有 BIOS/核心验收另列缺口。 |
| **RF12 联机控制面与实时 Hub 分离** | 盘点；已知缺陷待修。19 类 room/session/launch 写操作及恢复路径。 | 迁移控制面命令；修复先发布内存再持久化、持 Hub mutex 跨 SQL、事务内 UUID 等问题；保持实时输入协议。 |
| **RF13 普通导入、审核、发布与集成门面消除** | 盘点与测试整理；领域事务待迁。普通导入、审核、批审、发布、附件和来源交接的写集/策略；相关 integration lint 已整理。 | PublicationPlan、原子 Repo helper、业务 callback/集成门面消除；B2/RPG 的输入边界改造不能替代发布事务闭环。 |
| **RF14 Pegasus、EmulationStation 与服务器来源** | 盘点/计划。Pegasus、ES、server BIOS 来源写边界和消费者已登记。 | 迁移 Plan/Mapping/Scan/Start/Claim/Outcome/Materialization/Companion/Completion/Recovery；移除跨层 Discover/WithScan 等业务回调。 |
| **RF15 元信息抓取、缓存、候选和媒体任务** | 盘点/计划。10 类抓取/媒体事务及策略。 | 迁移抓取和媒体命令；补 import payload、父任务取消及结果对执行身份的 guard。 |
| **RF16 游戏目录、游戏编辑、标签收藏与读模型** | 盘点/计划。约 30 类目录/编辑/标签收藏事务及读写符号。 | 迁移命令和读投影；清理跨 Service 调用，验证分页、权限、内容替换与删除兼容。 |
| **RF17 任务调度、取消、重试与执行防护** | 盘点/计划。通用 job mutation、receipt 关系和现有任务符号。 | 落地生产 Kind registry、cancel/retry ports、恢复入口和 claim/outcome；处理休眠 IMPORT_ITEM_PIPELINE retry dispatch。 |
| **RF18 Payload 生命周期、归属注册与 GC** | 盘点与锁前置；生命周期待迁。release effect graph、嵌套写阶段、GC/过期/retirement 盘点；D22 锁 Adapter。 | 将锁接入全部 publication/reference/GC；33 个登记内容操作仍缺 acquire/release；完成 release/GC 命令、所有权重验和并发/崩溃恢复。 |
| **RF19 维护、备份恢复、诊断及只读探针** | 部分锁/诊断实现。维护 process lock、显式注入和 sanitized diagnostics；备份关闭顺序测试及维护写集盘点。 | 全部维护命令的文件准备与 SQL commit 分离，backup/restore 字节兼容、无 HTTP/Worker 入口及隐私验收。 |
| **RF20 前端 Feature、API Client 与 Player 公开边界** | 扫描器基础设施；产品迁移待做。Web 编译闭包、Feature/cycle/client-server 扫描及负向自测。 | 迁移 browser-client/server-client 及消费者；清理 Feature 图违规，证明 SSR 状态隔离并完成 Player/UI 合同验证。 |
| **RF21 架构扫描器与持久质量门禁** | 部分门禁；NOT_READY。Go/Web/contract/point/final coordinator、来源证明与真实反例；多个提交快照通过 backend-check。 | 清理最近报告的 811 处违规及 9 类 pending checks；完整传递纯度、生命周期、操作/证据、前端结构证明与永久接线仍缺。 |
| **RF22 正式文档、完整验证和交付收口** | 交接已整理；最终收口未完成。阶段提交、历史验证证据和本交接文档。 | 合并正式契约、消除产品对临时文档的依赖；最终干净固定 HEAD 的 CI/race/integration/Web E2E、102 具名场景、原 Required Case、回滚和兼容验收。 |

原包的执行依赖顺序应保留：

```text
RF01 → RF21 → RF03 → RF04 → RF05 → RF02 → RF07 → RF08 → RF09
→ RF11 → RF10 → RF12 → RF15 → RF13 → RF14 → RF16 → RF17
→ RF18 → RF19 → RF06 → RF20 → RF22
```

RF21 贯穿全程。不能以“工具已经能报告违规”替代规则全部实施、生产违规归零和最终强制接线。

## 4. 先收口当前 127 个未提交路径

本次按 `git status --porcelain=v1 --untracked-files=all --no-renames`，并仅在 Windows UNC 的该次只读 Git 调用中忽略可执行位差异，统计为 **52 modified、5 staged deletions、70 untracked**。没有永久修改 Git 配置。此前“116 entries”用了不同展示口径，不能直接解释成新增 11 处代码修改。实际 POSIX 权限仍应在 Linux 中复核。

完整路径、Git HEAD blob ID、现有文件大小/工作字节 SHA-256 在 JSON 中。**仅检出分支无法恢复这 127 个路径；普通 git diff 也不会包含 70 个 untracked 文件。** 交接给另一台机器时须另行保留未提交子仓库工作树和必要本地证据。源码仍由各子仓库管理，本次根仓库提交只保存交接信息。

### 4.1 B2：ZIP / NWJS / ASAR

核心目录为 `internal/adapter/content/archive`，以及 importing 的纯值规则、libraryimport/firmware/serverimport Model ports、Service 编排、Bootstrap 和实际消费者。

已保留的证据包括：61 组旧行为对照（37 个 B2 + 24 个旧 7z）、12 类旧 Go 错误树、6 个额外包装编译成功后变红的反例、owner/race/真实 CAS Stage 检查。ZIP Complete 的 EOF/data-descriptor CRC 漏检已修复并回归，但 **仍在工作树中，尚未进入 commit**。重点保护：

- `internal/adapter/content/archive/reader.go`
- `internal/adapter/content/archive/zip_cursor.go`
- `internal/adapter/content/archive/zip_cursor_eof_test.go`
- `internal/service/libraryimport/project_archive_zip_eof_test.go`

真实来源证明目前在 default/integration 均停于 `internal/adapter/content/archive/electron_asar_zip.go:68`：

```go
return nil, importing.ErrElectronASARInvalid
```

GB18030 外部来源和第 64/81 行局部错误 guard 已可证明；上述裸 sentinel 仍为 **UNPROVEN**。后续应证明真实初始化/使用和不可被改写的错误来源，保留可执行负控；不要按包名、错误名白名单放行或添加包装改变协议。

### 4.2 RPG Maker

冻结 owner 范围有 36 个路径（包含一个已移动测试的删除），另需 10 个 Service/Bootstrap/HTTP 接线路径；两个 Model port 已包含在 36 个 owner 中。122 组旧 Go 对照、有界输入/安全 fixture、owner/race 和实际消费者已有历史证据，当前 owner 字节仍匹配冻结记录。

RPG archive 路径依赖 B2，不能只提交 detector 目录。以下三个文件混有 RPG 与 B2 修改：

- `internal/bootstrap/composition/libraryimport/creation.go`
- `internal/service/libraryimport/environment.go`
- `internal/service/libraryimport/import_preparation.go`

`internal/transport/httpapi/server.go` 中 game-content composition 与 firmware composition 也属于不同修改块。优先完成 B2 的完整可编译检查点，再带上 RPG 的完整消费者；若合并提交，应纳入完整依赖闭包。现有 `rpg-exclusive-tracked-review.diff` 只是审阅片段，不能直接应用。

### 4.3 5 个暂存删除项

这些是前面将测试移动到 Adapter 时保留的删除项，不是一份可以立即独立提交的删除清单：

```text
internal/capability/engine/rpgmaker/detector/public_security_fixture_test.go
internal/capability/format/importing/archive_test.go
internal/capability/format/importing/electron_asar_lifecycle_linux_test.go
internal/capability/format/importing/electron_asar_test.go
internal/capability/format/importing/nwjs_executable_test.go
```

配对的新测试当前在 untracked Adapter 目录里。继续使用精确路径/分块提交并核对真实 index，避免把它们单独删除或把所有并行改动一起 `git add -A`。`quality/architecture/package-ownership.json` 也混有未提交 owner 记录，须跟随相应源码范围提交。

## 5. 明确的阻点与验收缺口

### 5.1 17 项精确 lint 例外尚未获批

现有申请分组如下，完整位置、源码 SHA、原因和协议不变量已写入配套 JSON：

| 范围 | 申请数量 | 保持的协议 |
| --- | ---: | --- |
| RPG detector | 9 wrapcheck | 原具体错误类型、错误文本、唯一领域包装、原 Open/Read/Close cause 和优先级 |
| RPG 缺失 Reader fixture | 1 nilnil | 真实 nil reader + nil error 的旧输入，不能替换为 typed nil 或其他 error |
| B2 archive | 6 wrapcheck | 原 ASAR/ZIP 分类错误及 Close cause 的对象/unwrap 结构 |
| Service archive EOF 分支 | 1 errorlint | 区分裸 io.EOF 与包裹 EOF 的损坏错误；不能改成 errors.Is 后吞掉损坏 |

自动审批此前拒绝登记 RPG 的 10 条抑制，依据是 Retrom AGENTS 第 5 节：没有明确批准不能持久降低质量门槛。后来合并的 17 项申请仍为 **PROPOSED_UNAPPROVED**，没有登记到中央 allowlist。

工作区 RPG 源码仍带 10 处未登记 annotation；它们不能被误当作已批准并随手提交。省略这些 annotation 后，已有诊断为 RPG 9 wrapcheck + 1 nilnil，另外还有 B2/EOF 的 7 项。此处不是本次新跑的全仓 lint 总数。若调整实现，必须用旧行为 golden、错误树和实际编译执行的负控证明协议没有被改变；不能通过转交错误、减少 fixture 或弱化断言绕过。

### 5.2 B3 7z 与其他 RF04 工作

7z worker/SDK 迁移尚未实施，已有设计和 24 个旧观察。另四类补充捕获没有执行完成：

1. 非法 JSON 的具体类型/Struct/Field/包装及多 JSON 行为。
2. 进程已退出与 Kill/Wait 的不同路径。
3. 目标写失败后的尾部 Read/Wait；是否阻塞尚未实证。
4. 单个/批量 Close 失败及 decoder 生命周期。

当时平台风险标记中止了补充工作，保留下来的报告没有能定位具体被拒命令的审批载荷；不能编造已经捕获或把它改记为产品失败，也不能换执行路径重试被拒步骤。现有 24 个观察仍有效，四个缺口单列。

仍有 ScummVM 输入物化、维护备份/恢复文件准备、各 Service 全局 cleanup、DAT/ES 原始字节缓存、ES Discover 业务回调等资源工作。DAT 获取迁移保留了原有合法有界纯解析，不代表流缓存或整个 Capability 已收口。

### 5.3 事务、CAS 与跨 Service

246 个操作登记是语义盘点，不是 246 个原子命令实现。必须完成权限/来源/execution/lease 的 writer 内重验、纯策略唯一归属、每一写阶段的原子回滚、幂等竞争与取消恢复。

D22 锁 Adapter 虽已提交，但 33 个内容操作的 acquire/release 接线与交错测试仍缺。引用发布须保护已验证 CAS 字节，GC 须在同一锁下重读 ownership/protection 后再提交和删除。最近架构报告仍有 25 条具体跨 Service 依赖；旧跨 Service 计划还列有 19 个 transaction/mixed edge，接手时应按真实调用图重验，不能独立提交原本属于一个事务的 metadata/consumption/release 子步骤。

### 5.4 私有样本与外部代理

MZ、ONS、KiriKiri、GameMaker/Butterscotch、TyranoScript、Flycast CHD/BIOS、expansion ROM 及部分主机样本未配置。用户已接受继续重构/公开测试并保留缺项；这些样本对应验收保持 BLOCKED，不妨碍独立公开开发，也不能用公开 envelope 检查冒充真实可玩性。

之前一个外部 Cursor 审计因潜在私有源码外发被自动审批拒绝，已改用内置子代理。用户“可以使用 Cursor”不等同于已获批准重试被拒的数据外发。常规任务优先 Sol 的策略仍然适用。

## 6. 验证证据及其有效边界

| 验证 | 已记录结果 | 绑定与限制 |
| --- | --- | --- |
| 初始基线/PFB | 包自检 14 tests；pfb-verify VERIFIED；backend；Web lint/typecheck、810 tests、3 scanner tests、build | 初始阶段历史结果，不是当前最终 HEAD 的 RF22 验收 |
| DAT `f3c12490` | 精确 tree 的 backend-check、完整 repo/dependencies + HTTP integration、DAT 三包 integration lint 0；13 组旧对照；owner race；两个 compiled RED mutations | 源获取、关闭和真实调用方范围；不代表所有 DAT/BIOS 事务已迁完 |
| 测试整理 `218c279a` | 精确 tree 的 backend-check、完整 libraryimport + runtime/launch integration、两包 integration lint 0 | 两包原 55 条 lint 清零；HTTP integration 另一次只读 census 也是 0 |
| 来源证明 `28504499` | 精确 tree 的 backend-check、完整 architecture integration、architecture/scripts integration lint 0；合并专项 default/integration 各 173 PASS events | 修复了真实误判，但 B2 仍在裸 ASAR sentinel 处 UNPROVEN |
| 广泛公开产品 integration | 210 packages，148 个有测试包 PASS，6090 test/subtest PASS，1 个 LocalDOSCorpus skip | 当时 HEAD 为 `b6ff2da2` 加 RPG/B2/CRC/batch6 工作树；排除了 architecture/refactor gate 包；不是最终干净 HEAD |
| 原最终协调器演练 | `77199430` 的准备和 checker selftest PASS，随后 architecture NOT_READY，248 后续步骤 NOT_RUN | 证明能诚实停止，不能当作最终通过；最终 frontend 结构证据仍未实现 |

最近完整 Go 架构报告记录 **NOT_READY / 811 violations**，分布为 AR02=124、AR03=152、AR04=112、AR05=389、AR08=25、GOV01=9；9 类已实现检查、9 类待实现检查；1049 ports、7924 functions、re-export=0。该报告写明的 HEAD 是 `218c279a` 加当时待提交的来源证明工作字节，**本次文档任务未重跑，也未改标为 `28504499` 的完整验收**。

9 类 pending 检查涉及：生成来源/构建注册、直接 Repo 边界/构造注入、传递可执行纯度/SQL 调用、组装和生命周期、原子 helper/策略唯一性、技术时钟/协议隐私、operation/job/dispatcher/test/evidence 注册、前端边界、测试完整性与永久门禁接线。早期 Web 报告的 WEB01=238/GOV01=4 同样只是历史结果。

尚无最终重构 HEAD 上的完整 CI、race、全 integration、Web E2E、102 新具名场景、逐操作故障矩阵和原 Required suite 闭环。原文档盘点了 217 个产品 Case（215 个非条件项），其中 24 个曾缺 CASE_COMMANDS 映射；有些是手动/直接流程，ACC-PFB-001–012 则明确需要核对 runner 映射，不能删 Case 解决。正式文档中 13/14 migrations 的陈述也须在 RF22 统一。

## 7. 建议接手顺序与运行方法

1. **恢复上下文，核对字节。** 从工作区根读取本说明/JSON、两层 AGENTS 和相关原方案；验证分支、HEAD、127 路径 SHA 与 5 个暂存项。goal 当前暂停，本次交接整理不恢复产品开发。
2. **优先收口现成的 B2/RPG。** 处理 17 项例外的明确决定；关闭 ASAR sentinel 来源证明；保留 CRC 修复和全部旧协议对照；按真实依赖分批或原子提交。每批保存准确 tree 与测试结果，不能把另一个工作树的成功当作本批成功。
3. **完成 RF04 剩余 I/O，再推进 RF05/RF02。** 7z、物化/cleanup/流资源与 D22 实际接线须有 owner；完成值命令公共规则和 Application 生命周期后，再依原顺序迁移领域。
4. **逐领域兑现登记矩阵。** guard 拒绝、每一写阶段回滚、affected-row、stale execution/lease、幂等、取消、恢复、直接消费者逐项留证据。不要用一个 aggregate test ID 代替这些场景。
5. **最后关闭门禁、正式文档和产品验收。** 在干净固定 HEAD 上运行完整 final；私有样本仍缺则按用户决定列明 BLOCKED，不将整份报告标为全部 PASS。

正常 Linux 用户在工作区根先运行只读盘点：

```bash
make pfb-list
git -C .worktree/retrom-project-structure/project/retrom status --short --untracked-files=all
git -C .worktree/retrom-project-structure/project/retrom diff --cached --name-status
git -C .worktree/retrom-project-structure/project/retrom-runtime status --short
```

在 Retrom PFB 中按变更影响面选择现有目标：

```text
make backend-check
make architecture-selftest
make architecture-check
make refactor-contract-check
make web-architecture-check
make refactor-verify POINT=RFxx
make refactor-final
```

这些是后续执行入口，不是此文声称已通过的命令清单。`backend-check` 只包含结构、格式、构建、默认测试和 Go lint，不包含完整 architecture/refactor-final；当前含未登记 annotation 的整个工作树也不能套用干净提交快照的 PASS。

之前 WSL 启动出现 `Wsl/Service/0x8007274c`，当时使用仍健康的现有 PFB 容器验证，未重启发行版/PFB。需要该路径时，可在 Windows Docker CLI 使用非 root 容器用户及明确工具链，例如：

```bash
docker exec --user 1000:1000 --workdir /workspace/retrom \
  retrom-pfb-retrom-proj-e20ec94170f0-app-1 \
  sh -lc 'PATH="/workspace/retrom/.cache/tools/go1.26.5-linux-amd64/bin:/workspace/retrom/bin:$PATH" GOTOOLCHAIN=local GOFLAGS="-p=2" make backend-check'
```

先重新确认环境事实，不要为排查 CLI 超时重建 PFB、清数据或更改测试期限。Windows Git 读取 UNC 曾把 38 个 executable 脚本显示成 mode-only 修改；已逐字节核对与基线相同。临时只读 `core.filemode=false` 是展示口径，不是修改模式规则。Git 操作要确认实际 worktree Git 目录，不改写 `.git` 指针。运行 golangci-lint 要串行协调，避免多个子任务抢同一个全局锁。

## 8. 本地证据入口与迁移注意事项

下列路径相对工作区根；都已经检查存在，但位于 ignored 目录。**克隆本根仓库不会自动取得它们。** 核心状态、剩余事项、例外和文件指纹已写入本文/JSON；下列日志用于进一步审计，不能成为产品构建依赖。

| 证据 | 本地入口 |
| --- | --- |
| 原方案及约束 | `td/retrom-baseline-refactor-82834ba/README.md`、`data/`、`workstreams/` |
| 逐次执行日志 | `td/refactor-execution/PROGRESS.md`；正文是历史追加记录，旧 ACTIVE/HEAD/计数不可覆盖本交接快照 |
| RF01/注册 | Retrom `quality/architecture/{baseline-census,operations,policies,test-cases,package-ownership}.json` |
| RF01–RF22 审计 | `td/refactor-execution/handoff-requirements-audit.md` / `.json`；本文已纠正其中历史 policy 近似计数与状态采样口径 |
| 本次仓库快照 | `td/refactor-execution/handoff-snapshot-2026-09-20.json` |
| 最近三次验证 | `td/refactor-execution/rf04-dat-resource-checkpoint.json`、`rf04-test-batch8-checkpoint.json`、`rf04-archive-origin-proof-checkpoint.json` |
| 17 项申请 | `td/refactor-execution/rf04-exact-protocol-exceptions-17.md` / `.json` |
| B2 与 CRC 修复 | `td/refactor-execution/rf04-archive-b2-result.json`、`rf04-archive-b2-eof-fix-result.json` |
| RPG 实现与审阅范围 | `td/refactor-execution/rf04-rpgmaker-detector-implementation.json`；Retrom `.artifacts/refactor/rf04-rpg-checkpoint-plan/manifest.json` |
| 最新来源证明/阻点 | `td/refactor-execution/rf04-archive-error-guard/result.json`、`actual-boundaries.json`、`actual-resource-proofs.json` |
| B3 四项未捕获 | `td/refactor-execution/rf04-archive-b3-plan.json`、`rf04-archive-b3-capture-paused-status.json` |
| 广泛公开 integration | `td/refactor-execution/rf04-archive-b2-public-product-integration-result.json`；详细事件在 Retrom `.artifacts/refactor/` |

PFB 的数据库/CAS/uploads/providers/cache 在该 Retrom worktree 的 `.pfb/workspace`，根 `.pfb` 保存共享 registry/gateway。它们是本地开发状态，不是本次根仓库文档提交的内容。此前精确验证用的 `.artifacts/refactor/test-lint-batch23-checkpoint-snapshot` 目录被多次复用；证据绑定的是记录中的 commit/tree/SHA，目录名不代表不可变快照。接手者不应盲目重跑含硬编码旧 HEAD 的历史 commit helper。

本交接任务只核对 Git/文件指纹、已有报告、容器状态及文档一致性；没有重新运行产品代码门禁、没有修改子仓库源码、没有推送或合并。本次文档检查结果应与上表历史产品验证分别理解。
