# PilotStd 治理问题台账（ISSUE LEDGER）

> **性质**：U36 全量治理对账的**唯一结论页**。每条含：证据、来源、影响验收用例、优先级、修复方案/代价/触发条件。
> **基线**：`main` @ `222c42c6`，`VERSION=0.181.1`，本地 schema v76；实测时间 2026-11-09 20:20–20:45（Asia/Shanghai）。
> **方法**：四步可复现流程——定义验收（`ACCEPTANCE_CASES.md`）→ 穷举来源（`docs/.local/U36-source-census.md`）→ 四维交叉（`docs/.local/U36-cross-check.md`）→ 本台账。
> **重要前提**：`W-001` 原文在仓库/历史/磁盘均不存在；本台账的“六问题”是 `26-fix-dossiers.md` D-01～D-06 的重建投影。**若 W-001 不同，本台账的覆盖结论失效。**

---

## 0. 总量与优先级判据

| 优先级 | 定义（用户给定，未自创） | 条数 |
|---|---|---:|
| **P0** | 影响验收用例通过 = 系统不能用 | **2** |
| **P1** | 影响验收用例的部分场景 = 能用但不完整 | **9** |
| **P2** | 不影响验收，但是质量债 | **13** |
| **P3** | 接受不修（写“为什么不修 + 什么条件下重新考虑”） | **15** |
| **合计** | | **39** |

**P0 自检**：P0=2，对应“最难通过的两条验收用例”——AC-1（批量一键闭环）与 AC-4（查询/缓存正确性）。不是 20 条，因为六问题中的 W2/W3/W4 已有代码/测试闭环，只剩局部场景；不是 1 条，因为“批量少下”和“旧结论当新结论”是两条独立的验收失败链。若把 10 条上限认定为已裁决设计，P0 降为 1；若公告回退过期也被接受，P0=0——那说明本审计过窄，需重跑第 1 步。

---

## 一、P0（阻断验收）

### P0-01 Web 一键下载硬上限 10 条，批量静默少下

| 项 | 内容 |
|---|---|
| **现象** | `web/src/views/TaskView.vue:277`：`dlNums = query.results.filter(!is_adopted && match_status==='exact').map(...).slice(0, 10)`。20 个 exact 项只下前 10 条；第 11 条起**不下载**（若该标准只有下载件、没有扫描件，也就没有归档件可进）；UI 也不显示“其余 N 条未处理”。 |
| **证据** | 代码行如上；`TaskView.test.ts:108/:136` 的用例只循环 **10** 次，未覆盖 11+；`08-known-boundaries.md:46`、`26-fix-dossiers.md:18`、`19-web-win-inventory.md:50`、`24-ui-action-matrix.md:40` 都把它记成“事实”，但**没有裁决记录**说明为什么是 10。 |
| **来源** | 08 #1、26 D-01、27 §1、AC-1、入口维度 A1 |
| **影响验收** | **AC-1 直接 FAIL**：通过判据要求 `downloadResult.stats.total == 所有 exact 非采标项数`，当前恒 ≤10。 |
| **修复方案** | 1）`TaskView.vue:277` 去掉 `.slice(0,10)`，把全部 `dlNums` 交给 `postDownload`；2）若确需限流，改为新增一个 `web_max_items` 配置项（0=不限，默认 0，**当前未实现**），并在 UI 显示“本次仅处理前 N 条，剩余 M 条未处理”；3）`TaskView.test.ts` 增加 20 条 exact 的用例，断言 `postDownload` 收到 20 个号、`buildArchiveItems` 收到 20 条下载结果；4）`docker/api/download.py` 的分批逻辑已有 `download.batch_size=10`，不需要在**选择阶段**再截断。 |
| **验证** | `pnpm.cmd test -- --run src/views/TaskView.test.ts`（应 20/20 通过）；`pnpm.cmd run type-check`；`pnpm.cmd run build`；后端 `pytest tests/test_api_tasks_endpoints.py`。 |
| **修后通过** | **AC-1**（批量一键闭环）。 |
| **状态** | **已修（2026-11-09，commit `72856e99`）**：`TaskView.vue` 移除截断；新增 20 条用例；AC-1 mock 全链通过。 |
| **若“10 条”是产品有意限制** | 则本项降为 P1，但必须补：配置项、UI 明示、`08` 写明“为什么 10”、验收 AC-1 改为“处理前 10 条 + 明示剩余”。当前没有任何一条满足，故按 P0 处理。 |

---

### P0-02 `announcement_match` 回退不校验 `expires_at`/`data_state`，旧状态可永久当新结论

| 项 | 内容 |
|---|---|
| **现象** | `pilotstd/query/cache.py:60-73` 的公告回退只 `SELECT standard_number, result_json FROM announcement_match`，**不读** `expires_at`、`data_state`、`cached_at`。`announcement/matcher.py:459` 虽然插入了 `expires_at` 列，但元组末位实际是 `None`（`cache_rows.append((..., now, None))`），等于没有 TTL。结果：只要这条行还在，已过期的公告匹配就会被 `CacheRepository.get()` 一直返回，查询/时效性把它当“当前状态”。 |
| **证据** | `cache.py:60-73`（无 expires_at）；`matcher.py:459`（写 `expires_at` 但值为 `None`）；`11-open-questions.md` Q7（517 条缓存 417 条 >30 天、live 全 stale）；`26-fix-dossiers.md` D-06（只修了主表 stale，没修公告回退）；表普查 B5。 |
| **来源** | 11 Q7、26 D-06、cache.py/matcher.py、AC-4、表维度 B5 |
| **影响验收** | **AC-4 局部 FAIL**：通过判据要求“announcement_match 过期行不得作为命中”；当前会命中。后果不只是显示旧状态，还会让 L1/L2 时效性判断基于旧公告，可能把现行标准判成废止或反之。 |
| **修复方案** | 1）`cache.py:61` 的 SELECT 增加 `expires_at, data_state, cached_at`；2）返回前判断：`data_state == 'stale'` → 跳过；`expires_at` 非空且 `< now` → 跳过（返回 None，让调用方回源）；3）若 `expires_at` 为空，按 `cached_at + DEFAULT_ACTIVE_TTL_DAYS` 兜底（与 `DEFAULT_ACTIVE_TTL_DAYS=30` 一致）；4）补 `tests/test_query.py` 三例：expired/stale/fresh；5）在 `08`/`26` 写明“公告回退也受 TTL 约束”。 |
| **验证** | `pytest tests/test_query.py -q`；`pytest tests/test_validity_l1_l2.py tests/test_validity_checker.py -q`；手工用一条过期 `announcement_match` 行查一次，确认回源而非返回旧值。 |
| **修后通过** | **AC-4**（查询正确性与缓存新鲜度）。 |
| **状态** | **已修（2026-11-09，commit `72856e99`）**：`cache.py` 增加 `_announcement_cache_fresh`（stale 拒绝、`expires_at` 优先、`cached_at+active_ttl` 兜底）；5 条缓存用例 + 1 条 QueryEngine 全链通过。 |
| **风险** | 过期行被跳过后，首次查询会回源，短期网络压力上升（与主表 stale 修复同类）；需在验证环境观察 QPS/失败率。 |

