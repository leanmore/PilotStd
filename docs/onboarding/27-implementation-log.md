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
### 56. M3 前置：实时抢占机制、quarantine 迁移、AC-6 集成（2026-11-16）

| 项 | 内容 |
|---|---|
| quarantine 迁移 | v0.190.3 部署后执行 `move_quarantine_to_data.py`：33 个文件 move 到 `/data/_quarantine`，ok=33/failed=0；`/inbox/_quarantine` 已空；`file_index` 773 不变、pending 35/resolved 570 不变；清单 `move_quarantine_manifest.json`、回滚 `rollback_quarantine_to_inbox.py` |
| 62 批第 4 条前置（实时抢占） | **机制：stop → 投放 → catchup → start**。`POST /api/monitor/stop` 停 observer（handler 保留）；`POST /api/admin/replay-stage` 投放；`POST /api/admin/monitor/catchup` 在 monitor 停止状态下也可触发（`trigger_catchup` 仅在 `handler is None` 时拒绝）；跑完 `POST /api/monitor/start` 恢复实时。此时只会走 `_collapse_catchup_dirs` 补扫分批，不会被实时抢跑 |
| AC-6 集成测试 | 新增 `tests/test_ac6_notification_isolation.py` 3 例：双用户各只看自己通知；user1 标记已读不影响 user2 未读数；user2 无法标记 user1 的通知（403/404）——全部通过 |
| A-40 | 技术口径不变（存量按 11-14 前界定），状态改为**待老板确认（产品决策）**，不标已完成 |
| 待办 | v0.190.4 部署后按 stop→catchup→start 流程做一次 62 批前置演练（可选）；M3 生产端到端待第二账号密码/窗口确认 |

### 57. M3 收口前置：A-40 订正、HJ 源白名单、AC-6 生产缺口（2026-11-16）

| 项 | 内容 |
|---|---|
| v71 时间 | 提交 `874aae24`，2026-10-31 19:17:58 +0800；迁移把两表 user_id 加列并回填 1 |
| 迁移前来源 | 代码写点：`docker/scheduler.py`、`pilotstd/announce/notifier.py`、`validity_checker`、`_auto.py`、`_organize.py`、`_scan.py`、`security_notifier`、`docker/api/*`。事件类型混杂：`task_result/daily/security_alert/announcement_*/notification_delivery_failed/anomaly_alert` 为系统；`test/notification_credential_changed` 明确用户动作；`archive_complete/batch_summary/scan_*` 双来源（UI 与 monitor 自动） |
| 单用户时代用户 | 仅 `mystdpilot`（id=1，admin，2026-07-02 创建）；`a35_user2` 2026-11-02 才建 |
| 订正 | 备份 `pilotstd_manual_20261116_203411.bak`；manifest `C:\Temp\a40_correction_ids.json`；rollback `C:\Temp\a40_rollback.sql`；`notification_log` **452 行** `user_id 1→0`（`sent_at < 2026-10-31T19:17:58` 且排除 test/credential_changed）；核对后 user0=2364、user1=91、user5=2；pre-v71 仅剩 `test` 2 + `notification_credential_changed` 4 保持 1 |
| queue | **未改**：`notification_queue.user_id` 语义是“静音补发收件人”，历史唯一用户即 id=1；改成 0 会破坏补发路由（报告口径） |
| 残余 | 2026-10-31~11-14 的 89 行仍是 user1（v71 后默认值、P1 context 前）；按老板“早于迁移日”口径未动，待决 |
| HJ 536 | `replay-stage` 源白名单加 `/data/_quarantine`；测试 7 例通过；v0.191.1 部署后可 `move` 到 `/inbox/__replay_hj536/` 再归档、pending 自动核销 |
| AC-6 生产缺口 | 临时用户 `add_user` 强制降级 user（`_determine_role`），`test-event` 403；普通用户无默认通知策略/渠道，收藏事件不落通知；`DELETE /api/users` 在用户有收藏时 FK 500（需先清 favorites/log/queue）。生产 e2e 需第二真实 admin 或补产品能力 |

### 58. 事故与修正：`/data/_quarantine` 未挂载，33 个隔离文件随 v0.191.1 重启丢失（2026-11-16）

| 项 | 内容 |
|---|---|
| 起因 | 11-16 19:4x 把 33 个文件从 `/inbox/_quarantine` 移到 `/data/_quarantine`。compose 只挂载 `./data:/app/data`、`./inbox`、`./standards`，**`/data` 是容器临时层** |
| 后果 | v0.191.1 部署重建容器 → `/data/_quarantine` 清空，33 个文件（含 `HJ 536-2009`）丢失；宿主无副本、DB 无文件、`file_index` 无记录 |
| 清单 | 33 条路径见 `C:\Temp\move_quarantine_manifest.json`（`target` 字段即丢失位置） |
| 修正 | `replay-stage` 的隔离路径改为 **`/app/data/_quarantine`**（`./data:/app/data` 已挂载，持久化）；源/目标白名单同步；测试 7 例通过 |
| 待做 | 依据清单评估可重新下载的条目（下载链/公告记录）；`HJ 536-2009` 的 exact pending 因文件丢失暂不能归档，待补文件 |
| 教训 | 写路径必须先对照 compose 挂载；“API 化”不等于“持久化”，测试工具的目标路径必须在持久卷内 |

### 59. M3 包：A1 缺失核查、A2 残余订正、A3 62 批演练、B AC-6 借渠道（2026-11-16）

| 项 | 内容 |
|---|---|
| A1 | 33 个文件（manifest `C:\Temp\move_quarantine_manifest.json`）：`file_index` 0 命中、`/standards` 树按文件名 0 命中 → **33/33 缺失**；已在 pending 置 `reason='file_missing'`（33 条，状态仍 pending，不伪装关闭）；清单 `C:\Temp\a1_missing.json`；`HJ 536-2009` 同列缺失 |
| A2 | 10-31~11-14 的 89 行：系统类 **67 行** user1→0（`security_alert/delivery_failed/task_result/daily/scan_empty/announcement_*/auto_backup/anomaly_alert`），条件含 `id <= 4415`（本批前最大 id，排除新行）；用户类保留：archive 10 / scan 2 / test 4 / credential 4；备份 `pilotstd_manual_20261116_212910.bak`，manifest `C:\Temp\a40_residual_ids.json`、rollback `C:\Temp\a40_residual_rollback.sql`；核对 user0=2437、user1=24、user5=2；queue 未动 |
| A3 | 62 批演练：`stop`（running=False）→ `replay-stage` 投放 5 文件 → `catchup` → `启动补扫开始 3 目录 / 5 文件`、1/3 a（2 文件）、2/3 b（1）、3/3 c（2）→ `start` 恢复 running=True；无实时抢跑 |
| B1 | 无现有 API 可给他人挂渠道/策略（`/api/notification/policy` 仅当前用户；渠道是全局配置）⇒ **代码改动**：`/api/notification/test-event` 增加 `target_user_id`（仅 admin），复用 `channels_for(target)` 与既有渠道，不新建渠道/策略；非 admin 403 |
| B2 | `replay-stage` 源/目标白名单已是 `/app/data/_quarantine`（持久卷）；A1 无需取回（文件已缺失），保留以备恢复 |
| B3 | 本批代码：`docker/api/notification.py`（target_user_id）、`tests/test_notification_test_event.py`（+2 例）；`replay_stage.py` 路径 `/app/data` |
| 部署 | v0.191.2 已部署；本批代码待 v0.191.3 |

### 60. AC-6 生产验证（读隔离）+ A1 /inbox 补查 + test-event 审计（2026-11-17）

| 项 | 内容 |
|---|---|
| 部署 | 生产 v0.192.0（`/api/system/version` 确认） |
| AC-6 | 临时用户 23：DB 种一条 `notification_log(user_id=23, channel=web)` 站内通知 → 该用户 `logs=1`、`unread=1` → 标记已读后 `unread=0`；同一行未出现在 admin(user1) 的日志中；清理（log/queue/favorites→DELETE 用户）后用户列表仅 `mystdpilot`、`a35_user2`；结果 **PASS（读/已读/隔离/清理）** |
| 触发段说明 | 生产渠道仅 wechat/dingtalk/feishu/telegram 且 wechat/telegram 启用，`test-event` 会**真实外发**；无 dry-run 渠道，故触发段用受控 DB 种子行代替（归属触发链已由 P1 生产验证）。`target_user_id` 代码已上线，但 `web` 不是合法渠道名 → 该端点无法用于站内通知播种 |
| A1 补查 | 33 个文件名在 `/inbox` 递归匹配 **0 命中**，与 `file_index`/`/standards` 一致 → 33/33 `file_missing` 维持 |
| B 审计 | `/api/notification/test-event` 的 `target_user_id` 分支写 `write_audit(action=NOTIFICATION_TEST_TARGET, detail={target_user_id, channel})`；审计失败仅告警不影响发送；测试 +1 例（共 7 例通过） |
| 62 批 | 四条前置全绿：v0.191.2+ 已部署、`/app/data/_quarantine` 持久卷、每目录 ≤30、stop→catchup→start 演练通过；仍不投 |


### 61. M3 关闭确认（精确口径）与遗留定触发（2026-11-17）

- **AC-6 验收口径**：**读/已读/隔离/清理 PASS**（临时用户 23：仅见自己、已读后未读 0、admin 不可见、按 FK 清理后删除）；**触发链路归属由 P1 生产验证**（33 份 TSG 归档 → `batch_summary user_id=1`），不由本轮重复验证。集成测试 3 例 + 生产读隔离证据归档于本记录。
- 遗留 1：无 dry-run/站内渠道 → `03-open` **A-45**，触发：新增渠道系统或 AC-6 复验触发链路。
- 遗留 2：33 个文件缺失 → `03-open` **A-46**，触发：公告记录/下载链可重取；pending 保持 `file_missing`。
- 遗留 3：v0.192.1 审计 patch 已推 + CI 绿，随下次部署，不单独发版。
- 62 批：缩小版（10 目录 / 202 文件）见下节；825 全量不做。
### 62. 62 批缩小版：10 目录 / 202 文件（2026-11-17）

| 项 | 结果 |
|---|---|
| 形态 | `/inbox/__replay_b62/d01..d10`，每目录 20 文件；d01 另含 `nested/` 2 文件，共 **202** |
| 分批 | `启动补扫开始: 10 目录 / 202 文件`；10 批 serial：d01（22 文件，nested 折叠进 d01）、d02..d10（各 20）；完成 `10 目录 / 202 文件` |
| 折叠 | 正确：d01 与 d01/nested 只产生 **1 批**；无根目录批次（不在 `/inbox` 根投放） |
| 归档 | `moved=12`、`skipped_exists=160`（副本来自 standards，目标已存在；`auto_clean_source` 清理副本）、`conflict_pending=0`、`failed=0` |
| 查询 | `scan=200`、`query_found=172`；另有 28 条无结果转入 pending |
| 差异说明 | d01 日志 22 文件但 auto `scan=20`：其中 2 个是 `d01/nested` 副本，父批次处理时由 `auto_clean_source` 清理，原始文件仍在 `/standards` —— **预期行为，非待查项** |
| 失败/不重试 | 无硬失败；30 个残留（28 pending + 2 未扫到）留原地，catchup 一次性结束、未重试；演练后已将 30 个副本移 `/app/data/_quarantine/__replay_b62` 清理 |
| 指标 | `no_result=189`、`quota_exhausted=0`、`chain_exhausted=0`；但 28 条 pending 的 `match_status=''`、`chain_exhausted=0` → **P3-16 三指标分流不完整**：无结果转 pending 时未记 `chain_exhausted`（A-47，查询线） |
| 825 结论 | **不做全量**：缩小版已覆盖多目录分批/折叠/根批次/失败留原地；全量只会重复配额耗尽与同类 pending，信息增量极低 |


