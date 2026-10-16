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
| **T-40** | V6 wechat 真发未取证 | `观察中` | 本地 `data/config.json` 的 `notification.channels.wechat` = `{"enabled": true, "webhook_url": ""}`（2026-10-16T22:07 实测）⇒ 非部署环境无法真发；渠道契约/错误映射/签名/i18n 单测已覆盖 | **部署环境补一次真发取证**（会真的发一条消息到企微，需你点头） | 部署后（容器内有凭据解密上下文） |
| **T-42** | 钉钉调用频率限制缺实现 | `待排期` | `pilotstd/core/notification/channels/dingtalk.py` 对 `429`/`backoff`/`退避`/`rate limit` **0 命中**（2026-10-16 实测） | 按 `errcode` 与实测回执定义退避（含上限与抖动）+ 补"429/限流不重复放大"回归 | 实际接入出现 429/限流回执 |
| **T-43** | 企微回调（XML+SHA1+AES）未实现 | `待排期` | `pilotstd/core/notification/callback.py:123` 明写"`wechat` 依能力调查缺口 1/2 **未取证**"；`:172` 一律拒绝（501）；`verify_callback` 仅 telegram/dingtalk/feishu 三支 | 按取证结论实现回调入站（XML 信封 + `MsgSignature` + AES 解密） | 业务侧提出"企微按钮交互"需求 |

## 二、可动作项（有明确动作，按"值不值得现在做"排序）

| # | 项目 | 状态 | 现在能做什么 | 触发条件 / 备注 |
|---|---|---|---|---|
| **A-1** | **P7-12：`docker/api/tasks.py:138` 越过 DAO 直调私有 `mgr.task_queue._persist(task)`** | 未修 | 改为公共接口（新增 `TaskQueue.persist()` 或在 DAO 层暴露方法），保持行为不变 | **无前置条件，可随时做**（`docs/plans/notification-redesign/10-阶段2投影入口调查.md:72` 明写"不得因 P4b 收尾而勾销"） |
| **A-2** | **G-049 防膨胀门禁只覆盖 `manager.py`**（`scripts/check_g_049_manager_size.py:18` 的 `TARGET`） | 未修 | 评估把 `TARGET` 扩到 `pilotstd/core/notification/` 其他大文件（先跑一遍看会红多少） | 触发条件＝通知模块再出现单文件膨胀 |
| **A-3** | **`channel_spec.schema ↔ get_config_schema()` 互证门禁缺失**（现只有字段级断言 `tests/test_channel_spec.py:72-119`） | 未修（可选） | 加一条"声明 ↔ 实现"一致性门禁 | 触发条件＝渠道字段再次漂移 |
| **A-4** | **Phase1 检查项 3：重试耗尽埋点三字段不达标** | 未修 | `enforcement/guardrails.py:433-453` 的 `_log_retry_exhaustion`：`retry_reason` 硬编码 `"validation"`（`:440`）、`caller_stack` 只输出 md5 前 8 位（`:445`）、**缺 `attempt_details` 字段** ⇒ 按验收标准补齐三字段 | **注：`enforcement/`、`src/` 不在本仓根目录的可达路径内时无法施工**（施工前先确认路径归属） |
| **A-5** | **cookiecutter 真实 CLI 端到端未入 CI** | 观察 | 模板改动涉及 hooks 时补一条真实 CLI 用例（渲染/编译/零字面量已由 jinja2 用例覆盖） | 触发条件＝hooks 变更或脚手架被频繁使用 |
| **A-6** | **`known-issues.md` 第 4 项：Telegram 429 的 55.6% 未复测** | 观察 | 部署后取 `GET /api/notification/logs` 的 success/failed 分布 + 容器日志 429 计数，给出改善证据 | 触发条件＝下次通知量统计复核 |

## 三、待裁定项（我已给建议，只需你一句话）