---

## 二、P1（部分场景不完整）

### P1-01 手动 `/api/validity/run` 不更新 `checked_count/round_completed`

| 项 | 内容 |
|---|---|
| **现象** | `docker/api/validity.py:265` 手动触发固定 `update_counters=False`；`/api/validity/config` 读 `validity.checked_count`（`:133`），所以手动跑完 N 条后页面仍显示 0、`round_completed=false`，而 `/api/validity/history` 有 15 天记录。 |
| **证据** | 代码行如上；`11-open-questions.md` Q4（checked_count=0 vs history 15 天）；`17-validity-state-machine.md:101` 明确写“手动不增加”。 |
| **来源** | 11 Q4、17 §六-2、AC-5 |
| **影响验收** | **AC-5 部分 FAIL**：判据要求“手动运行后页面计数与历史一致，或明示本轮不计入”。当前两者都没有。 |
| **修复方案** | 采用方案 A：手动 run 也传 `update_counters=True`，与定时任务同口径；`round_completed` 仍只在 `checked_count >= standard_validity` 合法总数时置真，不因单次手动 run 直接完成。改 `docker/api/validity.py`；补 API 测试断言“手动 run 必须传 true”。**已实现**。 |
| **验证** | `pytest tests/test_api_validity_manual_counters.py tests/test_batch3_validity_wiring.py tests/test_validity_checker_full.py tests/test_validity_config_api.py -q` → **95 passed**。 |
| **修后通过** | **AC-5 子场景（手动检查计数）**；AC-5 整体还受 P1-02/P1-07/P2-11 影响。 |
| **状态** | **已修（2026-11-10）**：`docker/api/validity.py` 手动 run 改 `update_counters=True`；新增 2 例 API 测试。 |

---

### P1-02 `validity_batch_report` 每 10 条中间消息硬编码 `count=0, changed=10`

| 项 | 内容 |
|---|---|
| **现象** | `pilotstd/core/_validity_pipeline.py:197-199`：每累计 10 条变化就发 `validity_batch_report`，payload 固定 `count: 0, changed: 10`，与最终报告（`:341-342` 的 `len(candidates)/len(changed_list)`）不一致。用户会收到“检查 0 条、变化 10 条”的消息。 |
| **证据** | 代码行如上；`17-validity-state-machine.md:94` 已把它记为细节；`tests/test_validity_checker_full.py:775` 只断言“发了”，没断言数字。 |
| **来源** | 17 §五注、AC-3/AC-5、代码复核 |
| **影响验收** | **AC-3/AC-5 部分 FAIL**：通知对账要求消息数字可对账；中间消息会污染对账。 |
| **修复方案** | 采用“真实进度”而非删消息：`_apply_validity_result` 增加 `checked_count/failed_count`，`_process_validity_batch` 传 `i+1` 与累计失败数；中间 payload 为 `count=已处理条数、changed=累计变化、failed=累计失败`；最终报告口径不变。改 `_validity_pipeline.py`；测试断言第 10 条变化时 `10/10/0`。**已实现**。 |
| **验证** | `pytest tests/test_validity_checker_full.py tests/test_notification_e2e.py -q`；相关 validity 套件 **95 passed**。 |
| **修后通过** | **AC-3、AC-5 子场景（中间报告数字）**。 |
| **状态** | **已修（2026-11-10）**：删除 `0/10/0` 硬编码，中间报告使用已处理/累计变化/累计失败。 |

---

### P1-03 `fetch_failures` 只写不读，公告抓取失败无可见出口

| 项 | 内容 |
|---|---|
| **现象** | `pilotstd/announce/persistence.py:67-70` 只 `INSERT INTO fetch_failures`；全仓**没有 SELECT**（表普查 read=0，只有 tests 读）。`GET /api/announce/fetch-log` 读的是 `announcement_record`，不是失败表。公告适配器抓取异常只进日志/`fetch_failures`，用户看不到“哪次抓取失败、失败几次、是否恢复”。 |
| **证据** | 代码行；表普查 B11；`docker/api/announce.py` 的 `fetch-log` 实现；`08 #21` 只承诺“超过 36 小时未成功抓取会告警”，未覆盖单次失败。 |
| **来源** | 表维度 B11、AC-7、公告链路文档 |
| **影响验收** | **AC-7 部分 FAIL**：判据要求“任一阶段故障用户能看到”。抓取失败是主链阶段，当前只有日志。 |
| **修复方案** | 1）新增 `GET /api/announce/fetch-failures`（登录用户只读）返回最近失败与未解决数；2）`AnnounceService.get_fetch_failures()` 聚合；3）适配器本轮成功时 `resolve_site_failures(source_site)` 把该站历史未解决失败标记 resolved；4）`AnnounceView` 显示失败面板（未解决数 + 最近 5 条）。**已按此实现**。 |
| **验证** | `pytest tests/announce/test_persistence.py tests/test_api_announce_fetch_failures.py -q`（12 passed）；`AnnounceView.test.ts` 7 passed；`check_i18n_key_count.py` 三语 947 键一致。 |
| **修后通过** | **AC-7 子场景（公告抓取失败历史可见）**；AC-7 整体仍待 P1-04/P1-05/P2-10；同时增强 AC-2/AC-4 的“抓取失败/未恢复”可见性。 |
| **状态** | **已修（2026-11-09，commit `35283be6`）**：`list_failures/failure_counts/resolve_site_failures` + `get_fetch_failures` + 端点 + 公告页面板；失败历史/是否恢复现在有读侧。 |

