# 27 · 实施记录（本地代码，未部署）

> 记录本轮已实际修改的代码、测试与回滚方式。  
> 环境：本地开发/验证；**未改生产、未部署**。

---

## 2026-11-10（P1-05/P1-07/P1-04）

### P1-04 batch_state 定性为完成审计（不实现续跑）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/query/engine/_batch_dispatcher.py`、`tests/unit/query/engine/test_batch_dispatch.py`、`docs/query/README.md`、`docs/architecture/overview.md`、`docs/migrations/README.md` |
| 行为 | `_persist_batch_state` docstring 写明“只写不读、完成审计，不是续跑”；`query/README` 的“断点续传机制/恢复流程”改为“批次完成审计/当前没有恢复流程”；表注释不改（P-106），文档以新定性为准 |
| 测试 | 新增 1 例：`_persist_batch_state` 写 `status=completed` 审计行；`test_batch_dispatch.py` **16 passed** |
| 回滚 | 还原 docstring/文档描述与新增测试 |
| 关联 | ISSUE_LEDGER P1-04；AC-7 子场景 |

### P1-07 auto_move_expired 默认值与文档对齐

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/core/validity_checker.py`、`docs/onboarding/26-fix-dossiers.md`、`tests/test_batch3_validity_wiring.py` |
| 行为 | 裁定“默认开”是 2026-11-07 有意决策：docstring 改“默认开启（FACTORY_DEFAULTS=True），显式 false 才不搬”；26 D-03 的根因/边界/就绪度三处“默认 false/仍未开启”更正；新增 FACTORY_DEFAULTS 默认值断言。**不改 defaults.py 行为** |
| 测试 | `pytest tests/test_batch3_validity_wiring.py tests/test_validity_checker.py -q` → **20 passed** |
| 回滚 | 还原 docstring/26 文字与默认值断言 |
| 关联 | ISSUE_LEDGER P1-07；AC-5 |

### P1-05 monitor_stats 重启恢复

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/monitor/config.py`、`docker/app.py`、`tests/test_monitor.py` |
| 行为 | 新增 `MonitorStats.load_today()`：启动时按 `stat_date=今天` 读 `monitor_stats` 恢复 processed/success/failed；DB 失败 warning 后保持 0；`get_today_stats` 不再因重启归零 |
| 测试 | 新增 2 例：恢复 7/5/2；DB 抛错保持 0。monitor 相关 **49 passed** |
| 回滚 | 删除 `load_today` 调用与两个测试 |
| 关联 | ISSUE_LEDGER P1-05；AC-2 |

## 2026-11-10（P1-01/P1-02，AC-5）

### P1-01 手动 `/api/validity/run` 推进轮次计数

| 项 | 内容 |
|---|---|
| 文件 | `docker/api/validity.py`、`tests/test_api_validity_manual_counters.py` |
| 行为 | 手动 run 由 `update_counters=False` 改为 `True`，与定时任务同口径；`checked_count` 是轮次累计，`/api/validity/history` 是按日聚合，语义不同但不再出现“历史有记录、计数 0” |
| 测试 | 新增 2 例：手动 run 必须传 `update_counters=True`；失败返回 500。相关 validity 套件 **95 passed** |
| 回滚 | 改回 `update_counters=False` 并删除新增测试 |
| 关联 | ISSUE_LEDGER P1-01；AC-5 |

### P1-02 `validity_batch_report` 中间消息真实进度

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/core/_validity_pipeline.py`、`tests/test_validity_checker_full.py` |
| 行为 | `_apply_validity_result` 增加 `checked_count/failed_count` 入参；每 10 条变化的中间报告 `count=已处理条数、changed=累计变化、failed=累计失败`，删除硬编码 `0/10/0`；最终报告口径不变 |
| 测试 | `test_batch_notification_at_10_changes` 增加断言：第 10 条变化时 `count=10/changed=10/failed=0`，`change_detail` 10 条 |
| 回滚 | 还原 `_apply_validity_result` 签名与 payload；测试同步还原 |
| 关联 | ISSUE_LEDGER P1-02；AC-3/AC-5 |

## 2026-11-09（P0 修复，commit `72856e99`）

### P0-01 移除 Web 一键下载 10 条硬上限（AC-1）

| 项 | 内容 |
|---|---|
| 文件 | `web/src/views/TaskView.vue`、`web/src/views/TaskView.test.ts` |
| 行为 | 删除 `dlNums` 的 `.slice(0, 10)`；全部 `exact` 非采标项交给 `postDownload`，由 `download.batch_size=10` 分批执行；新增 20 条 exact 用例，断言 `postDownload` 收到 20 个号、归档 payload 21 条（1 扫描件 + 20 下载件） |
| 测试 | `pnpm --dir web exec vitest run src/views/TaskView.test.ts` → **5 passed**；前端全量 **355 passed**；`type-check`/`lint`（0 error）/`build` 通过 |
| 回滚 | 还原下载选择块与新增测试；后端无需回滚 |
| 关联 | ISSUE_LEDGER P0-01；AC-1 |

### P0-02 公告缓存回退补 TTL/stale 守卫（AC-4）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/query/cache.py`、`tests/test_query.py` |
| 行为 | 公告回退 `SELECT *` 后先过 `_announcement_cache_fresh`：`data_state='stale'` 拒绝；`expires_at` 可解析时优先；否则 `cached_at + active_ttl`（默认 30 天，`<=0` 不按时间过期）；两个时间都缺失时保守命中 |
| 测试 | `pytest tests/test_query.py` → **83 passed**；新增：31 天前 cached_at miss、stale miss、显式 expires_at 过期 miss、fresh hit、QueryEngine 全链旧公告→最新状态 |
| 回滚 | 还原 `cache.py` 回退块与新增测试 |
| 关联 | ISSUE_LEDGER P0-02；AC-4 |

### P1-03 公告抓取失败历史补读侧

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/announce/persistence.py`、`pilotstd/announce/crawler_service.py`、`pilotstd/manager/announce_service.py`、`docker/api/announce.py`、`web/src/api/announce.ts`、`web/src/api.ts`、`web/src/views/AnnounceView.vue`、三语 locale、`tests/announce/test_persistence.py`、`tests/test_api_announce_fetch_failures.py`、`AnnounceView.test.ts` |
| 行为 | `fetch_failures` 增加 `list_failures/failure_counts/resolve_failure/resolve_site_failures`；`AnnounceService.get_fetch_failures()` 聚合；新增 `GET /api/announce/fetch-failures`；公告页显示“抓取失败 N 条未解决 / 共 M 条”及最近 5 条；某站抓取成功后把该站历史未解决失败标记 resolved |
| 测试 | 后端 **12 passed**（持久化 10 + API 2）；AnnounceView **7 passed**；三语 **947 键一致**；`check_i18n_key_count.py` PASS |
| 回滚 | 还原读方法/端点/页面板与新增测试；写入逻辑不变 |
| 关联 | ISSUE_LEDGER P1-03；AC-7 |

### P2-08 补 TaskView GUI 覆盖（不拆分）

| 项 | 内容 |
|---|---|
| 文件 | `web/src/views/TaskView.test.ts` |
| 决策 | 补覆盖，不拆 TaskView：已拆出 `TaskHistoryList`/`types`/`taskPipeline`，继续搬编排层会同时移动选择/状态机/模板，P0-01 刚改完，回归风险 > G-010 warning 收益（理由 + 触发条件见 ISSUE_LEDGER §5.4） |
| 新增用例 | 3 个：查询失败 → 错误可见 + 历史 `fail`；历史详情查看/删除；interrupted 恢复显示“继续任务”。用例数 5 → **8** |
| 覆盖率 | TaskView：行 **60.34% → 74.56%**、分支 **45.88% → 59.74%**、函数 **57.14% → 71.42%**（`vitest --coverage --coverage.include=src/views/TaskView.vue`） |
| 回滚 | 删除 3 个新增用例；无生产代码改动 |
| 关联 | ISSUE_LEDGER P2-08；AC-1 |

---

## 2026-11-07

### 1. Web 下载件进入归档（D-01，前端）

| 项 | 内容 |
|---|---|
| 文件 | `web/src/views/TaskView.vue` |
| 行为 | 下载结果中 `status=success` 且有 `saved_path` 的项，解析标准号后加入 `archiveItems`；按 `source_path` 去重 |
| 测试 | `web/src/views/TaskView.test.ts` 新增“下载成功的文件也进入归档 items” |
| 结果 | `pnpm test` 352 passed；`type-check`/`build` 通过 |
| 回滚 | 还原 `TaskView.vue` 归档块 + 删除新增测试 |

> 仍待：后端重复/覆盖策略、部署后 E2E。

### 2. 通知未读数/全部已读按用户隔离（D-04 部分）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/core/notification/_manager_ops.py`、`docker/api/notification_logs.py` |
| 行为 | `get_unread_count(user_id)` / `mark_logs_read(..., user_id)`；API 传当前用户；单条已读先校验归属 |
| 测试 | 新增 `tests/test_notification_unread_isolation.py`；相关 57 passed |
| 结果 | `ruff` 通过；`pytest` 57 passed |
| 回滚 | 还原两个函数签名/查询 + 删除新增测试 |

