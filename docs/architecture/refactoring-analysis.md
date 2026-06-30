# 大文件包化分析汇总

> 创建日期：2026-06-30
> 状态：全部完成（11 个文件包化 + 函数拆分）

本文档合并了以下已归档的分析文档：`facade_analysis.md`、`query_engine_analysis.md`、`parser_analysis.md`、`main_window_analysis.md`、`config_structure_analysis.md`、`query_mixin_analysis.md`、`organizer_service_analysis.md`、`db_structure_analysis.md`、`code_smell_audit.md`。

---

## 一、包化概览

| # | 原文件 | 原始行 | → 目录 | 子文件数 | 最大子文件 | 减少比例 |
|---|--------|--------|--------|---------|-----------|---------|
| 1 | `core/config.py` | 520 | `config/` | 6 | 139 (manager) | -73% |
| 2 | `core/db.py` | 863 | `db/` | 4 | 488 (migrations) | -43% |
| 3 | `manager/facade.py` | 1687 | `facade/` | 8 | 435 (_query) | -74% |
| 4 | `query/engine.py` | 1139 | `engine/` | 9 | 424 (_batch) | -63% |
| 5 | `scan/parser.py` | 962 | `parser/` | 5 | 247 (_exact) | -74% |
| 6 | `announcement/ocr.py` | 769 | `ocr/` | 5 | 381 (_base) | -50% |
| 7 | `ui/main_window.py` | 942 | `main_window/` | 3 | 344 (_ui_setup) | -63% |
| 8 | `ui/workers.py` | 551 | `workers/` | 10 | 116 (archive) | -79% |
| 9 | `ui/controllers/query_mixin.py` | 509 | `query/` | 4 | 256 (pending) | -50% |
| 10 | `manager/organizer_service.py` | 524 | `organize/` | 5 | 185 (organizer) | -65% |
| 11 | `cli/commands.py` | 524 | `commands/` | 12 | 139 (\_\_init\_\_) | -73% |

---

## 二、各文件分析摘要

### 1. `core/config.py` → `core/config/`

| 子文件 | 行数 | 职责 |
|--------|------|------|
| `__init__.py` | 15 | 公开导出 |
| `manager.py` | 139 | ConfigManager 核心 |
| `paths.py` | 72 | 路径解析 |
| `defaults.py` | 89 | 默认值定义 |
| `migrate.py` | 111 | 配置迁移 |
| `crypto.py` | 58 | 加密工具 |

### 2. `core/db.py` → `core/db/`

| 子文件 | 行数 | 职责 |
|--------|------|------|
| `__init__.py` | 13 | 公开导出 |
| `database.py` | 272 | Database 类 + 迁移引擎 |
| `migrations.py` | 488 | 26 个迁移步骤 |
| `_constants.py` | 26 | 常量定义 |

### 3. `manager/facade.py` → `manager/facade/`

| 子文件 | 行数 | 职责 |
|--------|------|------|
| `__init__.py` | 29 | StandardManager 类 |
| `_auto.py` | 180 | 一键处理流程 |
| `_base.py` | 158 | 基类 + 初始化 |
| `_download.py` | 134 | 下载管理 |
| `_file_index.py` | 55 | 文件索引 |
| `_organize.py` | 323 | 归档组织 |
| `_query.py` | 435 | 查询引擎调度 |
| `_scan.py` | 154 | 扫描管理 |

### 4. `query/engine.py` → `query/engine/`

| 子文件 | 行数 | 职责 |
|--------|------|------|
| `__init__.py` | 48 | QueryEngine 类 + 组合 |
| `_batch.py` | 424 | 批量查询主调度 |
| `_constants.py` | 35 | 常量 |
| `_core.py` | 86 | 缓存/配额/路由初始化 |
| `_routing.py` | 146 | 站点优先级路由 |
| `_single.py` | 88 | 单条查询 |
| `_csres.py` | 74 | CSRes 适配器查询 (mixin) |
| `_mini_bucket.py` | 152 | 小桶拆分与查询 (mixin) |
| `_report.py` | 105 | 统计报告 (mixin) |

### 5. `scan/parser.py` → `scan/parser/`

| 子文件 | 行数 | 职责 |
|--------|------|------|
| `__init__.py` | 184 | StandardParser 入口 |
| `_constants.py` | 189 | 正则/代号常量 |
| `_exact.py` | 247 | 精确匹配 |
| `_foreign.py` | 148 | 国外标准解析 |
| `_utils.py` | 235 | 工具函数 |

### 6-11. 其余包化

| 目录 | 说明 |
|------|------|
| `announcement/ocr/` | OCR 提供商分离 (阿里云/百度/腾讯 + 基类) |
| `ui/main_window/` | 主窗口拆分 (UI构建 + 事件处理) |
| `ui/workers/` | 10 个工作线程独立文件 |
| `ui/controllers/query/` | 查询控制器拆分 (混入 + 待确认 + 汇总) |
| `manager/organize/` | 归档逻辑拆分 (核心 + 镜像 + 过期) |
| `cli/commands/` | 12 个子命令独立文件 |

---

## 三、代码规模治理效果

| 指标 | 治理前 | 治理后 |
|------|--------|--------|
| 最大文件 | 1687 行 (facade.py) | 488 行 (migrations.py) |
| >500 行文件 | 11 | **0** |
| 平均文件行数 | ~350 | ~120 |
| 总文件数 (pilotstd/) | ~45 | ~110 |

---

## 四、相关文档

- [GATE-15 治理汇总](governance-summary.md)
- [GATE-15 规则说明](../development/gate-15-enforcement.md)
- [技术债登记簿](technical-debt-registry.md)
