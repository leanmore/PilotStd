# 技术债 · 可修复、尚未修复

> 本文件是 `docs/technical-debt.md` 四分类之一：**未修**（正式债 + 可动作项 + 待裁定项）。
> 判据：**有明确动作可做**、且尚未做完。做完即移入 [01-archive-closed.md](01-archive-closed.md)；
> 定性为"不做/不划算"则移入 [02-accepted.md](02-accepted.md)；修完但需盯一段时间则进 [04-watch.md](04-watch.md)。
> **最后核实：2026-10-27**（每条都注明核实方式与时间戳）。
> 回主档：[technical-debt.md](../technical-debt.md)


> **2026-11-02 E 组清理**：已闭环/已取消的 26 项（A-1/2/3/6/9~16/18~21/23~26/28/30/31/35/36/39）移入 [01-archive-closed.md](01-archive-closed.md)；本文件只保留仍需动作或等待外部条件的项。
---

## 一、正式存续债（3 条）

| # | 项目 | 状态 | 现状（实测） | 下一步动作 | 触发条件 |
|---|---|---|---|---|---|
| **T-40** | V6 wechat 真发未取证 | `观察中`（用户 2026-10-17 裁定：**后续再说**） | 本地 `data/config.json` 的 `notification.channels.wechat` = `{"enabled": true, "webhook_url": ""}`（2026-10-16T22:07 实测）⇒ 非部署环境无法真发；渠道契约/错误映射/签名/i18n 单测已覆盖 | 部署环境补一次真发取证（会真的发一条消息到企微） | 用户择期（本轮不做） |
| **T-42** | 渠道调用频率限制未逐家实现 | 已闭合（tests/test_notification_rate_limit.py 存在；码优先+429/5xx 重试+Retry-After） | 实测（2026-10-16）：限流/退避**只长在 telegram**（27 处命中），`dingtalk` 1、`feishu` 1、`wechat` 4、`base.py` **0** ⇒ 一次 429/抖动只有 telegram 退避重试，其余三家当场丢通知。**2026-10-17 已修**：重试/退避提升为渠道基座 `base._with_retry`（统一 3 次、退避 (2,4)、服务端 `retry after` 优先且截顶 60s、429/5xx 与限流关键词兜底、错误 120s 去重），**四家渠道全部接入**（提交 `191b7259`，2026-10-17T06:19:36+08:00；测试 195 passed） | **残留**：各渠道限流的**具体错误码未逐家取证**（钉钉官方文档 JS 渲染取不到正文；飞书/企微未逐码核对）⇒ 现用 `looks_rate_limited` 关键词兜底，取证到 `errcode`/`code` 后改为**按码判定** | 取到任一家官方限流码时 |
| **T-43** | **企微回调取证** | **已归并入 A-27**（2026-10-29） | A-24 取消后回调只服务菜单点击；端点/验签/解密/EventKey 解析作为 A-27 P1 的验收能力；需一条真实菜单点击报文校准 `EventKey/FromUserName/AgentID` | 随 A-27 |

## 二、可动作项（有明确动作，按"值不值得现在做"排序）

| # | 项目 | 状态 | 现在能做什么 | 触发条件 / 备注 |
|---|---|---|---|---|
| **A-5** | **cookiecutter 真实 CLI 端到端未入 CI** | 观察 | 模板改动涉及 hooks 时补一条真实 CLI 用例（渲染/编译/零字面量已由 jinja2 用例覆盖） | 触发条件＝hooks 变更或脚手架被频繁使用 |
| **A-22** | **Q7：Windows 端 15 个共享事件是否走托盘（S4 真实验收）** | 挂起 | 需 Windows 端实跑：触发一个共享事件，确认进托盘且 Web 端仍收到；本机/CI 无法覆盖 | 触发条件＝用户有空在 Windows 本机跑一次（5 分钟） |
| **A-27** | **自定义菜单（企微/飞书/Telegram/钉钉）** | 调研中（2026-10-29 立项，当前主线） | 企微 a（3+5）、飞书 b（3+5 或 5+10，仅单聊）、Telegram c（命令列表）、钉钉 d（待补信息）；菜单动作映射、配置存储、静态/动态生成待方案确认；复用回调端点处理菜单 click | 方案确认后开工 |

