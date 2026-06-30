# core/config.py 结构分析

> 分析日期：2026-06-29

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **520** |
| 类 | 1 个（`ConfigManager`，328 行） |
| 模块级函数 | 5 个 |
| 模块级常量 | 1 个（`FACTORY_DEFAULTS`，89 行） |
| 内部方法 | 5 个（_migrate_ui_keys, _load, _populate_first_run, _get_fernet, _walk_sensitive, _is_sensitive） |

### 模块级函数

| 函数 | 行数 | 职责 | 可移动性 |
|------|------|------|---------|
| `_get_config_dir()` | 24-50 | 返回配置文件目录路径 | 可移入 `paths.py` |
| `get_data_dir()` | 53-68 | 返回可写数据目录 | 可移入 `paths.py` |
| `get_db_path()` | 71-73 | 返回 SQLite 路径（调用 get_data_dir） | 可移入 `paths.py` |
| `get_network_timeout()` | 76-78 | 读取超时配置 | 可移入 `paths.py` |
| `get_library_root()` | 81-98 | 返回库根目录，自动创建 | 可移入 `paths.py` |

### ConfigManager 类

| 方法 | 行数 | 职责 |
|------|------|------|
| `__init__` | 22 | 初始化 + 环境变量覆盖 |
| `get` | 13 | 点号分层读取 |
| `set` | 11 | 点号分层写入 |
| `save` | 12 | 持久化 + 原子写入 |
| `reset` | 18 | 重置配置 |
| `populate_defaults` | 12 | 填充缺失默认值 |
| `export_rules` | 28 | 规则导出 |
| `import_rules` | 52 | 规则导入 + 合并 |
| `_migrate_ui_keys` | 28 | 旧版键迁移 |
| `_load` | 34 | 加载 + 自动填充 + 损坏恢复 |
| `_populate_first_run` | 8 | 首次写入默认值 |
| `_get_fernet` | 19 | 加密密钥管理 |
| `_walk_sensitive` | 23 | 敏感字段加解密 |
| `_is_sensitive` | 2 | 敏感字段判断 |

---

## 依赖关系

### 被引用次数

| 符号 | 引用数 | 类型 |
|------|--------|------|
| `ConfigManager` | 22 | 类 |
| `get_data_dir` | 12 | 函数 |
| `get_db_path` | 9 | 函数 |
| `get_library_root` | 5 | 函数 |

### 内部依赖

```
config.py
  → .frozen.is_frozen   (1 处)
  → cryptography.fernet  (1 处，惰性导入)
  → json, os, sys, threading (标准库)
```

### 核心导出（不可删除）

| 符号 | 原因 |
|------|------|
| `ConfigManager` | 全局 22 处引用，唯一配置入口 |
| `get_db_path()` | 全局 9 处引用 |
| `get_data_dir()` | 全局 12 处引用 |
| `get_library_root()` | 全局 5 处引用 |

---

## 拆分建议

```
pilotstd/core/config/
├── __init__.py       ← 重导出：from .manager import ConfigManager
│                            from .paths import get_data_dir, get_db_path, get_library_root
│                            from .defaults import FACTORY_DEFAULTS
├── manager.py        ← ConfigManager 核心类 (~330 行)
├── paths.py          ← _get_config_dir, get_data_dir, get_db_path, get_network_timeout, get_library_root (~75 行)
├── defaults.py       ← FACTORY_DEFAULTS 常量 (~90 行)
├── migrate.py        ← _migrate_ui_keys, export_rules, import_rules (~100 行)
└── crypto.py         ← _get_fernet, _walk_sensitive, _is_sensitive (~45 行)
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | ~15 | 重导出，保持外部 import 不变 |
| `manager.py` | ~330 | `ConfigManager` 核心类（get/set/save/reset/populate） |
| `paths.py` | ~75 | 目录/路径相关函数 |
| `defaults.py` | ~90 | `FACTORY_DEFAULTS` 出厂默认值 |
| `migrate.py` | ~100 | 规则导入导出 + 键迁移 |
| `crypto.py` | ~45 | 敏感字段加解密 |

### 拆分后影响

```
外部导入 from pilotstd.core.config import ConfigManager, get_db_path
                                     ↓ 不变！__init__.py 重导出
内部实现 pilotstd/core/config/manager.py  等 5 个文件
```

**35 处外部引用无需任何修改。** 只需确保 `__init__.py` 完整重导出所有公开符号。

### 不拆分部分

`get_network_timeout()` — 仅 3 行，可放在 `paths.py` 中。或直接 inline 到调用方（仅 `query/engine.py` 一处使用？）。需要确认。