> 仍待：11/7 批次日志缺失、聚合批次键、`notification_log` 不存 blocks。

### 3. monitor 并发锁 + 空目录清理（D-02 部分）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/monitor/scheduler.py` |
| 行为 | 懒加载 `StandardManager` 加 `_mgr_lock` 双检；归档后 `_cleanup_empty_dirs(watch_path, source_root)` 只删空目录 |
| 测试 | 新增 `tests/test_monitor_cleanup.py`；`test_monitor_archive_e2e.py` 7 passed |
| 回滚 | 还原锁/清理调用 + 删除新增测试 |

> 仍未做：monitor 查询/下载/兜底、每文件全目录扫描、`auto_run` 空目录清理。

### 4. 查询缓存 stale 检查（D-06）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/query/cache.py` |
| 行为 | `CacheRepository.get()` 对 `data_state='stale'` 返回 None；`put()` 更新时置 `data_state='fresh'` |
| 测试 | `tests/test_query.py::TestCacheRepository` 14 passed；全量 query 78 passed |
| 回滚 | 删除 stale 判断/恢复 UPDATE 语句 |

> 仍需部署后观察：517 条 live 缓存全 stale，首次查询会回源，可能有网络压力。

### 5. v74 validity 畸形键修复（D-03 数据层）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/core/db/_migrate_v74_repair_validity_keys.py`、`_constants.py`、`migrations.py` |
| 行为 | 可唯一还原的 705 条修复（704 改名 +1 合并）；4 条无法唯一还原保留；幂等 |
| 测试 | `tests/test_migrate_v74_validity_keys.py`；迁移链测试 134 passed |
| dry-run（prebatch 副本） | 803 → 802 行；畸形 709 → **4**；`47013-2015` 因 part=-1/.2 歧义保留 |
| 回滚 | 用 prebatch 副本替换；不写反向 UPDATE |

> 生产执行仍需维护窗口；dry-run 只在 `C:\Temp\pilotstd_v74_dryrun.bak` 副本上做。

### 6. v2 采样缺口（D-05）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/query/routing/router_v2_metrics.py`、`pilotstd/query/engine/_single.py` |
| 行为 | v2 开启但被缓存/指定站点截走时，写入 `routing_version=v2_skipped`，记录 reason/hit_site |
| 测试 | `tests/test_router_v2_skip_log.py`；v2 相关 26 passed |
| 回滚 | 删除 `record_v2_skip` 调用/函数 |

> 真实 ≥1000 条 v2 样本仍需验证环境；`v2_skipped` 不是 v2 路由决策，分析时要分开统计。

### 7. hcno 历史注释修正（Q6）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/query/models.py` |
| 行为 | 注释改为“站点详情 ID，不是 openstd hcno；下载侧禁止读取” |
| 测试 | 无行为变更；`openstd_download` 49 passed（此前） |
| 回滚 | 还原注释 |

### 8. validity_check_queue 建表 + 消费者（#12 / v75）

| 项 | 内容 |
|---|---|
| 文件 | `_migrate_v75_validity_queue.py`、`validity_service.py`、`docker/scheduler.py`、前端 `OrganizeView` 文案 |
| 行为 | 建队列表；`process_pending` 路径→标准号→`check_standard`；调度器 60s drain + 启动补跑 |
| 测试 | `tests/test_validity_queue_v75.py` 4 passed；迁移链 31 passed |
| 回滚 | 还原 v75 常量/迁移注册/服务与调度器；旧库不再自动建表 |

### 9. 归档通知正文（#9）

| 项 | 内容 |
|---|---|
| 文件 | `_builders_system.py`、`_organize.py`、`pilotstd/i18n/{zh_CN,zh_TW,en}.json` |
| 行为 | `archive_complete` 始终写 body（count/skip/fail/dirs）；payload 增加 total/skipped/failed |
| 测试 | `tests/test_notification_core.py` 新增零搬移正文、skip/fail 正文用例；78 passed |
| 回滚 | 还原 builder body 与 payload 字段 |

> 零搬移仍发送（按用户要求），不改成抑制。

### 10. Web 协作式停止（#15 / Web B）

| 项 | 内容 |
|---|---|
| 文件 | `pipeline_store.py`、`docker/api/tasks.py`、`web/src/api/tasks.ts`、`TaskView.vue`、三语 locales |
| 行为 | `running → stopping → stopped`；前端每阶段边界检查；当前阶段收尾后停 |
| 测试 | `test_pipeline_store.py` / `test_api_tasks_endpoints.py` 13 passed；`TaskView.test.ts` 4 passed |
| 回滚 | 删除 stop 路由/方法/按钮与状态文案 |

> Win 端仍为 A（只停 UI 等待，不杀 worker）。

### 11. monitor 改为触发主链（D-02）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/monitor/scheduler.py`、`tests/integration/test_monitor_archive_e2e.py` |
| 行为 | `_on_file` 按父目录去抖/加锁 → `mgr.auto_run(source_root)`；不再自建 scan+archive |
| 测试 | monitor e2e + cleanup 7 passed；同一目录 10 秒去抖 |
| 回滚 | 还原 `_on_file` 的 scan/archive 实现 |

### 12. 钉钉企业卡片/飞书应用消息重试（#16）

| 项 | 内容 |
|---|---|
| 文件 | `channels/dingtalk.py`、`channels/feishu.py`、`test_dingtalk_enterprise.py` |
| 行为 | 两条企业形态路径接入 `_with_retry`；429/5xx/网络错误退避；非重试错误不放大 |
| 测试 | 钉钉企业 9 passed；飞书应用 12 passed |
| 回滚 | 恢复单次 `_send_card` / `_post_app_message` 实现 |

### 13. 管理员默认可见系统通知（D-04）

| 项 | 内容 |
|---|---|
| 文件 | `_manager_ops.py`、`docker/api/notification_logs.py` |
| 行为 | 列表/未读数/全部已读对 admin 默认包含 `user_id=0/NULL`；普通用户仍只看自己；all=true 才是全部用户 |
| 测试 | 通知隔离/API/manager 60 passed |
| 回滚 | 去掉 include_system 参数与 API 传参 |

### 14. Web 阶段级续跑（#7 的 Web 部分）

| 项 | 内容 |
|---|---|
| 文件 | `pipeline_store.py`、`docker/app.py`、`tasks.py`、`TaskView.vue`、`taskRestore.ts`、三语 locales |
| 行为 | 启动 running/stopping → interrupted；`/task` 继续按钮；从最后一次完整阶段继续；不自动续跑半阶段 |
| 测试 | pipeline store/API 16 passed；TaskView+taskRestore 13 passed；type-check 通过 |
| 回滚 | 删除 interrupted/resume 路由与前端继续按钮 |

> 注意：这不是下载任务持久化；`DownloadTask` 仍在内存，边界 #7 的下载部分仍开放。

### 15. v2 路由默认启用（D-05）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/query/routing/router_v2.py`、`tests/test_router_v2_integration.py`、相关文档 |
| 行为 | `is_v2_enabled()` 默认 True；`ROUTING_ENGINE_VERSION=v1` 可回滚；无需在 compose/.env 写变量 |
| 测试 | router v2 集成 8 passed |
| 回滚 | 部署时设置 `ROUTING_ENGINE_VERSION=v1`，重启即可，不改代码 |

### 16. 并发写入原子化（#10）

| 项 | 内容 |
|---|---|
| 文件 | `file_index.py`、`validity_checker.py`、对应测试 |
| 行为 | file_index 单条 `ON CONFLICT DO UPDATE`；validity 首次登记 `INSERT OR IGNORE ... WHERE NOT EXISTS` + `rowcount` |
| 测试 | file_index 75 passed；validity 87 passed |
| 回滚 | 恢复两处 SELECT+INSERT/UPDATE 分支 |

### 17. 过期标准自动搬移 + 并行期（D-03）

| 项 | 内容 |
|---|---|
| 文件 | `validity_checker.py`、`_validity_pipeline.py`、`config/defaults.py`、有效性测试 |
| 行为 | 默认开启 `auto_move_expired`；被代替标准在新标准实施日前只标记/通知；实施日后补搬并补发 `expire_standard_moved` |
| 测试 | 有效性 129 passed |
| 回滚 | `validity.auto_move_expired=false` 或还原默认 |

### 18. 归档预览名 + 冲突待确认（D-01/#8）

| 项 | 内容 |
|---|---|
| 文件 | `organizer.py`、`mover.py`、`archive.py`、`service_factory.py`、organizer 测试 |
| 行为 | 归档以 `final_name`（Web 的 new_filename）为准；同 hash 跳过；不同内容不覆盖，写入 `pending_lookup`（reason=archive_conflict） |
| 测试 | organizer 116 passed |
| 回滚 | 恢复按标准号自动命名 + 目标存在直接跳过 |

### 19. 下载任务持久化 + 启动重试（#7 B）

