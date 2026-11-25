# 方向 C 深度扫描（第二轮，2026-11-25）

> 目的：不重复既有清单，用**新的扫描口径**找新问题（异常未捕获 / 性能 N+1 / 过期注释）。
> 方法：AST 扫描 + 关键词分类；脚本为一次性工具（未入仓，结果摘要见本文）。

## 1. 扫描口径与结果

| 扫描项 | 口径 | 命中 | 结论 |
|---|---|---|---|
| TODO/FIXME/XXX/HACK | 全库生产代码（`pilotstd`/`docker`/`scripts`/`web/src`） | **121** | `pilotstd` 仅 XXX×7、`scripts` 12、`web/src` 102；均为既有登记/说明性标记，**无新增未登记临时方案**（`临时兼容` 关键词 0 命中） |
| N+1（循环体内 SELECT） | AST：`For/While` 体内含 `SELECT` | 35 | 多数为迁移脚本（一次性）与「表名循环」的有界查询；**2 处真实可优化**（见 §2） |
| 循环内文件系统遍历 | AST + 人工复核 | 1 | `archive_reconcile` 每丢失文件 `rglob` 一次 → **已修** |
| 线程/任务异常可见性 | `Thread(target=)` / `create_task(...)` | 19 | 逐个复核：均在线程函数内部自带 `try/except + logger`（或由调用方 join 捕获），**无需改** |
| web `.then()` 无 `.catch()` | 行级 + 3 行前瞻 | 2 | 均为多行链误报（`.catch` 在 `.then` 体之后），**无需改** |
| 静默吞错 | G-050 棘轮（191→179） | — | 已收紧，无新增 |

## 2. 本轮修复（均带回归用例）

### 2.1 `pilotstd/core/archive_reconcile.py` —— 目录树 O(N×M) → O(1) 趟
原实现：每条「路径不存在」的 file_index 记录都执行一次 `expire_dir.rglob(name)`，
丢失 N 条就扫 N 遍「过期作废」目录树；并且孤儿清理再扫第 N+1 遍。
**修法**：一次遍历建 `文件名 → 路径列表` 索引，查找变字典命中，孤儿清理复用同一列表。
**回归**：`tests/unit/core/test_n_plus_one_batching.py::TestReconcileSingleWalk`
（`Path.rglob` 调用次数断言 = **1**；多条悬空路径均正确回填）。

### 2.2 `pilotstd/manager/pending_service.py::query_local_cache` —— 真 N+1
GUI 离线查询逐标准点查 1~2 次 DB（`standard_info_cache` 未命中再查 `announcement_match`）
→ N 条标准最多 2N 次查询。
**修法**：新增 `_fetch_result_json_map`，按批 `IN (...)`（批 500）预取成字典；
语义不变（先网络缓存 → 后公告缓存 → 未命中仍返回「本地数据库未找到」）。
**回归**：`::TestQueryLocalCacheBatched`（结果等价 + 查询次数为常数 **2**，非 2N）。

## 3. 复核后判定「不改」的项（附理由，避免后人重复排查）

| 项 | 理由 |
|---|---|
| `core/cache_manager.py` 表名循环内 SELECT | 循环上界是**固定表名元组**（约 20），不是用户数据量 |
| `core/name_resolution.py` 的 IN 查询 | **已经是批量**（`IN (...)` 占位符），扫描误报 |
| `announcement/matcher.py` 循环 | 是**分批 INSERT**（`_BATCH_SIZE` 分块），非 N+1 |
| `core/task_history.py` 清理循环 | 仅对「>2000 条」的任务逐条 DELETE，任务种类有限；且由写计数触发、非热路径 |
| 19 处线程/任务 | 逐个复核：线程函数内部自带异常捕获与 logger |
| 102 个 web TODO | 均为既有说明性注释（如「待后端接口」），非临时兼容逻辑 |

## 4. 验证
- 受影响域回归：`-k "pending or archive or manager or facade or gui"` → **898 passed, 5 skipped**
- 全量后端：**7037 passed, 23 skipped**
- 全量门禁全绿；能力矩阵重生成
