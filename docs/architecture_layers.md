# PilotStd 项目四层架构定义

> 调查日期：2026-06-29 / 基于实际代码分析

---

## 1. 四层架构总览

| # | 层次 | 目录 | 职责 | 上行导入 |
|---|------|------|------|---------|
| 3 | API 层 | `docker/api/` | HTTP 路由、请求校验、响应格式化 | → Manager |
| 2 | Manager 层 | `pilotstd/manager/` | 依赖组装、跨域编排、统一门面 | → 业务层 + Core |
| 1 | 业务层 | `pilotstd/query/` `download/` `scan/` `organizer/` `announcement/` `task/` 等 | 独立业务域，单一职责 | → Core |
| 0 | Core 层 | `pilotstd/core/` | 通用基础设施（DB、配置、日志、通知、缓存、文件、有效性检查） | 无 |

**无 `pilotstd/infrastructure/` 目录**。基础设施代码全部位于 `pilotstd/core/`。

**重要**：业务层各包之间原则上不互相导入（例外：`query/engine.py` 导入 `organizer/industry_lookup.py` 用于编码路由）。

---

## 2. 各层职责边界

### 2.1 API 层（`docker/api/` + `docker/app.py`）

- **职责**：HTTP 端点定义、请求体校验、响应格式化
- **消费方**：外部客户端（浏览器、CLI、Web API）
- **依赖**：通过 `Depends(get_manager_dep)` 获取 `StandardManager` 实例；偶尔惰性导入 Core（`from pilotstd.core.db import Database`）用于独立端点
- **禁止**：
  - 直接创建或管理 `StandardManager`（应通过 `docker/manager.py` 单例）
  - 在 API 端点中实现业务逻辑（应委派给 Manager）
  - 直接导入业务层（`pilotstd/query`、`download` 等）

**API 层直接引用 Core 的合法场景**：
- 历史记录/统计端点直接查数据库（如 `validity.py` 的 history 端点）
- 此类引用必须惰性导入（函数内 `from pilotstd.core.db import Database`）

### 2.2 Manager 层（`pilotstd/manager/`）

- **职责**：依赖组装（创建并注入所有子服务）、跨域编排（一次调用涉及多个业务域时在此组合）、暴露统一门面（`StandardManager`）
- **消费方**：API 层、桌面 UI、CLI
- **依赖**：Core 层 + 所有业务子层（query、download、scan、organizer 等）
- **关键文件**：
  - `facade.py`（`StandardManager`）— 主门面，~1200 行
  - `service_factory.py` — 子服务创建工厂
  - `scheduled_service.py` — 定时任务专用方法

### 2.3 业务层（`pilotstd/query/`、`download/`、`scan/` 等）

- **职责**：各自管理一个独立业务域
- **消费方**：Manager 层
- **依赖**：仅 Core 层
- **包列表**：

| 包 | 职责 | 关键类 |
|----|------|--------|
| `query/` | 标准号查询（多站点适配） | `QueryEngine`, `SiteRotator`, `DailyQuotaTracker`, `CacheRepository` |
| `download/` | 文件下载 | `DownloadEngine`, `BaseDownloadAdapter` |
| `scan/` | 文件扫描与解析 | `FileScanner`, `StandardParser` |
| `organizer/` | 文件归档整理 | `DirBuilder`, `ExpireHandler` |
| `announcement/` | 公告抓取与匹配 | `AnnounceEngine`, `AnnouncementMatcher` |
| `task/` | 后台任务队列 | `TaskQueue`, `TaskScheduler` |
| `pipeline/` | 扫描→查询→下载管线路由 | `PipelineRouter` |
| `monitor/` | 文件系统监控 | `MonitorScheduler` |
| `quality/` | 数据质量规则 | `QualityRunner`, 规则模块 |
| `wechat_ip/` | 微信 IP 检测（外部服务） | `Browser`, `CookieManager` |

### 2.4 Core 层（`pilotstd/core/`）

- **职责**：跨域共享的基础设施。数据库访问、配置管理、日志、文件系统、通知框架、有效性和缓存模块
- **消费方**：所有上层
- **依赖**：无（仅标准库和第三方包如 `cryptography`）
- **关键模块**：

