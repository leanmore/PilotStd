# 项目文件夹现状调查报告

> 调查日期：2026-06-29
> 对照依据：四层架构定义 v2.0 (`docs/architecture_layers.md`)

---

## 1. 目录结构总览

### 1.1 Core 层 (`pilotstd/core/`)

| 文件 | 类型 | 架构符合性 |
|------|------|-----------|
| `db.py` | 数据库封装 | ✅ 正确 |
| `config.py` | 配置管理 | ✅ 正确 |
| `logger.py` | 日志管理 | ✅ 正确 |
| `cache_manager.py` | 缓存管理 | ✅ 正确 |
| `file_index.py` | 文件索引仓库 | ✅ 正确 |
| `file_utils.py` | 文件工具 | ✅ 正确 |
| `validity_checker.py` | 时效性检查 | ✅ 正确 |
| `path_guard.py` | 路径安全 | ✅ 正确 |
| `std_utils.py` | 标准号工具 | ✅ 正确 |
| `notification/` | 通知子包（6 文件） | ✅ 正确 |
| `frozen.py` | 打包检测 | ⚠️ 见下文 |
| `project.py` | 项目状态管理 | ⚠️ 见下文 |
| `updater.py` | 桌面升级 | ❌ 见下文 |
| **`notify.py`** | **Qt 托盘通知** | **❌ 违规** |

**文件数**：23 个 .py 文件（含 notification/ 子包 6 个）

### 1.2 业务层

| 包 | 文件数 | 职责 | 架构符合性 |
|----|--------|------|-----------|
| `query/` | 18 | 标准号查询（含 adapters/ 子包 7 个适配器） | ✅ |
| `download/` | 7 | 文件下载 | ✅ |
| `scan/` | 7 | 文件扫描与解析 | ✅ |
| `organizer/` | 5 | 文件归档整理 | ✅ |
| `announcement/` | 11 | 公告抓取（含 adapters/ 子包 3 个适配器） | ✅ |
| `task/` | 4 | 后台任务队列 | ✅ |
| `pipeline/` | 2 | 管线路由 | ✅ |
| `monitor/` | 4 | 文件系统监控 | ✅ |
| `quality/` | 5 | 数据质量（含 rules/ 子包） | ✅ |
| `wechat_ip/` | 6 | 微信 IP 检测 | ✅ |

**合计**：69 个 .py 文件，10 个业务域全部独立

### 1.3 Manager 层 (`pilotstd/manager/`)

| 文件 | 行数 | 职责 |
|------|------|------|
| `facade.py` | ~2400 | 主门面 `StandardManager` |
| `service_factory.py` | ~100 | 子服务创建工厂 |
| `scheduled_service.py` | ~200 | 定时任务专用方法 |
| `classifier.py` | ~260 | 分类引擎 |
| `organizer_service.py` | ~850 | 文件组织服务 |
| `announce_service.py` | ~330 | 公告服务 |
| `pending_service.py` | ~310 | 待确认项服务 |
| `user_service.py` | ~130 | 用户管理服务 |
| `validity_service.py` | ~70 | 时效性检查服务 |
| `adapter_manager.py` | ~80 | 适配器状态管理 |
| `__init__.py` | ~20 | 包初始化 |

**文件数**：11 个 .py 文件（架构文档记录为 7 个，实际增加了 4 个 Service）

### 1.4 API 层 (`docker/`)

| 层级 | 文件 | 数量 |
|------|------|------|
| 入口 | `app.py` — FastAPI 应用 | 1 |
| 鉴权 | `auth.py` — JWT + 中间件 | 1 |
| 用户 | `users.py` — 用户管理逻辑 | 1 |
| 调度 | `scheduler.py` — APScheduler | 1 |
| 单例 | `manager.py` — `StandardManager` 单例工厂 | 1 |
| WebSocket | `websocket.py` | 1 |
| API 路由 | `api/*.py` | 32 |

**API 路由文件数**：32 个（架构文档记录 27 个，增加 5 个）

### 1.5 三端特有层

