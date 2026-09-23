---
name: retrom-core-integration
description: 在 Retrom 首次接入新的浏览器游戏核心时使用；协调核心仓库、retrom-runtime 与 Retrom 的实现、候选验收和正式发布。不用于已接入核心的版本升级、输入或存档等行为修改，也不用于单纯调研或 PFB 生命周期管理。
---

# Retrom 核心集成

本 skill 只指导新核心首次接入。已接入核心的输入、存档、退出、性能或版本维护按所属仓库规范处理，不触发本 skill；首次接入所需的能力验收仍由各仓 `AGENTS.md` 和产品 Case 规定。

## 职责与事实源

按核心实际架构选择 Provider，不能预设所有核心都属于 EmulatorJS。先阅读所选 Retrom、retrom-runtime 的适用 `AGENTS.md`；已有独立核心仓库时还要阅读其 `AGENTS.md`、`retrom-fork.json`（如有）和维护文档。从所选 Retrom checkout 的 `workspace/manifest.yaml` 确认仓库、维护分支与依赖关系。Retrom 的 `docs/core-runtime-validation.md`、`docs/project-acceptance.md` 和 `docs/dependency-management.md` 分别负责能力边界、产品 Case 与正式依赖。这里规定跨仓顺序，不替代各仓的门禁。

独立核心仓库或 fork 拥有第三方核心源码、构建、许可证与核心 Release；retrom-runtime 拥有 Provider 来源、Target declaration、adapter 与 checkpoint codec；Retrom 拥有平台、内容识别、BIOS、Target binding、正式 Provider 选择与产品验收。不要在 runtime 中临时编译第三方核心，也不要为新核心增加绕过公共 Provider/Launch 的宿主专用入口。

## 实施顺序

1. **确定接入边界。** 查明上游来源与再分发许可、浏览器构建方式、游戏文件与 BIOS/外设要求、资源体量及已知限制。确认有会话授权使用的游戏/BIOS；没有实际样本时明确产品验收会被阻断，不能用模拟画面替代。第三方游戏、BIOS、凭据与核心构建产物不得提交到仓库。
2. **准备隔离源码。** 跨仓实施使用命名 PFB，并按 [retrom-pfb-workflow](../retrom-pfb-workflow/SKILL.md) 准备同一 PFB 树中的 Retrom、runtime 与 core worktree。新增依赖只改该 PFB 的 Retrom `workspace/manifest.yaml`。若用户明确要求直接修改基线，遵从用户范围。fork 存在时按其维护分支开发，不把 Retrom 补丁写入上游镜像分支；是否 fork 或向远端写入以本次会话授权为准。
3. **完成核心候选。** 在独立核心仓库或 fork 中实现构建、原生/浏览器检查和 Release 所需的资产、许可证、来源元数据；明确 adapter ABI。对同一输入重复构建并比较完整归档的字节摘要，包含 tar/zip 元数据，不能只比较其中的 JS/WASM。通过 PFB 的显式 core build 取得候选字节；第三方核心源码和补丁留在核心仓库。
4. **登记 Provider Target。** 在对应 Provider 来源清单声明候选或已发布的固定来源，在 Provider catalog 声明独立 Target、运行文件、选项和能力；两处职责不能互换。实现新核心所需的 adapter，并按 runtime 仓库规范补齐准入回归，不在本 skill 中另设输入或存档行为规则。
5. **接入 Retrom 产品。** 补平台与格式识别、BIOS/依赖装配、`providerId + targetId` binding 和对应文档、产品 Case。不得用默认 Target 回退掩盖声明缺失。第三方测试素材只走授权输入，不能进入 Git、Provider 归档或镜像；自有或明确可再分发的 fixture 遵守 Retrom 仓库准入规则。
6. **验收候选。** 用同一 PFB 的核心与 runtime 构建完整 Provider 候选，验证资产身份与摘要；走真实 Retrom 上传/导入、Review Preview、发布和 Product Launch，完整执行新核心适用的产品 Case。保留结构化结果和当次截图，并逐图检查。修复失败后重跑原 Case；单一游戏通过仅证明该样本。
7. **按依赖顺序发布。** 候选通过后，先按 fork 维护规则合入并发布不可移动的核心 tag，复核 Release 的资产、许可证、commit 与摘要；再把 runtime 的候选来源换成固定的 repository、tag、commit、asset 与 ABI，运行其 Provider/聚合门禁，合入并发布 runtime tag；最后用 Retrom 的 `runtime-provider-pin-release` 固定已发布 runtime tag，准备并导入正式 Provider，重跑同一产品 Case，再完成 Retrom 门禁与发布。正式锁定中不得出现候选摘要、工作树路径或浮动分支。PR、合入、tag 和对外发布须由本次或此前会话的用户授权覆盖；已授权时直接推进。

## 正式复验与交付

正式包复验要核对实际运行的 core、Provider Bundle/module 和版本，并覆盖产品 Case 声明的每个阶段。如果复用已发布游戏而跳过 Review Preview，须另行验证正式资产的审核预览；无法完成时按验收规范报告缺口，不能宣称正式版全链路通过。

交付时报告各仓分支、PR/tag/Release、真实运行的资产摘要、候选与正式 Case 结果、逐图复核结论、未覆盖的 BIOS/外设/游戏范围、PFB 状态，以及基线 checkout 和工作树是否干净。只记录已验证的能力与发布结果。
