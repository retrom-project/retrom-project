# ci-gates 合入远端后的 CI 复跑（2026-10-28）

`ci-gates` PFB 已合入本次 fetch 得到的两仓库 `origin/master`，均无冲突；每仓库新增两个主线提交。工作区仓库的 master 没有新增提交。当前本地复跑结果为 **0 个失败测试用例、0 个未通过的已执行 CI 检查**；另有 Retrom `branch-image/build` 未执行，不能据此宣称全部 GitHub required checks 已绿。

这是按 PR CI 命令在本机复跑的记录，没有为本次检查创建 PR、tag 或 Release，GitHub Actions 未执行这些新分支提交。执行命令、退出码、耗时和原始日志位置见 [JSON 记录](ci-gates-post-merge-2026-10-28.json)。

## 代码快照

| 仓库 | 合入的远端 master | 验证的 PFB HEAD |
| --- | --- | --- |
| Retrom | `bc2992adeb4706940d2b73f30575158ac2d21e9b` | `ce30351f124521be7dc05579b7e8b98b65a7384b` |
| runtime | `3d0f4867dbb1f2d1d5e706a4b00ad72fd1fd0b65` | `cd056a9cdaabec68a92ac625e2e6ef5837ddf47b` |

两仓库分支均为 `codex/ci-gates`，已推送。runtime 完整 Provider 聚合和原源码检查在 merge commit `4b49661` 通过，随后只有浏览器 JSON 报告路径的一行修复；该修复另经 lint 和真实浏览器 25 例验证。Web/runtime 重复代码基线、阈值和排除项均未更改。

## 用例及门禁

| 范围 | 结果 |
| --- | --- |
| workspace Python / 协议检查器回归 | 59 通过，0 失败 |
| Retrom Go 普通测试 | 496 通过，0 失败（含子用例；210 个顶层测试） |
| Retrom Go integration 标签全套 | 585 通过，0 失败（含子用例；268 个顶层测试，包含普通测试） |
| Retrom Python 结构/数据/工具链回归 | 231 通过，0 失败 |
| Web Vitest | 575 通过，0 失败 |
| Web UI/门禁 Node 回归 | 13 通过，0 失败 |
| Retrom 产品浏览器四视口 | 36 通过，0 失败，0 跳过 |
| runtime Vitest | 2,345 通过，0 失败 |
| runtime Node scripts | 76 通过，0 失败 |
| runtime 公开 Chromium Content I/O | 25 通过，0 失败，0 跳过 |
| 格式、lint、类型、Go/Web build、API 生成同步、支持目录同步 | 全部通过 |
| migration 离线/最新已发布基线比对 | 通过；本次读取的最新 stable 为 `v0.0.160` |
| 独立 Docker PFB 网关路由与隔离 | 通过 |
| runtime 完整 Provider candidate 构建与 package 校验 | 通过；聚合构建本地约 301 秒，未发布任何产物 |

Go 的 integration 全套会包含普通测试，不将两行相加作为去重后的测试总数。浏览器保持原超时、无重试，四项目为 `chrome-1280`、`chrome-1440p`、`chrome-4k-150`、`chrome-mobile`。

| 重复代码 | 扫描文件 | 检出片段 | 新增片段 | 门禁 |
| --- | --- | --- | --- | --- |
| Web | 207 | 0 | 0 | 通过 |
| runtime | 414 | 22 | 0 | 通过 |

runtime 的 22 组为原基线中的存量重复，442 行，约 1.13%；没有新增可阻断的重复。未运行 baseline 更新命令。

## 首轮异常与修正

首轮使用的 `TMPDIR=/tmp/rci3f9` 是指向 PFB 磁盘目录的符号链接。Go integration 有两例 normalizing 输出路径验证失败，PostgreSQL 准备脚本回归有一例物理/字面路径不一致；改用真实磁盘路径 `/var/tmp/rci3f9` 后，Go integration 全量 585 例和工具链 8 例全部通过。没有修改业务代码、测试断言或超时；初始失败日志与复跑日志均保留。

核对证据时还发现 runtime 的 JSON reporter 相对路径按 Playwright 配置目录解析，原结果写在 `tests/content-io/.artifacts/`，未进入 CI artifact 目录。提交 `cd056a9` 使用绝对解析路径修正；25 例复验后，报告位于 `.artifacts/content-io/ci/results.json`，可被现有上传步骤收集。

额外执行 actionlint 并启用 ShellCheck 0.11.0 时，Retrom 既有 `branch-image.yml:77` 的连续 summary 重定向触发一条 `SC2129` 风格提示。现有 CI 未配置该检查，故未将它计入失败 CI 用例；原脚本未改动。

## 验证边界与环境

Retrom `branch-image/build` 的双镜像构建、镜像闭包和部署链验证尚未执行。[PFB skill](../../.codex/skills/retrom-pfb-workflow/SKILL.md) 规定“PR 的 `branch-image/build` 在 GitHub runner 上验证双应用镜像可构建”，并要求“不要为发布门禁在 PFB 或基线开发机运行 `make build-images` 下载第二份完整 Provider 包”。本次没有创建 PR，因此该项保留为未验证，未计作失败或通过。

PFB 名称 `ci-gates`，ID `ci-gates-3f907034bba7`，目录 `.worktree/ci-gates/project/`，保留 URL `http://ci-gates-3f907034bba7.localhost:3000`；状态仍为 INITIALIZED，未启动日常 PFB 应用。产品浏览器使用独立临时数据库、Redis、Go/Next 服务和正常公共导入路径。Retrom 使用本分支固定的正式 runtime `v0.90.0` 输入；runtime 聚合使用同一 PFB 源码与固定的已发布 fork 资产，没有编译 core。

Node 24.22.1、npm 11.19.1、Go 1.26.5、Chrome、Go lint 和 actionlint/ShellCheck 复用根 `tools/` 中的共享工具。新增共享 PostgreSQL 18.3 工具、psycopg 3.3.6 工具环境和固定字体缓存，分别位于 `tools/postgresql-18.3-linux-amd64`、`tools/retrom-postgres-python-3.3.6-linux-amd64`、`tools/retrom-e2e-fonts-droid8.1-dejavu2.37-linux`。测试临时资源结束后按创建时记录的名称/ID清理；未更改共享网关选择或其他 PFB。基线 child checkout 工作文件保持干净；根仓库原有未跟踪文档保留。

原始执行日志在 `.worktree/ci-gates/project/retrom/.artifacts/ci-audit-20261028/`；产品浏览器证据在 `.worktree/ci-gates/project/retrom/.artifacts/acceptance/209d45bb274245c0/cases/acc-rf-browser/`。