### 63. A-47 分类修复、pending 重查、健康检查、数据卫生（2026-11-17）

| 项 | 内容 |
|---|---|
| A-47 修复 | `_batch_dispatcher._finalize_batch` 对无结果条目的默认结果改为 `status=pending`、`match_status='chain_exhausted'`，并按缺失条数 +`chain_exhausted` 指标（`pending_fallback_result` 单测锁定） |
| pending 重查 | 实际 pending 61 条（33 `file_missing` + 28 空分类），非 34：`POST /api/query` 全量重查 61 条（35.7s）→ found 1、not_found 60；结果分类 59 `chain_exhausted` + 1 `exact` + 1 空 → 存量基本仍 no_result（预期，配额/站点覆盖），修复后新批次分类可正确落 chain_exhausted |
| P2-08 | 已有：`test_organize_stream_exception_counts_failed`（失败计数）、`test_archive_resolves_pending_by_canonical_key`（归档恢复核销）、`skipped_source/conflict_pending` 用例；结论：失败/恢复分支已覆盖，无需新增 |
| 健康检查 | 新增 `pilotstd/query/health_probe.py`（21 站固定探针，found/no_result/error + 耗时，JSON 结构化日志 + `/app/data/health_probe.json`）；API `GET /api/adapters/health`、`POST /api/adapters/health/run`（admin）；调度 `adapter_health` 每小时（默认启用）；测试 2 例；全量 **6428 collected / 6407 passed / 401 subtests / 21 skipped / 0 failed**；`--ci` 全绿 |
| user5 | 2 条 `notification_log`（11-03 收藏，channel wechat/telegram）已删，manifest `C:\Temp\user5_ids.json` |
| a35_user2 | 3 收藏 + 3 favorite_downloads 清理后删除用户（id=3）；users 现仅 `mystdpilot`；清单 `C:\Temp\a35_user2_data.json`；执行前备份 |
| 33 文件 | 扫全部挂载点（`/inbox`、`/standards`、`output`、`data`、`logs`）**0 命中** → 维持 `file_missing` |
| A-44 用户文档 | 08 仅开发侧；已在 `docs/guides/用户帮助文档.md` 增加“文件监控的已知限制”（新目录→重启补扫、批量 ≤30/目录） |


### 64. a35_user2 查证、探针校准、61 重查可信度、pending 对账（2026-11-17）

| 项 | 结论 |
|---|---|
| a35_user2 来源 | `audit_logs`：2026-11-02 10:51:03 `USER_ADD`（user_id=1，/api/users）创建；10:51:54 该用户以 role=user 访问 `/api/notification/logs/2483/diagnostics` 被拒（`ACCESS_DENIED`）——即 A-35 多用户日志隔离测试账号；无其他操作/通知记录 |
| 可恢复性 | 删除前备份 `pilotstd_manual_20261117_201624.bak` 存在（API 可列）；备份含 user3 + 3 收藏 + 3 favorite_downloads，可恢复；**确认为测试账号，删除正确，不恢复** |
| 探针校准 | 从 `standard_info_cache` 取每站最近 `match_status=exact` 号：std_gov GB/T 10827.6-2023、ahbz NB/T 47016-2023、csres GB/T 17395-2024、cssn GB/T 8165-2008、dbba DB50/T 1982-2026、hbba JB/T 13964-2020、iso_gov ISO 16852:2016、jjg JJG 141-2013、mee GB 37822-2019、njbz365 NB/T 47033-2013；其余 11 站无 exact 缓存 → `probe_pending`，不输出 no_result |
| 本地重跑 | found=3 / no_result=7 / error=0 / probe_pending=11；no_result 的 7 站（std_gov/ahbz/csres/dbba/hbba/iso_gov/njbz365）探针来自 exact 缓存，no_result 更像适配器/网络/解析退化（iso_gov 日志 503），不是探针选错 |
| 61 重查可信度 | `daily_quota` 今日各站 0~3 次、无 `quota_exhausted` 指标；抽查日志：SHB 6-1999 `tried=njbz365`、NB 47007/47019 `tried=energy→energy`（单站链+一次同站重试）⇒ 0.58s/条由**单站链**解释，不是配额快速耗尽；但**不能证明多站链 P3-16 存量效果**，需在链路/配额充足时用多站代码重跑；GB 抽查出现 csres 日志“找到 评分=100”而 API stats found=0（结果合并/统计异常，另记） |
| pending 对账 | 现 61 = 33 `file_missing`（32 chain +1 exact，11-13 创建，id 100~） + 28 空分类（11-17 由 62 批产生，id 600+）；原 35（34 chain +1 exact）中 **2 条**（GB/T 20671.4-2026、GB 3609.2-2025）已 `resolved`（file_moved_quarantine→目标在 file_index），34 = 32 file_missing + 2 resolved；28 不是 34 减少，而是**新产生** |
| 代码 | 探针表校准 + `PROBE_PENDING`（11 站）；测试更新（probe_pending 计数） |


### 65. 全局问题总表建立 + csres 合并修复 + 探针校准 + 数据处置（2026-11-17）

- 新建 docs/debt/00-global-issues.md（五维唯一基线）。
- csres 晚到结果：_collect_csres_results 现会在既有 NG 时用 found 结果覆盖，并补 _prog_ok；单测 	est_csres_result_replaces_ng_result；根因是“csres 后台结果晚到，idx 已存在即被跳过”，影响 API stats/auto query_found，不影响 moved。
- 探针校准：10 站用 standard_info_cache exact 号；11 站 probe_pending；本地 found=3/no_result=7/error=0。
- 28 条空分类 pending 回填 chain_exhausted + 
eason=copy_quarantined（manifest/rollback C:\Temp\pending28_*）；61 对账见 #64。
- 30 副本在 /app/data/_quarantine/__replay_b62（生产持久卷），对应 28 pending 已标 copy_quarantined。
- 审计确认：2986acde（v0.192.1）是 5e43c66b（v0.194.1）祖先。


### 66. v0.195.0 部署后验证 + 项目待办梳理（2026-11-17）

| 项 | 结果 |
|---|---|
| 部署 | 生产 **v0.195.0**（`/api/system/version` 确认） |
| 健康检查首轮 | `POST /api/adapters/health/run`：found=3/no_result=7/error=0/probe_pending=11；日志 `adapter_health site=...` 可见；7 个 no_result 探针来自 exact 缓存，属适配器/网络退化 |
| 61 重查 | 低峰重跑 298s：found=3/not_found=58；`SHB 6-1999` 日志 `tried=gongbiaoku→hbba→ahbz→njbz365`（4 站真查），`NB 47007` 单站 energy（能力模型配置）— **P3-16 多站链生效** |
| csres stats | 首次修复后仍 `GB 50016-2014 stats.found=0`：overflow 在 collect 之后又把 found 覆盖为 pending；已加 **overflow 后二次 `_collect_csres_results`** + 测试，待 v0.195.1 部署验证 |
| 项目梳理 | `03-open/04-watch` 未闭合项已映射进 `docs/debt/00-global-issues.md` 第七节；当前 **待做 3 / 等触发 14 / 明确不做 1 / 已闭合 12** |
| 已闭合回归 | A-47/P2/AC-6/健康检查/批次分发 46 例相关测试通过；A-40 数据核对：user0=2524、user1=24、无 user5、用户仅 mystdpilot |


### 67. v0.195.1 验证：csres 统计真相 + 日志修正（2026-11-18）

- v0.195.1 部署；GB 50016-2014 重查 stats.found=0，结果行 error_message=未找到匹配结果 ⇒ **stats 正确**，此前“找到 评分=100”是 csres **日志文案错误**（if result: 即打印“找到”）。
- 已修：新增 csres_state_text(result)，仅 is_found() 打印“找到”，否则“未找到”；单测 	est_csres_state.py。
- 61 重查（v0.195.0）：298s、found=3/58；SHB 	ried=gongbiaoku→hbba→ahbz→njbz365 四站真查；NB 单站为能力模型配置。
- 健康检查生产首轮：found=3/no_result=7/error=0/probe_pending=11（后续整点 hour 任务已跑，found=5/no_result=5）。
- 总表：G-02/G-04 闭合；G-01 修订为“日志文案”待 v0.195.2。


### 68. v0.195.2 核验：csres 日志“未找到”确认（2026-11-18）

- 生产 v0.195.2；GB 50016-2014 复跑：日志 [CSRES] ... 状态=未找到（不再误报“找到 评分=100”），stats.found=0，结果行 未找到匹配结果。
- 总表 **G-01 关闭**（docs/debt/00-global-issues.md）。
- 当前总表：待做 0、等触发 14、明确不做 1、已闭合 15。


### 69. Web 铃铛渠道副本去重（2026-11-18）

- 现象：同一收藏成功在铃铛出现 2 条（wechat/telegram 各一行），旧数据 `message_id` 为空无法按消息归并。
- 修复：`useNotification.dedupeMessages` 按 `(event_type,title,body,分钟)` 去重、未读优先；日志页仍按渠道展示原始行（投递诊断需要）。
- 测试：`useNotification.test.ts` 新增去重用例；前端四件套 type-check/lint/test/build 全绿（367 例）。
- 待部署 v0.195.3；部署后铃铛不再显示渠道副本，角标未读数同步按去重后计算。


### 70. 铃铛标记已读后弹层偏左（2026-11-18）

- 现象：点击“全部标记已读”后，PrimeVue Popover 停留在旧坐标，弹层偏到页面左侧（截图可见）。
- 根因：标记已读使 badge/按钮状态变化并触发重排，Popover 未按新触发器坐标重新对齐；此前仅固定按钮宽度不够。
- 修复：`markAllAsRead` 在 `nextTick` 后调用 `popover.alignOverlay()`；`NotificationBell.test` 新增断言（8 例通过）。
- 08 #18 同步标注“2026-11-18 再修”；总表 G-10 已修（待 v0.195.3 部署）。


### 71. 铃铛弹层偏左：真根因 + 真实 UI 验证（2026-11-18）

- 复现（Playwright 对 v0.195.3）：打开时 `x=623.47`，点“全部标记已读”后 `x=11.5`，左移 612px。
- 真根因：`AppHeader` 的 `topbar-right v-show="isHovered"`；鼠标移入弹层后 `mouseleave` 触发隐藏铃铛，Popover 锚点 rect 变 0，`alignOverlay` 反而把它对齐到左上角。
- 修复：`NotificationBell` 发 `popover-show/hide`；`AppHeader` 用 `isHovered || notificationOpen` 保持顶栏显示；`alignOverlay` 保留。
- 真实 UI 验证（dev 构建 + 生产 API，临时用户）：2 条渠道行 → 1 条展示；点击前后 `delta_left=8px`，弹层右缘距铃铛右缘 3.5px（无左跳），截图 `C:\Temp\bell_verified.png`。
- 结论：**dev 真实操作通过**；生产 v0.195.4 待部署复验（按 R-1 未计“已闭合”）。


### 72. G-03 健康检查探针自动发现（2026-11-19）

- health_probe.discover_probes()：运行时从 standard_info_cache 的 exact 记录为 probe_pending 站点补探针；仍无缓存才保留 pending。
- 测试 	est_discover_probes_fills_pending；待部署后生效。


### 73. U-4 公告抓取状态/补抓：已具备并有生产证据（2026-11-19）