| 项 | 内容 |
|---|---|
| 文件 | `download/engine.py`、`manager/facade/_base.py`、`docker/scheduler.py`、测试 |
| 行为 | 下载任务写 `task_queue`；启动补跑未完成任务；`retry_count >= max_retries` 不再重试 |
| 测试 | 下载持久化/下载链 57 passed |
| 回滚 | 去掉 `_persist_task`/`retry_pending` 与启动线程 |

### 20. 通知铃铛去重 + 可信 IP 错误可见（2026-11-07）

| 项 | 内容 |
|---|---|
| 文件 | `NotificationBell.vue`、`wechat_ip_service.py`、`browser.py`、`scheduler.py` |
| 行为 | 铃铛按事件去重；同事件多渠道一起已读；失败投递不进铃铛；收藏标题带标准号/名称；企微卡片长名称拆行；可信 IP 启动失败可见；空 URL 不误判 Cookie；不再用公开默认密钥 |
| 测试 | 前端铃铛 19 passed；可信 IP/状态 56 passed；通知/有效性 183 passed |
| 回滚 | 前端恢复按行展示；可信 IP 恢复原异常分支 |

### 21. Docker 接入 CloakBrowser（可信 IP A1）

| 项 | 内容 |
|---|---|
| 文件 | `docker/requirements-docker.txt`、`docker/Dockerfile`、`docker-compose*.yml`、`docker/cloakbrowser.sh`、`.env.example`、`wechat_ip/browser.py` |
| 行为 | CloakBrowser 0.7.1 自带 Chromium；启动预装 + `binary_info()` 检查；缓存 `/app/data/cloakbrowser`；license/env；`launch_persistent_context` 保持登录态 |
| 验证 | 需 Docker 构建；首次启动下载约 200MB 二进制 |
| 回滚 | 移除 cloakbrowser 依赖与缓存卷，回到 Playwright/人工更新 |

### 22. 时效性检查病历（v76）

| 项 | 内容 |
|---|---|
| 文件 | `db/_migrate_v76_validity_check_log.py`、`validity_log.py`、`_validity_pipeline.py` |
| 行为 | 每次 L1/L2/L3 结果/失败原因写 `validity_check_log`；状态仍写 `standard_validity`；失败继续发通知 |
| 测试 | 有效性 136 passed |
| 回滚 | 删除表/恢复 v75；不影响既有状态 |

### 23. 公告抓取回看窗口

| 项 | 内容 |
|---|---|
| 文件 | `announce/crawler_service.py`、`manager/announce_service.py`、`config/defaults.py` |
| 行为 | 定时/手动 `check_announcements` 从 checkpoint 多回看 `announcement.lookback_days=7` 天；定时入口超过 36 小时未成功抓取会在完成通知中标注漏跑 |
| 测试 | 公告/调度测试通过 |
| 回滚 | 设 `announcement.lookback_days=0` |

### 24. P2-14 部署验证（site_capabilities 播种）

| 项 | 内容 |
|---|---|
| 文件 | 无代码改动（验证既有 `docker/entrypoint.sh` + `docker/Dockerfile`） |
| 行为 | 远程已运行 `v0.181.8`（image `ghcr.io/leanmore/pilotstd:v0.181.8`，health commit `38d04b7c`，含 `8ca0106b`）；`POST /api/validity/run` → **200 / 40s / checked=30 / changed=8**；`/api/validity/history` 新增 `2026-11-13 checked=30 changed=8 success`（修复前最高停在 11-05） |
| 测试 | 远程实测（只读 + 一次 admin validity run，已获授权）；本地 `tests/test_docker_config_seed.py` 2 passed |
| 回滚 | 无（配置播种只在缺失时执行，不覆盖用户配置） |

### 25. P2-10 静默吞错批 1（50 条 triage）

| 项 | 内容 |
|---|---|
| 文件 | `docker/_static_token.py`、`docker/scheduler.py`、`pilotstd/core/config/manager.py`、`scripts/silent_errors_baseline.json`、新增 `tests/test_p2_10_silent_error_triage.py`、`docs/debt/p2-10-silent-errors-triage.md` |
| 行为 | 3 条升级 warning（静态令牌落库失败、备份目录不可读、`.bak` 回滚失败→默认值覆盖配置）；47 条 allowlist 并逐条写理由；基线 168 → 165（pass 46/return 49/debug 70） |
| 测试 | 新增 3 例；`tests/unit/core/config` + `test_backup_retention` + `test_scheduler_extra` 共 42 passed；G-050 PASS |
| 回滚 | 还原 3 处日志级别 + 恢复旧基线（`git show 635e0e93:scripts/silent_errors_baseline.json`） |

### 26. monitor 存量扫描判定（08 #23）

| 项 | 内容 |
|---|---|
| 文件 | 只读排查：`pilotstd/monitor/scheduler.py`、`handler.py`、`docker/app.py`、`docker/entrypoint.sh` |
| 行为 | 判定 **A（代码为纯事件驱动）+ B（不符合用户期望）**：`_run()` 只 `observer.schedule/start`，无启动遍历；`handler.py` 只有 created/modified/moved；`last_processed` 硬编码空串（`scheduler.py:248`）。远程 825 文档滞留即此场景 |
| 测试 | 无代码改动；`docs/onboarding/08-known-boundaries.md #23` 记录修复方案（`scan_existing_on_start` + watermark），**改生产行为需授权** |
| 回滚 | 不适用 |

### 27. P2-07 数字声明门禁（G-052 扩展）

| 项 | 内容 |
|---|---|
| 文件 | `scripts/check_docs_drift.py`、新增 `tests/test_check_docs_drift_counts.py`；文档 `03`/`19`/`20`/`onboarding/README` |
| 行为 | `COUNT_CLAIMS` 登记 6 处写死数字，与代码抽取（router 模块数 / 唯一 `/api` 路径 / route×method 对 / 迁移表数 / 迁移模块数）比对；不符或声明缺失 → `count_drift`/`count_missing` 阻断；同批修 4 处漂移 |
| 测试 | 新增 4 例（现状一致 / 事实变化检出 / 声明缺失 / 数值不符带行号）；`python scripts/check_docs_drift.py` → 0 违规 |
| 回滚 | 删 `COUNT_CLAIMS`/`check_count_claims` 调用与测试，数字声明随之回退 |

### 28. monitor 启动补扫（08#23 / P3-16；用户授权默认开）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/monitor/scheduler.py`、`handler.py`、`config.py`；新增 `tests/integration/test_monitor_catchup_e2e.py`、`scripts/stress_monitor_catchup.py` |
| 行为 | `_run()` 在 observer 启动后起 `monitor-catchup` daemon 线程：按目录分批、祖先折叠、1s 间隔、`stop` 可打断；`monitor.scan_existing_on_start` 默认 `true`；watermark `monitor_state.catchup_watermark`（= 扫描开始时间，被打断不推进）；`last_processed` 落 `monitor_state.last_processed` |
| 测试 | 新增 e2e 6 例（启动前放文件→归档、祖先折叠、watermark、禁用、stop 打断、last_processed）；monitor 相关 94 passed；本地 825 文件压测：62 批 / 825 搬移 / 0 UNIQUE / 0 locked / inbox 清空；全量 pytest **6740 passed / 12 skipped**；CI run `43434928596` success，镜像 v0.182.0 |
| 回滚 | `monitor.scan_existing_on_start=false` 立即停用；代码回滚删除 `_catch_up_existing` 与三个 state 辅助函数 |

### 29. P2-11 畸形 validity 键实测（7 条，非 4）

| 项 | 内容 |
|---|---|
| 数据 | 远程 `pre_migration_v75_to_v76.bak`（`/api/backup/download`）：`standard_validity` 819 行，前导空格缺代号键 7 条 |
| 判定 | ` 11-2020`/` 23-2021`/` 7-2019`/` 8001-2019`/` 8002-2022` → 合并到已存在的 `TSG …`（`T/SG` 候选都是修改单）；` 19001-2020`/` 47008-1947` → `manual_required`（file_index 无同号同年） |
| 下一步 | 一次性修复脚本 dry-run + 生产窗口执行；2 条在 UI 标 `manual_required`。未发现 `47013-2015` part 歧义 |

### 30. C24 导出接口恒失败（已修）

| 项 | 内容 |
|---|---|
| 文件 | `docker/api/export.py`、`tests/test_api_scheduler_export_auto.py` |
| 行为 | 远程实测 `/api/export/standards` 恒返回 `{"ok": false, "error": "'StandardManager' object has no attribute 'get_status_stats'"}`；改为 `mgr.file_index.get_status_stats()` |
| 测试 | 测试 mock 删除 `get_status_stats` 伪属性（`del mgr.get_status_stats`），9 passed；修复前该断言必红 |

### 31. P2-10 批 2（scripts 22 条）