---

### P1-04 `batch_state` 只写不读、状态恒 `completed`，无断点续跑

| 项 | 内容 |
|---|---|
| **现象** | `pilotstd/query/engine/_batch_dispatcher.py:370-394` 只在批次**结束时** `INSERT OR REPLACE ... status='completed'`；全仓**没有 SELECT**（表普查 B10，只有 tests）。表注释与 `_migrate_v16_v49.py:382` 写“支持中断后断点续传”，实际没有续跑逻辑。 |
| **证据** | 代码行；表 DDL 注释；`23-peripheral-features.md` 说任务中心真实消费方不完整；`tests/unit/query/engine/test_batch_dispatch.py:121` 只测 `_persist_batch_state` 写入。 |
| **来源** | 表维度 B10、AC-7、23 §三 |
| **影响验收** | **AC-7 部分 FAIL**：重启/中断后没有“从已完成项继续”的路径；表却声称有。 |
| **修复方案** | 采用方案 A：**定性为批次完成审计表**，不实现续跑。代码 docstring 写明“只写不读、不作为续跑读侧”；`query/README` 删除虚假的“恢复流程”，改为“当前没有恢复流程”；`overview`/`migrations` 同步改名。历史迁移注释不改（P-106）。**已实现**。 |
| **验证** | `pytest tests/unit/query/engine/test_batch_dispatch.py -q` → **16 passed**；新增“写入 status=completed 审计行”断言。 |
| **修后通过** | **AC-7 子场景（不再有假续跑承诺）**；AC-7 整体仍 partial（P1-05 已修，P2-10 等）。 |
| **状态** | **设计如此（2026-11-10）**：`batch_state` 是完成审计，不用于续跑；触发重开条件＝产品明确要求“进程重启后续跑批量查询”，届时按方案 B 补读侧/幂等/stale 判定。 |

---

### P1-05 `monitor_stats` 只写不读，服务重启后今日统计归零

| 项 | 内容 |
|---|---|
| **现象** | `pilotstd/monitor/config.py:82-154` 的 `MonitorStats.__init__` 从 0 开始，`_get_db` 只用于 `_flush()` 写 `monitor_stats`；全仓没有 SELECT（表普查 B12 read=0）。重启后 `processed_today/success_today/failed_today` 全部归零，监控面板“看起来今天什么都没发生”。 |
| **证据** | 代码行；表普查 B12；`tests/test_monitor.py` 只测内存单例，不测重启；`08 #2` 只修了归档，没有提统计。 |
| **来源** | 表维度 B12、入口 A5、AC-2 |
| **影响验收** | **AC-2 部分 FAIL**：判据明确要求“重启后今日统计不归零”。 |
| **修复方案** | 新增 `MonitorStats.load_today()`：按 `stat_date=今天` 读 `monitor_stats` 恢复 processed/success/failed；由 `docker/app.py` 启动时调用（不改变 `MonitorStats()` 单测默认零值）；DB 失败 warning 后保持 0。`_flush` 保持 INSERT OR REPLACE。**已实现**。 |
| **验证** | `pytest tests/test_monitor.py tests/test_monitor_scheduler.py tests/integration/test_monitor_archive_e2e.py -q` → **49 passed**；新增恢复 7/5/2、DB 失败保持 0 两例。 |
| **修后通过** | **AC-2**（重启后今日统计不归零）。 |
| **状态** | **已修（2026-11-10）**：`load_today` + 启动接线；DB 失败降级不阻断。 |

---

### P1-06 企微/钉钉/飞书真实发送未复测；wechat 曾 100% 失败

| 项 | 内容 |
|---|---|
| **现象** | 2026-10-19–11-02 生产 wechat `141/141 failed`（`<urlopen error Tunnel connection failed: 400>`）；11-02 清空 `proxy_url` 后 `/test` 成功、`/test-event` 落库 success。但 dingtalk/feishu 一直“未配置”，T-40 仍要求“部署环境补一次真发”；A-27.1 要求企微/飞书真实 API 验证。AC-3 的“每个启用渠道恰好 1 条”目前只有 telegram/wechat 的部分证据。 |
| **证据** | `2026-10-31-home-verification-checklist.md:29`（141/141）、`:58-59`（清 proxy 后成功）；`03-open.md` T-40；`03-open.md` A-27.1；`2026-10-29-stage-completion-summary.md` §二。 |
| **来源** | T-40、A-27.1、home checklist、AC-3 |
| **影响验收** | **AC-3 部分 FAIL**：多渠道路径未全部验证；如果唯一启用的渠道是 wechat，历史失败会直接导致“通知不可达”。 |
| **修复方案** | 不改代码（代码已有 fake transport 单测）；在验证/生产环境每渠道发 1 条（谁提供凭证谁发），把结果写回 `03-open` 对应行；至少覆盖 text + 一张卡片/markdown。若凭证不可得，标 `accepted-unverified` 并写入发布说明。 |
| **验证** | `POST /api/notification/test` + `POST /api/notification/test-event`；查 `notification_log.status/success`；记录时间/渠道/消息 id。 |
| **修后通过** | **AC-3**（四渠道真实可达）。 |

---

### P1-07 `validity.auto_move_expired` 出厂 True，与代码注释/部分文档“默认关闭/未开启”矛盾

