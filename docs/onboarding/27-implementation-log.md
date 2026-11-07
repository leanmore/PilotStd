# 27 · 实施记录（本地代码，未部署）

> 记录本轮已实际修改的代码、测试与回滚方式。  
> 环境：本地开发/验证；**未改生产、未部署**。

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