- 生产通知 id=4505/4504（2026-11-18 01:00）：距上次成功抓取已约 375 小时，本次已开启回看补抓 → _missed_gap_hours() + lookback override 真实生效；
- 
etch_checkpoint 有 3 个来源 last_fetched_at；	ests/test_announce_lookback.py 2 例 + 	est_announcement_checkpoint_regression.py 覆盖补抓/检查点不越失败项；
- 结论：**U-4 功能正常，无需补实现**；剩余仅为“抓取结果为 0”的数据源问题（公告源无新数据/抓取异常），归 U-4 数据侧观察。


### 74. CookieCloud 保存链路根因 + 有效性“—”根因（2026-11-19）

- **U-3 根因**：GET /api/wechat-ip/config 对 key/password 返回 ***；前端 saveConfig 把 config.value 原样 PUT → 后端 update_config 无条件写入 → 真实 key/password 被覆盖成字面量 ***。修：后端对 cookiecloud_key/password == *** 跳过写入；测试 	est_masked_secret_not_overwritten。
- **U-1 根因**：变更详情只写 new_status（
eason=new_status），没有 previous_status，所以显示 TSG 71-2023 — 现行，读起来像“— → 现行”。修：_record_change 接收 old_status，reason 改为 旧 → 新（缺旧值显示“未知”）。
- 两项均待部署验证；降级替代（GB 30871-2022→2014）仍待查数据源/解析。


### 75. GB 30871-2022“降级替代”根因（2026-11-19）

- 数据：nnouncement_record 把“代替旧号”写进 superseded_by（GB 30871-2022 → GB 30871-2014），语义反向；49,306 行非空，其中大量年份倒退。
- 修复（先止损）：_replacement_info 解析新旧年份，新<旧时忽略并留日志；测试 	est_validity_replacement_direction.py。
- 数据/源字段的彻底修正（合并方向迁移 + crawler 映射）另立任务，不在本轮改 4.9 万行。


### 76. A-43 表数核对（2026-11-19）

- 生产 sqlite_master 非系统表 **43** 张；scripts/check_schema_consistency.py 汇总 0 处不一致；docs/architecture.md 未声明固定表数，无需改文档。A-43 闭合。


### 77. A-44 monitor 热更新闭合（2026-11-19）

- 	ests/test_monitor_hot_reload.py 5 例通过：PUT 配置触发 stop→start；	ests/integration/test_monitor_catchup_e2e.py 7 例通过；watchdog 
ecursive 覆盖子目录。A-44 闭合。


### 78. V-16 TaskManager 失败分支闭合（2026-11-19）

- 	ests/test_core_task_manager.py 覆盖 
ailed 字段归一、终态词表（completed/cancelled/failed）、result_json 防御与两种 result 形状；TaskManager 仅只读门面，运行时失败落库不在该层。V-16 闭合。


### 79. T-42 渠道限流闭合（2026-11-19）

- channels/base.py 已码优先（wechat 45009、feishu 99991400；dingtalk/telegram 关键词+429）、Retry-After 上限、5xx 重试；	ests/test_notification_rate_limit.py 3 例通过。T-42 闭合。


### 80. CI test-backend 红：定位与修复（2026-11-19）

- **取证**：run `44507312315`（HEAD `9e884970`）与 `44432226468`（`8228fa78`）都在 `test-backend / Run backend tests` 失败；job 日志接口 404（BlobNotFound），run 级 `logs.zip` 里也没有该 job 的文件。改走 `check-runs/{job_id}/annotations` 拿到两条失败测试名——这是本次绕开 BlobNotFound 的有效路径。
- **失败 1**：`tests/unit/core/test_status_convergence.py::test_no_bare_status_literals_in_production` — `pilotstd/core/_validity_pipeline.py:102` 的 `f"{old_status or '未知'} → {new_status}"` 用了裸状态字面量，违反 #32-B 收敛守卫。
- **失败 2**：`tests/test_validity_checker_full.py::TestProcessValidityBatch::test_status_changed` — `4003372e` 把 `reason` 从“新状态”改成“旧 → 新”，旧断言未同步。
- **根因同源**：`4003372e`（交接单写作 `c322c1c0`，两者 patch-id 相同）只新增了 `	est_validity_change_detail.py`，漏改旧断言；且缺旧值时把“未知”写死。
- **修复**：`reason` 改用 `Status.UNKNOWN.value`；断言改为 `f"{Status.ACTIVE.value} → {Status.WITHDRAWN_NORMALIZED.value}"`。
- **验证**：受影响 4 个文件 159 例通过；全量单进程 `6421 passed / 23 skipped`（17:37）；CI 等价命令（`-n auto -p no:pytest-qt --timeout=60` + 同 ignore）`6371 passed / 23 skipped`，`EXIT=0`（9:04）；`ruff check` 通过；`mypy` 仅剩 OCR 模块缺 stub 的既有噪声（与本次无关）。
- **坑记录**：`python -m pytest ... 2>&1 | Tee-Object ...` 会让原生 stderr 变成 ErrorRecord，pwsh 退出码报 1（全绿也报 1）；判定退出码要用 `*> 文件` 后读 `$LASTEXITCODE`。
- **附带核实（影响 R-3）**：生产 v0.195.5（`5db18501`）**不含** `4003372e` → U-1“旧→新”、U-3“掩码不覆盖真实值”尚未上线；R-3 复验前必须先部署，否则会把“未部署”误判成“假闭合”。


### 81. G-012 `[LANG]` 语言警告收口：1511 → 0（2026-11-19）

- **现状**：全仓 557 个文件挂着 1511 条“注释必须全部用中文”警告（规则不阻断，但长期噪音）。
- **第一步（规则盲点）**：`# i18n-allow:` 是项目自己的放行标记（G-047 同款），但没进 `TOOL_DIRECTIVES`，被当成英文 → 补上后 1511 → 1402。
- **第二步（改口径）**：原判定是“注释里出现任意英文字母即违规”，对中文注释引用标识符（`PILOTSTD_API_TOKEN`、`aggregate_keys.py`、`task_id`）100% 误报，照字面清理只能把标识符意译成模糊中文，属降级。改为**按词判定**：先剔除工具指令、反引号行内代码、引号字符串、文件名形态；剩余片段只拦英文普通词，形如代码标识符的（含 `_` `.` `/` 括号连字符、数字，或含大写字母）放过 → 1402 → 504。新增 `tests/test_check_g_012_comment_lang.py` 9 例锁定口径。
- **第三步（逐行改写）**：504 行按 6 批并行改写——叙事词译中文（`只 warning 不 debug` → `只记警告不记调试`），裸小写标识符加反引号（`inbox` → `` `inbox` ``）→ 0。
- **验证**：
  - `python scripts/check_g_012_comment_density.py`：**0 项阻断、0 项语言警告**；
  - 200 个改动 `.py` 用 AST 归一化（docstring 文本换占位符）与 HEAD 对比：除检查器与其数据表外，**其余 198 个文件 AST 完全一致**，即只动注释/docstring；
  - 全量后端套件（CI 同参数）`6380 passed / 23 skipped`，`EXIT=0`；
  - 一处测试按源码文本断言注释（`test_notification_stage1c_fields.py`），注释加反引号后失配 → 改为剥离反引号再比对，保留“契约必须有可查落点”的原意。
- **口径依据**：gates.md v1.13 已裁定“能中文化的一律中文，用作查证入口的标识符不意译”；本次区别是标识符不再需要逐条登记白名单。`--fix` 仍然禁用（实现是删光英文字母，会把注释改成病句）。
- **编号澄清**：交接单把这条记作“V-17”，但 `04-watch.md` 的 V-17 实为“注释密度对新脚本反复红”，是另一件事，本次未动。

### 82. G-029 把“纯注释改动”误判为缺测试（2026-11-19）

- **现象**：V-17 注释批（15 个 `pilotstd/ui/` 文件、纯注释/docstring）让 CI 的 `repo-compliance` 红在 `G-029 核心模块变更测试同步检查`：UI 变更必须同批改 `tests/gui/`｜`tests/test_ui*`。
- **判定**：注释不进 AST、docstring 文本不影响语义，这类变更强制补测试只能产物化无意义用例。
- **修复**：新增 `is_comment_only(path, range)`——取范围左端基线内容与工作区内容各建 AST，docstring 文本归一化为 `<DOC>` 后比较，相同即从“需测试同步”集合剔除。基线取不到（新增文件/git 不可用/读失败）或任一侧语法错误，一律按真变更（宁可多要求一次测试）。
- **验证**：`G029_RANGE=aceaf82c..87ab358f` 由 FAIL 转 PASS；`tests/test_check_g_029_comment_only.py` 5 例（注释/docstring 跳过、代码变更仍红、新文件与缺基线按真变更）。
- **顺手修复**：该脚本缺 `sys.stdout.reconfigure(encoding="utf-8")`，Windows GBK 控制台在打印 ❌ 明细时 `UnicodeEncodeError`——失败原因不可见等于盲区，已按其余 20 个门禁同口径补齐。

### 83. R-3 只读复验：通知级别“假闭合”与修复（2026-11-20）

- **部署确认**：生产 v0.196.1（`286a4ed2`）；`git merge-base --is-ancestor` 逐项核对，U-1/U-3（`4003372e`/`4d9e3b7d`/`05113127`/`5d3d7aa5`/`63613598`）、G-03（`0e2ff79b`）、铃铛两项与 V-17 批全部在内。
- **只读复验**（登录后仅 GET，无写操作）：
  - `GET /api/system/version` → `0.196.1` / `v0.196.1`；
  - `GET /api/notification/logs`（100 条）→ 响应字段里**没有 `level`**；
  - `GET /api/wechat-ip/config` → `cookiecloud_key`/`cookiecloud_password` 返回 `***`（掩码生效），并已带 `cookie_status`/`cookie_source`（U-3 状态文案所需字段）；
  - 通知正文可见 `现行 → 新标准：GB 30871-2014`（`standard_status_changed` 侧的新标准格式）。
- **假闭合（R-3 抓到的第一例）**：`63613598` 声称“日志暴露业务级别并告警着色”，但 `NotificationLogItem` 未声明 `level`，FastAPI 按 response_model 序列化时把该字段丢掉 ⇒ 前端映射恒为 `info`，铃铛的 `warning`/`error` 着色形同虚设。更糟的是前端用例当时断言“后端不返回 level”，把缺陷锁成了契约。
- **修复**：响应模型补 `level: str`；前端 `useNotification` 注释与用例同步（保留缺失回退 + 新增“有值则透传”）；后端补 2 例（模型声明、序列化保留取值）。
- **验证**：`tests/test_notification_level_mapping.py` 3 例；`-k notification_log` 33 例；web vitest `useNotification.test.ts` 14 例。
- **仍待真实验证**：`_record_change` 的“旧 → 新”reason 要真实跑一次时效检查才会出现在通知里（本次 100 条日志无此类记录）；G-09 去重、G-10 弹层位置需要真实 UI（Playwright + 临时用户）。

### 84. R-3 真实 UI 复验：铃铛去重与弹层位置（2026-11-20）