| 项 | 内容 |
|---|---|
| **现象** | `pilotstd/core/config/defaults.py:154` 设 `"validity.auto_move_expired": True`；`ConfigManager` 会把默认值灌入配置。但 `pilotstd/core/validity_checker.py:80` docstring 写“默认关闭（false）”，`26-fix-dossiers.md:138` 写“仍未开启”，`08` 没有说明。实际 `data/config.json` 也是 `True`。也就是说：**升级/首装后，L2 判废止就会搬文件**，而维护者按注释以为不会。 |
| **证据** | 三个文件的行；`data/config.json` 的 `validity.auto_move_expired=true`；`26` 总结又说“已启用（2026-11-07）”——同一文档自相矛盾。 |
| **来源** | defaults.py、validity_checker.py、26 D-03、AC-5 |
| **影响验收** | **AC-5 部分 FAIL**：行为与文档不一致，验收无法判断“预期是否搬移”；若用户不想自动搬，会丢文件位置。 |
| **修复方案** | 裁定“默认开”是 2026-11-07 的有意决策：改 `validity_checker.py` docstring、`26` D-03 根因/边界/就绪度三处，补 `FACTORY_DEFAULTS` 默认值测试；不改 `defaults.py` 行为，避免升级后突然变成“不搬”。**已实现**。 |
| **验证** | `pytest tests/test_batch3_validity_wiring.py tests/test_validity_checker.py -q` → **20 passed**；`FACTORY_DEFAULTS["validity.auto_move_expired"] is True` 断言钉住。 |
| **修后通过** | **AC-5 子场景（默认开关与文档一致）**。 |
| **状态** | **已修（2026-11-10，文档/注释对齐）**：默认 true 不变；旧文档“默认 false/仍未开启”已更正；补默认值测试。 |

---

### P1-08 人工端到端验收未执行：`人工测试方案.md` 全部 ⬜

| 项 | 内容 |
|---|---|
| **现象** | `docs/guides/人工测试方案.md:307-359` 的记录表（1.1–8.5、含 6.1 一键、5.1–5.6 归档、3.1–3.7 下载）**没有任何一项打勾/填数**。仓库只有单元/集成/门禁证据，没有一份人工签署的“扫描→查询→下载→归档→通知”端到端结果。 |
| **证据** | 文档记录表全 ⬜；`ACCEPTANCE_CASES.md` §4 已把“人工验收未执行”列为局限；`2026-10-29-stage-completion-summary` 也只到接口级验证。 |
| **来源** | 人工测试方案 §五、AC-1..7、报告维度 D |
| **影响验收** | **全部 7 条 AC 的证据强度降级**：代码/单测通过 ≠ 用户可见流程通过。 |
| **修复方案** | 不改代码；在验证环境按 `人工测试方案` 的核心子集执行并记录：1.1–1.7（扫描）、2.1–2.10（查询）、3.1–3.7（下载）、5.1–5.6（归档）、6.1（一键）、6.5.1–6.5.4（缓存）、8.1–8.5（UI）。每项填结果/数字/截图路径；至少覆盖 20 个文件的一键。把“核心子集通过”作为发布门槛。 |
| **验证** | 文档记录表由 ⬜ 变 ✅/❌ 并附证据；失败项回到本台账新增 ID。 |
| **修后通过** | **AC-1、AC-2、AC-3、AC-5、AC-7** 的用户可见证据补齐；AC-4/AC-6 仍需接口/多用户用例。 |

### P1-09 monitor 归档后不清理 Inbox 根下的空子目录

| 项 | 内容 |
|---|---|
| **现象** | `pilotstd/monitor/scheduler.py:25 _cleanup_empty_dirs` 在 `start_dir == watch_root` 时直接 `return 0`。`_on_file` 对“文件直接放在 Inbox 根”的场景传 `source_root=inbox`，导致 `inbox/empty_child` 不被清理。U38 C21 实测：`_on_file` 归档后 `empty_child` 仍在。 |
| **证据** | `scheduler.py:25-50` 的 `start == root` 提前返回；`tests/test_u38_measurements.py::test_c21_on_file_cleans_empty_child_dir`（修复前 strict xfail，修复后 8 passed）。 |
| **来源** | U38 C21、AC-2/AC-7、W-001 空文件夹项 |
| **影响验收** | **AC-2/AC-7 部分 FAIL**：监控投放后 Inbox 残留空目录，用户看到“已归档但目录还在”。 |
| **修复方案** | 已修：`os.walk` 遍历时跳过 `dirpath == root` 本身，继续清理 root 下空子目录；不删除 watch_root。 |
| **验证** | `pytest tests/test_u38_measurements.py tests/test_monitor_cleanup.py -q` → **8 passed**；全量 **6279 passed**（C21 由 xfail 转正常）。 |
| **修后通过** | **AC-2/AC-7 子场景（Inbox 根空目录清理）**。 |
| **状态** | **已修（2026-11-10）**：`_cleanup_empty_dirs` 跳过 root 本身；C21 测试由 strict xfail 转正常。 |

---

> P2 规则：必须写“如果不修，代价是什么”。