| **A-32** | **cookiecutter 把 `myadapter.py` 判为二进制**（binaryornot 特征判定；同目录测试/README 正常） | 已兜底 | `post_gen_project.py` 用 `_CONTEXT`（`cookiecutter|tojson`）+ Jinja2 手动渲染；**属绕开行为**，判定边界：只匹配 `{{` + `cookiecutter` 字面量；**不覆盖** `{% if %}` 控制块（不含字面量会被跳过）、也可能误判合法代码里的 `{{`（如格式化字符串）。扩展其它文件前先检查这两类边界；待修复后删除该步 | 触发条件＝升级 cookiecutter 时 |

| **A-40** | **旧数据 `user_id=1` 的归属**：v71（2026-10-31 19:17）回填存量 user1。2026-11-16 查证：pre-v71 458 行中系统来源与用户动作混杂（`test`/`notification_credential_changed` 明确用户，`archive/batch/scan` 双来源）。已订正 **452 行** user1→0（备份+manifest+rollback 见 27 #57）；pre-v71 仅 test 2 + credential_changed 4 保持 1；`notification_queue` 因语义是收件人未改；2026-10-31~11-14 的 89 行仍 user1 待决 | 部分已订正（残余待决） | 依据：单用户时代唯一用户 id=1；双来源事件无法逐行溯源，故按“系统类型→0、明确用户动作→1”处理；queue 不适用 | 触发：若需清零残余 89 行，先确认是否含真实用户动作 |
| **A-42** | **API auto/archive 未传用户上下文**：两端点已有 @require_role("admin")，但调用 manager 时未传 NotificationContext(user_id=...) ⇒ 事件归 system（user 0），多用户下用户看不到自己触发的通知（原文"无 auth 依赖"已过时） | 未修 | 在调用点传 get_current_user_id() 的上下文；见多用户主线 P1 | 触发条件＝多用户主线 P1；**不阻塞主线** |
| **A-43** | **SQLite 实测表数（45）无法机械核对**：`18-schema-migrations.md` 写的"SQLite 实测业务表 45 张"来自**实跑迁移链后的 `sqlite_master` 计数**；`load_facts()` 只解析迁移源码（得到 43）。G-052 全量审计把它列为"已登记但无法机械核对"，未扩第 7 类 | 已闭合（2026-11-19 生产表数与迁移链一致；本行此前与 00-global 互斥，已对齐） | 修法二选一：① 新增"空库跑迁移后数表"的事实源（昂贵，需单独评估代价）；② 把该处数字改为"以实测为准"不写具体值 | 触发条件＝有人质疑 43/45 不一致、或动迁移链/表结构时 |
| **A-44** | **monitor 实时路径：新目录不触发（旧目录正常）**：19:02/19:06 的 572 文件写入已存在目录 → 572 条事件全部触发；12:29 后新建的 TSG 目录（33 文件）→ 零触发。推断：recursive watch 只在启动时对既有目录建 watch，新子目录依赖目录创建事件补 watch，而 Windows bind mount 下该事件未送达。规则：新目录投放必须 restart 补扫；旧目录可实时 | 已闭合（tests/test_monitor_hot_reload.py + tests/integration/test_monitor_catchup_e2e.py 均存在） | 修法：① 启动时/定时对子目录补 watch（watchdog 新目录事件 + 巡检）；② 改 `PollingObserver`（成本低，推荐评估）；③ 文档写明“新目录必须 restart”。 当前先按 ③ 执行 | 触发：实时性成为需求、或迁移 Linux 宿主时复验 |
| **A-45** | **无 dry-run/站内通知渠道**：生产渠道仅 wechat/dingtalk/feishu/telegram，`test-event` 会真实外发；AC-6 触发链路无法在生产安全复验（本次读隔离用受控 DB 种子行） | 已实现（notification.dry_run=true 只日志不投递，见 core/notification/manager.py:246；测试文件待补） | 触发：新增渠道系统，或 AC-6 需复验触发链路 | 修法：新增站内/dry-run 渠道（属新渠道系统，需产品决策）；不阻塞现有验收 |
| **A-46** | **33 个隔离文件丢失**（`file_missing`，含 `HJ 536-2009`）：误移到未挂载 `/data`，v0.191.1 重启丢失；清单 `C:\Temp\move_quarantine_manifest.json` / `a1_missing.json` | 定触发 | 触发：发现公告记录/下载链可重新获取对应标准 | 修法：重取后走归档并核销 pending；在此之前 pending 保持 `file_missing`，不伪装关闭 |
| **A-50** | **DT-12：状态色 `--warning` 对比度不足**（light 1.96/2.15、green 1.91/2.05；LogBar `log-warn` 是正文且背景为 `--bg`，需 4.5:1；圆点需 3:1） | **已修**（2026-11-21，`27` #109）：light/green `#f59e0b → #ad4f08`（light-bg 4.92 / green-bg 4.79），dark/blue 复测 8.31/8.69 不动；`themes.ts` 与 `style.css` 同批同步；`a11y-contrast.test.ts` 增四主题断言 | 已关闭（A-50 关闭，DT-12 同步关闭；未新开债号） | — |
| **A-51** | **2 条内联 `style` 尺寸无令牌**：`PendingView.vue:90`（20px 宽高）、`SystemResources.vue:49`（24px 高）。现状：两处均已改为组件属性注入（见状态列），不再用字面量 | **已修**（2026-11-21，`27` #110）：`SystemResources` 用 ProgressBar 的 `dt`（`dt('progressbar.height')`）；`PendingView` 因 **PrimeVue 4.5.5 的 ProgressSpinner 无 size/height prop**（样式内 width/height 是字面量 100px，`dt` 只覆盖四种颜色），改用官方 **`pt`（passthrough）** 注入 `var(--size-20)`。作用域限于该组件实例：未改全局 CSS、未新增 class、未动模板结构；同页仅此一个 spinner，另两处 spinner（`AnnounceDetail`、`LegacyRedirect`）不受影响。尺寸正确性靠视觉/人工验证（无渲染断言）。 | 已关闭；**TODO（不新开债号）**：若后续 PrimeVue 升级提供 size prop，回退到组件属性并删 `pt`。 | 触发：该两页有模板重构需求时；**禁止为过门禁单独新增 class** |
| **A-52** | **B 类 150 条无令牌硬编码总账**（P5-1 on-primary 6 条、P5-3 小尺寸 13 组、P5-4 `100%` 50 次、P5-5 `vh/fr/fit-content` 10 次）：余 overlay 半透明底、阴影组合、大块布局高度等，受 G-055 棘轮按基线次数保护 **阴影子项（P5-2）**：13 条原生 `box-shadow` 与既有层级均不相等，已加 TODO | 未修（存量受棘轮保护，明细见 `docs/design-token-audit.md` §4 / §11，本表不重复）；当前口径：A=0 / B=150 / C=559 / D=0（A-51 消除 3 条：B 2 内联 + C 1 条 `width:20px`） | 按类补语义令牌（先过四主题对比度）再批量替换，每类单独提交并同步收敛基线 | 触发：新增同类样式且确需令牌时；无触发则维持基线 |
| **A-53** | **`disabledBg` / `disabledText` 是死键**：`ThemeConfig` 有声明（light/dark/green/blue 各一套），但 `applyThemeToDom` 未映射、`style.css` 也无 `--disabled-bg/--disabled-text` 声明，全仓无消费者 | 已登记（P2 全量映射测试发现） | 二选一：接线成 `--disabled-bg/--disabled-text` 并在 `.p-button:disabled` 等消费；或删键（需同步 ThemeConfig 与四主题） | 触发：做禁用态无障碍/一致性专项时；**P2 约束禁止为过测试改值，故本轮只登记**；**DS 骨架暂用替代令牌**（Web `--border-light`+`--text-dim`、Win `borderLight`+`textDim`），接线后可直接替换，不新开债号；**DS 阶段三模块一完成（2026-11-22）**：`applyThemeToDom` 已接线 `--disabled-bg` / `--disabled-text`，`style.css` `:root` 补默认层；Web 侧 `AppButton`/`AppInput`/`AppSelect`/`AppSelectButton`/`AppCheckbox`/`AppToggle`/`AppDatePicker`/`AppConfirmDialog` 与 Win 侧 `BaseButton`/`BaseInput`/`BaseSelect` 的禁用态全部消费该令牌，替代令牌口径已移除。**对比度按棘轮处理**：light 2.08 / dark 2.96 / blue 1.93 达不到 3:1（P2 约束禁止为过测试改值），登记 `DISABLED_CONTRAST_EXEMPT` 并记实测值 —— 改低即红、新增未登记即红、修好删行自动收紧（见 `design-tokens.test.ts`）。**→ 已闭环，移入 01-archive-closed** |
| **A-54** | **Win 端主窗口/侧边栏/内容区布局未与 Web 的 PageContainer/AppCard 对齐**：Web 侧 DS 阶段三已把页面容器与卡片归一到 `PageContainer` / `AppCard`（8 个 views 容器 + 20 处卡片），但 Win 端 `QMainWindow` + 自定义 mixin 的布局结构与 Web 的 DOM 层级**不同构** —— Web 是 `AppLayout(.content-inner) → PageContainer → AppCard` 三层，Win 是 `QMainWindow → QSplitter/侧栏 → 各页 QWidget` 的 Qt 父子关系，没有等价的「页面级容器」概念 | **暂不处理（2026-11-23 用户裁定）** | 若将来要做，先出方案再动手，候选路径：① 在 Win 端引入 `BasePage(QWidget)` 承担 Web `PageContainer` 的职责（统一 padding / 标题排版 / max-width 等价物），`QMainWindow` 不动；② 只对齐「留白与标题字号」这类可量化项，不追求结构同构 | 触发：有具体业务需求（如新增 Win 端页面、或用户反馈 Win/Web 观感差异明显）时再评估；**本轮明确不做** |

