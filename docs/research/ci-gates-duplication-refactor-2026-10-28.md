# ci-gates 存量重复代码重构与验证

runtime 的 22 组存量重复已全部消除，Web 和 runtime 当前均为 **0 组重复、空基线**。`minTokens: 120`、`minLines: 10`、检测模式、扫描范围和排除项均保持不变，没有新增豁免或压低阈值。计数、构建耗时、模块身份和逐核心覆盖见 [结构化记录](ci-gates-duplication-refactor-2026-10-28.json)。

runtime 提交为 [`2fc6d18`](https://github.com/retrom-project/retrom-runtime/commit/2fc6d18fa7ab42744a98408b1bd062ccba05d35b)，已推送 `codex/ci-gates`。本轮没有修改 Retrom 的产品源码，其提交仍为 `ce30351f124521be7dc05579b7e8b98b65a7384b`。这是本地检查及候选验证记录；当前两个功能分支均没有打开的 PR，尚无对应 GitHub Actions 运行，Retrom 双镜像仍由 PR runner 验证。

## 实现范围

| 原重复逻辑 | 公共实现及保留边界 |
| --- | --- |
| Fantasy、MAME、NXEngine、PX68K 音频队列 | 公共 stereo PCM 队列；每个核心保留原采样上限、原生 ABI 和错误码 |
| NXEngine/PX68K 帧循环、事件与方向映射 | 公共帧调度、事件释放、joypad bit 转换；原键盘和手柄映射不变 |
| Ruffle/WebMSX 游戏文件物化与手柄轮询 | 统一使用原 Content I/O 策略、真实加载进度和相同按键生命周期 |
| NXEngine/OpenBOR 原生存档 JSON 封包 | 共用有界编码、解码和规范 base64；各自文件名、原生数据校验及格式声明不变 |
| Play/PSP 生命周期和 checkpoint 操作 | 共用启动失败处理、取消、退出清理及字节复制；格式、上限和错误码不变 |
| 原生 Web/Tyrano RPC 回复完成 | 认证、nonce 和请求关联仍由原 channel 校验，公共函数只完成已关联的 pending 回复 |
| 多个 Canvas 截图、MV/MZ 角色条目 | 提取原有截图行为及角色过滤，重新生成 isolated bridge |
| OpenBOR/Ruffle/WebMSX candidate 校验 | 共享完整有序文件集校验与 staging；保留每个核心的仓库、ABI、文件清单和大小上限 |
| 两个 Provider Bundle 构建 | 共用临时目录、资产索引、指纹、client 和 bundle 发布；保留各自资产来源、许可及 provenance |

Content I/O 的截图边界登记随实现迁入公共模块，移除不再存在的重复路径。没有改变协议、存档格式、版本标识、核心来源 pin 或 Retrom production lock。

## 源码与候选门禁

| 检查 | 结果 |
| --- | --- |
| runtime jscpd | 412 个文件，38,814 行，0 组重复；基线为空 |
| Web jscpd | 207 个文件，0 组重复；基线为空 |
| runtime lint / typecheck | 通过 |
| runtime Vitest | 2,365 通过，0 失败，0 跳过；新增 20 个公共边界用例 |
| runtime Node scripts | 76 通过，0 失败，0 跳过 |
| 公开 Chromium Content I/O | 25 通过，0 失败，0 跳过，本机约 32.4 秒 |
| 支持目录同步 | 通过 |
| 完整 Provider candidate 聚合 | 通过，本机约 169.6 秒；只聚合固定 fork 资产，未编译核心或发布产物 |
| package 校验 | 通过，本机约 2.7 秒 |
| 协议代际预检 / diff 空白检查 | 通过 |

新增用例覆盖 PCM 样本范围和队列清理、暂停后帧时钟重置、事件释放、取消与启动失败清理、退出期间 checkpoint 竞态、两种原生存档的精确 JSON 字节及异常输入。全量测试发现并修正了 bridge 公共函数重名和截图边界登记遗漏，随后完整 2,365 例通过。

本轮没有增加 CI job、release 检查或浏览器安装步骤。额外 20 例进入已有 Vitest 门禁，重复检测仍进入已有源码检查；上述本机耗时包含缓存复用，不用于推算云端增量，也不与前轮冷缓存构建作性能比较。

## 产品候选复验

本次复验使用当前源码生成的 loose dev module，基座为已验证的正式 `v0.90.0`。每个 Run 均核对 `/dev/` 模块路径；两个 Provider 共 112 个 Target 的核心指纹与正式基座全部一致，客户端模块更新不改变存档的核心身份。

9 个核心均经正常来源扫描、审核预览、发布、Product Launch、输入、暂停/恢复和退出清理。FAKE-08、WebMSX、PX68K、PPSSPP、MAME PV-1000、RPG Maker MV 六项另验证非空 payload 持久化、退出后的不同 Run 恢复及恢复后输入；保存的压缩 payload 大小分别为 48,446、6,489、1,619,734、327,998、1,307、6,906 字节。23 条记录的 Run 均核对为本次同一候选模块。

OpenBOR 和 NXEngine 的本轮游戏运行未完成游戏内原生进度保存与读取，不能计为完整原生存档验收。其公共封包通过原单元测试及新增的精确字节、格式、身份、文件集合和错误输入回归；未生成占位存档或放宽声明语义。

Ruffle 另验证 203 字节的真实 SharedObject 存储容器在不同 Run 导入，恢复后键盘输入可移动画面中的对象。该 Target 声明的是 `STORAGE`，此结果不扩展为关卡进度保证；对应 Run、截图及输入复核保存在机器证据中。

这是一组受影响核心的候选抽样，不表示全部核心、全部游戏或完整 T01–T47 已通过。本轮不重复修改无关的 Go、Web 或数据库实现。

验收驱动的初始失败记录均保留：项目来源改为导入完整目录，输入通过可见 Player 表面投递，MV 先用真实键盘推进禁用保存的开场剧情，再验证保存。不修改游戏源码、产品源码、既有 CI 超时或断言，不跳过保存检查。私有素材、路径、账号会话、游戏副本和机器记录只保存在忽略目录。

## 环境与证据

PFB 为 `ci-gates`，ID `ci-gates-3f907034bba7`，源码根 `.worktree/ci-gates/project/`，访问地址为 `http://ci-gates-3f907034bba7.localhost:3000`。PFB 已启动且基础 verify 通过；`PFB_SELECT=false`，未切换裸 `localhost:3000`。新数据和验收副本均属于该 PFB，来源只读。复用根 `tools/` 的 Node 24.22.1、npm 11.19.1 和 Chrome，以及现有开发工具链镜像；本轮未新增共享工具或构建生产镜像。

仅当前 PFB 的 app/PostgreSQL/Redis、workspace 及共享 registry/网关控制面按正常命令更新，未停止其他 PFB。基线 child checkout 工作文件保持干净，根仓库原有未跟踪文档保留。

runtime 原始检查、JSON 和构建结果位于 `.worktree/ci-gates/project/retrom-runtime/.artifacts/dedup-20261028/`；公开浏览器结果位于同仓库 `.artifacts/content-io/ci/results.json`。产品汇总位于 Retrom 的 `.artifacts/dedup-20261028/product-summary.json`，各轮原始报告、截图及手工复核位于相邻目录。PFB 基础验证证据为 Retrom `.pfb/evidence/20261028T124026Z/`。