| 项 | 内容 |
|---|---|
| 文件 | `scripts/check_g_013_test_coverage.py`、`scripts/silent_errors_baseline.json`、`docs/debt/p2-10-silent-errors-triage.md` |
| 行为 | 22 条中 21 条 allowlist（读文件/解析失败 → 保守回退；语法错误由 ruff 兜底）；`check_g_013` 读 commit message 失败由静默 `return ''` 改为 stderr `[WARN]`（空消息会让"fix 必须带测试"规则失效） |
| 测试 | G-013 相关 23 passed；G-050 基线 165 → 164，PASS |
| 回滚 | 删 `[WARN]` 两行并恢复基线 |

### 32. P2-10 exit-1 修复（聚合器 shutdown 后回调）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/core/notification/aggregate_buffer.py`、`tests/test_scheduler_timer_drift.py` |
| 行为 | 新增 `_closed`：`shutdown()` 置位后晚到的 `_on_timer`/`_schedule_next` 直接返回，不再续期/写 debug 日志（原先在 pytest 捕获关闭后写日志 → 线程内 `ValueError: I/O operation on closed file` → 全绿但 exit 1） |
| 测试 | 新增 `test_timer_callback_after_shutdown_is_dropped`；定时器/聚合 51 passed；通知相关 1248 passed；全量 6740 passed/12 skipped |
| 回滚 | 删除 `_closed` 三处判断与回归用例 |

### 33. monitor 根散件成批 + 替代关系补查属性（远程批量实测暴露）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/monitor/scheduler.py`、`pilotstd/manager/classifier.py`、`tests/integration/test_monitor_catchup_e2e.py`、`tests/unit/manager/test_classifier_coverage.py` |
| 行为 | ① 根目录散件不再与子目录折叠成 1 个超大批次，改为子目录批次在前、根散件最后单独一批；② `classifier.resolve_replaces` 由 `_use_cache`/`_cache` 改为 `use_cache`/`cache`（原写法每次补查都 AttributeError，被吞成"替代标准查找失败"） |
| 测试 | e2e 7 passed（新增根散件用例）；classifier 26 passed（测试改 `MagicMock(spec=QueryEngine)`，旧写法必红） |
| 回滚 | 还原折叠逻辑与两处属性名 |

### 34. 远程 825 文件真实批量（v0.182.0 部署实测）

| 项 | 内容 |
|---|---|
| 场景 | 2026-11-13 21:56–22:05，远程 826 文件/62 目录，首次启动补扫（部署前放入，无事件） |
| 结果 | 自动运行日志原值：`scan=809, query_found=796, download_success=0, organize_moved=204, organize_failed=0, mirror_skipped=0, fallback_mirrored=43`（成功 204 / 失败 0 / 兜底 43 / 解析失败 2、去重 9）；`/api/pending` 604 条 `chain_exhausted`；inbox 826→606；空目录 62→25；monitor processed=1/success=1/last_processed 有值；UNIQUE/locked/StandardManager 均 0；22:34 重启后 `启动补扫: 无待处理文件（watermark=…，跳过 605）` |
| 通知 | today notification_log 24→34：scan_complete 2、query_complete 2、替代失败聚合 8（每渠道一行） |
| 暴露 | 根目录 3 个散件触发祖先折叠 → 1 个超大批次（已修 `2e031a49`）；`classifier.resolve_replaces` 属性名错误导致替代补查全失败（同批修）；批量查询把站点链打空 → 604/809 `chain_exhausted`（下一轮查站点限流/适配器） |
| 结论 | 真实批量跑通、无 DB 竞争/多实例；"全部归档"未达成是 pipeline 语义（只归档 exact，其余待确认） |

### 35. P2-11 一次性修复脚本（dry-run 就绪）

| 项 | 内容 |
|---|---|
| 文件 | `scripts/repair_validity_keys_v2.py`、`tests/test_repair_validity_keys_v2.py` |
| 行为 | 默认 dry-run；`--apply` 先复制 `.bak-<ts>` 再写；5 条 TSG 合并（状态/检查时间/次数取优）、2 条 `manual_required`、可改名项 rename；幂等 |
| 验证 | 对远程备份 `remote_v76.bak` 实跑：**merge 5 / manual_required 2**；3 例测试（dry-run 不写、apply 备份+合并+幂等、计划分类） |
| 回滚 | 用 `--apply` 生成的 `.bak-<ts>` 还原 |

### 36. P2-10 批 3（query 19 + wechat_ip 5 + scan 4 = 28 条）

| 项 | 内容 |
|---|---|
| 文件 | `docs/debt/p2-10-silent-errors-triage.md`（仅文档，无代码变更） |
| 行为 | 28 条全部 allowlist：网络/解析/浏览器回退失败由上层结果暴露，逐条升 warning 会在批量查询刷屏；语法/编码由 ruff/G-047 兜底 |
| 测试 | G-050 基线保持 164（pass 46/return 48/debug 70），PASS |
| 回滚 | 不适用 |

### 37. P2-10 批 4（`pilotstd/ui/` 28 条，四批收官）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/ui/core/handlers/_cleanup.py`、`pilotstd/ui/pages/rules_page.py`、`scripts/silent_errors_baseline.json`、`docs/debt/p2-10-silent-errors-triage.md`、`tests/gui/test_ui_silent_errors_batch4.py` |
| 行为 | 28 条中 2 条升 warning：① `CleanupHandler.scan_empty_dirs` 扫描失败——原 debug 会让界面只显示"没有可清理目录"，像成功；② `RulesPage._get_rules` 的 `sites.rules` JSON 损坏——原静默返回 `[]`，用户再保存一次就把坏串覆盖成空表。其余 26 条 allowlist（Qt 对象已销毁/信号已断开、无权限子项逐条跳过、sip 不可用回退、退出路径），逐条理由见 triage §九 |
| 测试 | 新增 `tests/gui/test_ui_silent_errors_batch4.py` 2 passed（caplog 锁 WARNING + 返回值不变）；`tests/gui/test_cleanup_flow_engine.py` + `test_coverage_misc.py` 41 passed；G-050 基线 **164 → 162**（pass 46/return 47/debug 69）PASS；ruff 两文件 All checks passed |
| 回滚 | 两处改回 `logger.debug` / `return []` 并恢复基线对应项（`_cleanup.py:2`、`rules_page` return:1） |

### 38. P2-08 · G-054 GUI 单文件覆盖率棘轮（2026-11-14）

| 项 | 内容 |
|---|---|
| 文件 | `scripts/check_gui_coverage_ratchet.py`、`scripts/gui_coverage_baseline.json`、`tests/test_check_gui_coverage_ratchet.py`、`web/vite.config.ts`（reporter 加 `json-summary`）、`.github/workflows/ci.yml`（`test-frontend` 两步） |
| 行为 | 读 `web/coverage/coverage-summary.json`，对基线登记的前端**运行时**文件做"只降不升"（0.5pp 缓冲）：TaskView 74.56 / TaskHistoryList 9.09 / taskPipeline 87.5；`types.ts` 无执行行（0/0）列 `type_only`，只软提醒。**不发明固定阈值**（用户裁定）；上涨只提示收紧 |
| 测试 | `tests/test_check_gui_coverage_ratchet.py` 8 passed（等值/超缓冲下降/缓冲内下降/上涨提示/文件消失/type_only 软提醒/报告缺失 exit 2/Windows 绝对路径归一）；本地实跑覆盖率报告 PASS |
| 备注 | ① 超时**不全局放宽**：`NotificationConfig.test.ts` 的单个用例标 `30_000`（v8 插桩下该用例慢），其余恢复默认 5s；② 棘轮规则写死"提升覆盖率必须同 PR 收紧基线"，脚本在上涨时打印 `建议基线值 X.XX`；③ `type_only` 文件一旦出现可执行行即 FAIL（升格进棘轮或移出代码）；④ 基线文件消失 → 提示"同 PR 改路径，不加豁免"。`TaskProgress.vue`/`TaskManager.vue` 列为第二批候选（先确认是否落在同一失败/恢复分支） |
| 回滚 | 删 CI 两步 + 两个脚本/基线 + 还原 `vite.config.ts` reporter |
| 后续 | 2026-11-14 补 `TaskHistoryList.test.ts` 6 例（四状态/分页/详情-重跑-删除事件/英文 locale），行覆盖 **9.09% → 100%** 并同 PR 收紧基线；CI run `43584408939` **13/13 全绿**（含 `test-frontend` 的 G-054 步骤与 `repo-compliance` 的严格文档联动） |

### 39. G-052 第二阶段（计数声明全覆盖审计）+ 删除死组件 TaskProgress

