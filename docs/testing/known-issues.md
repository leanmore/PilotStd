# 已知问题

| 属性 | 值 |
|------|-----|
| 状态 | 活跃 |
| 版本 | v1.4 |
| 创建日期 | 2026-07-14 |
| 最后更新 | 2026-09-26（新增第 8 项：下载链 verifyCode 恒被拒；第 6 项状态改「已关闭」） |
| 关联 | `tests/test_adapters.py`、`tests/test_e2e_adapters.py` |

本文档记录当前已知但尚未修复的问题。已修复的问题不在此列。

## 一、未修复问题

### 1. njbz365 适配器多词前缀 match_status 返回 "mismatch"

| 属性 | 值 |
|------|-----|
| 问题描述 | `parse_std_number` 多词前缀修复后（如 `DIN EN` → code=`DINEN`），njbz365 适配器的 `match_result` 逻辑未同步调整，导致多词前缀标准（DIN EN、BS EN ISO）的匹配状态返回 `"mismatch"` 而非 `"exact"` |
| 影响范围 | njbz365 适配器对多词前缀国外标准的查询匹配 |
| 当前状态 | ✅ 已修复（2026-07-14），`_search_candidates` 新增从 `search_term` 自动解析标准编号字段，解析值优先于外部传入参数 |
| 修复内容 | `_search_candidates` 中新增 `parsed_target = _parse_result_number(search_term)`，以解析值（如 `DINEN`）优先于外部传入的单词语义 code（如 `DIN`） |
| 测试位置 | `tests/test_adapters.py::TestNjbz365Adapter::test_din_exact_match`、`test_bs_exact_match`（xfail 已移除） |

### 2. StdGovAdapter 端到端测试依赖外部 API

| 属性 | 值 |
|------|-----|
| 问题描述 | `test_e2e_adapters.py` 中 `test_gb_exact_match` 直接调用 `StdGovAdapter.query_with_strategy()` 发起真实 HTTP 请求，无法在 CI 环境中可靠运行 |
| 影响范围 | 仅影响 CI 中的端到端测试覆盖 |
| 当前状态 | 已标记 `@unittest.skip("外部 API 依赖 — CI 中跳过")` |
| 测试位置 | `tests/test_e2e_adapters.py::TestStdGovAdapter::test_gb_exact_match` |
| 计划修复 | 使用 mock HTTP 响应替代真实请求，或将此测试移入需要网络环境的独立测试套件 |

### 4. Telegram 通知因 429 限流大量丢失（2026-09-21 巡检）

| 属性 | 值 |
|------|-----|
| 问题描述 | 收藏下载链对**每条记录**发送 `download_started` / `download_failed` / `archive_abandoned` 通知，单日 150~200 条，触发 Telegram `HTTP 429 Too Many Requests` 限流；实测近半月 1119 条通知中 **622 条投递失败（55.6%）** |
| 影响范围 | 通知可达性（用户看不到过半告警）；渠道重试退避只能缓解单条，无法抵消量级 |
| 当前状态 | 未修复（仅 telegram 渠道有 3 次退避重试） |
| 证据 | `GET /api/notification/logs` 状态分布 success 497 / failed 622；容器日志 429 提及 3000+ 次 |
| 计划修复 | 链路通知聚合/限速（started 合并、failed 按批汇总），复用现有通知聚合器 |

### 5. 采标标准被当作"失败"重试 7 次（2026-09-21 巡检）

| 属性 | 值 |
|------|-----|
| 问题描述 | 采标标准（版权受限、自动跳过）与"非国标"在 `favorite_download.py` 中以 `FavoriteArchiveError` 抛出，链路按可重试失败处理 → 每条耗尽 7 天重试窗口后才 abandoned，并发出"归档任务放弃"通知 |
| 影响范围 | 无效重试与通知噪音（实测 6 条 × 7 天）；对用户而言是"永久失败却被反复重试" |
| 当前状态 | 未修复 |
| 证据 | 容器日志 `采标标准，版权受限，自动跳过` 6 条/天 × 09-14~09-20 |
| 计划修复 | 引入业务终态异常类型，链路识别后直接终态并只通知一次 |

