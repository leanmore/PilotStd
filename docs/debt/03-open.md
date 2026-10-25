# 技术债 · 可修复、尚未修复

> 本文件是 `docs/technical-debt.md` 四分类之一：**未修**（正式债 + 可动作项 + 待裁定项）。
> 判据：**有明确动作可做**、且尚未做完。做完即移入 [01-archive-closed.md](01-archive-closed.md)；
> 定性为"不做/不划算"则移入 [02-accepted.md](02-accepted.md)；修完但需盯一段时间则进 [04-watch.md](04-watch.md)。
> **最后核实：2026-10-16**（每条都注明核实方式与时间戳）。
> 回主档：[technical-debt.md](../technical-debt.md)

---

## 一、正式存续债（3 条）

| # | 项目 | 状态 | 现状（实测） | 下一步动作 | 触发条件 |
|---|---|---|---|---|---|
| **T-40** | V6 wechat 真发未取证 | `观察中`（用户 2026-10-17 裁定：**后续再说**） | 本地 `data/config.json` 的 `notification.channels.wechat` = `{"enabled": true, "webhook_url": ""}`（2026-10-16T22:07 实测）⇒ 非部署环境无法真发；渠道契约/错误映射/签名/i18n 单测已覆盖 | 部署环境补一次真发取证（会真的发一条消息到企微） | 用户择期（本轮不做） |
| **T-42** | 渠道调用频率限制未逐家实现 | `基座已具备`（2026-10-17） | 实测（2026-10-16）：限流/退避**只长在 telegram**（27 处命中），`dingtalk` 1、`feishu` 1、`wechat` 4、`base.py` **0** ⇒ 一次 429/抖动只有 telegram 退避重试，其余三家当场丢通知。**2026-10-17 已修**：重试/退避提升为渠道基座 `base._with_retry`（统一 3 次、退避 (2,4)、服务端 `retry after` 优先且截顶 60s、429/5xx 与限流关键词兜底、错误 120s 去重），**四家渠道全部接入**（提交 `191b7259`，2026-10-17T06:19:36+08:00；测试 195 passed） | **残留**：各渠道限流的**具体错误码未逐家取证**（钉钉官方文档 JS 渲染取不到正文；飞书/企微未逐码核对）⇒ 现用 `looks_rate_limited` 关键词兜底，取证到 `errcode`/`code` 后改为**按码判定** | 取到任一家官方限流码时 |
| **T-43** | 企微回调（XML+MsgSignature+AES）未实现 | `已实现·待取证`（2026-10-17 更新） | 原 `pilotstd/core/notification/callback.py` 对 wechat 一律 501（注释自述"能力调查缺口未取证"）。**已由 `bc3b4822` 落地**：`wechat_crypto.py`（SHA1 验签 + AES-256-CBC 解密，常量时间比较）、`callback.py`/`callback_service.py` 企微分支并入既有幂等/授权出口、`docker/api/notification_callback.py` 的 GET 回明文 `echostr`、POST 回明文 `success`（原 501）；测试三组 **56 例**（crypto 28 / 服务 16 / 端点 12） | **残留取证**：部署后取一次真实回调报文，确认 `EventKey`/`TaskId`/`FromUserName` 字段假设；`WechatChannel.capabilities().supports_callback` 仍为 `False`（语义是"我方下发消息带可回调按钮"，需前端联动，单独立批） | 部署环境收到首条企微回调时 |

## 二、可动作项（有明确动作，按"值不值得现在做"排序）