- **方法**：Playwright（headless chromium）登录生产 `192.168.1.18:9028`（v0.196.1），只做读操作——hover 顶栏让铃铛出现 → 打开弹层 → 把鼠标移入弹层（G-10 的原始触发路径）→ 量盒/截图；未点“全部标记已读”（避免写生产）。脚本 `ci.tmp/r3_bell.js`，截图 `ci.tmp/r3-bell.png`。
- **G-10 弹层偏左：真闭合**。弹层 `x=771.97`、右缘 `1154.97`，距铃铛右缘 8px；铃铛盒始终 35×30 未被隐藏，历史上“弹层跳到 x≈11.5、左跳 612px”未复现。
- **顺带发现并修掉 8px 锚点位移**：弹层打开后鼠标离开顶栏 ⇒ `.topbar.collapsed` 生效（`height` 60→40、`padding` 24→16），锚点被带走 8/10px，弹层仍停在旧坐标。修：`AppHeader` 的 collapsed 条件改为 `!isHovered && !notificationOpen`（与 v-show 同一判据），`AppHeader.test.ts` 补断言：弹层打开期间 header 不得带 `collapsed`。**该修复待部署验证**。
- **G-09 铃铛去重：未触发，不算已验证**。铃铛 10 条按 (标题, 正文, 分钟) 分组后同分钟重复 0 组；当前生产没有“同事件同分钟双渠道”样本，去重规则没被走到。要真闭合需构造样本（单测或临时双渠道投递），不能凭“看起来没重复”判闭合。
- **观察项（未修，已缩窄范围）**：铃铛里有 3 条同内容“IP 更新失败 / 无法获取企业微信 Cookie 状态: 失败”（5、10、16 小时前，约等于 `interval_hours`）。正文形态可定性：文本块来自 `wechat_ip/scheduler.py:57`，末尾“状态: 失败”是 `_build_trust_ip_update_message` 按 `status` 追加的键值块 ⇒ **走的就是去重分支**，所以问题不是“别的路径漏了”，而是去重键被重置。最可疑两处：同文件 `:83` 成功分支把 `last_fail_key` 清空（成功一次后失败会再通知），以及 `last_fail_key`/`last_ip` 是否跨重启持久化。下批查这两处，别再从“通知路径”查。

### 85. R-3 续：G-09 真闭合；IP 失败重复通知根因（2026-11-20）

- **G-09 铃铛渠道副本去重：真闭合（生产 v0.196.3）**。用接口精确时间做端到端比对：最近 100 条日志里 telegram/wechat 同分钟成对出现（同分钟重复组 81 个，raw 100 → 按 `(event_type,title,body,分钟)` 去重后 45），而铃铛只渲染去重后的 10 条，且与“接口去重后前 10”**按序一一对应**（10/10）。此前判“未触发”是因为只看了 UI 的粗粒度“N小时前”，属测量口径错误。
- **顶栏锚点位移：修后生产实测归零**。`bee0add4` 部署（v0.196.3）后重跑 Playwright：弹层打开前后铃铛盒完全一致（`x=1119.97, y=14.5`），`delta_bell_left=0`、弹层右缘与铃铛右缘差 0px。G-10 收口。
- **IP 失败重复通知：根因定位（未修）**。现象：同内容“IP 更新失败 / 无法获取企业微信 Cookie 状态: 失败”每 5~6 小时一条，且**从未出现“可信 IP 已更新”** ⇒ 成功分支没跑过，`scheduler.py:83` 的清空不是原因。
  - 复现（`ci.tmp/probe_config_race.py`）：同一配置文件建两个 `ConfigManager` 实例，A 写入 `wechat_ip.last_fail_key` 并 save，B 随后只写 `last_check_at` 并 save ⇒ **A 的键被整文件覆盖丢失**（读回 `None`）。
  - 生产侧对应物：`docker/scheduler.py` 有 5 处 `ConfigManager()`（201/243/414/509/552），每个都是构造时的快照；任一实例 save 都会用旧快照整文件覆盖，`wechat_ip.last_fail_key` 因此活不过下一个保存点 ⇒ 每次失败都“看起来第一次”，通知拦不住。
  - 修复方向（下批做，需设计）：进程内统一 `get_shared_config()`（该函数已存在但**全仓零使用**），或 `save()` 改为与磁盘内容合并；两者都要配“双实例不互相覆盖”的回归测试。**不要**用“再加一个去重键”绕过——根因是写盘模型，不是键不够。

### 86. 配置多实例覆盖写：根因与单键安全写入口（2026-11-20）

- **现象**：生产每 5~6 小时一条同内容“IP 更新失败 / 无法获取企业微信 Cookie 状态: 失败”，且**从无“可信 IP 已更新”**（说明成功分支没跑过，`scheduler.py:83` 清空不是原因）。
- **复现**（`ci.tmp/probe_config_race.py`）：同一文件两个 `ConfigManager` 实例，A 写 `wechat_ip.last_fail_key` 并 save，B 只写 `last_check_at` 并 save ⇒ A 的键被整文件覆盖（读回 `None`）。
- **生产对应物**：`docker/scheduler._check_validity_schedule` 在 :509 构造快照 → 跑完整轮时效检查（可达数分钟）→ :542 用旧快照 save，冲掉期间写入的键；`core/_validity_pipeline._finalize_validity_round` 同型（实例在 `run_validity_check` 开头构造，收尾时整快照写盘）。
- **修复**：`ConfigManager` 新增 `update(key, value)` / `update_many(values)` —— 先 `reload()` 读盘、再改键、再写盘；两处调用点改为单键/批量安全写（`validity.first_execution`、`validity.next_run`、`checked_count`、`round_count`、`round_completed`）。
- **验证**：`tests/unit/core/config/test_manager_update.py` 4 例（他方写入保留、批量记账保留、同键覆盖）；`tests/test_validity_checker_full.py` 80 例；`-k scheduler or validity` 366 例。
- **全仓 AST 扫描（同批做，不靠猜）**：
  - ① “同一函数内既 `ConfigManager()` 又 `save()`”只有 1 处：`notification_aggregator._save_pause_state`（毫秒级，安全）；
  - ② “保存**入参** config”共 7 处，其中真正跨长任务的是 `wechat_ip/scheduler.run_check`（检测 IP → 取 Cookie → 浏览器更新，可达数分钟），**已一并改为 `update()`/`update_many()`**；其余 `menu/service.sync_channel`、`config/migrate.import_rules` 均短事务。
  - 结论：同类风险已收口，不存在“还有 40+ 处待扫”——先前那句是未核实的估计。

### 87. 深色主题按钮文字不可读：遍历实测 111 个按钮，修 3 类（2026-11-20）

- **方法**：Playwright 遍历 15 个路由（登录后），对每个按钮类元素计算 WCAG 对比度——有效背景按祖先 `background-color` 逐层 alpha 合成，小字阈值 4.5、大字 3.0。脚本 `ci.tmp/contrast_scan.js`。
- **结果**：111 个按钮中 **32 个低于 AA**，归为 3 类：
  1. `p-button-danger p-button-outlined`（2 个：/task“停止任务”、/notification-logs“清理日志”）**1.36:1**——`.p-button.p-button-danger` 强制 `background: var(--danger)`，深色主题 `--danger` 是 #f87171（浅红），而 Aura 的 outlined 变体把文字也压成 #ef4444，两段红几乎同亮度，正是截图那种“深底看不见字”；
  2. `.floating-workspace-btn`（悬浮工作台按钮，每个页面 1 个，共 15 处渲染）**2.98:1**——白字 on 深色 `--primary` #818cf8；
  3. `.collapse-toggle`（侧栏“收起”，每页 1 个，15 处）**4.04:1**——13px 小字 `--text-secondary` #94a3b8 on `--surface` #334155，差 0.46 不达 AA。
- **修复**：
  1. 新增 `html .p-button.p-button-danger.p-button-outlined`：透明底 + 描边 `var(--danger)` + 文字 `var(--danger-text)`（深色 #f87171≈7.6:1、浅色 #991b1b≈8.3:1），hover 用 `--danger-bg`；
  2. 悬浮按钮底色改 `--primary-hover`（深色 #6366f1≈4.4:1、浅色 #4f46e5≈7.4:1），hover 改用 `brightness()` 提亮；该按钮可视内容只有图标（文案在 `aria-label`），适用 WCAG 1.4.11 的 3:1 而非 4.5；
  3. 收起按钮文字改 `--text-bright`（深色 #e2e8f0≈9:1、浅色 #334155≈9:1）。
- **验证**：同一扫描器指向本地 dev（vite 代理生产 API）复扫：**107 个按钮、0 个低于 AA**；两个 danger outlined 按钮实测 `color rgb(248,113,113)` + `background rgba(0,0,0,0)`；前端四件套（type-check/lint/test/build）全绿。
- **口径**：只覆盖“按钮类元素”；正文/链接/输入框未纳入，后续可扩扫描选择器。
- **回归测试**：`web/src/a11y-contrast.test.ts` 7 例——用 `themes.ts` 的真实令牌算 WCAG，锁住三处配色决定（outlined danger 文字、悬浮按钮底色、收起按钮文字），并断言 `style.css` 里 outlined 透明底规则未被删。

### 88. Inbox 空目录自动清理“假生效”：垃圾目录漏清 + 只清一层 + 空祖先残留（2026-11-20）

- **现象**：monitor 归档后 `_cleanup_empty_dirs` 看似在跑，但 Inbox 里仍留下：①只含 `Thumbs.db`/`~$` 锁文件的目录；②多层嵌套空目录只删最内层；③文件位于深层目录时，`source_root` 之上的空祖先目录永久残留（不再有文件事件触发它们被清理）。
- **根因**（实测，非推断）：
  - `pilotstd/monitor/scheduler.py:32`（旧实现）只用 `os.rmdir`，未复用 `file_utils` 的“系统垃圾文件也算空”口径，垃圾目录必然 `rmdir` 失败被 `except OSError: continue` 静默跳过；且只清 `start_dir` 子树，不向上收祖先。
  - `pilotstd/core/file_utils.py:311`（旧实现）用 `os.walk(topdown=False)` 的 `dirnames` 快照判断 `not dirnames`：子目录在遍历中被删后，父目录的快照仍含该子目录名 ⇒ 父目录被误判为非空，多层空目录只删最内层（复现：`root/a/b/c` 全空 → 只删 `c`，返回 1，`a/b` 残留）。
- **修复**：
  - `file_utils` 新增 `is_junk_file(name)` 与 `remove_dir_if_empty(dirpath)`：每次 `scandir` 重新判断、非空即保留，仅垃圾文件时先删垃圾再 `rmdir`；`remove_empty_dirs` 改为自底向上调用它（不再依赖 `dirnames` 快照）。
  - `scheduler._cleanup_empty_dirs` 改为调用同一 helper：`start_dir` 子树清完后沿 `dirname` 向上收空祖先，遇非空即停、到 `watch_root` 即止（不删 `watch_root`；路径不在其内仍直接返回 0）。
- **验证**（先红后绿）：先写 6 例失败测试（4 个 monitor + 2 个 file_utils）确认缺陷存在。`tests/test_monitor_cleanup.py` 新增 8 例：深层嵌套、仅 `Thumbs.db`/`~$`、非空目录与其中垃圾保留、空祖先、祖先遇非空即停、根目录触发、`watch_root` 垃圾不动、`_on_file` 用户路径集成；`tests/test_file_utils.py` 新增 3 例：3 层嵌套、垃圾目录递归、非空保留。`python -m pytest tests/test_monitor_cleanup.py tests/test_file_utils.py -q` → **52 passed**；monitor 相关 9 个套件（含 e2e/catchup/u38）→ **120 passed**。
- **回滚**：还原上述两个函数与新增测试；无 schema/配置/数据变更。
- **同类隐患（本轮未改，超出允许改动范围）**：`docker/api/organize.py:95 clean_empty_dirs` 逐层只删叶子、父层仍被判非空（与本次修掉的“只清一层”同型）；`pilotstd/ui/core/handlers/_cleanup.py:117` 是另一套手工扫描/确认流程。另：`remove_empty_dirs` 在非测试代码中无调用方，monitor 实际走 `_cleanup_empty_dirs`，两条路径现已同口径。
- **关联**：08#2（D-02）、26 D-02、ISSUE_LEDGER P1-09；实际文件是 `pilotstd/monitor/scheduler.py`（仓库不存在 `pilotstd/scan/scheduler.py`）。