> **A-27 子项（2026-11-08，实现完成后的部署/后续待办）**
> - **A-27.1 真实渠道 API 验证（部署时）**：企微需 `corpid`/`corpsecret`/`agentid`；飞书需 `app_id`/`secret` + 测试群 `chat_id`；Telegram 需 bot token。代码已实现，单测覆盖 fake transport，**真实 API 未调用**。**阻塞部署验证**。
> - **A-27.2 菜单配置前端 UI**：当前通过 config + admin API 管理，前端设置页未做。**不阻塞发布**。
> - **A-27.3 API 端到端鉴权测试**：**已补（2026-11-14）**——`tests/test_notification_menu_api.py` 9 例：无会话 401（中间件）、普通用户 403（`require_role`）、admin 200、同步失败 400、缺参 422、非 admin 不触发 `sync_channel`。**不阻塞发布**。
> - **A-27.4 Telegram 形态说明**：命令列表（`setMyCommands`）已实现，但这是 Telegram 官方唯一菜单形态，**非持久菜单**；文档已标注。**已接受**。

> **2026-11-08（W1-U1）遗留候选**：`pilotstd/ui/main_window/parts/_query_ops.py::_on_query_result_ready` 在 `MainWindow.query_result_ready` 信号删除后**仅剩测试直接调用**（`tests/gui/test_coverage_queries.py:44`、`tests/gui/test_main_window_core.py:328`），生产链路已由 `QueryUIHandler.on_query_result_ready`（`pilotstd/ui/core/handlers/_query.py:183/:199`）承担。**下次清理 UI 遗留代码时**：删方法并同步迁移/删除这两处测试。