| # | 项目 | 状态 | 现在能做什么 | 触发条件 / 备注 |
|---|---|---|---|---|
| **A-1** | **P7-12：`docker/api/tasks.py:138` 越过 DAO 直调私有 `mgr.task_queue._persist(task)`** | ✅ **已修（2026-10-18）** | `TaskQueue.persist()` 公共入口已加，`docker/api/tasks.py` 改调用它；测试断言 `persist` 被调且 `_persist` 不再被 API 触碰 | **无前置条件，可随时做**（`docs/plans/notification-redesign/10-阶段2投影入口调查.md:72` 明写"不得因 P4b 收尾而勾销"） |
| **A-2** | **G-049 防膨胀门禁只覆盖 `manager.py`**（`scripts/check_g_049_manager_size.py:18` 的 `TARGET`） | ✅ **已修（2026-10-18）** | `TARGETS` 扩展为 manager.py + 6 个通知热点文件，上限=当前有效行+约 5% 余量；`*_data.py` 静态规格表不纳入（避免每加渠道就红）。测试 `tests/test_check_g_049_notification_sizes.py`（3 例） | 触发条件＝通知模块再出现单文件膨胀 |
| **A-3** | **`channel_spec.schema ↔ get_config_schema()` 互证门禁缺失**（现只有字段级断言 `tests/test_channel_spec.py:72-119`） | 未修（可选） | 加一条"声明 ↔ 实现"一致性门禁 | 触发条件＝渠道字段再次漂移 |
| **A-5** | **cookiecutter 真实 CLI 端到端未入 CI** | 观察 | 模板改动涉及 hooks 时补一条真实 CLI 用例（渲染/编译/零字面量已由 jinja2 用例覆盖） | 触发条件＝hooks 变更或脚手架被频繁使用 |
| **A-6** | **`known-issues.md` 第 4 项：Telegram 429 的 55.6% 未复测** | 观察 | 部署后取 `GET /api/notification/logs` 的 success/failed 分布 + 容器日志 429 计数，给出改善证据 | 触发条件＝下次通知量统计复核 |
| **A-9** | **解析失败日志格式未统一**（`pilotstd/scan/parser/__init__.py:200` 的 `TODO(P2)`） | 未修 | 统一为"路径/类型/错误/详情"四段，牵动日志断言测试，需单独一批 | 触发条件＝下次动解析器日志或排障困难 |
| **A-10** | **设置页 Tab 定位依赖 DOM 顺序**（`web/src/views/settings/constants.ts:4` 的 `TODO(P2-FOLLOWUP)`） | 未修 | 改为 `data-tab` 名称定位，消除对子元素顺序的依赖 | 触发条件＝设置页 Tab 结构再调整 |
| **A-11** | **两条自定义 eslint 规则"已定义但未执行"**（`web/eslint.config.js` 把 `custom/no-raw-i18n-key`、`custom/no-sensitive-persist` 设为 error，但 package.json 无 lint 脚本、CI 无 eslint 步骤） | 未修 | 加 `lint` 脚本 + CI 一步；**先决**：56 条存量 `no-raw-i18n-key` 违规需先裁定（逐条修 or 基线），否则接入即红。2026-10-24 实测：`eslint src` = 56 errors（全部该类）+ 284 warnings；`no-sensitive-persist` **0 命中** | 触发条件＝下次改前端规范或要把 eslint 接入 CI 时 |
| **A-12** | **6 个适配器的 `_search` 无直接测试**（`ccsn`/`sppt`/`sppt_local`/`jtst`/`mee`/`nrsis`；`tests/` 中 grep 零命中） | 未修 | 第二轮 A1 抽取 helper 后：`_search` 由参数化测试覆盖（6 类 × 委托断言）；**仍未覆盖**各适配器 `query_standards` 的网络/解析路径——需按站补录制回放或 mock 响应 | 触发条件＝改任一适配器搜索逻辑或补适配器测试时 |
| **A-13** | **两套 HTTP 栈**：4 个通知渠道用 `urllib.request`（`dingtalk.py:19`、`feishu.py:11`、telegram、wechat），其余 21 个文件用 `requests` | 未修 | 引入提交 `c53d7500`（通知模块 v17+三渠道）与 `0da0dea7`（钉钉渠道），**提交信息均无 HTTP 栈选择理由**（2026-10-25 核查）。统一前置：逐条回归四渠道的 `timeout`/异常类型（`URLError` vs `RequestException`）与重试语义，再决定统一到 `requests` 还是保留并补注释 | 触发条件＝下一次动通知渠道网络层时 |

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