### 89. 公告「起始日期」语义纠偏：默认今天 → 最近 7 天（2026-11-20）

- **语义结论（问题 1）**：`since_date` 是**抓取起点（含当日）**，不是结果后置过滤。`pilotstd/announcement/base.py:112` `_fetch_list` 按 `sortName=NOTICE_DATE&sortOrder=desc`（`:121-126`）从最新往前分页，`:146-147` 遇到 `row["NOTICE_DATE"] < since_date` 的第一条就 `return`（提前终止）；空串 `:146` 短路 ⇒ 不限起点（全量历史）。`crawler_service.check_filtered`（`pilotstd/announce/crawler_service.py:287-309`）原样透传，**不读也不写** checkpoint（与 `docs/reference/announcement-pipeline.md:53-54` 一致：手动 `since_date` 是「历史漏抓恢复方式」）。
- **缺陷（问题 2）**：旧版 `AnnounceView.vue::defaultSince()` 直接返回 `new Date()` = 今天 ⇒ 手动「立即抓取」只覆盖当天；当天无新公告时 `count=0`、界面无变化，且漏掉前几天晚发布/漏抓的公告——这就是用户感知到的「日期选了没用/抓不到历史」。因 `check_filtered` 不走 checkpoint，默认今天既非增量也非补抓。**判定：bug（默认值 + 文案双重误导）**。
- **修复**：默认改「最近 7 天」（`AnnounceView.vue:22-38`，对齐后端 `announcement.lookback_days` 默认值 7，见 `pilotstd/core/config/defaults.py:48`），日期选择器加 `showClear`（清空=不限起点=全量历史补抓）、`placeholder` 与可见提示「起始日期（含当日）：只抓该日期及以后发布的公告；清空=全量历史补抓」（`AnnounceView.vue:154-155`、三语 `since_placeholder`/`since_hint`）。`check()` 起点为空时不再带 `since_date`（`:111`）。**后端抓取行为零变更**，只纠正注释失真：`docker/api/announce.py:170-178/255-262/267-271/311` 四处「仅抓取该日期之后」→「含当日」。
- **定时一次性回填（问题 3）：设计意图成立，但接线是缺陷**。`pilotstd/manager/announce_service.py:147-152` 读到 `app_preferences.announce_since_date` 就按该日期补抓一轮并清空——读后即清是一次性回填的**有意设计**（否则每个周期都重抓同一段历史）。但 Web 端 `usePreferencesStore().set('announce_since_date', …)` 写的是 `user_preferences`（`PUT /api/user/preferences/{key}` → `settings_manager.UserPreferenceManager`/`user_service.save_preference`），**不是** `app_preferences`；全仓 `app_preferences` 写入方只有 v20/v58 迁移默认值与**零调用**的 `save_user_preference`（`announce_service.py:114`）⇒ 该通道在生产等价死代码，UI 日期从未进入定时任务。本次**不接线**（接上会让「选个日期」静默触发隔夜重复重抓，且多用户语义不明），只在代码注释 `announce_service.py:89-100` 与本文记录；顺手把清空 `UPDATE` 改 upsert（`announce_service.py:102-112`）——行缺失时 `UPDATE` 影响 0 行会静默失效，导致每周期重复回填。
- **观察项（未修，超范围）**：① `_sync_wait_check`（`docker/api/announce.py:267`）虽接收 `since_date`/`types`，但 `AnnounceTaskRunner.trigger` → `check_all` 只用 checkpoint，参数被丢弃（该路径已 DEPRECATED，改注释说明）；② `since_date` 无格式校验，传 `2024/1/1` 之类会因字符串比较「恒早于起点」→ 静默 0 条。
- **测试**：`tests/announce/test_crawler_service.py::TestCheckFiltered` +3（空值=全量且不读 checkpoint、等于今天原样透传、早于 checkpoint 仍透传=补抓不被裁剪）；新增 `tests/test_announce_backfill_pref.py` 4 例（一次性回填+清空、第二轮回 checkpoint、无偏好走增量、缺行清空 upsert）；`web/src/views/AnnounceView.test.ts` +4（默认最近 7 天、清空后不带 `since_date`、提示语文案、localStorage 沿用手选日期）。
- **验证**：`python -m pytest tests/announce tests/test_announce_lookback.py tests/test_announce_fetch_notification.py tests/test_api_announcement_write_endpoints.py tests/test_migrate_v58.py -q` → 68 passed；`pnpm.cmd run type-check` → exit 0；`pnpm.cmd vitest run src/views/AnnounceView.test.ts` → 11 passed。
- **回滚**：前端 `SINCE_DEFAULT_DAYS/defaultSince/formatDate` + `showClear/placeholder/.since-hint` + 三语 `since_*` 键；后端 `_clear_user_since_date` 的 upsert。无 schema 变更、无数据迁移，回滚不影响已入库数据。

### 90. 公告原文/附件归档：目录只建不写（2026-11-20）

- **现象**：`data/announcements/{gb,hb,db}` 目录存在但永远为空——抓到的详情 HTML 只进了 DB 的 `announcements.raw_data`，附件下载后只在内存里解析、从不落盘；连带 `_finalize_items` 里 `attachment_path` 一直是空串（字段建了没人填）。
- **修复**：新增 `pilotstd/announcement/_raw_archive.py`
  - `archive_html(std_type, announce_no, html)` → `{data_dir}/announcements/{std_type}/{公告号}.html`
  - `archive_attachment(std_type, announce_no, url, data)` → 同目录，扩展名取白名单（`.pdf/.doc/.docx/...`），未知则 `.bin`
  - 文件名安全化（保留中日韩/字母数字/`._-`，其余压 `_`，限长 80），杜绝 `../` 越级
  - 开关 `announcement.save_raw_files`（默认开）、目录 `announcement.raw_dir`（默认空 ⇒ data 卷内）
  - **归档失败只告警**，不影响解析（原文是证据链，不是业务数据）
- **接线**：`base._process_one_detail` 落 HTML；`base._parse_items(..., announce_no=)` 落附件并把路径写进 `attachment_path`（同时覆盖 `reparse_from_source` 路径，它复用 `_process_one_detail`）。
- **验证**：`tests/unit/announcement/test_raw_archive.py` 6 例（写入、后缀白名单、未知后缀、越级文件名、关闭开关、写盘失败不抛）；`-k announce` 637 例通过。
- **观察**：归档随抓取增长，磁盘占用需定期看；如需关闭在设置里置 `announcement.save_raw_files=false`（只保留 DB 正文）。

### 91. 四主题配色统一：拆开「强调色」与「按钮底色」（2026-11-20）

- **根因**：`--primary` 一个 token 同时当**强调文字/图标**和**主按钮底色**用。两种用途对亮度的要求相反——
  文字要“对 surface 够亮/够深”，按钮底色要“白字够深”。四主题只能各挑一边，于是出现 light 强调色 4.47（差 0.03 不达标）、
  dark 主按钮白字 4.47、green 文字梯度整体偏低（bright 4.79）这类“各调各的”。
- **规范 v2**：
  1. `--primary` 只做强调色（文字/图标/描边），对 surface ≥ 4.5:1；
  2. 新增 `--primary-fill` / `--primary-fill-hover`：主按钮与选中态底色，白字 ≥ 4.5:1，且 **hover 恒比 fill 更深**（四主题同向）；
  3. 文字梯度统一为 heading ≥ 12、bright ≥ 9、text ≥ 7、secondary ≥ 4.5、dim ≥ 4.5（对 raised）；
  4. 语义 `-text` 对 surface ≥ 4.5；背景透明度同族一致（primaryBg 0.08~0.16、语义 bg 0.10~0.18、描边 0.28~0.40）；
  5. 边框必须与 surface 可分辨 ≥1.15:1。
- **改值**：light 强调 `#6366f1→#5c5ef2`（4.47→4.84）、fill `#4f46e5`/hover `#4338ca`；dark fill `#6366f1→#5b5ef0`（白字 4.47→4.88）、hover `#4f46e5`；
  green 强调 `#22c55e→#15803d`、文字梯度 `#14532d/#064e3b/#052e16`（8.7/4.79→8.7/9.28）、禁用 `#86efac→#4d7c5f`；blue 描边 `#1e293b→#334155`（原与 raised 同色，描边不可见）。
- **接线**：14 处“白字主按钮/选中态”底色改用 `--primary-fill`（`.p-button-primary`、分页高亮、下拉选中、悬浮工作台按钮、步骤指示器、加载更多等），
  `style.css :root` 补静态默认值，`applyThemeToDom` 注入新变量。
- **验证**：`web/src/config/theme-spec.test.ts` 30 例（四主题 × 7 条契约 + 族内透明度一致 + dangerBg 派生一致性）；
  已有 `a11y-contrast.test.ts` 7 例；前端四件套（type-check/lint/test/build）全绿。
- **观察**：green 主题文字色整体压深后，界面观感偏“深绿”，如需更轻可在不破坏契约的前提下微调（阈值写死在测试里，改值会被拦）。

### 92. 公告列表只显示最近 100 条（LIMIT 100）+ 历史补抓脚本（2026-11-20）

- **现象**：用户把抓取起点设为 2022-01-01 点“立即抓取”，列表仍只到 2024 年第 22 号，怀疑没抓到。
- **取证**：直接查生产 DB——`announcement_record` 里 GB 有 **2,850 行**日期为 2022 年，`2022年第5~9号` 都在；
  抓取本身没问题。真正原因在 `docker/api/announce.py::_build_announce_results_query` 末尾的 **`LIMIT 100`**：
  三个来源都恰好返回 100 条（hb/db 每年 12 条，100 条正好覆盖 2018–2026；GB 公告多，100 条只到 2024-09）。
- **修复**：列表改服务端分页——端点接 `page/page_size`（默认 1/50，上限 200），去掉硬编码 LIMIT，响应加 `total/page/page_size`；
  前端 `getAnnounceResults(source, from, routeTag, page, pageSize)`，`AnnounceView` 用 `totalRecords` 驱动 Paginator，翻页/改每页条数都重新取数。
- **验证**：`tests/test_api_announce_results_headers.py` 新增 2 例（两页不重叠 + total 正确、默认 50）；
  `AnnounceView.test.ts` 11 例（含服务端分页参数断言）。
- **历史补抓**：新增 `scripts/backfill_announce_archive.py`——遍历 `announcements` 表 945 条公告，逐条调
  `POST /api/announcements/{no}/reparse?source=...` 重新抓取，让新归档逻辑把历史 HTML/附件落盘；
  断点续跑（状态在 `%TEMP%/pilotstd_archive_backfill.json`）、默认 1.5s/条、失败不中断。
  用法：`python scripts/backfill_announce_archive.py --dry-run` → `--limit 20` → 全量。
  **必须先部署含归档代码的版本**，否则重抓也不会写文件。

### 93. 公告归档统计端点 + 历史补抓实况（2026-11-20）

- **新增** `GET /api/system/archive-stats`（admin，只读）：返回归档根目录、是否存在、HTML/附件分来源计数、
  总体积与前 10 个样例文件名。用途是核对补抓是否真的落盘——`/api/files` 只允许 standards/inbox，
  看不到 `data/announcements`，没有这个端点就只能靠登主机查目录。
- **补抓实况**：`scripts/backfill_announce_archive.py` 已在生产（v0.197.1）跑起来，945 条历史公告逐条 `reparse`；
  断点状态写 `%TEMP%/pilotstd_archive_backfill.json`，实测约 10s/条（详情+附件+解析），全量预计数小时，可随时中断续跑。
