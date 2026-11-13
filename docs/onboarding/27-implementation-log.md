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
| 测试 | 新增 e2e 6 例（启动前放文件→归档、祖先折叠、watermark、禁用、stop 打断、last_processed）；monitor 相关 94 passed；本地 825 文件压测：62 批 / 825 搬移 / 0 UNIQUE / 0 locked / inbox 清空 |
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
