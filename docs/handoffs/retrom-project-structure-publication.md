# Retrom 重构成果发布记录（2026-09-20）

本记录更新 [12:58 的交接快照](retrom-project-structure.md)。用户随后明确要求将所有重构成果提交到 GitHub 并创建 PR；原来未提交的 127 个相关路径现已全部入库。整体重构仍未完成。

- 代码 Draft PR：[retrom-project/retrom #57](https://github.com/retrom-project/retrom/pull/57)。
- 分支：`testcgd/retrom:refactor/retrom-project-structure`，目标 `retrom-project/retrom:master`。
- 当前提交：`6fb031a90ef9db0a3dd3b6578d6d4925ed00ed57`；tree：`df7a7752cb24e720c7dab598d6f9626a9df0114f`。
- 从固定基线 `82834bad` 起共 60 个提交。新增检查点收录 127 个原待处理路径；Git 识别 5 个测试移动后统计为 122 个变更文件。
- Retrom 源码工作树和暂存区已清空；runtime 保持 `3ba27985`，没有新增改动或空提交。
- [机器可读发布清单](retrom-project-structure-publication.json) 包含本批路径与哈希、提交/tree、测试命令和结果，以及原注释到已发布字节的映射。

## 已保存的成果

代码 PR 包含基线盘点、操作/策略与所有权登记、共享 Model、部分 Adapter 迁移、DAT 生命周期、测试整理和架构检查器，以及这次完整收入的 B2 archive / RPG Maker 实现及真实消费者。五个移动测试原有的顶层测试名称全部保留。

70 个原未跟踪文件全部是 B2/RPG 的源码或兼容性测试资料，包含文本 golden、捕获源与相对 provenance；没有把私有 ROM/BIOS、游戏、凭据、Provider 缓存或 PFB 数据纳入 Git。根目录原有 ZIP 及 Zone.Identifier 项保持原样。

10 条未获批准的 `nolint` 已改为普通解释注释，保留原理由和代码行为，没有登记中央 allowlist、改变错误包装或放宽超时/质量标准。因此旧交接 JSON 中这三个文件的哈希属于发布前快照；发布清单保存当前字节。17 项协议例外仍未获得批准。

## 本次验证

以下验证针对新提交的同一份源码执行；源码摘要前后保持一致。没有将旧检查点 PASS 当作本批 PASS。

| 检查 | 实际结果 |
| --- | --- |
| 精确路径、文件哈希与 `git diff --check` | PASS |
| 结构、格式、构建 | PASS |
| `make -k backend-check` | FAIL；默认测试 148 包 PASS、architecture 包失败；另有 17 项 lint finding |
| `make integration-test` | FAIL；148 包 PASS，architecture 包相同两项测试失败 |
| 串行单独复跑 architecture integration | FAIL，相同超时再次出现 |
| archive / RPG detector / libraryimport / gamecontent / firmware / serverimport 聚焦 race | 6 / 6 包 PASS |

失败测试为：

- `TestRefactorRF03_adapter_free`
- `TestRefactorRF03_no_reexport`

三次均报告 `architecture: incomplete Go type analysis: context deadline exceeded`。单独复跑没有修改规则或超时，故目前不能把该问题只归因于整套测试并行。

lint 为 **15 wrapcheck、1 nilnil、1 errorlint**。本批 `backend-check` 同时在 test 和 lint 两阶段失败，不能写成“默认测试通过、仅 lint 失败”。详细原始日志保存在本地 ignored `.artifacts/refactor/pr-publish`；可移交的命令、结果和日志指纹已在 JSON 中记录。

未在本次重新执行完整 Web E2E、私有样本验收和最终 RF22 验证。最近已有架构报告的 NOT_READY / 811 条违规 / 9 类 pending 检查仍是历史工作树报告，并非此提交的新报告。

## PR 状态与剩余工作

GitHub 已确认代码 PR 为 Draft；相对新上游 `36574c39`（Content I/O #56）存在 **CONFLICTING / DIRTY** 合并状态。本次保存原重构成果，没有把该上游改动合入或执行合并。接手时须处理上游集成冲突，并重新验证受影响的产品边界。

后续优先级：

1. 解决两个可复现的架构分析超时、17 项协议 lint 问题及 ASAR sentinel 来源证明。
2. 处理与上游 Content I/O 的集成冲突，核对新旧资源边界和实际消费者。
3. 继续原 RF04、RF05、RF02 及领域/前端迁移顺序，完成逐项退出条件。
4. 在干净、固定的最终 HEAD 上完成完整验收；私有样本缺项按用户决定继续单列。

根仓库用 `codex/retrom-refactor-handoff` 单独提交交接与发布元数据，不包含已关闭的旧 PR #8 的 AGENTS 文案。原 `codex/add-user-facing-instruction` 分支及 `f74e1b82` 提交仍保留。源代码始终由 Retrom 子仓库管理。

`retrom-project-structure.md` 和 `retrom-project-structure-state.json` 保留 12:58 的历史快照，其中“59 提交、127 未提交路径、5 暂存删除、70 untracked”描述的是发布前状态；接手当前分支以本记录及发布 JSON 为准。