- **注意**：`attachment_path` 字段只在解析结果字典里，`announcement_record` 表**没有这一列**（此前误以为“字段恒空”，
  实际是压根没落库）；归档的验收口径是**磁盘文件**，不是 DB 字段。
- 验证：`tests/test_api_archive_stats.py` 2 例（计数/字节/样例、目录不存在）。

### 94. 设置页「界面语言」下拉消失（computed ref 未解包，2026-11-20）

- **现象**：设置 → 界面，只剩“界面语言”标签，右侧下拉框不见了（截图）。同一 Tab 的登录页背景图等也可能整块不渲染。
- **取证**：Playwright 打开 `/settings?tab=ui`，页面报
  `TypeError: this.visibleOptions.findIndex is not a function`，Tab 内容区为空。
- **根因**：2026-07-01 `87b36f0b` 把逐项 prop 改成 `v-bind="tabProps"` 时，同一行里 `selectedLocale` 取了 `.value`，
  但 `localeOptions` 仍是 **computed ref**；`v-bind` 不会深解包，PrimeVue `Select` 拿到 Ref 后把 `options` 当数组用，
  `visibleOptions.findIndex` 直接崩，整个 Tab 渲染中断。
- **修复**：`SettingsView.vue` 的 `tabProps` 里改成 `localeOptions: localeOptions.value`，并加注释说明“不能传 ref”。
- **验证**：dev 环境 Playwright 复查——`#lang-select` 存在、宽 200、可见，标签显示“简体中文”，无 pageerror；
  `SettingsView.test.ts` 新增源码级回归断言（该行必须取 `.value`），9 例通过；前端四件套绿。
- **同类排查**：同一 `tabProps` 里 `sections: systemSections.value` 已解包、`selectedLocale.value` 已解包，只有这一处漏。

### 95. 生产验证四连：U-3 / G-03 / A-46 / superseded_by 演练（2026-11-20）

- **U-3 保存链路（已授权，已执行）**：GET 配置（key/password 掩码 `***`）→ 原样 PUT 回写 → 再 GET：
  `cookie_source`、`cookie_status`、`cookiecloud_url`、`enabled` 全部未变，PUT 返回 `{"ok":true}`。
  说明掩码回写不会把状态/来源打坏；真实密钥未被覆盖由后端跳过逻辑 + `test_masked_secret_not_overwritten` 保证。
- **G-03 探针复跑（已授权，已执行）**：`POST /api/adapters/health/run` 3.8s；
  `found 6 / no_result 4 / error 0 / probe_pending 11`，与复跑前一致。**11 站仍 pending，原因不是没跑**：
  查 `standard_info_cache` 整表 **0 行**，没有 exact 缓存可补 → `discover_probes()` 无数据可用。
  这是新问题（缓存写入/TTL 链），已登记 G-26。
- **A-46 重扫（已授权，已执行）**：`POST /api/scan-and-index` 15.2s，`indexed=0 / skipped=825 / failed=0`；
  `pending_lookup` 里 `file_missing` 仍 **33 条**未变。结论：不是“缺重扫窗口”，是扫描/匹配逻辑对这批文件无效，需再查。
- **superseded_by 演练（已授权演练，未全量）**：
  - 备份：`POST /api/backup/create` 成功；列级备份表 `announcement_record_bak_20261120`（232,668 行）。
  - 非空行实测 **32,432**（方案文档写的 49,306 是旧数）。
  - 从 3,000 条候选中取 100 条「单值且年份倒退」，其中**仅 33 条可安全演练**——另外 67 条的目标旧标准行**本身已有 superseded_by**，
    直接写会覆盖既有信息 → **迁移规则必须先定**（仅空才写 / 追加 / 保留较新者）。
  - 33 条应用 + 按备份表回滚，样例 `GB/Z 31477-2026 → GB/Z 31477-2015` 双向验证通过；演练后库已回滚到演练前状态。

### 96. A-27 补配置写入口 + V-17 清零（2026-11-21）

- **A-27 真实缺口**：菜单客户端（企微/飞书/Telegram/钉钉）与 `POST .../menu/sync` 都已在线，`GET .../menu/status`
  在生产显示 `wechat supported=true enabled=false`、`telegram supported=true enabled=false`、`feishu supported=false`
  （缺 `chat_id`）——**菜单配置没有任何写入口**，`notification.menus.*` 只能手改 config.json，所以“四家全做”卡在没配置路径。
- **本批补齐**：新增 `PUT /api/notification/menu/config`（admin）：
  - 复用 `menu_from_config`/`validate` 校验（一级 ≤3、二级 ≤5、Telegram ≤3 命令、group 才可有子项、order 连续）；
  - 钉钉启用直接 400（平台无服务端菜单 API，见 02-accepted #9）；飞书启用必须给 `chat_id`；
  - 落 `notification.menus.<channel>.enabled/items/(chat_id)`，并把 `last_synced` 置空，保证下次 sync 真下发；写审计。
  - 7 例测试（3×5 合法、超限、未知渠道、钉钉、飞书缺 chat_id、飞书带 chat_id、停用空配置）。
- **V-17（G-012 注释语言）**：全仓 `check_g_012_comment_density` 从「0 阻断 + 3 警告」清到 **0 阻断 + 0 警告**
  （`organize.py` / `config/defaults.py` / `file_utils.py` 三处裸英文词改中文），`1511 → 0` 正式收口。

### 97. 更正与查证（2026-11-21）：G-26 误判、U-1 根因、A-46 文件、迁移方向

- **G-26 更正（我上一轮查错了）**：上一轮用 `SELECT site, match_status ...` 查 `standard_info_cache`，这两列在表里
  **都不存在**，查询报错被我当成“0 行”，于是写了“整表为空”。实测：**939 行**（`source=network` 全部），
  列名是 `standard_number/source_site/result_json/...`；`result_json` 里 939 行都含 `"match_status": "exact"`。
  真正原因：11 个 `probe_pending` 站点里，**只有 njbz365 在缓存里有数据（157 行）且它已被固定探针覆盖**，
  其余 9~10 个站点在缓存里**一条都没有** → 探针自动发现无料可用。属“这些适配器从未返回结果”，不是探针机制坏了。
- **U-1 旧值来源**：`_apply_validity_result` 的旧值取 `SELECT status FROM standard_validity WHERE standard_number=?`
  （`_validity_pipeline.py:193-194`），**不是** `last_status`。实测 824 行 validity：`未知 740`、`现行 66`、`即将实施 16`、
  `废止/作废 各 1`；740 条「未知」的 `last_changed_at` 全为空、`check_count` 为 1~2（检查跑过）。
  结论：旧值不是“读不到”，而是**这批标准的检查结论本身就是「未知」**（查询没命中来源），所以显示「未知 → 现行」。
  显示层修（空→未知）只是文案兜底，根因在覆盖：这些标准在查询源里查不到，检查器只能给未知。
- **A-46 33 条 file_missing**：样例路径全在 `/inbox/...`（不在 `/standards`），用 `/api/files` 逐条核对**文件确实不存在**；
  这 33 条是历史遗留的 `/inbox` 路径，文件已被整理/移动，属**陈旧 pending**，不是扫描匹配失效。
- **superseded_by 方向**：抽样 4,000 行，方向倒退 **3,695（92%）**、已是正向 1、无法判年 304；
  再看这 33 个「目标旧标准行」的已有值，**没有一条是正向**（也是旧的/乱的）→ 迁移规则可采用「仅当目标行为空才写」，
  已有值的 23 条需先清洗，不适合直接覆盖。

### 98. 自查回归：V-17 清零后又引入 1 条 [LANG]（2026-11-21）

- 21 条已闭合项重验在 HEAD `e448158f` 上扫出 `docker/api/notification_menu.py` 注释里的裸词 `sync`，
  `[LANG]` 从 0 回到 1 —— 与本批“V-17 清零”同批，属自查不严。
- 修复：该注释里的 `sync` 加反引号；全仓复跑 0 阻断 / 0 警告，菜单配置 7 例测试通过。
- 教训：`[LANG]` 只是警告不阻断，新增注释必须自己按“中文 + 标识符加反引号”写，不能等门禁拦。

### 99. 补抓失败里的 3 条修改单：全角分隔符 + 混合措辞（2026-11-21）

- **现象**：`reparse` 对 2013年第12号 / 2014年第12号 / 2015年第34号 返回 `produced no records`（历史 0 条）。
- **根因两类**：
  1. 全角分隔符：标题是 `GB／T 27967－2011`（`／` U+FF0F、`－` U+FF0D），`_parse_amendment` 的正则只接受半角 `/` → 匹配失败返回 0；
  2. 混合措辞：`…第1号修改单等3项国家标准修改单的公告` 命中 `_is_amendment` 的“N 项…”批量排除规则，
     被当作普通清单公告去解析正文，正文没有清单 → 0。
- **修复**：`_parse_amendment` 先 `unicodedata.normalize("NFKC")` 再匹配（全角转半角）；
  `_process_one_detail` 增加回退——正文解析为空且标题含「修改单」时，用标题提取兜底。既有分类语义不变。
- **测试**：`tests/test_announcement_base_full.py` 新增 2 例（全角标题、`等N项…修改单`），该类 63 例全过。
- **剩余**：2015年第7号（国家标准样品，解析出 0）与 2018/2019 三条（详情页返回空壳）未修，属数据源/支持范围问题，见 G-34。

### 100. superseded_by 迁移脚本落地（2026-11-21，本地可跑，未执行全量）

- **脚本**：`scripts/migrate_superseded_by_direction.py`，三档用法：默认演练、`--limit N` 小批、`--apply` 写库、
  `--rollback plan.json` 回滚；`--apply` 前自动建列级备份表 `announcement_record_bak_<日期>`。
- **两阶段写入**（演练中发现并修正）：先把所有倒退值清掉，再给“此时为空”的目标旧标准行补反向指针。
  单循环会互相阻塞——目标行自己也是倒退值时，先回填再清理等于白写。
- **回滚范围**（演练中发现并修正）：只按源行 id 还原会漏掉被回填的目标行（它们不在计划里），
  改为「源行 id + 目标标准号」一起按备份表还原；单测覆盖了这条。
- **测试**：`tests/test_migrate_superseded_by_direction.py` 6 例（年份解析、中英文逗号拆分、单向/多值/无年份、
  两阶段写入、回滚含目标行）。
- **规则依据**（`27` #97 数据实证）：抽样 4,000 行 92% 方向倒退；33 个目标行已有值无一条正向 →
  规则定为“只写空位 + 已有乱值交给清洗”，脚本严格按此实现，不覆盖既有值。

### 101. 补只读隔离区统计端点（G-05 重验“无法复现”的缺口，2026-11-21）

- **问题**：`/api/files` 只允许 `standards`/`inbox` 两个根，`data/_quarantine` 看不到，
  “30 个物理副本”这类结论在生产无法自证 → 21 项重验里 G-05 只能判“DB 吻合、文件无法核对”。
- **修复**：新增 `GET /api/system/quarantine-stats`（admin，只读），复用归档统计的通用扫描
  `_scan_tree(root, primary_ext)`；返回目录、是否存在、文件数、总字节、按子目录分布与样例。
- **测试**：`tests/test_api_archive_stats.py` 增 2 例（PDF 计主类型/非 PDF 计附件、目录不存在），共 4 例通过。

### 102. A-27 飞书群发现 + U-1 根因修复 + 迁移前提查证（2026-11-21）