| 端 | 目录 | 文件数 | 状态 |
|----|------|--------|------|
| Web | `docker/api/` + `docker/app.py` | 38 | ✅ |
| WinUI | `pilotstd/ui/` | 29（controllers/ + widgets/） | ✅ |
| CLI | `pilotstd/cli/` | 2 | ✅ |

### 1.6 根目录杂项

| 位置 | 内容 | 状态 |
|------|------|------|
| `pilotstd/` 根 | `__init__.py` + `models.py` | ✅ 无游离文件 |
| `docker/` 根 | 6 个 .py 文件 | ✅ 各有明确职责 |
| 空目录 | 无（除 `__pycache__/`） | ✅ |

---

## 2. 文件归属违规清单

### 2.1 共享层包含端特有依赖 ❌

| # | 文件 | 违规导入 | 严重度 | 建议 |
|---|------|---------|--------|------|
| 1 | `pilotstd/core/notify.py:6` | `from PyQt6.QtWidgets import QSystemTrayIcon` | **高** | 移入 `pilotstd/ui/notify_service.py`，Core 层只保留抽象接口 |
| 2 | `pilotstd/core/updater.py` | 包含 Windows 专属逻辑（`update.bat` 生成、Windows 路径） | **中** | 移入 `pilotstd/platform/updater.py` 或保留但标记为 Desktop 平台 |
| 3 | `pilotstd/core/frozen.py` | `sys.frozen` / `__compiled__` 检测 — 打包专用 | **低** | 可保留（轻量检测，无框架依赖），或移入 `pilotstd/platform/` |
| 4 | `pilotstd/core/project.py` | 应用级状态管理 — 非基础设施 | **低** | 可移入 Manager 层或保留 |

**核心问题**：`notify.py` 是 Core 层直接依赖 PyQt6 的唯一入口。当 Docker/CLI 环境 import Core 时，PyQt6 不可用会导致 `ImportError`。

实际验证——代码中有防御：
```python
# notify.py 未做 try/except 保护，
# 但调用方（pilotstd/manager/facade.py）使用了惰性导入和 try/except
```

如果 Docker 部署时 `pilotstd.core` 被扫描，`notify.py` 的顶层 `from PyQt6.QtWidgets import QSystemTrayIcon` 会导致整个应用崩溃。

### 2.2 端特有层包含业务逻辑 ⚠️

#### 2.2.1 API 层直接导入业务层

| # | 文件 | 违规导入 | 严重度 |
|---|------|---------|--------|
| 1 | `docker/api/monitor.py:7-8` | `from pilotstd.monitor.config import ...` `from pilotstd.monitor.scheduler import ...` | **中** |
| 2 | `docker/api/wechat_ip.py:11-24` | 4 个 `from pilotstd.wechat_ip.*` import | **中** |
| 3 | `docker/api/tasks.py:77,102` | `from pilotstd.task.models import TaskType, TaskStatus` | **低** |
| 4 | `docker/api/quality.py:18` | `from pilotstd.quality import QualityRunner`（惰性） | **低** |
| 5 | `docker/app.py:133-179` | 6 处 `from pilotstd.{task,monitor,wechat_ip}.scheduler` import | **中** |

**分析**：
- `monitor.py` 和 `wechat_ip.py` 是最严重的违规——API 路由直接导入并使用业务层模块，完全绕过 Manager
- `app.py` 的 lifespan 中直接操作业务层调度器，这些逻辑应封装在 Manager 的方法中
- `tasks.py` 和 `quality.py` 为惰性导入，相对轻微

#### 2.2.2 API 层直接操作数据库

| # | 文件 | 操作 | 严重度 |
|---|------|------|--------|
| 1 | `docker/api/notification.py:151-196` | 通过 `nmgr._db`（私有属性）直接 SQL | **高** |
| 2 | `docker/api/users.py:51-52` | 创建独立 DB 连接查用户 | **中** |
| 3 | `docker/api/adapter.py:55` | `mgr.db.fetchall("SELECT * FROM adapter_health")` | **中** |
| 4 | `docker/api/export.py:20` | `mgr.db.fetchall("SELECT ... FROM standard_validity")` | **低** |
| 5 | `docker/api/announce.py:161` | `mgr.db.fetchall("SELECT DISTINCT ... FROM announcement_record")` | **低** |
| 6 | `docker/api/standards.py:22,65,71` | 3 处 `mgr.db.fetchone/fetchall` | **低** |
| 7 | `docker/api/announce_lookup.py:21` | `mgr.db.fetchall(...)` | **低** |