| 项 | 内容 |
|---|---|
| 文件 | `scripts/audit_count_claims.py`、`scripts/count_claims_exempt.json`、`tests/test_audit_count_claims.py`、`scripts/check_all.sh`（`--fast` 接入）、`.github/workflows/ci.yml`（`repo-compliance` 步骤）、`web/src/components/TaskProgress.vue`（删除） |
| 行为 | ① 审计 `git log --since` 近 3 个月改动文档中**含计数类声明**的部分：命中必须登记在 `COUNT_CLAIMS`（数字由 G-052 校验）或在豁免表写明理由，空理由按违规；豁免过期给 WARN。分母只算"改动且含声明"，纯错别字改动不误伤；拿不到 git 历史降级 WARN。② 删除 `TaskProgress.vue`（全库无 import、0/3 行覆盖），P2-03 首次真删除 |
| 测试 | `tests/test_audit_count_claims.py` **9 passed**（含浅克隆：`--strict` 无历史 → exit 2；非 strict → WARN）；`tests/test_check_docs_drift_counts.py` 6 passed；审计实跑 221 篇改动文档 / **6 篇已登记** / 2 篇豁免 → PASS；前端 366 passed、build 通过 |
| 备注（评审加固） | ① `--strict` 下拿不到 git 历史直接 FAIL（exit 2），不再降级——`repo-compliance` 的 checkout 已确认 `fetch-depth: 0`；② 宽口径抽样 15 篇发现"`N 张`"写法未被原规则命中（文档实际把数字写在粗体里、后面只跟一个"张"字，原规则只认"张表"），已修正正则；③ 新增第 6 类"通知事件数"（`**N 个事件**`，由 `load_facts()["events"]` 核对，`16-notification-matrix.md` 登记）；④ 豁免表加 `review_due=2027-02-14` 季度复审；⑤ 顺带核实 `TaskProgress` 删除后 `git grep` 在 `web/src` **0 命中**；⑥ **全量证据（非抽样）**：按命中位置复跑 221 篇 × 6 类——18 处命中 / 11 处覆盖 / 6 处豁免 / **0 未登记** / 1 处无法机械核对（SQLite 实测表数），详见 `docs/records/2026-11-14-g052-count-claims-full-audit.md`；⑦ **G-052 一期封版**（6 类冻结、不主动找第 7 类）：7 条边界数字 1 条立项 A-43、6 条明确不做；⑧ **V-15 裁定接受**：隔离实测该用例仅 1.185s，30s 是全量并发下的余量（不是等真实定时器，fake timers 无效），理由与复审触发见 `docs/debt/02-accepted.md` §六 |
| 回滚 | 删审计脚本与豁免表、还原 `check_all.sh`/`ci.yml` 两处接线；`git revert` 恢复 `TaskProgress.vue` |

### 40. A-37 网络 e2e 显式开关 + C-6 pending 提示 i18n（2026-11-14）

| 项 | 内容 |
|---|---|
| 文件 | `tests/test_e2e_adapters.py`、`pilotstd/ui/core/handlers/_download.py`、`pilotstd/i18n/{zh_CN,en,zh_TW}.json` |
| 行为 | ① A-37：网络 e2e 从"CI 才跳过"改为"**显式开启才跑**"（`PILOTSTD_RUN_NETWORK_TESTS=1`），无外网的办公室/离线环境不再因真实站点打不通而误红；② C-6：pending 弹窗"另有 N 条因发布日期格式异常"从行内中文拼接迁入三语键 `download_skipped_bad_date`，删除 `i18n-allow` 豁免 |
| 测试 | `pytest tests/test_e2e_adapters.py` → **2 passed / 15 skipped**（默认全跳过网络用例）；`check_i18n_key_count` PASS（三语 947 键一致）、`check_i18n_hardcoded_python` PASS；ruff 通过 |
| 回滚 | 还原三语键与提示拼接、恢复 `@unittest.skipIf(_CI, …)` |

### 41. 技术债销账：V-1 / V-5 / V-12（2026-11-14）

| 项 | 内容 |
|---|---|
| 文件 | `docs/debt/04-watch.md`、`docs/debt/01-archive-closed.md`、`docs/technical-debt.md` |
| 行为 | 三条"观察中"经复核销账：V-1（T-16 严格模式）CI 早已 `--strict-block`；V-5/V-12（G-032 交叉引用）复跑只剩 4 条 warning，其中唯一"不存在引用"是 gates.md 版本历史行自述的历史死链，属该条目目标场景，无原文所称"10 处" |
| 验证 | `check_g_032_doc_health.py --guards` → 4 warning（与销账前一致）；`check_all --fast --guards --local` 全绿；观察中计数 16 → 13 |
| 回滚 | 从 01 删除该节并恢复 04-watch 三行 |

### 42. A-37 CI 缺口确认 + A-33 查证 + A-41 接受 + 多用户主线计划（2026-11-14）

| 项 | 内容 |
|---|---|
| 文件 | `scripts/run_local_e2e.sh`、`tests/test_e2e_adapters.py`、`docs/records/2026-11-14-a33-lazy-getters-audit.md`、`docs/plans/2026-11-14-multiuser-mainline.md`、`docs/debt/{02,03}`、`.github/PULL_REQUEST_TEMPLATE.md` |
| 行为 | ① **A-37 确认**：CI 不设置 `PILOTSTD_RUN_NETWORK_TESTS` ⇒ 网络 e2e **不在 CI 运行**（明确缺口，非静默跳过）；`run_local_e2e.sh` 内显式 export 变量，作为唯一手动入口；② **A-33 查证**（只读）：20 个 getter 来自 Initial commit `9256b383`，9 个仅被 `tests/test_query_init.py` 引用、11 个零引用；与 `registry.py` 的 22 个适配器**非一一对应**（缺 ahbz/dbba）；无动态/文档引用 ⇒ 按三分法归 ①（保留 + 注明勿新增），不满足 ②/③；③ **A-41 转接受**（不做 admin 跨用户视图，理由入 02-accepted）；④ **多用户主线**拆 P1（事件归属接线）/P2（队列聚合隔离）/P3（AC-6 验收），A-40/A-42 等枝节标"不阻塞主线"；⑤ **diff coverage 两步走**（先只报告不阻断，PR 模板写死"先补测试"） |
| 测试 | `pytest tests/test_e2e_adapters.py` → 2 passed / 15 skipped；文档门禁与 `check_all --ci` 全绿 |
| 回滚 | 还原 `run_local_e2e.sh` 的 export、删除两份新文档、恢复 A-41/A-42 原行 |

### 43. A-33 删除 + A-27.3 鉴权 e2e + V-4 销账 + 08 状态刷新（2026-11-14）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/query/__init__.py`、`tests/test_query_init.py`、`tests/test_notification_menu_api.py`（新增）、`.github/workflows/ci.yml`、`docs/onboarding/08-known-boundaries.md`、`docs/debt/{01,04}`、`docs/plans/2026-11-14-multiuser-mainline.md` |
| 行为 | ① **A-33 删除**：`query/__init__.py` 删 20 个 `_get_*_adapter`（140 行），留一句"适配器统一走 registry，勿再加 getter"；`test_query_init.py` 只保留顶层导出契约；CI 里对 `_get_mock_adapter` 的旧 grep 豁免同步移除。② **A-27.3**：新增菜单端点鉴权 e2e 9 例（无会话 401 / 普通用户 403 / admin 200 / 同步失败 400 / 缺参 422 / 非 admin 不触发 `sync_channel`）。③ **V-4 销账**：空库迁移探针复跑 `schema_version=76`、`error_records=0`，三条旧 `OperationalError` 不可复现。④ **08 状态刷新**：`#19`（CloakBrowser）、`#23`（monitor 补扫）从"待部署"改为"已部署验证"；`#23` 小节标题同步。⑤ 多用户计划 P1 的 A-40 口径收紧为"不阻塞判据、顺手可做、不为此中断" |
| 测试 | `pytest tests/test_notification_menu_api.py` → 9 passed；`pytest tests/test_query_init.py tests/test_query.py` → 84 passed；**全量 `pytest tests/ -q -n 8` → 6338 passed / 21 skipped / 0 failed（398s，exit 0）**；`--ci` 全绿 |
| 回滚 | 恢复 `query/__init__.py` 的 20 个 getter 与测试、删除新测试文件、恢复 08 两行与小节标题 |

### 44. 多用户主线 P1：事件归属接线（2026-11-14）

| 项 | 内容 |
|---|---|
| 文件 | `docker/api/_identity.py`（新增）、`docker/api/auto.py`、`docker/api/archive.py`、`tests/test_api_auto_archive_user_context.py`（新增）、`tests/test_api_identity_resolve.py`（新增）、`tests/test_api_scheduler_export_auto.py`（断言同步） |
| 行为 | `/api/auto`、`/api/archive` 调用 manager 时显式传 `NotificationContext(scope="admin", user_id=当前用户)`；此前不传 ⇒ 事件归 system(0)。当前用户由 `resolve_user_id(request)` 解析：优先中间件写入的 ContextVar，缺失时退回 JWT cookie 的 `sub`，**无法确定则 401，绝不返回 0** |
| 测试 | 新增 2 + 3 例：端点收到 `context.user_id==1 / log_user_id==1`（先红后绿）；`resolve_user_id` 三分支（ContextVar 优先 / cookie 兜底 / 无身份 401）。回归：`test_api_scheduler_export_auto.py`、`test_docker_api.py` 共 65 passed |
| DB 级判据 | 待真实双用户环境执行 SQL：`SELECT user_id,count(*) FROM notification_log WHERE event_type IN ('auto_pipeline_summary','archive_complete') AND date(sent_at)=date('now','localtime') GROUP BY user_id;` 期望两人各一行、无 0（见计划 P1） |
| 回滚 | 删 `_identity.py` 与两处调用、恢复原调用与测试断言 |