### 6. `user_favorites.archive_retry_count` 列缺失导致状态接口 500（2026-09-21 巡检）

| 属性 | 值 |
|------|-----|
| 问题描述 | 当时的 `GET /api/favorites/{record_id}/status` 对全部收藏返回 500：`sqlite3.OperationalError: no such column: archive_retry_count`（原定位 `docker/api/favorites.py:210`） |
| 影响范围 | 单条收藏状态接口不可用（前端走 `POST /api/favorites/batch-status`，不受影响）；`last_archive_attempt` 无读取方 |
| 当前状态 | **已关闭**：v59 兜底迁移补列后 500 消失；该端点本身已于第七轮 #19 删除（现场日志实测零仓外调用方），故障载体不复存在 |
| 证据 | 容器日志 SQL + `sqlite3.OperationalError`；`GET /api/backup/list` 显示 `pre_migration_v57_to_v58.bak`（2026-08-29）。**根因曾是迁移已到版本顶**（库内 `_schema_version` 已到 58），`_run_migrations()` 直接 early-return，重发镜像也不会补列；v52 兜底只补了 `publish_date` |
| 计划修复 | 已完成：新增 v59 兜底迁移（幂等 ALTER 补 `archive_retry_count`/`last_archive_attempt`）+ `CURRENT_SCHEMA_VERSION` 58→59；端点删除见 `docs/technical-debt.md` 「一、已清理」 |

### 7. `daily_quota` 写入偶发失败（2026-09-21 巡检）

| 属性 | 值 |
|------|-----|
| 问题描述 | 日志出现 `SQL执行失败: INSERT INTO daily_quota (site_name, query_date, count) VALUES (?, ?, 0)`，09-14 起 1~2 次/天 |
| 影响范围 | 配额计数可能漏记（不影响下载主流程） |
| 当前状态 | 未修复 |
| 计划修复 | 改为 `INSERT OR IGNORE` 或显式处理唯一冲突 |

### 8. 收藏下载链 verifyCode 恒被拒（2026-09-24~26 现场）

| 属性 | 值 |
|------|-----|
| 问题描述 | 收藏下载链 GB 类成功率 **0**：`verifyCode` 提交恒被拒（现场 `verifyCode 结果` 15 次 error / 0 次 success）；即使请求成功，`viewGb` 也返回 200 + 0 字节 |
| 影响范围 | 收藏→自动入库这一核心出口实质失效，用户只能手工下载；6 条 failed 会在 7 天后变 `abandoned` 脏终态（届时即使修好也不能自动补下） |
| 当前状态 | **已修复待部署验证**：修复已提交（`532d994f` + `62fba6ef`），真实站点实测 9/9 下载成功、6 条收藏标准全部覆盖；生产库需等 v0.111.x 部署后复核日志与下载结果 |
| 证据 | 现场 v0.110.2 日志 15×error/0×success；三条根因：旧路径 `/bzgk/gb/*` 301 让 POST 退化 GET（body 丢失）、hcno 误用 `std_gov` 的 pid（openstd 不认）、缺「全文下载页」步骤（`viewGb` 200 但 0 字节）。控制实验：GB/T 5613-2026 不走下载页 0 字节、走下载页 251074 字节 |
| 计划修复 | 已完成（见上）；现场验证后从本节移除，落 `docs/technical-debt.md`「一、已清理」 |

## 二、测试收集排除项

以下测试文件未纳入 pytest 自动收集（通过 `tests/conftest.py` 中 `collect_ignore` 排除）：