| ID | 问题 | 证据 | 如果不修，代价 | 修复建议 | 来源 |
|---|---|---|---|---|---|
| **P2-01** | 死列/只写字段 7 个：`announcement_record.approved_by`、`api_keys.created_by`、`fetch_checkpoint.since_date_override`、`fetch_failures.last_retry_at`、`query_metrics.recorded_at`、`standard_validity.last_status_updated_at`、`validity_check_log.previous_status` | 表列普查 + grep：前 5 个仅迁移/DDL；后 2 个只写不读 | 维护者以为“有审批人/重试时间/上一状态”可查，实际查不到；schema 噪声增加误判 | 新增 v77 迁移：能删的删（`approved_by/created_by/since_date_override/last_retry_at/recorded_at`），不能删的在 `18` 标“预留/未读”；`last_status_updated_at/previous_status` 要么接 UI/API，要么删除 | 表维度 B22、§2.3 |
| **P2-02** | 死配置 `validity.update_interval`（`defaults.py:157`、`config.json`），API 实际用 `total_weeks*7` | `defaults.py`、`docker/api/validity.py:133-136`、config 普查 | 运维改 `update_interval` 不生效，误以为检查频率变了 | 从 defaults 删除或标 deprecated；读取处统一 `total_weeks`；`settings_schema` 同步 | 配置普查、P2-02 |
| **P2-03** | 零调用函数/方法：`CacheManager.mark_stale/mark_valid`、`scope_of`、`TaskQueue.register_handler/pause`、`PipelineStore.is_stop_requested/mark_interrupted`、`verify_password`、`to_iso/days_ago_iso`、`get_fallback_chain`、`install_wheel_bytes`、`parse_hcno_from_search_page`、`execute_request_interval`、21 个 `_get_*_adapter`、`_on_query_result_ready`、`DirBuilder.ensure_expire_dir`（U38 实测零调用） | vulture 60% + grep 逐条 | 死代码让 vulture 噪声/维护者误以为有入口；`verify_password` 是安全陷阱（旧格式） | 分批删除；`verify_password` 先确认无外部调用后删；getters 已由 A-33 裁定“下轮清理”；给 vulture 加“零调用 allowlist”防回潮 | A-33、W1-U1、vulture |
| **P2-04** | 文档数字/状态漂移：`13` 仍把 Q7 写成“未覆盖”（未区分主表已修/公告回退未修）、`17` 说队列表不存在、`18` 同页写“43 表/清单 41”（SQLite 实测 **45 张业务表**，46 含 `sqlite_sequence`；G-052 从迁移提取 **43**）、`19/24` 说无停止按钮/归档不含下载件、`20` 写 **134 条**（G-052 口径 **123 个 `/api` 路径**；`audit_api_matrix` **139 route/call pairs**，含非 `/api` 与方法对；三个口径未注明）、`index` 写 G-005~G-050（有 G-052）、`DOCUMENTATION_MAP` 117 篇（当前活跃 155＝审计前 153 + 本次新增 2） | 各文件行；G-052 `load_facts()`=123 routes/43 tables；`audit_api_matrix`=139；SQLite=45 业务表 | 下一个人按文档会得出相反结论，重复排查/误改 | 更新上述 8 处；**在同一处写清口径**（“唯一 `/api` 路径”/“route×method 对”/“业务表”）；把“路由数/表数/文档数”改为生成或加门禁；`index/MAP` 与 `find_docs` 输出对齐 | 13/17/18/19/20、index、MAP |
| **P2-05** | **8 条** markdown 死链 + 4 篇孤儿文档：`docs/architecture/modules/core.md:452`、`manager.md:199/200`、`parser.md:60`、`ui.md:61/62/85`、`debt/02-accepted.md:113` 指向已归档/已删的 plans 或 `STATUS.md`；孤儿 `notification-custom-menu.md`、`notification-field-contract.md`、`notification-stages-contract.md`、`openapi-frontend-contract.md`（扫描器另报的 `PITFALLS.md` “self” 是代码块 `](self)` 假阳性，已剔除） | 自写链接扫描（相对/根路径都试）；G-032 只查代码 span | 新人点开 404；契约文档没人找到，重复定义 | 修 8 条链接（改 `../../debt/...`/归档路径/删 `STATUS` 链接）；4 篇入 `DOCUMENTATION_MAP` 或 `index`；G-032 增加 markdown 链接维度并跳过 fenced code block | 链接扫描、G-032 |
| **P2-06** | `scripts/check_g_032_doc_health.py` 首字节 EF BB BF（BOM）；G-010 报 `invalid non-printable character U+FEFF` 并跳过函数规模检查；G-050 对 SyntaxError 文件静默跳过 | 字节检查；`check_all` 输出 `[WARN] 语法解析失败`；G-050 已知局限 | 文档健康门禁自身不在 AST 门禁覆盖内；BOM 类问题可能扩散 | 去 BOM（UTF-8 无 BOM 保存）；在 G-038/G-050 增加 BOM 检查；把“SyntaxError 跳过清单”打印出来 | 入口 A/门禁输出 |
| **P2-07** | 门禁覆盖缺口：`ci.yml:898` `check_module_doc_mappings.py --strict` 仍是告警期（exit 0）；G-031 只校验“文档存在+映射齐全”，不校验内容数字；G-048 只校验 `core.md` 的模块数 | `ci.yml`、gates G-031/G-048、A-4/E-6 | docs-sync 永远不阻断；`index/MAP/18/20` 的数字漂移无人拦 | 给 `--strict` 定截止日并切 `--strict-block`；把“路由数/表数/文档数”纳入 G-048 同类检查；或明确写“只告警”并从发布门槛移除 | A-4/E-6、G-031/G-048 |
| **P2-08** | UI 覆盖率 23%（U56），`TaskView.vue` 有效行 462 > 400（G-010 警告）；GUI 只在 CI/Windows 跑。**状态：部分完成（2026-11-09）**——补 3 个 GUI 用例，TaskView 行覆盖 **60.34→74.56%**、分支 **45.88→59.74%**、函数 **57.14→71.42%**；**不拆分**（理由见 §5.4） | U56 §2；G-010 输出；本次 vitest coverage | GUI 回归只能等 CI；TaskView 继续膨胀，后续改一键流程风险高 | 保持现有拆分（`TaskHistoryList`/`types`/`taskPipeline`）；本次补失败/历史/恢复分支；拆分触发条件见 §5.4 | U56、G-010、本次覆盖 |
| **P2-09** | `/api/auto` 调 `mgr.auto_run()` 无 `root_path`；`auto_run(root_path, ...)` 必 TypeError，admin 调用 500 | `docker/api/auto.py:25`、`facade/_auto.py` 签名、`08 #13` | 暴露的 admin 端点不可用；若有人按 API 文档调用会以为系统坏了 | 传 `get_settings().storage.root_dir` 或 `get_library_root()`；若确实废弃则返回 410 并从 `20` 删除；补 API 测试 | 08 #13、入口 A7 |
| **P2-10** | 验证底座问题：G-050 仍余 168 条（46 pass/50 return/72 debug）；`pytest` 6254 passed 但进程 exit 1（stderr 的 `UnicodeDecodeError` 被 PowerShell 包成 NativeCommandError）；`pnpm test` 354 passed 但 exit 1（同类） | `silent_errors_baseline.json`；本次全量；`04-watch` V-2 | “全绿但 exit 1”会训练人忽略退出码，真失败被漏；静默错余量让新错误混入 | 非迁移文件的 pass/return 逐条 triage（cache/file_utils/config 优先）；测试命令用 `cmd /c` 或 `--junitxml` + 解析，不靠 stderr；CI 以 JUnit 为准 | G-050、V-2、本次实测 |
| **P2-11** | v74 后仍有 4 条畸形 `standard_validity` 键无法唯一还原（如 `47013-2015` part=-1/.2 歧义） | 26 D-03、27 §5、`_migrate_v74` | 这 4 条标准永远不被 L1/L2 正确处理，统计分母也排除它们 | 出 4 条逐条 mapping/人工裁定；能合并的合并，不能的标 `manual_required` 并在 UI 可见；生产执行需窗口 | 26 D-03、27 §5 |
| **P2-12** | CLOSEOUT 遗留：明文凭证文件已删除、3 个文件已脱敏，但**凭证未轮换**（百度/腾讯/阿里云/Docker 密码） | `CLOSEOUT_REPORT.md` §四-1、`待确认清单.md` §二 | 如果这些是真实凭证，删除文件不等于失效；仍可能被已读过的进程/备份使用 | 在云控制台/Docker 轮换；轮换后更新 `config.json` 并复测通知/OCR；记录日期 | CLOSEOUT、P2-12 |
| **P2-13** | 11 个前端视图未配置 `meta.permission`（`audit_api_matrix` 的 `unguarded_views`：`AnnounceDetail`、`AnnounceView`、`FavoritesView`、`ForbiddenView`、`HomeView`、`LegacyRedirect`、`NotificationLogsView`、`OrganizeView`、`PendingView`、`RegisterView`、`StandardsStatusView`）；其中 **`OrganizeView` 的“加入有效性队列”调用 admin-only `/api/validity/enqueue`**，非 admin 点按钮会得 403 | `scripts/audit_api_matrix.py`：`unguarded_views=11`；`docker/api/validity.py` 的 `@require_role("admin")`；`OrganizeView.vue:77-88` | 非 admin 进入页面后点按钮得 403/空白，误以为系统坏；权限体验不一致 | 给这些路由/视图补 `meta.permission` 或按钮级 `v-if`（至少 OrganizeView 的 enqueue）；后端 403 返回可读中文；加前端路由守卫测试 | 入口 A2、API 审计 |