**真实验证执行**：凭证到位后每渠道发 1 条（谁提供凭证谁发），确认收到即把本行状态改为"已验证"；失败则区分代码/环境问题再修 | 无；**真实验证为独立验收项，不阻塞实现** |

### A-18 历史 hash 映射表（2026-10-28）

**对账**：上一轮"9 无法解析（6 hash 类 + 3 日期串）+ 27 not-in-main = 36"
→ 剔除 3 个日期串（`20260820`/`20260725`/`20260724`，非 commit）与 `9982141d`
（只出现在本条清单与 ignored 的 `docs/.local`，不是文档引用）
→ **本轮 5 个 hash 类缺失 + 27 个 not-in-main = 32**；其中 git 跟踪文件 **6 个、19 处**
（**9 可定位** + **10 不可考**）。

| 旧 hash | 现行 hash | subject（稳定，可用于再次定位） |
|---|---|---|
| `1b2c2a1f` | `feef8f6a` | feat(health): 为两类适配器增加独立的每小时健康检查轮询 |
| `518e5b06` | `12dd027a` | fix(api): 修复查询适配器卡片状态永远显示正常的问题 |
| `df182a3d` | `355f62f5` | fix(db): 将 adapter_state 的 INSERT OR REPLACE 改为安全写法 |
| `317f6975` | `38810e99` | fix: 处理主线修复三项次生问题 |
| `d32ccd0b` | `0de89747` | docs: 新增实现摘要、路线图与文档整理审计报告 |
| `b38c5da7` | `8b56d770` | chore(repo): 归档 78 篇过程稿并清理仓库根目录 |
| `f409ab1e` | `0b13563f` | feat(notify): 新增一键处理管道级终局汇总事件 |
| `acf2a7fd` | `3c71e92a` | ﻿fix(tests): eliminate env pollution from guard-state |
| `cfe1bbc4` | `c564a69c` | refactor(status): B1/5 状态字面量收敛 |