| 文件 | 排除原因 |
|------|---------|
| `stress_selfcheck.py` | 独立压测脚本，含模块级 `sys.exit` |
| `stress_web.py` | 独立压测脚本 |
| `stress_docker.py` | 独立压测脚本 |
| `stress_cli.py` | 独立压测脚本 |
| `stress_runner.py` | 独立压测脚本入口 |
| `stress_driver.py` | 已废弃，由 stress_runner.py + stress_cli.py 替代 |
| `stress_winui.py` | 由 stress_runner.py 显式调用 |
| `gui/` | GUI 测试需 Qt 环境，CI 中由独立 job 运行 |

### 3. pilotstd/wechat_ip/ — 暂不纳入单元测试覆盖率考核

| 属性 | 值 |
|------|-----|
| 状态 | 已豁免 |
| 版本 | v1.0 |
| 创建日期 | 2026-07-31 |
| 关联 | `pilotstd/wechat_ip/browser.py`、`scheduler.py`、`cookie_mgr.py`、`detector.py` |

- **原因**：核心逻辑依赖 Playwright 浏览器自动化（模拟登录企微后台），需真实浏览器环境，Mock CDP 协议栈投入产出比极低
- **当前保障**：`docker/app.py` 中注册为生产 API 路由，可通过集成测试验证；故障影响局限于"企业微信 IP 白名单更新失败"，属于可容忍的边缘功能降级
- **后续计划**：评估 Playwright E2E 容器化测试替代方案

## 三、G-032 设计保留项（2026-08-21 登记）

> 以下 8 条 G-032 警告为**设计保留**（非遗漏），由迁移与治理流程明确裁决，无需修复。运行 `python scripts/check_g_032_doc_health.py` 时仍会显示，属预期行为。

| # | 警告内容 | 保留理由 |
|---|----------|----------|
| 1 | `docs/testing/known-issues.md 已 21 天未更新` | 宽限期内（上限 14 天），本文档更新即自然消除 |
| 2 | `AGENTS.md 引用了不存在的文件: ~/.claude/CLAUDE.md` | 历史来源标注，用户裁决保留（Claude Code 迁移记录） |
| 3-8 | `STATUS.md:23/49/57-60 含 [legacy-manual] 标记的数值`（6 条） | 设计如此——手动维护数值，标记 `[legacy-manual]` 走宽限期，待自动化指标接管后清除 |

## 四、门禁联动

当以下文件发生变更时，需确认关联的已知问题是否有进展或需更新：

| 变更文件 | 关联问题 |
|----------|---------|
| `pilotstd/query/adapters/njbz365.py` | 问题 1（match_status 逻辑） |
| `pilotstd/core/std_utils.py`（`parse_std_number`） | 问题 1（多词前缀解析） |
| `pilotstd/query/adapters/std_gov.py` | 问题 2（端到端测试） |
| `scripts/check_g_032_doc_health.py` | 第三节（G-032 设计保留项） |
| `STATUS.md` / `docs/testing/coverage-report.md` | 第三节（自动生成文档，G-032 降级 INFO） |

## 五、版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.5 | 2026-09-26 | 新增第 8 项（下载链 verifyCode 恒被拒，已修复待部署验证）；第 6 项状态改「已关闭」（端点已于 #19 删除）；头部「最后更新」同步 |
| v1.4 | 2026-09-21 | 新增第 4~7 项（局域网容器巡检结论）：Telegram 429 通知丢失 55.6%、采标被当失败重试 7 次、`archive_retry_count` 缺列致状态接口 500、`daily_quota` 偶发写入失败 |
| v1.0 | 2026-07-14 | 初始版本，记录 njbz365 match_status 和 StdGovAdapter e2e 两个已知问题 |
| v1.1 | 2026-07-14 | njbz365 适配器 match_status 已修复（`_search_candidates` 自动解析 search_term），移除 xfail |
| v1.2 | 2026-07-31 | 新增 wechat_ip 单元测试豁免（P2-2 处置审批），浏览器自动化模块暂不纳入覆盖率考核 |
| v1.3 | 2026-08-21 | 新增第三节"G-032 设计保留项"（8 条裁决登记）；门禁联动补充 check_g_032/STATUS 关联 |
