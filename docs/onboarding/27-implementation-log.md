# 27 · 实施记录（本地代码，未部署）

> 记录本轮已实际修改的代码、测试与回滚方式。  
> 环境：本地开发/验证；**未改生产、未部署**。

---

## 2026-11-09

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