**不可考（10）**：`4bc58444`、`6e473096`、`3d16d662`、`1528176b`、`c574ccda`、`70b631b4`、
`d6a56b11`、`f04f1b92`、`f4f812e7`、`f247cf2e`（`git cat-file` 缺失或对象存在但不在 main，且无同 subject 提交）。

**文档处理**：9 处直接换现行 hash，并在 3 个文件末尾注明"映射见 A-18"；
10 处在原处标"（历史提交已不可考，见 A-18）"，`download-pipeline.md` 用一条统一说明代替逐处标注。
**未处理**：`docs/.local/` 内 **13 处**失效引用暂不修（32 − 19 跟踪 = 13；ignored、不随仓库发布）；若未来纳入仓库，需一并处理。

**subject 核对**：9 个映射逐个比对 `git show -s --format=%s` 旧/新，**9/9 一致**（可达且同一提交）。

**宽模式复核（2026-10-28）**：用 `[0-9a-f]{7,40}`（不要求反引号、含范围写法）重扫跟踪文件，又发现 4 类未标注项并修正：① `ROADMAP.md` 的 `409ab1e`（`f409ab1e` 漏首字母）→ 改 `0b13563f`，并修复同行的 `\x07uto_pipeline_summary` 控制字符；② `archive_migration_protocol.md` 的 `cdb6705`/`be50271`（对象存在但不在 main）→ 标不可考；③ `debt/01` 的 32 位大写字串是**文件内容 MD5**，非提交 hash → 已注明；④ `07-impl-design-A.md` 的 `a1b2c3d4e5f60718` 是 JSON 示例占位 → 已注明。复核后跟踪文件 unannotated=0。

## 三、待裁定项（我已给建议，只需你一句话）

| # | 项目 | 我的建议 | 理由 |
|---|---|---|---|
| **D-1** | **T-16：`docs_sync_check.py` 由 `--strict`（告警期）切 `--strict-block`（阻断期）** | ✅ **已切换（2026-10-18）** | CI `ci.yml` 已改 `--strict-block`；实测发现 `CHANGELOG.md` 由 CI 自动生成、不可能同批提交，故该规则改为 `in_repo=False`（只提示）；到期/回滚说明见 `gates.md` v2.10 |
| **D-2** | **N-b / N-e：通知阶段 2 是否先做"前置确认"只读批；附-2 口径澄清由谁完成** | **建议暂不启动** | 阶段 2（`task_progress` 接通知）与阶段 3 补取证均无业务阻塞，且当前无需求方；维持"触发式" |
| **D-3** | **观察项「主题判定改为事件键优先、关键词兜底」** | **建议保持待排期** | 属设计改进而非缺陷；现有 i18n 契约表兜底已被 `tests/test_notification_aggregator_topic_i18n.py` 锁定 |