### 45. P3-16/P2-11 只读归因 + file_index 批量删除保护（2026-11-15）

| 项 | 内容 |
|---|---|
| 文件 | `docs/records/2026-11-15-p3-16-p2-11-attribution.md`（新增）、`pilotstd/core/file_index.py`、`tests/test_file_index_validation_guard.py`（新增）、`docs/testing/testing-baseline.md`、`docs/onboarding/08-known-boundaries.md`（#24）、`docs/debt/04-watch.md`（V-18）、`docs/architecture/modules/core.md` |
| 证据 | 远程 v0.187.0 只读：`app.log.3/.4` 的 `[NG]` 604（`tried=none` 445）、`[LO]` 160（全为空 match_status 的"未找到"哨兵）、冷却 0/配额耗尽 0/溢出失败 0、`[QUOTA]` 用量；`app.log.9` 2026-11-11 21:41:42 `清理 820 条失效记录`；11-09 备份 `file_index=820`（TSG 34）vs 线上 204（TSG 0）；本地 `RouterEngine` 探针（配额耗尽前后链长 4→0） |
| 结论 | P3-16：主因是 **v2 单次运行配额耗尽→空链 + 溢出 start=1 跳过主站**（445），其次 **"未找到"哨兵被误记 0 分 `[LO]`**（160），单站链无重试（159）；**不是补源/策略为主**。P2-11：`file_index` 的 TSG 行于 11-11 被启动校验批量删除（挂载未就绪），非归档遗漏/迁移/清理任务 → 线上只能 **0 merge / 7 manual**，恢复需数据决策 |
| 修复 | `validate_paths` 加批量删除保护（缺失 ≥90% 且 ≥50 行 → 跳过 + WARNING）；8 例回归（含 55 真/5 失、全失 60 行、小表仍清理）；`core.md`/`08` #24 回写 |
| 观测 | V-18：`query_metrics` 无法区分 chain_exhausted 原因（0 不落库），归因靠日志；待 P3-16 修代码时一并落键 |
| 未做 | P1 DB 级判据（触发 `/api/auto` 会重查 604 pending + 发通知，属生产写 → 未执行，评估见汇报）；P3-16 代码修复、P2-11 apply 均未动 |
| 测试 | 全量 **6381 collected / 6360 passed / 401 subtests / 21 skipped / 0 failed**（359s，exit 0）；`--ci` 全绿 |

---

## 验证汇总

| 检查 | 结果 |
|---|---|
| `pnpm run type-check` | 通过 |
| `pnpm run lint` | 0 errors，283 warnings（存量） |
| `pnpm test` | 352 passed |
| `pnpm run build` | 通过 |
| `pytest` 通知 + monitor 相关 | **69 passed** |
| `pytest tests/test_query.py` | **78 passed** |
| `pytest` 迁移链 + v74 | **135 passed** |
| `ruff` 改动 Python 文件 | 通过 |

---

## 未做

- 未部署到 Docker；
- 未改生产数据库；
- 未执行 709 条数据修复；
- 未改 monitor 的查询/下载/兜底、validity、缓存、v2；
- 未提交 git。

### 46. P2-11 文件核对 + P1 集成验证 + P3-16 语义修复（2026-11-15）

| 项 | 内容 |
|---|---|
| 文件 | `docs/records/2026-11-15-p3-16-p2-11-attribution.md`、`pilotstd/query/engine/{_overflow,_mini_bucket}.py`、`pilotstd/query/routing/router_v2.py`、`pilotstd/core/file_index.py`、`tests/test_p316_overflow_semantics.py`、`tests/test_p1_multiuser_integration.py`、`tests/test_file_index_validation_guard.py`、`docs/architecture/modules/query.md`、`docs/plans/2026-11-14-multiuser-mainline.md` |
| P2-11 第一步 | 11-09 备份 820 条索引逐条核对容器 `/standards`：**154 在**（18.8%）/ 494 文件名缺 / 172 父目录 404；**TSG 34 条全部父目录 404**。整类缺失：TSG、HG/T、JB/T、HG、API… ⇒ "文件大面积不在" |
| P2-11 新约束 | 直接恢复备份不可持久：666/820=81% < 90% 保护阈值，下次启动仍会被删；需"离线复算 + 一次性数据修复"或"重扫重建"，待授权/决策 |
| P1 集成 | 新增 `tests/test_p1_multiuser_integration.py` 3 例（真实 `NotificationManager` + 临时库 + 真实路由/中间件）：管理员 1 触发 auto → `user_id=1`；管理员 2 触发 archive → `user_id=2`；全表无 `user_id=0`。P1 状态：代码 + 集成完成，生产端到端待环境 |
| P3-16 修复 | ① "未找到"哨兵按 NG，不再计 `[LO]` 0 分（`_overflow`/`_mini_bucket`）；② `start` 只在主站确实尝试过时跳过；③ 单站链同站重试一次（`_retried` 上限）；④ 空链区分 `quota_exhausted`（v2 全站配额耗尽）与 `chain_exhausted`，指标分开计数；`QuotaManager.all_exhausted()` 支撑 |
| 测试 | `test_p316_overflow_semantics.py` 4 例、`test_p1_multiuser_integration.py` 3 例、`test_file_index_validation_guard.py` 8 例；相关 overflow/routing/query 66 例通过；全量与 `--ci` 见汇报 |
| 回滚 | 还原 4 个代码文件与 3 个测试文件、恢复记录/计划相应段落 |

---

## 验证汇总

### 47. P2-11 数据修复验证 + 根因修复 + TSG 文件查证（2026-11-15）

| 项 | 内容 |
|---|---|
| 文件 | `scripts/repair_validity_keys_v2.py`（新增 `--source validity`）、`pilotstd/core/std_utils.py`（`build_standard_number`/`CANONICAL_KEY_RE`）、`pilotstd/manager/facade/_organize.py`、`pilotstd/core/validity_checker.py`、`tests/test_p211_root_cause.py`（新增）、`tests/test_repair_validity_keys_v2.py`（+2 例）、归因记录 §五、`08` #25、`core.md`/`manager.md`、ISSUE_LEDGER P2-11 |
| 文件查证 | TSG 文件**未全丢**：`/inbox` 35 处（33 份在 `AQ 安全生产/TSG 特种设备安全技术规范/`）+ `/standards` 8 处（1 主文件 + 修改单）；`/output`、`/app/output` 0 ⇒ 不立"文件缺失"债务 |
| 数据修复 | 线上快照副本（`/query` 灌 819 行）实跑：**merge 5 / manual 2**；`--apply` 后 819→814、畸形 7→2、二次 dry-run 幂等；生产 apply **未执行**（待窗口） |
| 根因 | 归档时 `f"{logical_code} {number}"` 在代号为空时写出 `" 11-2020"`；`register_new_standard` 无校验直接落库，每轮复检复现（线上 `updated_at` 持续变化）。修复：`build_standard_number` 空代号返回空串、归档从文件名补解析、仍无则跳过、`register` 增加规范键守卫 |
| 测试 | `tests/test_p211_root_cause.py` 10 例通过；`test_repair_validity_keys_v2.py` 5 例通过；全量与 `--ci` 见汇报 |
| 回滚 | 还原脚本 `--source` 分支与三个代码文件、删两个测试文件、恢复文档段落 |

---

## 验证汇总

### 48. P2-11 生产 apply + 33 份 TSG 归档 + 合订本解析根因（2026-11-15）

| 项 | 内容 |
|---|---|
| 文件 | `pilotstd/core/std_utils.py`（合订本归一 + TSG 前缀解析）、`tests/test_p211_root_cause.py`（+2 例）、归因记录 §六~§八、ISSUE_LEDGER P2-11、多用户计划 P1 |
| P2-11 apply | 备份 `pilotstd_manual_20261115_123510.bak` → `/query` 逐条 merge：819→**814**、distinct=814、畸形 7→**2**；integrity ok；FK 4 条与 11-09 备份一致（既有、非本次）；二次 dry-run 仅 2 manual |
| TSG 归档 | 33/33 解析成功（含 `TSG Z8002` 前缀修复）；`POST /api/archive` **moved 33 / failed 0 / conflict 0**；inbox 0 剩、standards 33 份、file_index TSG 0→33（总 204→237） |
| P1 生产验证 | 归档后 `notification_log` 新增 `batch_summary` 两行，`user_id=1`（触发人）、无 0 ⇒ P1 生产端到端验证通过 |
| 47008-1947 根因 | `bddc6943`（2026-08-20）的合订本归一只落在 scan `TextCleaner`，`parse_std_number` 未覆盖；归档/validity 路径直取 1947 当年份。已在 `parse_std_number` 入口补同一归一，并补 TSG 字母前缀通道 |
| 未决 | 2 条 manual 键保留（` 19001-2020`/` 47008-1947`），待裁定删除或标记 |
| 测试 | 新增/修改后 `test_p211_root_cause.py` 12 例、`test_std_utils.py` 全通过；全量与 `--ci` 见汇报 |