| 模块 | 职责 |
|------|------|
| `db.py` | SQLite 数据库封装（`Database` 类） |
| `config.py` | 配置管理器（`ConfigManager`，JSON 持久化，线程安全） |
| `logger.py` | 统一日志入口（`LoggerManager`） |
| `file_utils.py` | 文件哈希、大小计算 |
| `file_index.py` | 本地文件索引仓库（`FileIndexRepository`） |
| `cache_manager.py` | 缓存失效管理 |
| `validity_checker.py` | 标准时效性检查（`ValidityChecker` + `run_validity_check()`） |
| `notification/` | 通知子包（manager、events、channel、渠道实现） |
| `path_guard.py` | 路径安全检查 |
| `std_utils.py` | 标准号工具函数 |

---

## 3. 层间依赖规则

| 源层 | → 目标层 | 是否允许 | 证据 |
|------|---------|---------|------|
| API | Manager | ✅ | `docker/api/query.py:8` — `from ..manager import get_manager_dep` |
| API | Core | ✅ 惰性 | `docker/api/validity.py:164` — 函数内 `from pilotstd.core.cache_manager import ...` |
| API | 业务层 | ❌ | grep `from pilotstd.query` in `docker/` 返回 0 结果 |
| Manager | 业务层 | ✅ | `facade.py:27-38` — 导入所有 query adapter、cache、engine、rotator |
| Manager | Core | ✅ | `facade.py:14-19` — 导入 config、db、file_index、notification、validity_checker |
| 业务层 | Core | ✅ | `query/engine.py:13` — `from ..core.db import Database` |
| 业务层 | 业务层 | ⚠️ 例外 | `query/engine.py:50` — 仅此一例：`from ..organizer.industry_lookup import _DB_PROVINCE_MAP` |
| Core | Manager | ❌ | `grep -rn "from pilotstd.manager" pilotstd/core/` → 零命中 |
| Core | 业务层 | ❌ | 无此方向导入 |
| Core | API | ❌ | `grep -rn "from docker" pilotstd/core/` → 零命中 |

**总规则：依赖只能向下流动。上层可引用下层，反之禁止。**

---

## 4. 新组件归属判断

### 4.1 判断流程

```
新组件需要哪些依赖？
    │
    ├── 仅 Standard Library + 第三方包 → Core 层
    │
    ├── 需要 Core 层的 DB/Config → 业务层 或 Core（如果本身就是基础设施）
    │
    ├── 需要聚合多个业务层组件 → Manager 层
    │
    └── 仅处理 HTTP 请求/响应 → API 层
```

### 4.2 AdapterManager 归属分析

**功能描述**：聚合 `SiteRotator`（query 层）、`DailyQuotaTracker`（query 层）、`adapter_health` 表（数据库），提供统一的适配器状态查询接口，供通知模块和 API 层使用。

**依赖分析**：
- 依赖 `pilotstd.query.rotator.SiteRotator`（业务层）
- 依赖 `pilotstd.query.daily_quota.DailyQuotaTracker`（业务层）
- 依赖 `pilotstd.core.db.Database`（Core 层）
- 依赖 `pilotstd.core.config.ConfigManager`（Core 层）

**被依赖分析**：
- 被 `pilotstd/core/notification/manager.py` 调用（Core 层）
- 被 `docker/api/adapter.py` 调用（API 层）
- 可能被 `docker/scheduler.py` 调用（API/Docker 层）

**结论：应放在 `pilotstd/manager/adapter_manager.py`**

**理由**：

1. **跨业务层聚合**：`AdapterManager` 需要同时持有 `SiteRotator` 和 `DailyQuotaTracker` 的引用，这两个类分属 query 层的不同模块。如果在 Core 层创建，Core 就无法 import 它们（违反了 Core 不依赖业务层的规则）。只有 Manager 层可以合法地聚合业务层组件。

2. **符合 manager 层现有模式**：Manager 层已有 `classifier.py`（聚合 query engine + router）、`announce_service.py`（聚合 announcement engine + matcher）等子服务，`adapter_manager.py` 遵循相同模式。

3. **消除 API→Core 直接访问的反模式**：当前 `docker/api/adapter.py` 直接 `from pilotstd.core.db import Database` 读取 `adapter_health` 表，绕过 Manager。`AdapterManager` 在 Manager 层可以提供统一的 `get_all_adapter_status()` 方法，API 层只需 `mgr.adapter_manager.get_all_adapter_status()`。

4. **保持 Core 层纯粹**：Core 层应仅包含"不依赖任何业务组件的通用基础设施"。任何需要了解具体业务类型（如 `SiteRotator`、`DailyQuotaTracker`）的代码都不应放入 Core。

