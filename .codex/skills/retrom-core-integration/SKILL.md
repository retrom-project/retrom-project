---
name: retrom-core-integration
description: 在 Retrom 首次接入新的浏览器游戏核心，或为已接入核心扩展平台且涉及内容加载时使用；协调核心仓库、retrom-runtime 与 Retrom 的实现、候选验收和正式发布。不用于单纯的版本升级、输入或存档行为修改、调研或 PFB 生命周期管理。
---

# Retrom 核心集成

本 skill 指导新核心首次接入，以及已接入核心扩展平台时的内容加载集成。单纯的输入、存档、退出、性能或版本维护按所属仓库规范处理；能力验收仍由各仓 `AGENTS.md` 和产品 Case 规定。

## 职责与事实源

按核心实际架构选择 Provider，不能预设所有核心都属于 EmulatorJS。先阅读所选 Retrom、retrom-runtime 的适用 `AGENTS.md`；已有独立核心仓库时还要阅读其 `AGENTS.md`、`retrom-fork.json`（如有）和维护文档。从所选 Retrom checkout 的 `workspace/manifest.yaml` 确认仓库、维护分支与依赖关系。Retrom 的 `docs/core-runtime-validation.md`、`docs/project-acceptance.md` 和 `docs/dependency-management.md` 分别负责能力边界、产品 Case 与正式依赖。这里规定跨仓顺序，不替代各仓的门禁。

独立核心仓库或 fork 拥有第三方核心源码、构建、许可证与核心 Release；retrom-runtime 拥有 Provider 来源、Target declaration、adapter 与 checkpoint codec；Retrom 拥有平台、内容识别、BIOS、Target binding、正式 Provider 选择与产品验收。不要在 runtime 中临时编译第三方核心，也不要为新核心增加绕过公共 Provider/Launch 的宿主专用入口。

本地 `RETROM_MODE=test` 开发实例的默认测试账号为 `test/test`。产品验收先使用该账号；环境已显式覆盖账号或密码时以实际配置为准。若登录失败，先核对测试模式与配置，确认没有可用测试凭据后再向用户询问。不要将此账号用于正式环境。

## 实施顺序

1. **确定接入边界。** 查明上游来源与再分发许可、浏览器构建方式、游戏文件与 BIOS/外设要求、资源体量、核心是否能按偏移读取内容及已知限制。逐平台核对核心实际支持的内容格式、扩展名、主文件与伴随文件、BIOS，以及 Retrom 当前的平台识别和 Target binding；标明核心能运行但产品尚未暴露的组合，用真实样本确定接入范围。确认有会话授权使用的游戏/BIOS；没有实际样本时明确产品验收会被阻断，不能用模拟画面替代。除上述公开测试账号外，第三方游戏、BIOS、凭据与核心构建产物不得提交到仓库。
2. **准备隔离源码。** 跨仓实施使用命名 PFB，并按 [retrom-pfb-workflow](../retrom-pfb-workflow/SKILL.md) 准备同一 PFB 树中的 Retrom、runtime 与 core worktree。新增依赖只改该 PFB 的 Retrom `workspace/manifest.yaml`。若用户明确要求直接修改基线，遵从用户范围。fork 存在时按其维护分支开发，不把 Retrom 补丁写入上游镜像分支；是否 fork 或向远端写入以本次会话授权为准。
3. **完成核心候选。** 新核心或需修改核心时，在独立核心仓库或 fork 中实现构建、原生/浏览器检查和 Release 所需的资产、许可证、来源元数据；明确 adapter ABI。对同一输入重复构建并比较完整归档的字节摘要，包含 tar/zip 元数据，不能只比较其中的 JS/WASM。通过 PFB 的显式 core build 取得候选字节；第三方核心源码和补丁留在核心仓库。仅扩展已有核心的 Target/adapter 且核心字节不变时，复用已固定的核心资产。
   默认须尽可能实现符合 runtime 规范的即时或游戏原生存档，并验证新 Launch 恢复。`NO_SAVE` 只用于用户明确允许该平台不支持存档的范围；核心当前没有序列化接口、实现困难或缺少测试素材本身都不构成启用许可。该语义在现有公共契约中由 `capabilities.checkpoint: false` 与 `checkpoint: null` 表示，宿主也须明确提示不能创建或恢复存档。不生成占位 checkpoint，也不能把分数、设置或 NVRAM 冒充进度恢复。保留尝试实现存档的事实、限制和未来补齐条件；其他平台的存档准入不随之放宽。
