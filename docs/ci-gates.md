# CI 门禁与耗时

本轮在 `ci-gates` PFB 补齐全部 P0 的检查接线、数据库结构规则、service SQL 类型边界、lint 配置回归、公开 Content I/O 浏览器组、稳定 runtime 的 RC core 来源规则，以及 P1 的已发布 migration 不可修改。Retrom/runtime 分支均为 `codex/ci-gates`；根仓库独立维护 workspace CI 和分支保护配置。

## 检查入口

| 仓库 | 本地/CI 入口 | 新增覆盖 |
| --- | --- | --- |
| retrom-project | `make test` | workspace Python 全套、协议代际检查器自身回归；PR 和 master push 执行 |
| Retrom | `make backend-check` | service 的 `Repository.Count/Execute` 类型边界及反例、Go lint 配置回归 |
| Retrom | `make integration-test` | 真实 PG 最终结构、精确表集合、全部 migration 登记、禁用对象和空目录关系；每条规则有违规反例 |
| Retrom | `make web-check` | Web 有效 lint 规则、忽略范围回归及重复代码检测 |
| Retrom | `make ci-contracts` | 补接 3 组 PFB/runtime Python 回归、离线 migration 摘要检查 |
| Retrom | `make migration-check-released` | PR CI 对照最新已发布 GitHub stable release 的 tag SQL |
| Retrom | `make pfb-gateway-test` | 独立 Docker 网关分流/隔离检查，纳入 quality 聚合 |
| runtime | `npm run ci:checks` | 原 lint/type/Vitest/catalog 检查，加 Node script、lint 配置回归及重复代码检测 |
| runtime | `npm run test:content-io:ci` | 8 个公开 fixture 文件、25 个 Chromium 用例，无 PFB/私有游戏依赖 |
| runtime | `npm run release:build` | 正式构建在下载前验证两个来源清单：stable 禁 RC core，正式发布禁 development inputs |

Retrom 保持现有 PR 触发范围，复用 backend/integration/web/contracts，网关任务独立并行。runtime PR 将公开浏览器与原有 Provider candidate 构建并行，`quality` 聚合要求两者成功。migration 历史比对、lint/type/unit/script、支持目录同步及公开浏览器测试均在 PR 阶段完成。tag release 负责 tag 身份/来源约束、正式构建和产物校验；Retrom 同时记录当前 migration 摘要。产品真实游戏验收继续使用原入口。

## Web/runtime 重复代码检测

两个项目锁定 jscpd 5.4.2，使用 `npm run check:duplicates` 扫描各自项目内的 JS/JSX/TS/TSX，包含新目录、生产脚本及 bridge 源码。重复片段至少 120 token、10 行；忽略注释/空白，识别一致的标识符改名，并跨 JS/TS 格式比较。排除测试、声明文件、依赖及构建缓存；Web 额外排除生成 API，runtime 精确排除两个生成的 isolated bridge 输出，保留其源码。