**分析**：
- `mgr.db.fetchone/fetchall` 是 Manager 故意暴露的只读接口，用于轻量统计查询。架构文档将此列为"合法场景"
- `notification.py` 通过 `nmgr._db` 访问私有属性是明确的违规
- `users.py` 创建独立 DB 连接是违规——应通过 `user_service` 查询

#### 2.2.3 WinUI 层直接操作数据库

| # | 文件 | 操作 | 严重度 |
|---|------|------|--------|
| 1 | `pilotstd/ui/widgets/notification_bell_widget.py:49-121` | 直接 `sqlite3.connect()` + 建表 + CRUD | **高** |

该 Widget 自己管理了一个独立的 `notification_cache` SQLite 表，完全绕过了 Core 层的 `Database` 封装和 Manager 层的 `notification_mgr`。

### 2.3 循环依赖

**检查结果**：✅ 未发现循环依赖。

### 2.4 跨层直接调用

| 方向 | 检查结果 |
|------|---------|
| API → Manager | ✅ 正常（通过 `Depends(get_manager_dep)`） |
| API → Core（惰性） | ✅ 合规（架构文档明确允许） |
| API → 业务层 | ❌ 违规（monitor/wechat_ip/tasks/quality 4 个 API 文件） |
| CLI → Manager | ✅ 正常（通过 `StandardManager()`） |
| WinUI → Manager | ✅ 正常（通过 `StandardManager`） |
| Core → Manager | ✅ 无此方向导入 |
| Core → 业务层 | ✅ 无此方向导入 |
| Core → API | ✅ 无此方向导入 |

### 2.5 游离文件

| 位置 | 检查结果 |
|------|---------|
| `pilotstd/*.py` | ✅ 仅 `__init__.py` + `models.py` |
| `docker/*.py` | ✅ 6 个文件各有明确用途 |

---

## 3. 端侧重复实现

| 功能 | Web 端 | CLI 端 | WinUI 端 | 状态 |
|------|--------|--------|---------|------|
| 查询 | `mgr.query_by_numbers()` | `mgr.query()` | Manager 门面 | ✅ 一致 |
| 下载 | `mgr.download_by_numbers()` | `mgr.download()` | Manager 门面 | ✅ 一致 |
| 扫描 | `mgr.scan_and_index()` | `mgr.scan_directory()` | Manager 门面 | ✅ 一致 |
| 归档 | `mgr.organize_files()` | `mgr.organize_files()` | Manager 门面 | ✅ 一致 |
| 一键处理 | `mgr.auto_run()` | N/A | `mgr.auto_run_stream()` | ✅ 一致 |
| 时效性检查 | `mgr.check_validity()` | N/A | Manager 门面 | ✅ 一致 |
| 通知 | `mgr.notification_mgr` | N/A | 独立 `notification_bell_widget.py` | ❌ WinUI 绕过 Manager |

**结论**：核心业务功能三端均通过 Manager 调用，架构一致性好。唯一例外是 WinUI 的通知铃铛 Widget 自建了数据库连接。

---

## 4. Web 前端结构 (`web/src/`)

| 目录 | 文件数 | 状态 |
|------|--------|------|
| `api/` | 10 个 .ts 文件 | ✅ 按业务域拆分，每个文件 ≤8 个函数 |
| `components/` | 13 个 .vue 文件 + 2 个 .test.ts | ✅ 含测试 |
| `composables/` | — | ✅ 组合式函数 |
| `stores/` | — | ✅ Pinia 状态管理 |
| `types/` | — | ✅ TypeScript 类型定义 |
| `views/` | — | ✅ 页面视图 |
| `locales/` | 3 个 JSON（中/英/繁） | ✅ i18n 完整 |