---

## 四、P3（接受不修；写理由与触发条件）

> P3 规则：必须写“为什么不修 + 什么条件下重新考虑”。

| ID | 问题 | 接受理由（为什么不修） | 触发条件（何时重新考虑） | 来源 |
|---|---|---|---|---|
| **P3-01** | v49 迁移 `DROP TABLE user_preferences` 会清空真实偏好；受 P-106 迁移 checksum 不可改 | 改源码会让所有已跑过 v49 的库启动即 `DatabaseError`；实际影响面仅“停在 v48 且有真实 KV 偏好”的库，发布已近 3 个月，基本不存在 | 有人报告“升级后偏好丢失” → 人工从升级前备份恢复，再评估新增 v77 | 08 #22、P-106 |
| **P3-02** | `.doc`（OLE2）附件 python-docx 不支持，正文为空 | 无用户反馈、无样本证明占比；现已从静默升为 warning，不是“不可见” | 出现 `.doc` 附件解析需求 → 引入 antiword/textract 或 UI 明示不支持 | 01 观察项、`_attachment_parser` |
| **P3-03** | 非 GB 无下载适配器；采标 GB 受版权限制 | 设计边界 + 法律限制；不是重试能解决 | 业务要求自动获取且拿到合法来源/授权 → 新增适配器 | 08 #14、11 Q3 |
| **P3-04** | Win watcher 只更新 `file_index`，不归档 | 设计边界；Win 一键走 `auto_run_stream` 是闭环的，watcher 不是主链 | 用户要求“Win 监控目录自动归档” → 接 `auto_run` 并补 GUI 测试 | 08 #3 |
| **P3-05** | 手动/一键下载无 HTTP 断点续传；`.part` 只清理不续传 | 下载成功率高、单文件小；续传需服务端 Range 支持，openstd 不保证 | 大文件/不稳定网络成为主要失败源 → 评估 Range + `.part` 续传 | 08 #7、23 §三 |
| **P3-06** | 外部验证包：T-40 wechat 真发、T-42 限流码、T-43 回调报文、A-22 Windows 托盘、A-27.1 真实菜单 API、A-28 rollback | 全部依赖凭证/公网/Windows 桌面，代码侧已实现并有 fake transport 单测；CI 无法覆盖 | 凭证到位、有 Windows 本机 5 分钟、或发版前必须真验 → 按 `03-open` 逐项执行 | 03-open、ROADMAP S7 |
| **P3-07** | D-14 分档阈值（30/60s）未用真实分布校准 | 样本量不足；当前阈值是初版，且有 `task_context` 埋点可后续取数 | 样本 ≥ 数百条管道/适配器耗时 → 用 P50/P90 校准 | 26 N3、D-14 |
| **P3-08** | `docs/query/README.md:61` 的 v2 细节 TODO；`HomeView.vue:17` 的 grid-layout-plus workaround | v2 仍在积累样本；workaround 在库升级后才可评估，收益低 | v2 灰度稳定 / 升级 grid-layout-plus >1.1.1 → 补文档/删 workaround | V-10、query README |
| **P3-09** | A-32 cookiecutter 把 `myadapter.py` 判为二进制（已用 Jinja2 绕行）；A-5 cookiecutter 真实 CLI e2e 未入 CI | 模板不常改；绕行有注释边界，升级时才需处理 | 升级 cookiecutter / hooks 变更 / 脚手架频繁使用 → 修判定或补 e2e | 03-open A-32/A-5 |
| **P3-10** | A-40 旧数据 `user_id=1` 归属未校验；A-41 failed-items 无 admin 全量视图；A-37 网络 e2e 未接 `PILOTSTD_RUN_NETWORK_TESTS` | 单用户升级可接受；admin 暂无跨用户排障需求；无外网时网络测试才会红 | 启用多用户 / admin 需要跨用户 / 下次改网络测试 → 按条修 | 03-open |
| **P3-11** | `query_metrics` 只被离线脚本 `analyze_routing_metrics.py` 读，无生产出口 | 当前无指标看板需求；表数据可用于离线分析，不算死 | 做查询性能看板/告警 → 接 API/导出 | 表维度 B20 |
| **P3-12** | G-050 已知局限：改名/拆分假红、多语句 `return` 不识别、同 handler 多 debug 只算 1 | 门禁口径有意偏松；假红可人工确认；多语句 handler 的 `info` 在生产可见 | 文件大规模改名/拆分，或新增“多语句 return”模式 → 调整基线键/扫描口径 | gates G-050 |
| **P3-13** | `data/backups/` 保留 2 份迁移前备份（v74→v75、v75→v76，共 4.3 MB） | 迁移前备份是回滚资产；体积小；已清理到只留最近两份 | 磁盘压力 / 备份保留策略变更 → 移出仓库或归档 | CLOSEOUT、目录实测 |
| **P3-14** | CLI `main.py --help` 在无 `SUPERUSER` 时于 argparse 前 FATAL 退出 | CLI 不是交付物（Q8：exe `console=False`、无入口声明），仅开发调试；设置 `SUPERUSER` 后 12 命令正常 | CLI 被列为交付物/文档主推 `main.py --help` → 把 env 校验移到命令执行前，help 先可用 | 入口 A4、Q8 |
| **P3-15** | monitor 批处理化（D25 598 批次键 / D26 34 manager 实例） | U38 实测：598 个独立 scope=598 键、同一 scope=1 键；同一 scheduler 34 目录并发只建 1 个 manager，34 未复现。598 是“独立 scope 聚合”的当前语义；批量场景应由 monitor debounce/批处理合并，不是改 `ensure_batch_key`。 | 每个文件事件一个 `auto_run` → 通知不合并；但这是 monitor 批处理化需求，不是 `ensure_batch_key` 缺陷 | 做 monitor 批处理化时一并验证：把同目录短时间多事件合并为一个批次，再断言通知条数/manager 实例数；当前接受 | U38 D25/D26、`08` #11/#D-04 |

