# query/engine.py 结构分析

> 分析日期：2026-06-30

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **1139** |
| 类 | 1 个（`QueryEngine`，~1070 行） |
| 模块级函数 | 1 个（`_build_default_code_routes`） |
| 模块级常量 | 5 个（`PROGRESS_TAG`, `PROD_PRIORITY`, `FOREIGN_ROUTE`, `CODE_ROUTES`, `INDUSTRY_ROUTE`） |
| 方法数 | ~20 个 |
| 外部引用 | 8 个文件 |

---

## 方法清单

### 模块级（第 1-67 行）

| 符号 | 行 | 类型 | 说明 |
|------|-----|------|------|
| `PROGRESS_TAG` | 38 | str | 跨进程日志协议标识 |
| `PROD_PRIORITY` | 43 | list | 默认站点优先级 |
| `FOREIGN_ROUTE` | 45 | list | 国外标准路由 |
| `_build_default_code_routes()` | 49-61 | func | 按代号生成路由表 |
| `CODE_ROUTES` | 64 | dict | 代号→适配器链映射 |
| `INDUSTRY_ROUTE` | 66 | list | 行业标准路由 |

### QueryEngine 类方法

| # | 方法 | 行数 | 职责 | 分组 |
|---|------|------|------|------|
| 1 | `__init__` | 34 | 注入缓存/轮转器/配额/适配器 | 初始化 |
| 2 | `is_query_running/overflow/csres/idle` | 25 | 状态查询 | 状态 |
| 3 | `_query_one` | 65 | 单条查询：轮转→调用→记录 | 单查询 |
| 4 | `query_standards` | 52 | 批量查询入口：缓存→分组→并发 | 批量查询 |
| 5 | `plan_batch` | 18 | 按配额分割任务 | 路由 |
| 6 | `get_quota_info/adapter/cooldown/sites` | 20 | 配额/适配器状态查询 | 路由 |
| 7 | `_get_priority` | **82** | 站点优先级计算（含 fallback） | 路由 |
| 8 | `_record` | 8 | 查询记录统计 | 记录 |
| 9 | `_verify_adoption` | 24 | 采标状态校验 | 记录 |
| 10 | `_bucket_key` | 5 | 站点分桶键 | 路由 |
| 11 | `_build_chain_for_item` | 7 | 构建适配器链 | 路由 |
| 12 | `query_batch_parsed` | **220** | **最复杂方法**：含 5 个嵌套函数（bump/heartbeat/try_overflow/csres_worker/record） | 批量查询 |

### 分组统计

| 分组 | 方法数 | 总行数 | 占比 |
|------|--------|--------|------|
| 模块常量+工具 | 1 func + 5 常量 | 67 | 6% |
| 初始化+状态 | 5 | 60 | 5% |
| 单查询 | 2 | 89 | 8% |
| 批量查询 | 2 | **272** | **24%** |
| 路由/规划 | 6 | 132 | 12% |
| 记录/校验 | 2 | 32 | 3% |
| 空行/注释/导入 | — | ~487 | 42% |

---

## 依赖关系

### 外部引用（8 个文件）

| 符号 | 文件数 | 说明 |
|------|--------|------|
| `QueryEngine` | 3 | facade.py, test_query.py, test_e2e_adapters.py |
| `PROGRESS_TAG` | 4 | stress_docker/web/driver, test_observability |
| `CODE_ROUTES` | 1 | test_query.py |
| `PROD_PRIORITY` | 1 | test_query.py |
| `INDUSTRY_ROUTE` | 1 | test_query.py |
| `FOREIGN_ROUTE` | 1 | test_query.py |

### 内部依赖

```
engine.py
  → search_strategy (ADAPTER_TYPE_MAP, MATCH_SCORE)
  → adapters.base (BaseAdapter)
  → cache (CacheRepository)
  → daily_quota (DailyQuotaTracker)
  → models (QueryResult)
  → rotator (SiteRotator)
  → organizer.industry_lookup (_DB_PROVINCE_MAP)
```

---

## 拆分建议

```
pilotstd/query/engine/
├── __init__.py         ← 重导出 QueryEngine + 所有常量
├── _constants.py       ← PROGRESS_TAG, PROD_PRIORITY, FOREIGN_ROUTE, CODE_ROUTES, INDUSTRY_ROUTE (~50行)
├── _routing.py         ← _get_priority, plan_batch, get_quota_info, get_adapter, get_cooldown, get_sites, _bucket_key, _build_chain (~132行)
├── _single.py          ← _query_one, _verify_adoption (~89行)
├── _batch.py           ← query_standards, query_batch_parsed (~272行)
└── _core.py            ← __init__, is_query_running, get_overflow, get_csres, is_idle, _record (~92行)
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | ~15 | 重导出 `QueryEngine` + 所有常量 |
| `_constants.py` | ~50 | 路由表 + 常量（可独立测试） |
| `_routing.py` | ~130 | 路由/规划逻辑 |
| `_single.py` | ~90 | 单条查询 |
| `_batch.py` | ~270 | 批量查询核心（最复杂） |
| `_core.py` | ~90 | 初始化 + 状态 |

### 导入兼容性

```python
# 外部零改动
from pilotstd.query.engine import QueryEngine, PROGRESS_TAG, CODE_ROUTES
# → __init__.py 重导出，完全兼容
```

---

## 拆分优先级

| 优先级 | 理由 |
|--------|------|
| **高** | 1139 行。`query_batch_parsed` 单个方法 220 行含 5 层嵌套回调。`_get_priority` 82 行。 |
| 收益 | 路由和批量逻辑独立后，各自 <300 行 |
| 风险 | `PROGRESS_TAG` 被外部压测脚本引用，需确保重导出 |
