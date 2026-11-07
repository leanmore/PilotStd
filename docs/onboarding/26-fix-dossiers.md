# 26 · 修复 Dossier（L3/L4）

> 目的：把选定问题细化到“可改代码”的层级。每份 dossier 只覆盖一个问题，不再全项目泛读。  
> 状态：**方案级，不是执行记录**；未改代码、未写生产。

---

## D-01 Web 下载件不进入归档

### 现象

Web 五段式执行后，下载成功的文件留在 `/standards` 根目录，不在分类目录、不在 `file_index`、不在 `standard_validity`。

### L3 调用链

| 步骤 | 代码 | 事实 |
|---|---|---|
| 下载 | `web/src/views/TaskView.vue` `postDownload(dlNums)` | `dlNums` 只取 `exact` 非采标，`.slice(0,10)` |
| 下载结果 | `downloadResult.value = dl` | 只用于汇总展示 |
| 规范化 | `TaskView` 用 `scan.files` 生成 `normItems` | 不包含下载件 |
| 归档 | `TaskView` `archiveItems = scan.files` + `normalizeResult` | **不包含 `downloadResult`** |
| API | `docker/api/archive.py` | 只接收 body `items`，每项构造 `ParsedStdInfo`，调 `mgr.archive_standards` |
| 归档核心 | `manager/facade/_organize.py::archive_standards` | 统一入口；写 `file_index`/`standards`/`standard_validity` |

### 根因

`TaskView` 的归档入参只来自扫描件 + 规范化结果；下载结果 `saved_path` 没有转成 `ParsedStdInfo` 加回 `archiveItems`。

### 改法候选

- A：下载成功后，把 `saved_path` 按 `(logical_code, number, year, part)` 构造 `ParsedStdInfo`，并入归档 items；
- B：让 `/api/archive` 支持 `source_path` 来自下载结果，并返回归档明细；
- C：下载完成后单独调用一次 `archive_standards`（会多一个批次/通知）。

### 必须先定的边界

1. 同一标准扫描件 + 下载件重复时，保留哪个？
2. 下载件已在分类目录时，是否跳过？
3. 下载失败/采标跳过是否进入归档汇总？
4. 归档失败时，下载件是否留在根目录？

### 测试

- `TaskView` 单测：`downloadResult` 进入 `archiveItems`；
- API 测试：`/api/archive` 接受下载件；
- 后端：重复/覆盖/路径校验；
- E2E：下载成功后分类目录 + `file_index` 出现。

**就绪度**：前端已实现（下载成功项进入 `archiveItems`，`TaskView.test.ts` 3 passed）；仍待后端重复/覆盖策略确认与部署验证。

---

## D-02 Docker monitor 只 scan+archive / 空目录不清理

### 现象

监控投放文件后，无标准号文件/跳过目录留在 Inbox；空目录不清理；每文件事件扫整个目录。

### L3 调用链

| 步骤 | 代码 | 事实 |
|---|---|---|
| 触发 | `monitor/scheduler.py::_on_file(path)` | 每个文件稳定后触发 |
| 扫描 | `mgr.scan_directory(os.path.dirname(path))` | **扫整个父目录**，不是单文件 |
| 归档 | `mgr.archive_standards(scanned, word_source_root=source_root)` | 只归档解析出的条目 |
| 收尾 | 无 `organize_skipped_dirs` / `organize_fallback` / clean | `_on_file` 不调用 |
| 空目录 | `docker/api/organize.py::clean_empty_dirs` | 只有手动 `/api/clean-empty`，monitor/auto 不调用 |
| 并发 | `if self._mgr is None: self._mgr = StandardManager()` | 无锁，多个 Timer 线程可能各建一个 |

### 根因

`_on_file` 是“单文件回调 + 全目录扫描 + 只归档”，没有批次收尾/清理；`clean_empty` 是独立手动端点。

### 改法候选

- A：`_on_file` 单文件解析，不再扫全目录；
- B：保留全目录扫描，但加去抖/批次，事件合并；
- C：归档后调用 `organize_skipped_dirs` + `organize_fallback` + 空目录清理；
- D：`self._mgr` 启动时注入 + 锁，禁止懒加载竞争。