---

## 5. 治理规则

### 5.1 新组件分层检查清单

1. **该组件是否需要 import 任何来自 `pilotstd/query/`、`download/`、`scan/` 等的类？**
   - 是 → 不能放入 Core，至少放 Manager
2. **该组件是否需要被多个上层消费（API + UI + CLI）？**
   - 是 → 放 Manager 或 Core
3. **该组件是否纯基础设施（无业务逻辑、无业务类型依赖）？**
   - 是 → 放 Core
4. **该组件是否仅处理 HTTP 请求解析/响应格式化？**
   - 是 → 放 `docker/api/`

### 5.2 代码审查检查项

- [ ] Core 层无 `from pilotstd.manager` 或 `from pilotstd.query` 导入
- [ ] API 端点无直接业务逻辑实现
- [ ] Manager 层的服务通过依赖注入获取子组件（不通过全局单例）
- [ ] 新增组件路径与依赖方向一致

---

## 6. 证据附录

### 证据1：目录结构

```
pilotstd/
├── core/            # 15 个 .py 文件 + notification/ 子包（6 个 .py 文件）
├── manager/         # 7 个 .py 文件（facade ~1200行）
├── query/           # 12 个 .py 文件 + adapters/ 子包（7 个适配器）
├── download/        # 5 个 .py 文件 + adapters/ 子包
├── scan/            # 6 个 .py 文件
├── organizer/       # 4 个 .py 文件
├── announcement/    # 8 个 .py 文件 + adapters/ 子包
├── task/            # 3 个 .py 文件
├── pipeline/        # 1 个 .py 文件
├── monitor/         # 3 个 .py 文件
├── quality/         # 3 个 .py 文件 + rules/ 子包
├── wechat_ip/       # 7 个 .py 文件
├── ui/              # 桌面 GUI（PyQt6）
├── cli/             # 命令行接口
├── i18n/            # 国际化
└── models.py        # 共享数据模型

docker/
├── api/             # 27 个 API 路由模块
├── app.py           # FastAPI 入口
├── manager.py       # StandardManager 单例
├── scheduler.py     # APScheduler 调度器
├── auth.py          # 认证中间件
└── users.py         # 用户管理
```

### 证据2：导入关系验证

```
$ grep -rn "from pilotstd.manager" pilotstd/core/
(零命中 — Core 不依赖 Manager)

$ grep -rn "from pilotstd.core" pilotstd/manager/ | head -5
pilotstd/manager/facade.py:14: from ..core.config import ConfigManager, get_db_path, get_library_root
pilotstd/manager/facade.py:15: from ..core.db import Database
pilotstd/manager/facade.py:16: from ..core.file_index import FileIndexRepository
...

$ grep -rn "from pilotstd.query" docker/ | head -5
(零命中 — API 不直接依赖业务层)

$ grep -rn "from docker" pilotstd/
(零命中 — Core/Manager 不依赖 API 层)
```

### 证据3：正确调用模式

**模式 A：API → Manager**（[docker/api/query.py:8](docker/api/query.py#L8)）
```python
from ..manager import get_manager_dep
@router.post("/api/query")
def query_standards(..., mgr=Depends(get_manager_dep)):
    results, stats = mgr.query_by_numbers(numbers, ...)
```

**模式 B：Manager → 业务层**（[facade.py:86-107](pilotstd/manager/facade.py#L86-L107)）
```python
from ..query.engine import QueryEngine
from ..query.rotator import SiteRotator
from ..query.daily_quota import DailyQuotaTracker
# 在 __init__ 中组装：
sites = create_default_sites()
self.rotator = SiteRotator(sites, db=self.db)
self.query_engine = QueryEngine(adapters, ..., rotator=self.rotator, ...)
```

**模式 C：业务层 → Core**（[query/daily_quota.py:10](pilotstd/query/daily_quota.py#L10)）
```python
from ..core.db import Database
class DailyQuotaTracker:
    def __init__(self, db: Database, ...):
        self._db = db
```

### 证据4：AdapterManager 分层结论

**明确结论**：AdapterManager 应放在 `pilotstd/manager/adapter_manager.py`。

不可放入 Core 层，因为它必须导入并使用 `SiteRotator` + `DailyQuotaTracker`（均为业务层类型），而 Core 层禁止向上引用业务层。