使用 jscpd 的[原生基线](https://github.com/kucherenko/jscpd/blob/master/docs/rust.md#baseline)记录当前内容指纹与副本数量；Web 空基线，runtime 接受 22 组存量重复（扫描行数约 1.14%）。检查允许 0 组新增重复，也拒绝对同一存量片段再增加副本。日常 CI 不更新基线；有明确理由接受新增重复时，基线变更通过普通 PR 一起审阅。

Web 接入现有 `web-lint/web-check`，runtime 接入现有 `ci:checks`；回归使用真实检测器验证新增/改名/同文件/跨文件复制、行号移动、额外副本、豁免及空扫描失败。现有作业在成功/失败后上传 `.artifacts/duplicates/web/` 或 `.artifacts/duplicates/` JSON 报告，显示文件与行号。检测不新增 runner job、浏览器准备或 release 步骤。

本地完整扫描 Web 约 0.13 秒、runtime 约 0.16 秒，各自检测器回归约 0.32 秒；新增工具通过原有 `npm ci` 安装，冷安装仍包含平台二进制下载。云端增量待首轮 PR 复核。

## 合入保护配置

配置文件位于 `.github/branch-protection/`。它们要求 PR、指定 GitHub Actions 检查成功，禁止 force push/删除 master；审批人数为 0，保留管理员绕过，不要求分支每次先更新到最新 master。检查来源 app ID `15368` 来自当前真实 check-run API；Retrom 的 `build` 来自 branch-image workflow。

| 仓库 | required check | 配置文件 |
| --- | --- | --- |
| retrom-project/retrom-project | `quality` | `workspace.json` |
| retrom-project/retrom | `quality`、`build` | `retrom.json` |
| retrom-project/retrom-runtime | `quality` | `runtime.json` |

本次交付只准备配置，**尚未修改远端分支保护**。将各仓库功能分支合入、确认新检查实际通过后，从根仓库执行：

```bash
gh api --method PUT repos/retrom-project/retrom-project/branches/master/protection --input .github/branch-protection/workspace.json
gh api --method PUT repos/retrom-project/retrom/branches/master/protection --input .github/branch-protection/retrom.json
gh api --method PUT repos/retrom-project/retrom-runtime/branches/master/protection --input .github/branch-protection/runtime.json
```

这些命令设置上述完整保护配置；执行前读取当时的远端设置，保留期间新增的团队要求。门禁配置和回归本身按普通 PR 审阅。

## 耗时核对（2026-10-28）

已实测新增命令，并读取改动前的成功 Actions 记录。以下“预计变化”基于当前 workflow 并行关系及历史 runner 耗时，**新 workflow 尚未在 GitHub runner 执行**。依赖/浏览器下载、Actions 排队和不同机器速度会影响结果；本地已安装依赖、复用 Chrome，浏览器安装时间计入 PR 浏览器 job 的云端估计。

| 流程 | 最近成功的原耗时 | 预计等待变化 | 预计 runner 累计执行时间变化 |
| --- | --- | --- | --- |
| workspace PR | 原先无 CI | 20–45 秒 | 20–45 秒 |
| Retrom 产品 PR | 8 分 05 秒 | 约 0–10 秒 | 约 30–90 秒 |
| Retrom 纯文档 PR | 浏览器原本跳过 | 约 5–20 秒 | 约 30–90 秒 |
| Retrom 镜像 tag release | 4 分 11 秒 | 约增加 2–10 秒 | 约增加 2–10 秒 |
| runtime PR | 4 分 24 秒 | 约 5–15 秒 | 约 1.5–3 分钟 |
| runtime tag release | 4 分 46 秒 | 约减少 1–2 分钟 | 约减少 1–2 分钟 |

“等待”取最长依赖链；“累计执行时间”将并行 job 相加，未按账单逐 job 进位。Retrom 原产品浏览器矩阵最长 job 为 7 分 42 秒，新增检查所在任务明显更短，branch-image 保持原流程。runtime 原 PR quality job 为 4 分 21 秒，新增浏览器可与这条链重叠。Retrom 不新增 master push 的整套 CI；workspace 的轻量检查和 runtime 已有的 master push 检查在合入后后台执行，不与 tag 工作流串行连接。

按 PR/发布职责调整后，release 已移除 migration 历史比对和整套源码/浏览器质量检查。runtime 原线上 release 的 lint、typecheck、`npm test` 分别为 6、6、101 秒，合计 113 秒；这些现由 PR 门禁承担，release 新增的来源预检和 package 校验为秒级。因此原先 runtime release“增加 1–3 分钟”的估计已撤销，当前预计比原线上流程缩短约 1–2 分钟。Retrom release 的增量来自 master 来源检查及 migration 清单生成/上传。

新增检查的本地实测：

| 命令/检查 | 实测 |
| --- | --- |
| workspace `make test` | 5.49 秒 |
| Retrom 离线 migration / 最新发布联网比对 | 0.11 / 3.77 秒 |
| Retrom 3 组补接 Python 回归合计 | 0.19 秒 |
| Go 类型边界及 lint 配置回归 / 扫描实际 service | 2.08 / 1.63 秒 |
| PG schema 正常与违规用例，含编译启动 | 1.22 秒 |
| Web lint 配置回归 | 约 1.1 秒 |
| PFB Docker 网关测试 | 1.82 秒 |
| migration 发布清单生成 | 0.04 秒 |
| runtime Node script 回归 | 2.45 秒 |
| runtime 公开 Chromium 25 项 | 27.81 秒 |
| runtime catalog / package 检查 | 4.32 / 3.29 秒 |

原有线上证据：[Retrom CI](https://github.com/retrom-project/retrom/actions/runs/40525269923)、[branch-image](https://github.com/retrom-project/retrom/actions/runs/40525270036)、[镜像 release](https://github.com/retrom-project/retrom/actions/runs/40527351936)、[runtime PR](https://github.com/retrom-project/retrom-runtime/actions/runs/40522179736)、[runtime release](https://github.com/retrom-project/retrom-runtime/actions/runs/40523465599)。本地命令、环境和线上逐 job/step 时间保存在 [原始测量数据](research/ci-gates-measurements-2026-10-28.json)。

首个合入后的正常 PR 和下一次常规 tag release 应复核该估计；无需为计时额外发布版本。本轮未运行私有游戏验收、完整 Provider/core 下载打包或生产双镜像构建。