- **A-27 四渠道现状**（代码层已全写，真实下发等生产机器）：
  | 渠道 | 菜单能力 | 实现 | 缺口 |
  |---|---|---|---|
  | 企微 | 3 一级 + 5 二级 | `WecomMenuClient` get/create/delete | 需部署后 `PUT menu/config` + `sync` |
  | 飞书 | 群菜单（3+5） | `FeishuMenuClient` get/create/delete | **本批补 `list_chats()`**，chat_id 可自动发现 |
  | Telegram | 3 命令 | `TelegramCommandClient` setMyCommands | 需部署后配置命令并 sync |
  | 钉钉 | 无服务端菜单 API | `DingtalkMenuClient` 显式 unsupported | 平台限制（02-accepted #9），非实现缺口 |
  新增 `GET /api/notification/menu/chats?channel=feishu`（admin，只读）：列出机器人所在群（chat_id+名称），
  供 `PUT /api/notification/menu/config` 自动填 chat_id。测试 4 例（客户端 2 + 端点 3，共 24 例菜单类通过）。
- **U-1 根因（回答“为什么旧状态为空”）**：不是读库失败。`update_status` 只在**状态变化**时写 `last_status`，
  而首次入库（`register_new_standard` 与首次检查 INSERT）从不初始化它 → 生产 740/824 行 `last_status` 恒 NULL，
  界面“上一状态”永远空。**属入库/更新路径缺初始化**。
  修复：① 登记入库即写 `last_status=未知`；② 首次检查 INSERT 写 `last_status=本次状态`；
  ③ 未变化分支对历史遗留 NULL 做一次性回填。新增 `tests/test_validity_last_status.py` 4 例。
- **迁移前提查证（`--check-existing`）**：原规则“只清倒退、空位补反向”是否存在误伤，取决于目标行已有值方向。
  脚本新增只读模式，输出「目标行总数 / 方向正确 / 本身倒退 / 无法判年 / 为空」。
  本地两个库（`data/pilotstd.db` 与其备份）`announcement_record` 均为 0 行，无法离线取样；
  生产不可达期间以既有实测为准：4,000 行样本中方向倒退 3,695（92%），33 个目标行已有值**方向正确 0 条**。
  规则安全性由构造保证：只清 `year(sup) < year(std)`，方向正确的值不在清理集合内（单测 `test_check_existing_*` 锁定）。

### 103. D-2 阶段 1 三缺口落地 + 企微构造参数错位（2026-11-21）

- **缺口①（28 个事件无出厂渠道）**：不改 44 条事件声明，改**投递回退**——
  `NotificationPolicyHelper.get_channels_for_event` 在“策略表无行 + config 规则为空”时，
  回退到**当前已启用的渠道**（`notification.channels.<ch>.enabled`）。
  效果：用户配了哪个渠道就收得到全部事件，新装用户不再只收 16/44；未配置渠道不会被尝试。
  测试：`tests/test_notification_policy_fallback.py` 6 例（含“显式规则优先”）。
- **缺口②（message.link 四渠道不渲染）**：构建期用 `_links.absolutize_message_link()` 把
  `/standards/xxx` 拼成 `notification.web_base_url` 下的绝对地址（未配置/回环则清空，不给坏链）；
  渲染层新增 `detail_link_line()`，基类 `render()` 统一追加，飞书/钉钉卡片各自追加。
- **缺口③（级别跨渠道不可见）**：新增 `level_prefix()`（warning/error 才加），
  在基类 `render()`、飞书卡片标题、钉钉卡片正文统一体现；info 不加噪声。
- **企微测试连接参数错位**：`_format_utils.do_test_send` 里 `cls(corpid, agentid, corpsecret)` 与
  `WechatChannel(webhook_url, corpid, agentid, corpsecret, ...)` 六参数签名错位一位，
  应用形态测试连接实际拿 webhook_url=corpid、corpid=agentid…；改为关键字传参，
  新增 `tests/test_notification_wechat_test_connection.py` 锁定。
- 补充：i18n 三语新增 `notification.renderer.detail` / `level.warning` / `level.error`；
  `manager.py` 因 G-049 体积上限，把链接绝对化下沉到 `_links`（有效行回落至上限内）。

### 104. G-02 批次结果落表 + G-13 级别口径确认（2026-11-21）

- **G-02**：`query_batch_parsed` 此前只把 `validate_failed` 写进 `query_metrics`，
  `found`/`not_found` 从未落表（所以“61 条重查 found=3/not_found=58”只能从日志还原）。
  新增 `record_result_metrics(metrics, results, total)`：按 `QueryResult.is_found()` 计 found，
  `not_found = total - found`（total 用入参，防止分桶丢项被算成 0 漏命中），在 `finally` 持久化前写入。
  测试：`tests/test_batch_result_metrics.py` 3 例。
- **G-13 口径确认（不是统计偏差）**：`docker/api/notification_logs.py:122` 的 `_business_level()`
  是**纯 event_type 映射**——`security_alert → warning`、`task_failure → error`、其余 `info`，
  与投递 `status` 无关、无时间窗聚合。因此“100 条里 info/warning 数”只随**最新 100 条的内容**变化；
  声称 68/32、实测 66/34 属窗口内容变化（新增日志构成不同），统计逻辑无偏差，不改。

### 105. 追问回复：零渠道行为 / G-13 更正 / U-1 回填方式 / A-46 本地可查性（2026-11-21）

- **零渠道用户（D-2 缺口①的真实边界）**：改投递回退之前，策略表无行 + rules 为空 ⇒ 返回 `[]`
  ⇒ `_dispatcher` 只记 `logger.info` 就 return，**DB 不落任何行** ⇒ 站内完全看不到，等于静默丢弃。
  上一批回退到“已启用渠道”只解决了“配了渠道但策略表没行”的用户，**零渠道用户仍 0/44**。
  本批补强：零渠道时写一行 `channel='none'`、`status='skipped'` 的记录（可用
  `notification.record_unconfigured_events` 关闭），前端把 `none` 显示为「未配置渠道」
  ⇒ 至少“丢了什么”在站内可查。测试：后端 2 例 + 前端 1 例。
  仍未做（记为缺口 G-45）：首次登录引导配置渠道（前端提示），需要产品文案与交互设计。
- **G-13 更正**：上一批我写“68/32→66/34 属窗口内容变化（新增 2 条 info）”，**这句自相矛盾**——
  若新增 2 条 info，应为 70/32 而不是 66/34。正确说法：100 条窗口内 info 净减 2、warning 净增 2，
  要定论必须拿到两个时点的 `event_type × level` 分布；当前生产不可达，**结论降级为“待核实”**。
  核实 SQL：`SELECT event_type, COUNT(*) c FROM notification_log GROUP BY event_type ORDER BY c DESC;`
  再按 `ORDER BY id DESC LIMIT 100` 取窗口分布对比。判定标准：若窗口内 warning 类（`security_alert`、
  `task_failure`）行数确为 34，则 66/34 正确、口径无偏差；若 event_type 分布与 68/32 相同，则是统计口径问题，需修。
- **U-1 历史回填方式**：**是代码自动触发，不是独立脚本**。`ValidityChecker.update_status()` 的“状态未变化”
  分支里带 `last_status=COALESCE(NULLIF(last_status,''), status)`，因此某标准**下一次被检查时**才会回填；
  没有一次性全表脚本、也未在生产跑过（需要一次 validity 检查，属生产写操作）。
  明天验证口径：跑一轮检查后 `SELECT COUNT(*) FROM standard_validity WHERE last_status IS NULL` 应从 740 降到“未被检查过的行数”。
- **A-46 本地可查性**：**缺数据，不缺环境**。本地 `data/pilotstd.db` 与 `data/backups/*.bak` 的
  `announcement_record` / `file_index` 均为 0 行，仓库里也没有 `/standards` 目录（`standards/` 不存在），
  无法复现“825 跳过、33 找不到”。已确认的事实是：那 33 条的 `file_path` 全在 `/inbox/...`，
  且 `/api/files` 逐条核对文件**确实不存在** ⇒ 属陈旧 pending，不是匹配算法失效。
  若要在本地复现匹配逻辑，需要一份 `/standards` 目录 + 对应 `file_index` 快照（生产数据）；
  代码层可以补“路径不存在 → 记 file_missing”的单测（构造临时目录），这不依赖生产。

### 106. 本地收尾四项：G-45 引导 / A-46 判定 / 能力矩阵 / 菜单注册表（2026-11-21）

- **G-45 首次配置引导**：通知设置页在“所有渠道都未启用”时显示醒目提示——
  「还没有配置任何通知渠道，事件仍会记录到通知日志但不会推送，请在下方启用一个」。
  数据源是已加载的渠道 spec + 各渠道 `enabled`；spec 未加载时不算零渠道（不闪误报）。
  测试：`NotificationConfig.test.ts` 增 2 例（零渠道显示 / 有渠道不显示），共 19 例通过。
- **A-46 本地判定（不依赖生产）**：新增
  `pending_service.resolve_reason(record, exists)` 与 `mark_missing_files(db, limit)`——
  有路径但文件不存在 → `file_missing`（幂等，只改 reason，不删行、不移动文件）。
  此前代码里**没有任何地方写 `file_missing`**（该值只存在于历史数据），这是缺口。
  测试：`tests/test_pending_file_missing.py` 2 例，用临时目录构造“存在/不存在/空路径”三种情况。
  默认不接定时任务或 API，调用点后续单独评审。
- **能力声明（D-2 模块化缺口）**：`ChannelCapabilities` 增 `supports_image` / `supports_mention` / `supports_buttons`，
  并新增 `channel_capabilities(channel)` 单一来源矩阵（按各渠道渲染器实际能力声明，不按渠道名猜）：
  企微 `mention=True`（`touser=@all`）、飞书/Telegram `buttons=True`（卡片 action / inline_keyboard）、
  钉钉全 False、四家 `image=False`（通知链路不发图）。
  测试：`tests/test_notification_channel_capabilities.py` 4 例（含未知渠道全 False）。
- **菜单写死分支**：`menu/service.build_client` 的 if/elif 链改为 `MENU_CLIENT_FACTORIES` 注册表
  （四个工厂函数），加渠道只需登记一次；未知渠道仍落钉钉 unsupported 客户端（行为不变）。
  测试：同文件断言注册表键与 `MENU_CHANNELS` 一致、四渠道解析到预期类。

### 107. mark_missing_files 入口：定时（带挂载保护）+ 手动端点（2026-11-21）

- **定时任务** `pending_missing_check`：默认每天 03:30 UTC（`pending.mark_missing_cron`），
  可用 `pending.mark_missing_enabled=false` 关闭；挂在调度器启动注册处，与 validity/health 等并列。
- **挂载保护**：复用 `file_index._is_mass_delete_anomaly`（≥50 行且缺失比例 ≥90% ⇒ 疑似挂载/根目录未就绪）。
  命中时整轮跳过、`skipped=true`、只留 WARNING，**一条都不改**——避免一次根目录异常把整表 pending 误标。
- **手动端点** `POST /api/pending/mark-missing`（admin）：只读扫描 + 改 reason，不删行、不移文件；
  返回 `checked/missing/updated/skipped`。不做前端按钮（按需 curl 调用）。
- **测试**：`tests/test_pending_mark_missing_entry.py` 5 例——挂载保护跳过（100 行全缺失）、
  小批量标记 + 幂等（第二次 updated=0）、`protect=False` 可关闭、非 admin 403、admin 返回统计。
- 配置键：`pending.mark_missing_enabled`（默认 true）、`pending.mark_missing_cron`（默认 `30 3 * * *`）。

### 108. 设计令牌治理：审计 → 缺陷修复 → 全量替换 → G-055 门禁（2026-11-21）

> 全链路 14 个提交（本地未合并），PR #9 draft，CI/CD + Deep Gate 双绿。