---

## 验证汇总

### 49. 62 批目的/补扫并发/试投放定位 + monitor 实时缺陷挂账（2026-11-15）

| 项 | 内容 |
|---|---|
| 文件 | `docs/records/2026-11-15-p3-16-p2-11-attribution.md`（§十一 实时路径证据）、`docs/debt/03-open.md`（A-44）、`docs/onboarding/08-known-boundaries.md`（#26）、`docs/technical-debt.md`（计数） |
| 目的判定 | 62 批/825 是**本地压测**，远程从未跑过（远程 11-13 补扫仅 1 目录/3 文件，809 文件是 API 触发）；**建议先做 3~5 目录的小场景**验证 `2e031a49` 分批语义，825 全量作为压力测试单独评估（预期与 11-13 同：配额耗尽、604 chain_exhausted，无新信息） |
| 并发结论 | **串行**：`_process_catchup_batches` 逐目录 `for`，每批 `_on_file` **同步**调 `auto_run(dir)`，目录间 `CATCHUP_INTERVAL_SECONDS=1.0s`（`scheduler.py:261-286`、`:101`、`:376`）；不存在并发全扫。restart 方案可行；但配额是跨目录累计消耗，825 仍会像 11-13 一样耗尽站点 |
| 分批语义证据 | 本地 `tests/integration/test_monitor_catchup_e2e.py` **7 passed**（嵌套目录祖先折叠、根散件最后单独一批、watermark 跳过旧文件、stop 打断） |
| 试投放 | 需宿主执行（我只有 API，无投放/改 mtime 通道）：放 1 文件到新孙目录 → `LastWriteTime=now` → 先等 15s 看 `检测到新文件`（预期无）→ `docker compose restart app` → 看 `启动补扫开始: 1 目录 / 1 文件`（预期有） |
| monitor 缺陷 | **A-44 / 08#26**：Windows bind mount 下 inotify 不传播，实时路径实际未工作；修复选项 PollingObserver / named volume / 文档写明仅 restart 补扫；**挂待办，不现在修**，与 62 批并行不互为前置 |
| 测试 | 监控 e2e 7 例通过；文档门禁 `--fast --guards --local` 见汇报 |

---

## 验证汇总

### 50. 三批移入复盘 + P1 pending 核销修复/回填 + 216 残留查证 + 实时路径规则（2026-11-15）

| 项 | 内容 |
|---|---|
| 口径 | 以 **572 事件 / 22 批 / 扫描 572 / 搬移 355** 为准（此前 413/10/530/317 是 19:06:42 后中间观察，已废弃） |
| P1 修复 | `_organize._resolve_archived_pending`：归档成功（源文件已不在）后按 `build_standard_number` 同键把 pending 置 `resolved`；新增 2 例测试（归档核销/源仍在不核销） |
| 历史回填 | 线上按 `file_index` 精确同键回填 **387 条** → `pending` 605→217；另补 `TSG Z8002-2022` 1 条（Z 前缀格式不匹配）→ 现在 pending **217**、resolved **388** |
| 216 残留 | 216 个非杂项文件全部未进 `file_index`；与 pending 一一对应（pending 217 = 216 + 孤儿 `GB 31422.1-2025`）；`skipped_exists/conflict_pending` 历史未落日志，需下批按新日志细分 |
| P3 补日志 | `_auto_run_impl` 新增 `归档明细: moved/failed/skipped_exists/conflict_pending/skipped_source/dedup_skipped` |
| 实时规则 | 572 文件写入既有目录 → 全部触发；12:29 后新建 TSG 目录 → 零触发。推断：recursive watch 只对启动时既有目录建 watch，新子目录依赖目录创建事件补 watch（Windows bind mount 未送达）。**结论：新目录必须 restart 补扫；旧目录可实时**（A-44/08#26 已更新） |
| mtime 硬前置 | API 读不到 inbox mtime（`/api/files`/`scan` 只回 size）；216 若 mtime>watermark 则下次 restart 会重扫，需宿主 `Get-ChildItem` 确认；确认前 62 批全量不投 |
| 测试 | 全量见汇报；`test_p211_root_cause.py` 14 例（含 2 例核销） |

---

## 验证汇总

### 51. M1 工具代码：mtime / 受控投放端点 / Z 前缀 / no_result / 冲突超时（2026-11-15）

| 项 | 内容 |
|---|---|
| #1 mtime | `DirItem` 增 `mtime: float`（epoch），`/api/files` 对文件回 `st_mtime`（目录 0）；只读、不改旧字段 |
| #2 受控端点 | 新增 `POST /api/admin/replay-stage`（`docker/api/replay_stage.py`）：默认关（`PILOTSTD_ENABLE_REPLAY_STAGE=1` 才开），仅 copy/move，目标限 `/inbox/__replay_*` 与 `/inbox/_quarantine`，源限 `/inbox`、`/standards`，realpath 校验、逐条错误、写 `REPLAY_STAGE` 审计、单次 ≤2000 |
| #3 Z 前缀 | `build_standard_number` 增 `num_prefix`（`TSG Z8002-2022`）；归档核销“同键 + 带前缀变体”双试；回归覆盖 Z/无前缀/带前缀 |
| #4 no_result | 查询 NG（None/未找到哨兵）时 `no_result` +1，与 `quota_exhausted`/`chain_exhausted` 并列；V-18 可关 |
| #5 冲突超时 | `26-fix-dossiers.md` D-04：30 天未处理视为过期、置 resolved + `expired_conflict` 备注、运维责任；本批不做定时任务 |
| 测试 | `test_p211_root_cause.py` 16 例、`test_p316_overflow_semantics.py` 4 例（含 no_result 断言）；全量与 `--ci` 见汇报 |
| 待部署 | #1/#2 随镜像部署后，才能做 #6~#10（mtime 查证、216 处置、小场景、P3-16 生产验证） |

---

## 验证汇总

### 52. M1 工具修正：去掉 env 开关 + 服务端补扫触发（2026-11-15）

| 项 | 内容 |
|---|---|
| #2 端点 | `/api/admin/replay-stage` 去掉 `PILOTSTD_ENABLE_REPLAY_STAGE` 开关，直接可用；安全边界仍为 admin + realpath + `/inbox/__replay_*`/`_quarantine` 白名单 + 逐条审计 |
| 补扫触发 | 新增 `POST /api/admin/monitor/catchup`（admin + `MONITOR_CATCHUP_TRIGGER` 审计）；`FileMonitorScheduler.trigger_catchup()` 起一个 `monitor-catchup-manual` 线程，已在跑时返回 `started=False` 不排队 |
| watermark 语义 | 补扫完成时仍把 watermark 设为 `scan_started`（不是完成时间）：补扫期间新写入的 mtime 更晚，下次仍会处理，**不会把新文件推前跳过**；与实时 monitor 共用 `_on_file` 目录去重（`_active_dirs`/`_recent_dirs`），同目录不会被两条路径重复处理 |
| 测试 | replay 端点改为“默认可用 + 源缺失逐条 ok=False”；新增 catchup API 2 例、scheduler trigger 2 例（未运行/启动+并发拒绝）；`test_monitor_scheduler.py` 共 27 例通过 |
| 文档计数 | 唯一 API 路径 125→126、route×method 141→142（03/19/20 已同步） |

### 53. 小场景补扫暴露的两个 monitor 缺陷（2026-11-15，已修）

| 缺陷 | 现象 | 修复 |
|---|---|---|
| 折叠计数少算 | `/inbox/__replay_small` 的 a 与 a/nested 折叠后日志报 `3 目录 / 4 文件`（应为 5），`1/3: a（1 文件）` 少算子目录文件 | 新增 `_count_catchup_files(groups, kept)`：按 kept 祖先汇总其自身+后代文件数；总览与逐目录日志都用它 |
| 祖先/后代重复处理 | 补扫 `a` 批递归覆盖 `a/nested` 时，nested 的实时事件又自己触发一次（生产日志 21:47:12 补扫 a / 21:47:17 nested 单独处理） | `_on_file` 增加 `_covered_by_ancestor()`：路径在正在跑或 10s 内跑过的祖先目录下 → 跳过；同一目录去重逻辑保留 |
| 附带发现 | 生产 `organize.auto_clean_source=true`，`skipped_exists` 会删除源文件（小场景 5 个副本处理后被自动清理，属预期配置） | 不改配置，记录到边界（复制件不会残留） |

验证：`test_monitor_scheduler.py` + `test_monitor_catchup_e2e.py` 共 29 例通过；全量与 `--ci` 见汇报。

### 54. `_quarantine` 移出 watch 根：`/inbox/_quarantine` → `/data/_quarantine`（2026-11-16）

- 根因：`/inbox/_quarantine` 在 monitor 的 `/inbox` 递归 watch 内，移入的文件被实时重新处理
  （11-15 216 个隔离文件里 183 个被二次处理：`file_index` 592→773、`pending` 216→35）。
