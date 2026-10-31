# A-21 迁移方案（v71：notification_log / notification_queue 加 user_id）

## 1. Schema

| 表 | 变更 |
|---|---|
| `notification_log` | `ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1`；索引 `(user_id, sent_at)` |
| `notification_queue` | `ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1`；索引 `(user_id, status)` |

迁移版本 `v71`（当前 `CURRENT_SCHEMA_VERSION=70`），只加列/索引，不重建表。

## 2. 回填

- 存量行统一 `user_id=1`（单用户模式）；
- 不删不改旧数据；`DEFAULT 1` 保证旧 INSERT 兼容。

## 3. 读写路径

- 写：`_manager_ops` 落库、`_suppression_queue.enqueue` 写当前 `_user_id`；
- 读：`get_logs` / `release` / 统计按 `user_id` 过滤；
- **管理员视图**：不传 `user_id` 仅 admin 可用（`require_role("admin")`），普通用户强制使用自己的 id——否则隔离失效。

## 4. 回滚

- 迁移前备份 DB 文件；
- 回滚 = 恢复备份 + 代码回退；
- **已知代价**：恢复备份会丢失迁移期间新写入的行；如不可接受，回滚前先导出增量
  （`WHERE id > 备份最大 id`）再合并。

## 5. 验证

- 迁移幂等（重复执行不报错）；
- 旧数据可读、新数据带 `user_id=1`；
- 双用户隔离 1 例（user1/user2 各自日志）；
- `get_logs` 普通用户强制过滤、admin 可看全量；
- 日志查询/队列 release 的 EXPLAIN 与迁移前耗时对比（性能抽查）。
