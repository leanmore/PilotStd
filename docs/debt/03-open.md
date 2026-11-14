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
| **T-42** | 渠道调用频率限制未逐家实现 | `基座已具备`（2026-10-17） | 实测（2026-10-16）：限流/退避**只长在 telegram**（27 处命中），`dingtalk` 1、`feishu` 1、`wechat` 4、`base.py` **0** ⇒ 一次 429/抖动只有 telegram 退避重试，其余三家当场丢通知。**2026-10-17 已修**：重试/退避提升为渠道基座 `base._with_retry`（统一 3 次、退避 (2,4)、服务端 `retry after` 优先且截顶 60s、429/5xx 与限流关键词兜底、错误 120s 去重），**四家渠道全部接入**（提交 `191b7259`，2026-10-17T06:19:36+08:00；测试 195 passed） | **残留**：各渠道限流的**具体错误码未逐家取证**（钉钉官方文档 JS 渲染取不到正文；飞书/企微未逐码核对）⇒ 现用 `looks_rate_limited` 关键词兜底，取证到 `errcode`/`code` 后改为**按码判定** | 取到任一家官方限流码时 |
| **T-43** | **企微回调取证** | **已归并入 A-27**（2026-10-29） | A-24 取消后回调只服务菜单点击；端点/验签/解密/EventKey 解析作为 A-27 P1 的验收能力；需一条真实菜单点击报文校准 `EventKey/FromUserName/AgentID` | 随 A-27 |

## 二、可动作项（有明确动作，按"值不值得现在做"排序）

| # | 项目 | 状态 | 现在能做什么 | 触发条件 / 备注 |
|---|---|---|---|---|
| **A-5** | **cookiecutter 真实 CLI 端到端未入 CI** | 观察 | 模板改动涉及 hooks 时补一条真实 CLI 用例（渲染/编译/零字面量已由 jinja2 用例覆盖） | 触发条件＝hooks 变更或脚手架被频繁使用 |
| **A-22** | **Q7：Windows 端 15 个共享事件是否走托盘（S4 真实验收）** | 挂起 | 需 Windows 端实跑：触发一个共享事件，确认进托盘且 Web 端仍收到；本机/CI 无法覆盖 | 触发条件＝用户有空在 Windows 本机跑一次（5 分钟） |
| **A-27** | **自定义菜单（企微/飞书/Telegram/钉钉）** | 调研中（2026-10-29 立项，当前主线） | 企微 a（3+5）、飞书 b（3+5 或 5+10，仅单聊）、Telegram c（命令列表）、钉钉 d（待补信息）；菜单动作映射、配置存储、静态/动态生成待方案确认；复用回调端点处理菜单 click | 方案确认后开工 |

| **A-32** | **cookiecutter 把 `myadapter.py` 判为二进制**（binaryornot 特征判定；同目录测试/README 正常） | 已兜底 | `post_gen_project.py` 用 `_CONTEXT`（`cookiecutter|tojson`）+ Jinja2 手动渲染；**属绕开行为**，判定边界：只匹配 `{{` + `cookiecutter` 字面量；**不覆盖** `{% if %}` 控制块（不含字面量会被跳过）、也可能误判合法代码里的 `{{`（如格式化字符串）。扩展其它文件前先检查这两类边界；待修复后删除该步 | 触发条件＝升级 cookiecutter 时 |
| **A-33** | **`_get_*_adapter()` 懒加载全库零调用**（A-31 调查发现） | 未修 | 保留现有代码不动（超 A-31 范围）；模板已停止生成新 getter；可整体清理 | 触发条件＝下次清理遗留代码时 |

| **A-37** | **网络 e2e 未与 PILOTSTD_RUN_NETWORK_TESTS 机制对齐**：	ests/test_e2e_adapters.py 仅按 CI 跳过，办公室/无外网时直接跑真实站点并红（如 ahbz 查不到 GB/T 19001-2016） | 未修 | 触发：无外网环境；修法：复用 PILOTSTD_RUN_NETWORK_TESTS=1 显式开关，不另搞探测逻辑 | 触发条件＝下次改网络测试 |
| **A-40** | **旧数据 `user_id=1` 的归属未校验**：v71 回填把所有存量日志/队列归 user 1；真正多用户时需判断归属（单用户升级可接受） | 未修 | 触发：启用多用户；修法：迁移时按用户映射或标记来源 | 触发条件＝A-21 多用户上线 |
| **A-41** | **failed-items 无 admin 全量视图**：当前只按 user_id 过滤 | 未修 | 需要时加 `all=true`（仅 admin）或 `user_id` 查询参数 | 触发条件＝admin 需要跨用户排障 |
| **A-42** | **API auto/archive 无 auth 依赖，事件归 system**：`/api/auto`、`/api/archive` 未接 `get_current_user_id`，多用户时用户看不到自己触发的通知 | 未修 | 需要前端 token + 端点加 auth 后再传 context=user；单用户不影响 | 触发条件＝多用户 API 场景 |
| **A-43** | **SQLite 实测表数（45）无法机械核对**：`18-schema-migrations.md` 写的"SQLite 实测业务表 45 张"来自**实跑迁移链后的 `sqlite_master` 计数**；`load_facts()` 只解析迁移源码（得到 43）。G-052 全量审计把它列为"已登记但无法机械核对"，未扩第 7 类 | 未修（已单独立项，2026-11-14） | 修法二选一：① 新增"空库跑迁移后数表"的事实源（昂贵，需单独评估代价）；② 把该处数字改为"以实测为准"不写具体值 | 触发条件＝有人质疑 43/45 不一致、或动迁移链/表结构时 |
| **C-6 遗留** | **pending 弹窗 skipped 提示的 i18n**：`pilotstd/ui/core/handlers/_download.py` 的「另有 M 条因发布日期格式异常，未加入等待队列，请手动检查」目前用行内 `# i18n-allow` 豁免（G-047 通过，但仅中文） | 未修 · **P2** | 三语化：在 `pilotstd/i18n/{zh_CN,en,zh_TW}.json` 加键（建议 `download_skipped_bad_date`），代码改 `_("download_skipped_bad_date").format(count=...)` 并删掉 `i18n-allow` | 触发条件＝多语言用户反馈，或下次 i18n 统一迁移；**不影响功能，只影响多语言用户** |

> **A-27 子项（2026-11-08，实现完成后的部署/后续待办）**
> - **A-27.1 真实渠道 API 验证（部署时）**：企微需 `corpid`/`corpsecret`/`agentid`；飞书需 `app_id`/`secret` + 测试群 `chat_id`；Telegram 需 bot token。代码已实现，单测覆盖 fake transport，**真实 API 未调用**。**阻塞部署验证**。
> - **A-27.2 菜单配置前端 UI**：当前通过 config + admin API 管理，前端设置页未做。**不阻塞发布**。
> - **A-27.3 API 端到端鉴权测试**：`sync`/`status` 端点有服务层单测，未做 TestClient 端到端鉴权测试（admin 装饰器依赖运行期用户上下文）。**不阻塞发布**。
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