| 阶段 | 改动 | 提交 |
|---|---|---|
| 令牌层 | 新增 `web/src/styles/design-tokens.css`（63 令牌，无颜色字面量）+ `main.ts` 接线 | `2bc21202` |
| 缺陷修复 | D1 未定义变量 11 名/26 处清零、D2 默认层漂移、D4 失效引用、D5 文档字面量 + 6 例回归测试 | `53b7d3ee` |
| 审计 | `scripts/audit_design_tokens.py` + `docs/design-token-audit.md`（A 979 / B 115 / C 628 / D 0） | `6fd9cb04` |
| 试点 | `NotificationBell.vue` A 17 条 + 1 条 TODO | `cdee6c46` |
| 全量替换 | settings 118 / dashboard 204 / views 272 / components 333 / style.css 35，**共 979 条 A 类** | `e0fdd780` `fd9b5c69` `231cd5cc` `9d0ec26b` `b48c7e77` |
| 文档刷新 | 报告按替换后代码重跑（A 0 / B 115 / C 628 / D 0），补试点与全量记录 | `10585bd1` `075387ee` `b64741be` |
| 门禁 | **G-055** 棘轮：A=0；B/C 不得超过基线次数；基线 611 条目/18 组；接入 `check_all.sh --fast` + CI | `00097f12` |
| CI 修复 | PR 路径两处既有缺陷：G-029 范围表达式、deep-gate 缺 pytest（+3 例回归守卫） | `bc061a9f` |

**验证**：每批四件套（type-check 0 / lint 0 errors·304 warn / vitest 421 passed / build 0）；
`check_all.sh --fast --guards --local` 与 `--ci` 均 exit 0；PR #9 的 CI/CD（10 success/3 skipped）
与 Deep Gate 均 success，G-055、G-029、GUI 步骤级 success。

**回滚**：**文档类提交（7-1/7-3）必须逆序**（先撤 §12 交付摘要 → 再撤本文件与债务台账回写 → 最后撤能力矩阵时间戳）——§12 引用了本批定义的 A-50/A-51/A-52 与 V-19，先撤本批会让引用悬空；代码类提交按粒度独立回滚。令牌文件（`2bc21202`）与缺陷修复（`53b7d3ee`）是其余替换的前提，单独回滚它们会让 `var()` 失去定义；删基线后 G-055 以 exit 2 报"基线缺失"，不会静默通过。

**遗留**：DT-12（`--warning` 圆点 2.15/2.05）、2 条内联白名单、B 类 115 总账、`no-literal` 177 口径风险
（分别见 `docs/debt/03-open.md` A-50/A-51/A-52 与 `04-watch.md` V-19）。

### 109. A-50 状态色 `--warning` 对比度修复（2026-11-21）

- **取证**（`ci.tmp/a50_contrast.py`，WCAG 2.x）：现值 `#f59e0b` 在 light-bg 1.96、light-surface 2.15、
  green-bg 1.91、green-surface 2.05 —— LogBar 的 `log-warn` 是**正文文字且背景为 `--bg`**，需 4.5:1；
  NotificationBell 的 `.item-dot` 是非文本 UI，需 3:1。
- **候选实测**：`#b45309` green-bg 4.46（差 0.04 不达标）；`#ad4f08` light-bg 4.92 / green-bg 4.79 / light-surface 5.39 → **选定**。
- **改动**：`themes.ts` light/green 的 `warning` 与 `warningBg`（色相跟随、alpha 0.12 不变）；`style.css` 默认层同步两值
  （D2 教训：两处必须一致）；dark/blue 不动，复测 8.31 / 8.69。
- **测试**：`a11y-contrast.test.ts` 增「四主题 warning on bg ≥ 4.5」4 例；该文件 11 例、theme-spec 30 例通过。
- **视觉影响**：状态色变深（非品牌色）；影响 `NotificationBell` 圆点、`LogBar` 文字、`.mp-badge-warning`，已登记 §12.4.1。

### 110. A-51 内联高度改组件属性（2026-11-21）

- `SystemResources.vue:49`：ProgressBar 原生支持 `dt`（`dt('progressbar.height')`）→ `:dt="{ height: 'var(--size-24)' }"`。
- `PendingView.vue:90`：ProgressSpinner 在 PrimeVue **4.5.5 没有 size/height prop**（样式里 width/height 是字面量 100px，
  `dt` 只覆盖四种颜色）→ 只能经 **`pt`（passthrough 组件属性）** 注入：`:pt="{ root: { style: { width: 'var(--size-20)', height: 'var(--size-20)' } } }"`。
  未新增 class、未改模板结构（只替换属性）。
- 新增两个尺度令牌 `--size-20` / `--size-24`（放在 `:root` 内，非颜色；首版误放在右括号外导致 lightningcss 报
  “Invalid token in pseudo element”，已修正）。
- 结果：G-055 当前命中 0 次、基线仍记 3 条 → 输出 `[STALE]`（非阻断）。基线更新按规矩**单独提交 + 人工确认**，本提交不动基线。

### 111. P2（D2 结构性）：默认层与运行层校验扩到全量映射（2026-11-21）

- **问题**：`design-tokens.test.ts` 只校验 `:root` 与 light 的 4 个变量（bg/surface/surface-raised/border），
  其余三主题无校验，新增颜色键漏接线不会被发现。
- **做法**（纯测试，未改任何令牌值）：
  1. 从 `applyThemeToDom` 源码解析 `'--var': c.prop` 映射（单一真相来源），断言映射内每个 prop 在**四主题**都存在；
  2. 每主题每个映射值非空；颜色型值（`#`/`rgb` 开头）形态校验，`focusRing` 这类阴影串不套颜色正则；
  3. `:root` 默认层与 light 主题**全量**逐项比对（支持 `var()` 别名解析，如 `--accent: var(--primary)`）；
  4. 覆盖断言改为“除已登记死键外不漏接线”。
- **测试发现（登记 A-53）**：`disabledBg` / `disabledText` 在四主题都有值，但 `applyThemeToDom` 未映射、
  `style.css` 也无声明 → **死键**。按 P2 约束（不得为过测试改值）只登记，不接线。
- **结果**：`design-tokens.test.ts` 9 例通过（原 6 例 + 新增 4 例 - 合并重复 1 例）。

补充记录（裁决条件②）：
1. **PrimeVue 4.5.5 的 ProgressSpinner 无 size/height prop**：其 `@primeuix/styles` 里 `.p-progressspinner{width:100px;height:100px}`
   为字面量，`dt` 仅覆盖 `color.one..four`；故采用官方 `pt`（passthrough）注入 `var(--size-20)`，**作用域为该组件实例**。
2. **不泄漏**：同页只有这一个 spinner；`AnnounceDetail.vue`、`LegacyRedirect.vue` 的 spinner 未加任何覆盖，保持默认尺寸。
3. **验收方式**：未新增渲染断言（仓库无该组件的渲染测试），尺寸正确性靠构建通过 + 视觉/人工验证；
   构建期已验证 `pt` 绑定被正确编译（`pnpm build` 通过）。
4. **回退 TODO**：若后续 PrimeVue 提供 size prop，改回组件属性并删 `pt`，不新开债号（挂在 A-51 关闭说明）。

### 112. P3：G-013 规则 0 增加“纯文档提交”豁免（2026-11-21）

- **背景**：`26-fix-dossiers.md` 文件名含 `fix`，纯文档提交被规则 0 判成“缺陷修复提交”而阻断。
- **实现**：`check_g_013_test_coverage.py` 新增 `is_docs_only()`；规则 0 在“消息命中 fix/bug 词”时先判纯文档：
  改动**非空且全部**在 `docs/` 或 `*.md` → 放行；含任一代码/脚本/配置路径或空列表 → 按原规则阻断。
  未触碰与审计脚本共用的 `classify()`。
- **测试**：`tests/test_check_g_013_bugfix_message.py` 由 6 例扩到 10 例——纯文档放行 / 含代码阻断 / 混合阻断 /
  空列表不豁免；原“docs-only 必阻断”用例改为“含代码才阻断”。
- **登记**：`gates.md` G-013 行、`ci-lessons.md` 一条、审计报告 §12.4 G-013 行改“已修”。

### 113. P4：V-19（`no-literal` 收紧）只读评估（2026-11-21）

- 报告：`docs/analysis/2026-11-21-v19-assessment.md`（未改门禁、未改基线）。
- 关键数字：`no-literal` 177 条 = **非视觉 134**（`0/none/auto/transparent/unset`）+ **布局单位 42**（`100% 33 / 100vh 4 / 1fr 3 / fit-content 2`）；
  收紧布局单位 → **+42 阻断**（非 177）；再纳入非视觉值 → 91 条量级，噪音过大。
- overlay：196 处 / 20 个 alpha 取值，集中 ≈0.06·0.12·0.30·0.85；统一 4 档有可见视觉变化 → **维持现状**，登记 **V-20**。
- 阴影：47 处声明 / 20 个不同值，其中 33 处已用令牌、**仅 14 处原生** → 只映射到既有层级，不新拆。
- 裁决落地：布局单位**分批**收紧（先 `100%` 33 条，再 `vh/fr/fit-content` 9 条），134 条非视觉值维持观察。

### 114. P5-1：`--text-on-primary` 令牌 + 主色底白字替换（2026-11-21）

- **新增令牌**：`ThemeConfig.textOnPrimary`（四主题均 `#ffffff`）→ `applyThemeToDom` 映射 `--text-on-primary`；
  `style.css` 默认层同步（D2 口径：两层必须一致）。
- **替换 6 处**（背景确为 `--primary-fill` / primary 渐变者）：`RouteDebugPanel`、`TableLoadFooter`、
  `UnifiedFilterBar`、`AppLayout`、`SettingsView`、`TaskView`（`.step.running`）；同时删除其上方已过期的
  “无精确令牌”TODO。
- **未替换（语义不符）**：`HomeView`（danger 底）、`TaskView` 的 success/danger 步骤、`RegisterView`
  登录页深色渐变上的白字 —— 它们不在 `on-primary` 语义内，保持字面量并留在 A-52 观察。
- **测试**：`a11y-contrast.test.ts` 增「四主题 on-primary on primaryFill ≥ 4.5」4 例（该文件 15 例）。
- **数字**：G-055 `B 113→107`、总命中 740→734；基线/审计 §0·§11/A-52 三处同步；STALE=0。

### 115. P5-2：原生阴影映射评估——无可精确映射项（2026-11-21）

- 逐条比对 13 条原生 `box-shadow` 与既有令牌（`--shadow-xs/sm/md/lg`、`--focus-ring`、`--button-primary-shadow`）：
  **没有一条半径/扩散/透明度完全相等**；其中既有 `--shadow-md` 为 `0 8px 16px -6px`，而原生多为
  `0 4px 12px`/`0 6px 16px`/`0 2px 8px` 等，替换会产生可见视觉变化。
- 按裁决“不强行映射”：**只加 TODO 标注 13 条**（注明“与既有层级不匹配，待统一评估（A-52）”），
  **不新拆 `--shadow-*` 层级**、不改任何阴影值；G-055 数字不变（A=0 / B=107 / C=627，STALE=0）。
- `box-shadow: var(...)` 的既有 33 处不受影响；A-52 阴影子项已登记。

补记（2026-11-22）：P5-2 分支因 A-52 冲突做过一次 rebase（force-push），使 PR 事件里的 `github.event.before`
指向已不可达的旧 head，`repo-compliance` 的范围检查因此判“显式范围 0 变更”而红（run 44971267154）。
处置：在分支上追加一次普通提交刷新 before 指针，**不修改任何门禁配置**。