| # | 项目 | 我的建议 | 理由 |
|---|---|---|---|
| **D-1** | **T-16：`docs_sync_check.py` 由 `--strict`（告警期）切 `--strict-block`（阻断期）** | **建议切换** | 该门禁的切换条件是"连续 3~5 次零误报"，而实测 main 上自 2026-09-27 起已有 **176 次 push 运行**（2026-10-01 起 130 次）、期间计数一直未回写 ⇒ 条件事实上早已满足。切换后"改了源码没同批改文档"会直接挡提交（属你日常提交习惯变更，故仍请你点头） |
| **D-2** | **N-b / N-e：通知阶段 2 是否先做"前置确认"只读批；附-2 口径澄清由谁完成** | **建议暂不启动** | 阶段 2（`task_progress` 接通知）与阶段 3 补取证均无业务阻塞，且当前无需求方；维持"触发式" |
| **D-3** | **观察项「主题判定改为事件键优先、关键词兜底」** | **建议保持待排期** | 属设计改进而非缺陷；现有 i18n 契约表兜底已被 `tests/test_notification_aggregator_topic_i18n.py` 锁定 |
| **D-4** | **Phase1 检查项 2（pre-commit 增量校验 + 3s 超时熔断）与检查项 5（受保护路径 `git diff --exit-code` Job）** | **建议关闭为"已接受"** | 检查项 5 的实质目标（防生成物漂移）已由 `check_capabilities_sync.py` 覆盖；检查项 2 属早期阶段的性能优化，当前 pre-commit 全量跑在本机约 3~5 分钟、可接受 |
| **D-5** | **Phase1 检查项 7（把 Phase 1 拆成 ≥3 P0 + 2 P1 Story）** | **建议关闭为"已过时"** | Phase 1 的交付物已全部落地（检查项 1/4/6 均已实现），再补 Story 文档无收益 |

## 四、本次（2026-10-16）由我直接裁定关闭的项

| 项目 | 裁定 | 依据 |
|---|---|---|
| 原 §六「**风格项：台账历史条目判断词清理**」（『建议』7 处 /『不必』2 处） | **不处理** | 历史条目是"当时原话"的留痕，改写措辞会削弱可追溯性；且实测该计数（含本条 8/3、本条自身 1/1）与文档自述**精确一致**，不构成缺陷 |
| 原 §六「**R14-5 记载的"状态汇总表"**」 | **确认从未存在** ⇒ 已由主档的「四类状态汇总」替代 | `git log -S "状态汇总表"` 仅 `db71496a`（2026-10-01T13:46:30+08:00）1 次，且只出现在记录文本里，从未作为表存在 |
| 原 §六「**平台侧告警行复核方法写"24 warning"**」 | **更正为 0 warning / 9 notice** | 逐作业拉 check-run annotations：`ef469672`（2026-10-07T14:10:34Z 触发）与 `bc490c28`（2026-10-16T13:40:07Z）均 `warning=0 / notice=9 / failure=0`；24 条是升级前的旧数 |
| 原 §六「**`.doc`（OLE2）行现状写"静默解析为空"**」 | **更正为"已显式告警"** | `pilotstd/announcement/_attachment_parser.py:104-106` 现为 `logger.warning("附件正文解析失败（若为 .doc/OLE2 则正文为空）…")`，改动于 `a0204e3f` **2026-10-01T16:54:08+08:00** |
| 原 §六「**T-38 行写"G-032 现报 8 处"及行号 539/540/577**」 | **更正为 10 处，且原行号已失效** | 实测 `python scripts/check_g_032_doc_health.py` 报 **10 处**；原所指引用已不存在（详见 [04-watch.md](04-watch.md) T-38 行） |
| 原 §六「**`tests/` 受控测试行②"流程补强（未实施）"**」 | **更正为"已由 R16 P0 落地"** | `scripts/check_all.sh:427` 定义 `run_gate_selftests`，`:465`/`:472` 调用 |
