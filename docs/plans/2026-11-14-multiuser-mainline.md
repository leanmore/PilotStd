# 多用户主线推进计划（2026-11-14）

> 用户裁定（2026-11-14）：**多用户是明确目标**；问题不是"做不做"，而是主线反复被枝节带偏、停在半路。
> 本文把主线拆成可验收的阶段，并把所有枝节标注为**不阻塞主线**。

## 一、纪律（先于阶段）

1. **主线优先**：只有"挡住当前阶段完成判据"的问题才允许中断主线去修。
2. **枝节只记录不处理**：遇到枝节（含下表 A-40/A-42 等）→ 记入 `docs/debt/03-open.md` 或 `ISSUE_LEDGER`，继续主线。
3. **每阶段有唯一完成判据**，判据不满足不进入下一阶段；判据要能用命令/数据复核。

## 二、现状（证据，2026-11-14 核查）

| 层 | 现状 | 证据 |
|---|---|---|
| 数据模型 | `notification_log` / `notification_queue` 已有 `user_id`（默认 1），索引 `(user_id, sent_at)` | 迁移 v71（`docs/onboarding/18-schema-migrations.md`） |
| 投递归属 | `NotificationManager(config, db, user_id)` 按实例解析用户；分发层有 `delivery_user_id` | `pilotstd/core/notification/manager.py:73/78`、`_dispatcher.py:63/120` |
| 读侧隔离 | `get_logs(..., user_id=...)` / 未读数按用户过滤，含系统通知口径 | `_manager_ops.py:199-235`；`tests/test_notification_unread_isolation.py` 等 57 passed（历史记录） |
| 端点鉴权 | `/api/auto`、`/api/archive` **已有** `@require_role("admin")`；archive 还写审计（`get_current_user_id()`） | `docker/api/auto.py:23-24`、`docker/api/archive.py:61-62/124-126` |
| **缺口 1** | 上述两端点**未把当前用户传给 `NotificationContext`** ⇒ 事件归 system（user 0），多用户下用户看不到自己触发的通知 | `auto.py:30` 直接 `mgr.auto_run(root_path)`；archive 侧同上（未见 context 传参） |
| **缺口 2** | v71 把存量日志/队列一律回填到 user 1，未区分"系统/迁移前/真实用户" | A-40（`docs/debt/03-open.md`） |
| **缺口 3** | 队列 release / 聚合是否按用户隔离**未验证**（`aggregate_buffer` 按 event_type 分桶） | 待 P2 用并发双用户用例验证 |

> 更正：A-42 原文写"无 auth 依赖"已过时——两端点都有 admin 鉴权；真实缺口是"未传用户上下文"。

## 三、阶段与完成判据

### P1 · 事件归属接线（下一步，先做这个）

- **进度（2026-11-14）**：代码完成——`/api/auto` 与 `/api/archive` 均构造
  `NotificationContext(scope="admin", user_id=get_current_user_id(...))` 并传入
  `auto_run` / `archive_standards`（此前不传 ⇒ system(0)）。API 层测试
  `tests/test_api_auto_archive_user_context.py` 2 例（先红后绿）：断言 context 非空、
  `user_id==1`、`log_user_id==1`。
- **2026-11-15 集成验证完成**：`tests/test_p1_multiuser_integration.py` 3 例（真实
  `NotificationManager` + 临时库 + 真实路由/中间件）：两个管理员分别触发 auto/archive →
  `notification_log.user_id` = 1/2、无 0。**状态：代码 + 集成测试完成，生产端到端待有环境时补。**
- **DB 级判据（待真实双用户环境复核）**：
  ```sql
  SELECT user_id, count(*) FROM notification_log
  WHERE event_type IN ('auto_pipeline_summary','archive_complete')
    AND date(sent_at)=date('now','localtime')
  GROUP BY user_id;
  ```
  期望：两个用户各一行、`user_id` 分别为两人；**不得出现 user_id=0**。
- **不阻塞（明确口径）**：A-40 不阻塞 P1 判据；顺手可做，不顺手不碰，**不为此中断 P1**。

### P2 · 队列/聚合隔离验证

- **动作**：写并发双用户用例（两个用户同时触发同 event_type），检查 `notification_queue` 行归属、聚合是否跨用户合并；不通过则修 `aggregate_keys`/release 的 user 维度。
- **完成判据**：并发用例通过；两用户各自只看到自己的队列/聚合结果。
- **前置**：P1 完成（否则事件本身归 system，测不出隔离）。

### P3 · AC-6 验收

- **动作**：双用户端到端（登录 → 触发 → 通知 → 未读/已读 → 切换用户互不可见），写入 `ACCEPTANCE_CASES` 的 AC-6 证据列。
- **完成判据**：AC-6 从 PARTIAL 转 PASS（或明确列出剩余缺口）。
- **不阻塞**：A-41（admin 跨用户排障视图）已裁定**不做**；`P3-10` 旧 `user_id` 观察项。

## 四、枝节清单（明确不阻塞主线）

| 枝节 | 处置 |
|---|---|
| A-40 旧数据归属 | P1 内可小步处理；不达 P1 判据也可先放 |
| A-41 admin 全量视图 | **已裁定不做**（排障走现有日志/机制） |
| A-42 端点无 auth | **表述更正**为"缺用户上下文"，并入 P1 |
| A-37 网络 e2e | 已修（显式开启才跑），与主线无关 |
| V-16/V-17、A-43 等 | 事件触发，不打断主线 |

## 五、下一步（本计划生效后的第一件事）

读 `/api/auto`、`/api/archive` 的 manager 调用链，确定 `NotificationContext` 的传入点与 `get_current_user_id()` 在 admin 依赖后的可用性；写 1 个失败测试（当前 user_id 为 0），再改代码。