4. **登记 Provider Target。** 在对应 Provider 来源清单声明候选或已发布的固定来源，在 Provider catalog 声明独立 Target、运行文件、选项和能力；两处职责不能互换。实现新核心所需的 adapter，并按 runtime 仓库规范补齐准入回归，不在本 skill 中另设输入或存档行为规则。先定位核心或封装层的共享文件系统入口；可统一接入时，让文件打开、定位、读取和关闭通过 retrom-runtime 的 Content I/O，避免按光盘格式或平台另设下载旁路。确需格式专用桥接时，记录共享入口无法覆盖的原因，并验证其他格式仍走原有路径。
   核心能够按需随机读取游戏内容时，使用通用 Range reader/session 管理网络请求、分块缓存、校验、取消和生命周期，核心桥接只转发必要的文件操作。必须先完整物化内容时，使用 runtime 的公共持久缓存，以稳定内容身份复用并校验文件字节数；不能只依赖浏览器 HTTP 缓存。一个核心支持多个平台时，在共享加载路径实现并复用相应能力，平台可以有各自的格式、BIOS 和 Target 配置，但不得为每个平台另造下载路径。
5. **接入 Retrom 产品。** 补平台与格式识别、BIOS/依赖装配、`providerId + targetId` binding 和对应文档、产品 Case。不得用默认 Target 回退掩盖声明缺失。第三方测试素材只走授权输入，不能进入 Git、Provider 归档或镜像；自有或明确可再分发的 fixture 遵守 Retrom 仓库准入规则。
6. **验收候选。** 用同一 PFB 的核心与 runtime 构建完整 Provider 候选，验证资产身份与摘要；走真实 Retrom 上传/导入、Review Preview、发布和 Product Launch，完整执行新核心适用的产品 Case。先在 Review Preview 中确认浏览器线程与 WASM 初始化、文件挂载和首帧，再执行后续能力 Case；构建成功本身不代表浏览器能够启动。Range 路径须验证启动前不会整包物化、读取请求有界；完整物化路径须跨两个独立 runtime 实例核对网络请求，确认再次启动不会重复下载整包。多平台共享核心时覆盖各平台 Target，确认使用同一核心加载机制。检查各浏览器运行阶段的 console；出现报错时，包括以 warning 级别输出的 WebGL/API 错误，须分析来源、修复并复测，不能仅凭数据断言和截图通过判定候选通过。
   每个新增平台 Target 至少用一个真实、可游玩的游戏验证手柄输入。先核对该游戏实际使用的核心按键映射，确认开局必需按键（如投币、Start）没有映射到 `SWITCH_NOTHING` 等无效操作；再从 Retrom 产品页面实际操作手柄，记录操作前状态、按键及操作后可观察的游戏状态，确认能进入可玩状态并完成方向和主要操作。调试面板提供按键显示时，核对其显示与实际按键一致。仅收到浏览器按键事件、调用了输入接口或看到待机动画变化，均不能算输入 Case 通过；无法证明状态转换时，明确标记该 Case 未通过并保留证据。
   接入改动触及共享内容加载、宿主显示或渲染路径时，选有代表性的现有核心做回归。涉及高分辨率或性能时，记录实际渲染尺寸、帧率和主线程负载；缩小并恢复浏览器视口后，核对 iframe、画布尺寸与游戏原有宽高比。通用像素预算和布局问题应在所属共享层解决，不为单一平台增加特例。保留错误记录、结构化结果和当次截图，并逐图检查。修复失败后重跑原 Case；单一游戏通过仅证明该样本。
7. **按依赖顺序发布。** 候选通过后，若核心资产改变，先按 fork 维护规则合入并发布不可移动的核心 tag，复核 Release 的资产、许可证、commit 与摘要；再把 runtime 的候选来源换成固定的 repository、tag、commit、asset 与 ABI。核心资产未变时沿用已有固定来源。运行 runtime 的 Provider/聚合门禁，合入并发布 runtime tag；最后用 Retrom 的 `runtime-provider-pin-release` 固定已发布 runtime tag，准备并导入正式 Provider，重跑同一产品 Case，再完成 Retrom 门禁与发布。正式锁定中不得出现候选摘要、工作树路径或浮动分支。PR、合入、tag 和对外发布须由本次或此前会话的用户授权覆盖；已授权时直接推进。

## 正式复验与交付

正式包复验要核对实际运行的 core、Provider Bundle/module 和版本，并覆盖产品 Case 声明的每个阶段。如果复用已发布游戏而跳过 Review Preview，须另行验证正式资产的审核预览；无法完成时按验收规范报告缺口，不能宣称正式版全链路通过。

交付时报告各仓分支、PR/tag/Release、真实运行的资产摘要、候选与正式 Case 结果、逐图复核结论、未覆盖的 BIOS/外设/游戏范围、PFB 状态，以及基线 checkout 和工作树是否干净。只记录已验证的能力与发布结果。
