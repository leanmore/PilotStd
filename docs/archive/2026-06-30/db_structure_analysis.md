# core/db.py 结构分析

> 分析日期：2026-06-30

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **863** |
| 类 | 2 个（`Database` 285行 + `DatabaseError` 4行） |
| 模块级函数 | 17 个（1 个 decorator + 16 个 migration） |
| 常量 | 1 个（`CURRENT_SCHEMA_VERSION`） |
| 外部引用 | 23 处 |

### 行数分布

| 区块 | 行数 | 占比 |
|------|------|------|
| 迁移函数（v2-v25） | **530** | **62%** |
| Database 核心类 | 285 | 33% |
| 模块级常量/工具 | 30 | 3.5% |
| 导入+文档 | 18 | 2% |

---

## 方法清单（Database 类）

| # | 方法 | 行数 | 职责 | 分组 |
|---|------|------|------|------|
| 1 | `__init__` | 10 | 初始化 + 触发迁移 | 核心 |
| 2 | `_init_pragma` | 13 | WAL/DELETE 模式检测 | 连接 |
| 3 | `_get_conn` | 11 | 线程本地连接复用 | 连接 |
| 4 | `connect` | 8 | 独立连接（备份用） | 连接 |
| 5 | `close` | 8 | 关闭当前线程连接 | 连接 |
| 6 | `close_all` | 10 | 关闭所有连接 | 连接 |
| 7 | `execute` | 18 | 写操作（自动 commit） | CRUD |
| 8 | `executemany` | 10 | 批量写操作 | CRUD |
| 9 | `fetchall` | 13 | 读操作（无锁） | CRUD |
| 10 | `fetchone` | 4 | 单行查询 | CRUD |
| 11 | `schema_version` | 16 | 返回当前版本 | 迁移 |
| 12 | `_run_migrations` | 26 | 按序执行迁移 | 迁移 |
| 13 | `backup` | 22 | 一致性快照备份 | 备份 |
| 14 | `update_adapter_stats` | 42 | 适配器统计写入 | 统计 |
| 15 | `get_adapter_success_rate` | 14 | 成功率查询 | 统计 |
| 16 | `get_adapter_stats_all` | 33 | 全量统计报表 | 统计 |
| 17 | `__enter__`/`__exit__` | 15 | 上下文管理器 | 核心 |

### 迁移函数列表（16 个）

| 版本 | 函数 | 行数 | 内容 |
|------|------|------|------|
| v2 | `_migrate_v2_add_file_index` | 20 | file_index 表 |
| v3 | `_migrate_v3_queue_and_pending` | 46 | download_queue + pending_lookup |
| v4 | `_migrate_v4_add_fetch_checkpoint` | 13 | fetch_checkpoint 表 |
| v5 | `_migrate_v5_announcement_match` | 18 | announcement_match 表 |
| v6 | `_migrate_v6_add_rotator_state` | 15 | rotator_state 表 |
| v7 | `_migrate_v7_add_last_checked` | 10 | file_index 加列 |
| v8 | `_migrate_v8_drop_expires_at` | 11 | 删除列 |
| v9 | `_migrate_v9_add_requery_count` | 8 | pending_lookup 加列 |
| v10 | `_migrate_v10_add_source_and_status_history` | 11 | cache 加列 |
| v11 | `_migrate_v11_add_daily_limits` | 10 | rotator_state 加列 |
| v12 | `_migrate_v12_adapter_stats` | 11 | adapter_stats 表 |
| v13 | `_migrate_v13_adapter_stats_extend` | 16 | adapter_stats 扩展列 |
| v14 | `_migrate_v14_api_keys` | 16 | api_keys 表 |
| v15 | `_migrate_v15_announcement_record` | 20 | announcement_record 表 |
| v16 | `_migrate_v16_validity_status` | 20 | standard_validity 表 |
| v17 | `_migrate_v17_notification_log` | 16 | notification_log 表 |
| v18 | `_migrate_v18_notification_is_read` | 7 | 加 is_read 列 |
| v19 | `_migrate_v19_users` | 18 | users 表 |
| v20 | `_migrate_v20_register_runtime_tables` | 10 | 运行时表登记 |
| v21 | `_migrate_v21_user_layouts` | 13 | user_layouts 表 |
| v22 | `_migrate_v22_user_preferences` | 13 | user_preferences 表 |
| v23 | `_migrate_v23_cache_system` | 88 | 缓存系统（最大迁移） |
| v24 | `_migrate_v24_task_queue_enhance` | 38 | task_queue 扩展 |
| v18 | `_migrate_v18_fetch_task_adapter_health` | 27 | fetch_task + adapter_health |
| v25 | `_migrate_v25_announcement_match_safeguard` | 15 | 兜底创建 |

**总计**：530 行，26 个迁移（含重复 v18）

---

## 依赖关系

### 外部引用（23 处）

| 符号 | 引用数 | 说明 |
|------|--------|------|
| `Database` | 22 | 核心类，几乎全部项目引用 |
| `CURRENT_SCHEMA_VERSION` | 3 | 测试验证 |
| `MIGRATIONS` / `migration` | 1 | 测试用 |
| `_migrate_v18_notification_is_read` | 1 | 测试直接调用 |

### 内部依赖

```
database.py → _constants.py (CURRENT_SCHEMA_VERSION, MIGRATIONS, DatabaseError)
database.py → migrations.py (imported once to populate MIGRATIONS)
migrations.py → database.py (Database type hint in function params)
```

**关键**：migrations 需要在 Database.__init__() 之前被导入，以填充 `MIGRATIONS` 字典。

---

## 拆分建议

```
pilotstd/core/db/
├── __init__.py        ← 重导出 + 触发 @migration 装饰器注册
├── database.py        ← Database 核心类（~285行）
├── migrations.py      ← 所有 @migration 函数（~530行）
└── _constants.py      ← CURRENT_SCHEMA_VERSION, MIGRATIONS, migration(), DatabaseError（~30行）
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | ~10 | `from ._constants import *` + `from .migrations import *` + `from .database import Database` |
| `database.py` | ~285 | Database 类（CRUD + connection + backup + stats） |
| `migrations.py` | ~530 | 26 个 @migration 函数 |
| `_constants.py` | ~30 | 常量 + decorator + 异常类 |

### 导入兼容性

```python
# 外部零改动
from pilotstd.core.db import Database, CURRENT_SCHEMA_VERSION
# → __init__.py 重导出，完全兼容
```

### 注意事项

- `_constants.py` 中 `MIGRATIONS` 是模块级可变字典，跨模块共享
- `__init__.py` 中 `from .migrations import *` 触发所有 `@migration()` 装饰器执行
- `test_notification_db.py` 直接导入 `_migrate_v18_notification_is_read` — 需在 `__init__.py` 中导出
- `stress_selfcheck.py` 导入 `CURRENT_SCHEMA_VERSION` — 需在 `__init__.py` 中导出
- 存在重复 v18 迁移（第 819 行重复），建议合并或确认

---

## 拆分优先级

| 优先级 | 理由 |
|--------|------|
| **高** | 863 行，62% 是迁移代码。Database 核心逻辑与 schema 定义混在一起，每次看代码都要滚动过半迁移 |
| 收益 | 拆分后 database.py 仅 ~285 行，migrations.py 独立维护 |
| 风险 | 需确保 @migration 装饰器在 Database.__init__() 之前执行（`__init__.py` 的 import 顺序解决） |