### 必须先定的边界

1. 监控是否要“查询/下载/兜底/清理”完整链，还是只整理？
2. 空目录清理是否只清 Inbox，还是标准库也清？
3. 每文件事件是否允许重复扫描？

### 测试

- `tests/integration/test_monitor_archive_e2e.py`；
- 多文件同目录并发；
- 无标准号/跳过目录/空目录；
- `auto_archive=false`。

**就绪度**：已实现 manager 锁 + 空目录清理（本地，7 passed）；仍缺“监控是否要完整 auto 链/清理范围”的职责决策。

---

## D-03 无“过期作废”/有效性不落地

### 现象

批次后 `过期作废` 目录为 0；`standard_validity` 746 未知/43 现行/14 即将实施/0 废止（prebatch）；当前 `/api/stats` expired=0。

### L3 调用链

| 层 | 代码 | 事实 |
|---|---|---|
| L1 | `validity_checker.check_standard()` | 公告缓存只信“否定”；名称关键词只作废止正证据 |
| L2 | `QueryEngine.query_standards()` | 查到则 evidence=L2；status 空按现行 |
| L3 | `standard_validity` 历史行 | 返回历史，不产生新结论 |
| 副作用 | `should_apply_side_effects` | 必须 `evidence=="L2"` 且 `validity.auto_move_expired=true` |
| 搬文件 | `_move_expired_file` | 按 code/number/year/part 找 `file_index`；失败回滚；不写废止状态 |
| 采样 | `_sample_due_standards` | `check_ratio` 线上 12；`next_check` 到期 |
| 计数 | `_finalize_validity_round` | 只有 `update_counters=true`（定时任务）才加 |

### 根因候选

1. L2 没有拿到“废止”结论（查询结果/缓存/站点）；
2. `auto_move_expired` 默认 false；
3. `standard_validity` 709 条畸形键，L1/L2 对不上；
4. 历史未知 → L3 自证循环；
5. 手动运行不更新 `checked_count`，看起来“没检查”。

### 必须先定的边界

1. 是否开启 `auto_move_expired`？默认关闭是有意保护。
2. 废止状态集合以 `ABOLISHED_STATUSES_WITH_EXPIRED` 为准；
3. 搬文件失败是否保持原状态（当前是）；
4. 3 条无法还原的 validity 行是否保留。

### 测试

- `tests/test_validity_*`；
- L1 否定/L2 实时/L3 历史；
- 搬文件成功/失败回滚；
- 709 条修复 dry-run。

**就绪度**：v74 迁移已实现（dry-run 副本 803→802，畸形 709→4）；生产执行仍需维护窗口 + `auto_move_expired` 开关决策。

---

## D-04 通知聚合失效 / 页面与通知不一致

### 现象

- 批次 598 次归档调用 → 1196 条通知；
- 未读数 1441 > 列表 578 > 当前用户未读 7；
- `notification_log` 最新 11/3，11/7 批次无记录；
- `archive_complete.body` 为空。

### L3 调用链

| 步骤 | 代码 | 事实 |
|---|---|---|
| 归档 | `_organize.py::archive_standards` | 每次调用 `ensure_batch_key("arch")`；每次发 `archive_complete` |
| 批次键 | `notification.batch.ensure_batch_key` | 外层有 `batch_scope` 才共享；monitor 没有 |
| 聚合 | `NotificationAggregator` | 5s / 50 条；`correlation_id × notify_event` |
| 零计数 | `archive_standards` | `moved=0` 仍发送 count=0 |
| 未读 | `_manager_ops.get_unread_count()` | **无 user_id 过滤** |
| 列表 | `get_logs()` | 有 user_id 过滤 |
| 全部已读 | `mark_logs_read(ids=[])` | 更新全表 |
| 日志内容 | `notification_log` | 只存 title/body，不存 blocks；archive count 在 block |

### 改法候选

