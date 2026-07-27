# 数据库迁移说明

> 最后更新：2026-07-27 | 最新迁移：v44

## 迁移版本清单

迁移脚本路径：[pilotstd/core/db/migrations.py](pilotstd/core/db/migrations.py)（v16+），[pilotstd/core/db/_migrate_v2_v15.py](pilotstd/core/db/_migrate_v2_v15.py)（v2-v15），[pilotstd/core/db/_migrate_v31_plus.py](pilotstd/core/db/_migrate_v31_plus.py)（v31-v36），[pilotstd/core/db/_migrate_v37_plus.py](pilotstd/core/db/_migrate_v37_plus.py)（v37-v40）

| 版本 | 说明 | 脚本路径 |
|------|------|----------|
| v2 | file_index 表 | `_migrate_v2_v15.py` |
| v3 | queue + pending 表 | 同上 |
| v4 | fetch_checkpoint 表 | 同上 |
| v5 | announcement_match 表 | 同上 |
| v6 | adapter_state 表 (rotator) | 同上 |
| v7 | last_checked 列 | 同上 |
| v8 | drop expires_at | 同上 |
| v9 | requery_count 列 | 同上 |
| v10 | source + status_history | 同上 |
| v11 | daily_limits 表 | 同上 |
| v12-v13 | adapter_stats 表 | 同上 |
| v14 | api_keys 表 | 同上 |
| v15 | announcement_record 表 | 同上 |
| v16 | standard_validity 表 | `migrations.py:42` |
| v23 | standard_info_cache 缓存字段 | `migrations.py:126` |
| v30 | fetch_failures + app_preferences | `migrations.py:288` |
| v31 | monitor_stats 表 | `_migrate_v31_plus.py` |
| v36 | user_favorites 表 + announcements 表 | `_migrate_v31_plus.py:178` |
| v41 | file_index raw_number 列 | `migrations.py:339` |
| v42 | standards 表 (四要素) | `migrations.py:402` |
| **v43** | **batch_state + query_metrics** | `migrations.py:427` |
| **v44** | **favorite_downloads 解耦** | `_migrate_v44.py` |

## 重点迁移详细说明

### v43 — 断点续传表 [src: `migrations.py:427-464`]

**表结构**：

```sql
CREATE TABLE IF NOT EXISTS batch_state (
    batch_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','paused')),
    total_items INTEGER NOT NULL DEFAULT 0,
    completed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    overflow_pool TEXT,              -- JSON: 待重试条目列表
    adapter_quota_snapshot TEXT,     -- JSON: 中断时适配器状态快照 v1
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS query_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    metric_value INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES batch_state(batch_id)
);
```

**运行时接入**：
- 写入：[`_batch_dispatch.py:_finalize_batch()`](pilotstd/query/engine/_batch_dispatch.py#L347) `INSERT OR REPLACE`
- 读取：待步骤5完整实现（当前仅写入）

**回滚方案**：`DROP TABLE IF EXISTS batch_state; DROP TABLE IF EXISTS query_metrics;`（两张表为全新创建，无历史数据依赖）

### v44 — 收藏归档解耦 [src: `_migrate_v44.py`]

**DDL 变更**：

```sql
CREATE TABLE IF NOT EXISTS favorite_downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    favorite_id INTEGER NOT NULL,         -- FK → user_favorites.id
    record_id INTEGER NOT NULL,           -- FK → announcement_record.id
    status TEXT DEFAULT 'pending',
    local_path TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (favorite_id) REFERENCES user_favorites(id) ON DELETE CASCADE,
    FOREIGN KEY (record_id) REFERENCES announcement_record(id),
    UNIQUE(favorite_id, record_id)
);
```

**数据迁移 SQL**：

```sql
INSERT OR IGNORE INTO favorite_downloads
  (favorite_id, record_id, status, local_path, error_message,
   retry_count, last_attempt, created_at, updated_at)
SELECT id, record_id, status, local_path, error_message,
       archive_retry_count, last_archive_attempt,
       created_at, updated_at
FROM user_favorites
WHERE status IN ('downloading', 'archiving', 'done', 'failed', 'abandoned')
  AND record_id IS NOT NULL;
```

**状态清理**：

```sql
UPDATE user_favorites
SET status = 'pending', updated_at = CURRENT_TIMESTAMP
WHERE status IN ('downloading', 'archiving', 'done', 'failed', 'abandoned')
  AND record_id IS NOT NULL;
```

**事务保护**：整个迁移在 SQLite 自动事务中执行（Python 调用层无额外事务包装，依赖 SQLite 的原子性 DDL）。

**⚠️ 同步部署约束（必读）**：

| 顺序 | 操作 | 说明 |
|------|------|------|
| 1 | 部署服务代码（3 文件） | `favorite_download.py`, `archive_retry_service.py`, `date_reminder.py` |
| 2 | 执行 v44 迁移 | DDL + 数据迁移 + 状态清理 |
| **禁止** | 单独执行迁移 | 服务代码未就绪时迁移会导致归档状态丢失 |
| **禁止** | 先部署迁移后部署代码 | 迁移后 `user_favorites` 归档状态已清理，旧代码将写入错误表 |

**部署后验证 SQL**：

```sql
-- 验证 user_favorites 无残留归档状态
SELECT COUNT(*) FROM user_favorites
WHERE status IN ('downloading','archiving','done','failed','abandoned');
-- 预期结果: 0

-- 验证数据完整迁移
SELECT COUNT(*) FROM favorite_downloads;
-- 预期: >= 迁移前的归档记录数
```

**回滚方案** [src: `scripts/rollback_v44.sql`（待创建）]：

```sql
-- 将 favorite_downloads 数据回写 user_favorites
UPDATE user_favorites SET
  status = (SELECT status FROM favorite_downloads WHERE favorite_id = user_favorites.id),
  local_path = (SELECT local_path FROM favorite_downloads WHERE favorite_id = user_favorites.id),
  error_message = (SELECT error_message FROM favorite_downloads WHERE favorite_id = user_favorites.id),
  archive_retry_count = (SELECT retry_count FROM favorite_downloads WHERE favorite_id = user_favorites.id),
  last_archive_attempt = (SELECT last_attempt FROM favorite_downloads WHERE favorite_id = user_favorites.id),
  updated_at = CURRENT_TIMESTAMP
WHERE id IN (SELECT favorite_id FROM favorite_downloads);

DROP TABLE IF EXISTS favorite_downloads;
```

**回滚前置条件**：未执行步骤1的服务代码部署（即服务代码仍在读写 `user_favorites`）。

## 迁移执行规范

1. **前置检查**：确认数据库可写、磁盘空间充足（> 数据库文件大小 * 2）
2. **备份先行**：`cp pilotstd.db pilotstd.db.bak.$(date +%Y%m%d_%H%M%S)`
3. **执行迁移**：通过应用启动时自动执行（`Database.__init__` 中调用 `run_migrations()`）
4. **验证**：运行部署后验证 SQL
5. **异常处理**：迁移失败时应用启动失败，需修复后重启（SQLite DDL 失败自动回滚）