**状态**：✅ 前端结构清晰，符合 Vue 3 最佳实践。

---

## 5. 建议整改清单

### 5.1 高优先级

| # | 问题 | 位置 | 整改方式 |
|---|------|------|---------|
| 1 | Core 层 `notify.py` 依赖 PyQt6 | `pilotstd/core/notify.py` | 移入 `pilotstd/ui/notify_service.py`，Core 保留抽象 `NotifierProtocol` |
| 2 | UI 层直接 SQL 操作 | `pilotstd/ui/widgets/notification_bell_widget.py` | 改用 `StandardManager.notification_mgr` 统一接口 |
| 3 | API 通过 `nmgr._db` 私有属性操作 | `docker/api/notification.py:151-196` | 在 `NotificationManager` 上暴露公开查询方法 |

### 5.2 中优先级

| # | 问题 | 位置 | 整改方式 |
|---|------|------|---------|
| 4 | API 层直接导入 monitor/wechat_ip 业务层 | `docker/api/monitor.py`, `wechat_ip.py` | 通过 `StandardManager` 暴露调度器控制方法 |
| 5 | `app.py` lifespan 直接操作业务层调度器 | `docker/app.py:133-179` | 封装为 `StandardManager` 的 `start_schedulers()` / `stop_schedulers()` |
| 6 | `users.py` API 创建独立 DB 连接 | `docker/api/users.py:51-52` | 通过 `user_service` 查询（已部分实现） |
| 7 | `updater.py` 包含 Windows 专有逻辑 | `pilotstd/core/updater.py` | 移入 `pilotstd/platform/updater.py`，Core 保留纯网络/校验逻辑 |

### 5.3 低优先级

| # | 问题 | 位置 | 整改方式 |
|---|------|------|---------|
| 8 | `project.py` 非基础设施 | `pilotstd/core/project.py` | 移入 Manager 层或保留（依赖纯标准库，无框架耦合） |
| 9 | `frozen.py` 应用级检测 | `pilotstd/core/frozen.py` | 移入 `pilotstd/platform/` 或保留（3 行代码，无依赖） |
| 10 | API 层惰性导入 quality | `docker/api/quality.py:18` | 改为通过 Manager 调用（已有 `QualityRunner` 可用） |

---

## 6. 目录结构调整建议

基于以上分析，建议的调整：

### 6.1 新增 `pilotstd/platform/`

```
pilotstd/platform/
├── __init__.py
├── notify.py       # 从 core/notify.py 移入（Qt 托盘通知）
├── updater.py      # 从 core/updater.py 移入（桌面升级逻辑）
└── frozen.py       # 从 core/frozen.py 移入（打包检测）
```

`platform/` 包明确标记为"桌面平台专属"，允许依赖 PyQt6。Core 层保留无平台依赖的纯基础设施。

### 6.2 Manager 层扩展

为消除 API→业务层的直接导入，Manager 层需新增：

```python
# facade.py 新增方法
def get_monitor_status(self): ...       # 替代 monitor.py 直接导入
def start_monitor(self): ...
def stop_monitor(self): ...
def get_wechat_ip_status(self): ...     # 替代 wechat_ip.py 直接导入
def trigger_wechat_ip_check(self): ...
```

### 6.3 Core 层清理

```
移除：
  core/notify.py   → platform/notify.py
  core/updater.py  → platform/updater.py（或拆分为 core/update_checker.py + platform/updater_ui.py）
  core/frozen.py   → platform/frozen.py

保留：
  core/project.py  → 无框架依赖，可暂留
```

---

## 7. 合规性总结

| 检查维度 | 结果 |
|---------|------|
| 目录结构完整性 | ✅ 四层架构完整，10 个业务域独立 |
| 依赖方向 | ⚠️ 发现 7 处 API→业务层违规 |
| Core 层纯洁性 | ❌ `notify.py` 依赖 PyQt6 |
| 端侧重复实现 | ✅ 三端统一通过 Manager |
| 循环依赖 | ✅ 无 |
| 游离文件 | ✅ 无 |
| Web 前端结构 | ✅ 清晰规范 |
| 空目录 | ✅ 无 |