### 4.1 U38 对账补记（2026-11-10）

> 只补状态/证据，不新增 P2 ID；C21 已单列 P1-09。

| 项 | 台账状态 | 证据 |
|---|---|---|
| C20 `ensure_expire_dir` | **规格描述错（已更新文档）**；P2-03 已补零调用 | 用户路径 `_move_expired_file` 通过；`safe_move` 懒建目录；方法 0 调用 |
| C22 无标准号兜底 | **规格描述错（已更新文档）** | `_on_file→auto_run→organize_fallback` 实测通过；`02`/`08` 已改 |
| C23 监控判有效性 | **规格描述错（已更新文档）** | `_on_file→auto_run→query→effect_status` 实测通过；`02`/`08` 已改 |
| D24 694 UNIQUE | **已测量达标（补记）** | 694 并发 `register_new_standard`：UNIQUE 0、行数 694；台账不新增 P2 |
| D25 598 批次键 | **P3 接受** | 598 独立 scope=598 键；同一 scope=1 键；批量场景归 P3-15 monitor 批处理化 |
| D26 34 manager | **未复现，接受** | 同一 scheduler 34 目录并发=1 个；34 未复现；归 P3-15 时验证 `_mgr_lock` 覆盖 Timer 路径 |

---

## 五、验收覆盖与优先级自检

### 5.1 每条 AC 被哪些条目影响

| AC | 阻断/缺口条目 | 当前能否通过 |
|---|---|---|
| AC-1 批量一键 | P0-01（已修）、P2-08（已补覆盖/不拆）、P1-08（人工未验） | **PASS（mock 全链）**；严格端到端待人工 |
| AC-2 监控投放 | P1-05（已修）、P1-09（已修）、P1-08（人工未验） | **PASS（代码/集成）**；人工/部署待验 |
| AC-3 通知对账 | P1-02（已修）、P1-06（渠道真发）、P2-13（前端权限） | PARTIAL |
| AC-4 查询/缓存 | P0-02（已修）、P3-06（v2 样本） | **PASS（缓存/查询链）**；v2 合并链/真实样本待验 |
| AC-5 时效性 | P2-11（4 行） | **PARTIAL**；P1-01/P1-02/P1-07 子场景已修 |
| AC-6 多用户 | P2-13、P3-10（旧 user_id） | PARTIAL |
| AC-7 失败可见/恢复 | P2-10（验证底座） | **PARTIAL**；P1-03/P1-04/P1-05 子场景已修 |

### 5.2 P0/P1 的“修后通过”一览

| ID | 修后通过的 AC |
|---|---|
| P0-01 | AC-1 |
| P0-02 | AC-4 |
| P1-01 | AC-5 子场景（手动检查计数） |
| P1-02 | AC-3、AC-5 子场景（中间报告数字） |
| P1-03 | AC-7 子场景（抓取失败历史可见）；AC-7 整体仍 partial |
| P1-04 | AC-7 子场景（不再有假续跑承诺）；整体仍 partial |
| P1-05 | AC-2（代码/集成；人工/部署待验） |
| P1-06 | AC-3 |
| P1-07 | AC-5 子场景（默认开关与文档一致） |
| P1-08 | AC-1/2/3/5/7 的证据强度 |
| P1-09 | AC-2/AC-7 子场景（Inbox 根空目录清理） |

### 5.3 为什么 P0 不是 20 条，也不是 1 条