- 代码：`docker/api/replay_stage.py` 的目标白名单 `_DST_EXACT` 改为 `/data/_quarantine`
  （`/inbox/__replay_*` 不变）；路径比较统一 POSIX（去盘符），Windows 单测可跑。
- 迁移：`C:\Temp\move_quarantine_to_data.py`（清单 `C:\Temp\move_quarantine_manifest.json`、
  回滚 `C:\Temp/rollback_quarantine_to_inbox.py`），v0.190.3 部署后执行 33 个文件移位。
- 测试：`test_api_replay_stage.py` 6 例（新增 `/data/_quarantine` 正例）；`--ci` 见汇报。

### 55. M2：A-40 归属结论 + P2 双用户隔离修复（2026-11-16）

| 项 | 内容 |
|---|---|
| A-40 证据 | `notification_log`：user0=1908、user1=543（541 条 `sent_at<2026-11-14`，2 条 11-15 真实用户）、user5=2；`notification_queue`：user1=147（137 条 <11-14）。⇒ v71 回填的“存量 user1”可按 **sent_at/created_at < 2026-11-14** 界定；多用户上线后新数据由 P1 context 正确归属 |
| A-40 结论 | **接受现状、不回溯**：历史 541 日志 + 137 队列行保留 user1，不做迁移/标记列；新数据可区分（user0 系统 / user1..N 真实）。依据：单用户升级期无第二用户，回溯无法可靠拆分 |
| P2 缺陷 1 | 静音队列 `user_id or 1` 把 system(0) 写成 1 → 改为原值入库（0 保留） |
| P2 缺陷 2 | 聚合键无用户维度，user1/user2/system 合并 → 键加 `u{origin}`（批次 `1·uN·batch·notify`、常规 `2·notify[·entity]·uN`、daily 同）；system 自成 u0，不与 user1 混 |
| P2 缺陷 3 | `_QUEUE_MESSAGE_FIELDS` 漏 `delivery_user_id`，补发回退 host._user_id（默认 1）→ 加入白名单，补发按队列 owner 选渠道 |
| 测试 | 新增 `tests/test_p2_notification_isolation.py` 3 例（队列归属/system=0、聚合不跨用户、补发路由）；相关回归 64 例通过；全量与 `--ci` 见汇报 |
### 56. M3 鍓嶇疆锛氬疄鏃舵姠鍗犳満鍒躲€乹uarantine 杩佺Щ銆丄C-6 闆嗘垚锛?026-11-16锛?
| 椤?| 鍐呭 |
|---|---|
| quarantine 杩佺Щ | v0.190.3 閮ㄧ讲鍚庢墽琛?`move_quarantine_to_data.py`锛?3 涓枃浠?move 鍒?`/data/_quarantine`锛宱k=33/failed=0锛沗/inbox/_quarantine` 宸茬┖锛沗file_index` 773 涓嶅彉銆乸ending 35/resolved 570 涓嶅彉锛涙竻鍗?`move_quarantine_manifest.json`銆佸洖婊?`rollback_quarantine_to_inbox.py` |
| 62 鎵圭 4 鏉″墠缃紙瀹炴椂鎶㈠崰锛?| **鏈哄埗锛歴top 鈫?鎶曟斁 鈫?catchup 鈫?start**銆俙POST /api/monitor/stop` 鍋?observer锛坔andler 淇濈暀锛夛紱`POST /api/admin/replay-stage` 鎶曟斁锛沗POST /api/admin/monitor/catchup` 鍦?monitor 鍋滄鐘舵€佷笅涔熷彲瑙﹀彂锛坄trigger_catchup` 浠呭湪 `handler is None` 鏃舵嫆缁濓級锛涜窇瀹?`POST /api/monitor/start` 鎭㈠瀹炴椂銆傛鏃跺彧浼氳蛋 `_collapse_catchup_dirs` 琛ユ壂鍒嗘壒锛屼笉浼氳瀹炴椂鎶㈣窇 |
| AC-6 闆嗘垚娴嬭瘯 | 鏂板 `tests/test_ac6_notification_isolation.py` 3 渚嬶細鍙岀敤鎴峰悇鍙湅鑷繁閫氱煡锛泆ser1 鏍囪宸茶涓嶅奖鍝?user2 鏈鏁帮紱user2 鏃犳硶鏍囪 user1 鐨勯€氱煡锛?03/404锛夆€斺€斿叏閮ㄩ€氳繃 |
| A-40 | 鎶€鏈彛寰勪笉鍙橈紙瀛橀噺鎸?11-14 鍓嶇晫瀹氾級锛岀姸鎬佹敼涓?*寰呰€佹澘纭锛堜骇鍝佸喅绛栵級**锛屼笉鏍囧凡瀹屾垚 |
| 寰呭姙 | v0.190.4 閮ㄧ讲鍚庢寜 stop鈫抍atchup鈫抯tart 娴佺▼鍋氫竴娆?62 鎵瑰墠缃紨缁冿紙鍙€夛級锛汳3 鐢熶骇绔埌绔緟绗簩璐﹀彿瀵嗙爜/绐楀彛纭 |


M3 前置（补）：AC-6 集成 3 例、离线补扫（stop 后 catchup）1 例；全量 6425/6404。
### 57. M3 鏀跺彛鍓嶇疆锛欰-40 璁㈡銆丠J 婧愮櫧鍚嶅崟銆丄C-6 鐢熶骇缂哄彛锛?026-11-16锛?
| 椤?| 鍐呭 |
|---|---|
| v71 鏃堕棿 | 鎻愪氦 `874aae24`锛?026-10-31 19:17:58 +0800锛涜縼绉绘妸涓よ〃 user_id 鍔犲垪骞跺洖濉?1 |
| 杩佺Щ鍓嶆潵婧?| 浠ｇ爜鍐欑偣锛歚docker/scheduler.py`銆乣pilotstd/announce/notifier.py`銆乣validity_checker`銆乣_auto.py`銆乣_organize.py`銆乣_scan.py`銆乣security_notifier`銆乣docker/api/*`銆備簨浠剁被鍨嬫贩鏉傦細`task_result/daily/security_alert/announcement_*/notification_delivery_failed/anomaly_alert` 涓虹郴缁燂紱`test/notification_credential_changed` 鏄庣‘鐢ㄦ埛鍔ㄤ綔锛沗archive_complete/batch_summary/scan_*` 鍙屾潵婧愶紙UI 涓?monitor 鑷姩锛?|
| 鍗曠敤鎴锋椂浠ｇ敤鎴?| 浠?`mystdpilot`锛坕d=1锛宎dmin锛?026-07-02 鍒涘缓锛夛紱`a35_user2` 2026-11-02 鎵嶅缓 |
| 璁㈡ | 澶囦唤 `pilotstd_manual_20261116_203411.bak`锛沵anifest `C:\Temp\a40_correction_ids.json`锛況ollback `C:\Temp\a40_rollback.sql`锛沗notification_log` **452 琛?* `user_id 1鈫?`锛坄sent_at < 2026-10-31T19:17:58` 涓旀帓闄?test/credential_changed锛夛紱鏍稿鍚?user0=2364銆乽ser1=91銆乽ser5=2锛沺re-v71 浠呭墿 `test` 2 + `notification_credential_changed` 4 淇濇寔 1 |
| queue | **鏈敼**锛歚notification_queue.user_id` 璇箟鏄€滈潤闊宠ˉ鍙戞敹浠朵汉鈥濓紝鍘嗗彶鍞竴鐢ㄦ埛鍗?id=1锛涙敼鎴?0 浼氱牬鍧忚ˉ鍙戣矾鐢憋紙鎶ュ憡鍙ｅ緞锛?|
| 娈嬩綑 | 2026-10-31~11-14 鐨?89 琛屼粛鏄?user1锛坴71 鍚庨粯璁ゅ€笺€丳1 context 鍓嶏級锛涙寜鑰佹澘鈥滄棭浜庤縼绉绘棩鈥濆彛寰勬湭鍔紝寰呭喅 |
| HJ 536 | `replay-stage` 婧愮櫧鍚嶅崟鍔?`/data/_quarantine`锛涙祴璇?7 渚嬮€氳繃锛泇0.191.1 閮ㄧ讲鍚庡彲 `move` 鍒?`/inbox/__replay_hj536/` 鍐嶅綊妗ｃ€乸ending 鑷姩鏍搁攢 |
| AC-6 鐢熶骇缂哄彛 | 涓存椂鐢ㄦ埛 `add_user` 寮哄埗闄嶇骇 user锛坄_determine_role`锛夛紝`test-event` 403锛涙櫘閫氱敤鎴锋棤榛樿閫氱煡绛栫暐/娓犻亾锛屾敹钘忎簨浠朵笉钀介€氱煡锛沗DELETE /api/users` 鍦ㄧ敤鎴锋湁鏀惰棌鏃?FK 500锛堥渶鍏堟竻 favorites/log/queue锛夈€傜敓浜?e2e 闇€绗簩鐪熷疄 admin 鎴栬ˉ浜у搧鑳藉姏 |