**总体评估**：架构骨架健康，四层模型在实际代码中得到较好遵守。主要问题集中在：(1) Core 层包含的 Qt 通知代码应该移出；(2) 部分 API 端点绕过 Manager 直接导入业务层；(3) WinUI 的一个 Widget 自建数据库连接。这些问题不影响当前功能，但会在未来重构或跨平台部署时造成障碍。

---

## 8. 证据附录

### 证据 A：目录结构

```
pilotstd/ (70 个业务 .py 文件)
├── core/            23 文件（含 notification/ 子包 6 文件）
├── manager/         11 文件
├── query/           18 文件（含 adapters/ 子包 7 文件）
├── download/         7 文件
├── scan/             7 文件
├── organizer/        5 文件
├── announcement/    11 文件（含 adapters/ 子包 3 文件）
├── task/             4 文件
├── pipeline/         2 文件
├── monitor/          4 文件
├── quality/          5 文件（含 rules/ 子包）
├── wechat_ip/        6 文件
├── ui/              29 文件
├── cli/              2 文件
└── i18n/             4 文件（含 3 种语言）

docker/
├── api/             32 路由文件
├── app.py           入口
├── auth.py          鉴权
├── users.py         用户管理
├── manager.py       单例工厂
├── scheduler.py     定时任务
└── websocket.py     WebSocket

web/src/
├── api/             10 API 封装文件
├── components/      13 组件（含测试）
├── composables/     组合式函数
├── stores/          Pinia Store
├── types/           类型定义
├── views/           页面视图
└── locales/         3 语言包
```

### 证据 B：导入违规扫描

```
$ grep -rn "from pilotstd.\(query\|download\|scan\|organizer\|announcement\|task\|pipeline\|monitor\|quality\|wechat_ip\)" docker/
docker/api/monitor.py:7:  from pilotstd.monitor.config import ...
docker/api/monitor.py:8:  from pilotstd.monitor.scheduler import ...
docker/api/quality.py:18: from pilotstd.quality import QualityRunner
docker/api/tasks.py:77:   from pilotstd.task.models import TaskType
docker/api/tasks.py:102:  from pilotstd.task.models import TaskStatus
docker/api/wechat_ip.py:  (6 imports)
docker/app.py:            (6 imports)

$ grep -rn "from docker" pilotstd/
(零命中 — Core/Manager 不依赖 API 层)

$ grep -rn "from pilotstd.manager" pilotstd/core/
(零命中 — Core 不依赖 Manager)

$ grep -rn "from PyQt6" pilotstd/core/
pilotstd/core/notify.py:6: from PyQt6.QtWidgets import QSystemTrayIcon
(1 处违规)

$ grep -rn "import PyQt6\|from PyQt6" pilotstd/ | grep -v "/ui/" | grep -v "/cli/"
pilotstd/core/notify.py:6: from PyQt6.QtWidgets import QSystemTrayIcon
(Core 层中仅 notify.py 引入 Qt 依赖)
```

### 证据 C：端侧数据库直接操作

```
$ grep -rn "\.execute\|\.fetchone\|\.fetchall" pilotstd/ui/
pilotstd/ui/widgets/notification_bell_widget.py:49-121 (9 处 SQL 操作)

$ grep -rn "\.execute\|\.fetchone\|\.fetchall" docker/api/
docker/api/adapter.py:55       mgr.db.fetchall(...)
docker/api/announce.py:161     mgr.db.fetchall(...)
docker/api/announce_lookup.py  mgr.db.fetchall(...)
docker/api/export.py:20        mgr.db.fetchall(...)
docker/api/notification.py:    nmgr._db.fetchone/fetchall/execute (5 处)
docker/api/standards.py:       mgr.db.fetchone/fetchall (3 处)
docker/api/system.py:173       mgr.db.fetchone(...)
docker/api/users.py:52         独立 db.fetchone(...)
```