- 六问题里 W2（monitor 归档）、W3（validity 搬移/回滚）、W4（未读隔离/归档 body）、W6（主表 stale）都已有代码 + 测试证据，失败面收窄为“统计/计数/中间消息”等局部场景 → P1。
- 真正“验收链断掉”的只有两条：批量选择被截断（AC-1）、旧公告结论被当新结论（AC-4）。
- 如果 P0 有 20 条，说明把“P2 质量债/待实测”都算成了阻断；如果 P0 只有 1 条，说明漏掉了“批量少下”或“旧结论”其中一条。

### 5.4 P2-08 决策：补 GUI 覆盖，暂不拆 TaskView

**选择**：补覆盖，不拆分。

**理由**

1. `TaskView` 已经做过低风险拆分：`TaskHistoryList.vue`、`TaskView/types.ts`、`utils/taskPipeline.ts` 都在；剩余 464 有效行主要是五段编排 + 模板/样式，继续拆需要搬 60+ 行并重接 props/emits，属于结构改动。
2. 刚完成 P0-01（下载选择），此时拆编排层会把“选择逻辑 + 状态机 + 模板”同时移动，回归面大于收益；G-010 目前只是 warning，不是阻断。
3. 真正的风险是**未测分支**（失败、历史、恢复），不是行数本身。本次补 3 个用例后，TaskView 行覆盖 **60.34→74.56%**、分支 **45.88→59.74%**、函数 **57.14→71.42%**（5→8 tests），已覆盖此前未测的 catch/finally、历史详情/删除、interrupted 恢复。
4. 拆分触发条件（满足任一即重开）：`TaskView` 再增 >50 有效行；G-010 从 warning 升为 block；或下一次 P0/P1 又落在 `runPipeline` 编排块。

**待做（不阻塞）**：给 GUI 作业设单文件覆盖率下限，避免“补了用例但没人看趋势”。

---

## 六、证据与复现

### 6.1 本次实跑命令

```powershell
# 全量后端（GUI 除外）
.venv\Scripts\python.exe -m pytest tests/ -q -n 8 -k "not gui"
# → 6254 passed, 10 skipped, 399 subtests passed, 333.29s
#   进程 exit 1 来自 PowerShell 对 stderr 的 NativeCommandError，不是 pytest 失败

# 定向验收
.venv\Scripts\python.exe -m pytest tests\integration\test_monitor_archive_e2e.py `
  tests\test_monitor_scheduler.py tests\test_validity_checker.py `
  tests\test_validity_checker_full.py tests\test_validity_queue_v75.py `
  tests\test_notification_unread_isolation.py tests\test_notification_logs_user_isolation.py `
  tests\test_router_v2.py tests\test_router_v2_skip_log.py `
  tests\test_download_task_persistence.py tests\test_pipeline_store.py `
  tests\test_archive_reconcile.py -q
# → 167 passed

# 前端
pnpm.cmd test            # → 45 files / 354 passed；exit 1 来自 stderr

# 门禁（bash 内）
bash scripts/check_all.sh --fast --guards --local   # → EXIT 0
```

### 6.2 关键静态普查

```powershell
python -m vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100
# → 0 输出（CI 口径干净）

python scripts/audit_api_matrix.py --json %TEMP%\u36_api.json
# → routes=139 calls=111 write_without_admin=0 unmatched=0 method_mismatch=0 unguarded_views=11

python scripts/check_g_032_doc_health.py
# → 4 warning（STATUS ×2、known-issues 22 天、gates 引用 docs/architecture/architecture.md）
```

### 6.3 数据与限制

- 本地 `data/pilotstd.db`：46 表，`_schema_version` 76；`file_index=0`、`notification_log=0`，**不能代表生产**。
- 生产 `192.168.1.18` 按文档不可达；`/api/health` 本地未起服务（8000 拒绝）。所有“生产通过”均标“待实测”。
- `logs/app.log*` 是 pytest 产物（20:11–20:12），不是生产日志；189×Telegram 404 等不能当生产根因。

---

## 七、方法可复用性（下次如何重跑）

1. **定义验收**：先读 `08/11/25/26`，用“主链闭环/结论正确/失败可见/隔离/可恢复/可验证”六条，写 3–7 条“操作 + 一句话判据 + 依赖”。
2. **穷举来源**：按 `U36-source-census.md` 的 44 个来源清单重跑；每个来源写“读到了什么/读到什么程度”，扫一眼的必须单列。
3. **四维交叉**：入口（Web/Win/CLI/monitor/scheduler/API/回调/启动）、表（写/读/失败/无读）、AC 链（出错可见/数据会错）、历史报告（每个问题→台账 ID）；每个格子写“已核实”或“补 ID”。
4. **判优先级**：只用 P0–P3 四条判据；P0/P1 写“修后哪条 AC 过”，P2 写“不修代价”，P3 写“理由+触发”。
5. **回写**：本台账 + `ACCEPTANCE_CASES.md` + `U36-cross-check.md` 同批；下次直接重跑，不要等新清单。

> **方法缺陷（自曝）**：第 2 步的“TODO 扫描”在 2026-11 已基本无产出；真正有效的是表读写矩阵/零调用/文档-代码对照。第 3 步的表维度依赖静态 SQL，动态表名会漏。第 1 步若无 W-001 原文，只能做“重建验收”，不能声称原文覆盖。

---

## 八、结论与置信度

**结论**：PilotStd 的主链（扫描/查询/下载/归档/通知/有效性）在代码与单测层是**可运行且大部分闭环**的；六问题中 W2/W4/W6 基本闭环，W1/W3/W5 仍有局部缺口。真正阻断验收的是 **2 条 P0**：批量下载硬上限、公告回退旧结论。

**置信度：中。** 理由：

- 高置信：代码级事实（10 上限、回退无 TTL、write-only 表、死列、BOM、`/api/auto`、门禁告警期）均逐行/实测；
- 中置信：完整性受四个限制——W-001 原文缺失、生产不可达、GUI/人工未执行、日志是测试产物；
- 低置信：任何“生产上已经/没有发生”的判断；本台账一律标“待实测”，不猜。

**如果只能做一件事**：先修 P0-01（一行选择逻辑 + 一个 20 条测试），因为它让“一键处理”在真实批量下名不副实；再修 P0-02（回退 TTL），因为它让系统给出错误结论。