## 四、本次（2026-10-16）由我直接裁定关闭的项

| 项目 | 裁定 | 依据 |
|---|---|---|
| 原 §六「**风格项：台账历史条目判断词清理**」（『建议』7 处 /『不必』2 处） | **不处理** | 历史条目是"当时原话"的留痕，改写措辞会削弱可追溯性；且实测该计数（含本条 8/3、本条自身 1/1）与文档自述**精确一致**，不构成缺陷 |
| 原 §六「**R14-5 记载的"状态汇总表"**」 | **确认从未存在** ⇒ 已由主档的「四类状态汇总」替代 | `git log -S "状态汇总表"` 仅 `db71496a`（2026-10-01T13:46:30+08:00）1 次，且只出现在记录文本里，从未作为表存在 |
| 原 §六「**平台侧告警行复核方法写"24 warning"**」 | **更正为 0 warning / 9 notice** | 逐作业拉 check-run annotations：`ef469672`（2026-10-07T14:10:34Z 触发）与 `bc490c28`（2026-10-16T13:40:07Z）均 `warning=0 / notice=9 / failure=0`；24 条是升级前的旧数 |
| 原 §六「**`.doc`（OLE2）行现状写"静默解析为空"**」 | **更正为"已显式告警"** | `pilotstd/announcement/_attachment_parser.py:104-106` 现为 `logger.warning("附件正文解析失败（若为 .doc/OLE2 则正文为空）…")`，改动于 `a0204e3f` **2026-10-01T16:54:08+08:00** |
| 原 §六「**T-38 行写"G-032 现报 8 处"及行号 539/540/577**」 | **更正为 10 处，且原行号已失效** | 实测 `python scripts/check_g_032_doc_health.py` 报 **10 处**；原所指引用已不存在（详见 [04-watch.md](04-watch.md) T-38 行） |
| 原 §六「**`tests/` 受控测试行②"流程补强（未实施）"**」 | **更正为"已由 R16 P0 落地"** | `scripts/check_all.sh:427` 定义 `run_gate_selftests`，`:465`/`:472` 调用 |
| 「**隐式依赖 `cryptography` 未显式声明**」（我于 2026-10-17 曾登记为 A-7） | **撤回该条目**（不成立，不是债） | 我上一轮**漏查**：只 grep 了 `pyproject.toml` 与 `docker/requirements-docker.txt`，而那条"逐文件检查"命令因 PowerShell 语法错误**静默失败**，我据此误判"四个依赖文件均无声明"。实测 `requirements.txt:6` = `cryptography>=48.0.1`（段注释"敏感数据加密"）⇒ **本就是显式依赖**。教训：命令失败时不得依据其输出下结论（R-004 实证优先） |
| **A-47** | **无结果转 pending 时未记 chain_exhausted**：62 批缩小版 28 条 pending 的 match_status 为空、chain_exhausted=0，no_result 188+ 与最终 pending 原因脱节（P3-16 指标分流不完整） | **已修（待部署 v0.192.x）** | 修法：`_finalize_batch` 对无结果条目返回 `status=pending`、`match_status=chain_exhausted` 并 +chain_exhausted 指标；单测锁定 | 触发：pending 中 `match_status=''` 且 `chain_exhausted=0` 的行累计 >10 条时；或下次动 P3-16 查询分类代码时 |
| **A-55** | **CI 整体覆盖率门槛临时降到 58%**（原为无主 TODO，2026-11-23 认领）：`ci.yml` 的 `--fail-under=58`，注释原写 `TODO(P2): restore to 68 after UI handler tests are added` 但没有债号、没有触发条件，永远不会被跟踪 | **已认领** | 恢复条件：UI handler 测试补齐后回到 68。判据：`python -m pytest tests --cov=pilotstd --cov-report=term-missing` 看 TOTAL 行是否 ≥68%；未达标前保持 58，但**不得再降** | 触发：每次新增 UI handler 测试后复核；或有人质疑覆盖率门槛为何是 58 时 |