- 监控/批量入口包 `batch_scope("arch")`，一次导入一个键；
- `moved=0` 不发 `archive_complete`（或显式 `scan_empty`）；
- `get_unread_count(user_id)` / `mark_logs_read(user_id)`；
- `notification_log` 增 `payload_json` 或把 blocks 摘要写入 `body`；
- 11/7 日志缺失先查清理/恢复/写库失败，不要先改聚合。

### 测试

- 500 文件批量只发 1 条；
- 多用户未读/全部已读隔离；
- 0 搬移不发；
- 日志能还原 count。

**就绪度**：未读数/全部已读已按用户修（本地代码 + 57 passed）；仍缺“11/7 日志为什么没落库”的 L4 证据。

---

## D-05 路由 v2 采样为 0

### 现象

`router_v2_decisions.jsonl` 2133 条全 v1，0 条 v2。

### L3 调用链

| 路径 | 代码 | 事实 |
|---|---|---|
| 开关 | `is_v2_enabled()` | 只认 `ROUTING_ENGINE_VERSION=v2` |
| 单条 | `_single._query_one()` | 先 cache lookup；命中直接 return；`preferred_site` 跳过 v2 |
| v2 记录 | `_query_one_v2()` | 命中/全失败才 `record_decision` |
| 批量 | `_mini_bucket._record_v2_hit()` | 只在 v2 开启时记录 |
| 写入 | `router_v2_metrics` | 异步 daemon；失败只 debug |

### 改法候选

- C（用户已选）：先修“缓存命中/指定站点绕过采样”的采集缺陷；
- 再在验证环境跑 ≥1000 条；
- 不直接切 v2 默认。

### 测试

- `tests/test_router_v2*`；
- 缓存命中、preferred_site、批量路径都产生/解释 v2 记录；
- 写盘 flush/失败可见。

**就绪度**：已加 `v2_skipped` 采样（cache_hit/preferred_site），26 tests passed；真实 ≥1000 条样本待验证环境。

---

## D-06 查询缓存不新鲜

### 现象

517 条 `standard_info_cache`：496 >7 天、417 >30 天、live 517 全 stale；`get()` 不校验。

### L3 调用链

| 步骤 | 代码 | 事实 |
|---|---|---|
| 单条 | `_single._step_cache_lookup` | `use_cache` 且非 `force_refresh` 时 `cache.get()` |
| 读 | `query/cache.py::CacheRepository.get()` | 只查 `standard_info_cache` → `announcement_match` |
| 未校验 | 同上 | 无 `cached_at`/`data_state`/`source_version` 检查 |
| TTL | `active_ttl`/`inactive_ttl` | 定义但未使用 |
| 失效 | `CacheManager.invalidate_by_source` | 标 stale；`CacheRepository` 不调用 |
| 绕过 | `query.use_cache=false` / `force_refresh` | 可绕过 |

### 改法候选

- A：TTL + `data_state` 校验，过期回源；
- B：接 `CacheManager` 版本校验；
- C：显式刷新，保持现状；
- D：先做只读统计/清理。

### 测试

- 过期/未过期/stale/valid；
- `force_refresh`；
- `announcement_match` 回退；
- 性能不退化。

**就绪度**：已实现“stale 不当命中 + put 置 fresh”（本地，14 cache tests + 78 query tests passed）；待部署观察网络回源压力。

---

## 总结

| Dossier | 就绪度 | 阻塞 |
|---|---|---|
| D-01 Web 归档 | 前端已实现 | 后端重复/覆盖策略 + 部署验证 |
| D-02 monitor/空目录 | 部分修复（锁+清理） | 监控职责范围/完整链 |
| D-03 有效性/过期 | v74 迁移已实现 | 生产窗口 + 开关决策 |
| D-04 通知聚合/页面 | 未读数已修；聚合待查 | 11/7 日志缺失 L4 |
| D-05 v2 采样 | 已加 v2_skipped 采样 | 真实 1000 条待验证环境 |
| D-06 查询缓存 | 已修 stale 检查 | 待部署观察回源压力 |

> 这些 dossier 已到“可以评审方案”的层级；真正改代码前，还需对每个 D 补齐“边界决策 + 失败测试 + 回滚”。
