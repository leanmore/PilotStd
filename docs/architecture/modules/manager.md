# 模块文档：管理模块（Manager）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/manager/` |
| G-031 映射 | `pilotstd/manager/` |
| 核心类 | `StandardManager(BaseFacade)` |
| 子模块数 | 32 个文件；facade 7 个处理类/子系统（另为包入口、基类、容器）|
| 总行数 | ~4,781（2026-09-21 实测）|
| 状态 | 活跃 |

## 模块职责

PilotStd 的业务逻辑中枢，作为 CLI / WinUI / Docker 三端的统一后端。所有用户操作（扫描、查询、下载、归档、公告检查、设置管理）均通过 `StandardManager` 门面路由到对应的 Handler 或 Service。三端通用逻辑必须在此层实现，禁止在各端各自实现。

> **名称决策结果落库（2026-10-05，名称解析统一批次二）**：`manager/classifier.py::QueryClassifier.classify()`
> 在 `_dispatch_by_router()`（＝`PipelineRouter.apply_actions` ⇒ `_resolve_names`，即名称决策出口）**之后**调用
> `_persist_final_names()`，把决策产出的 `final_name` 用**单次 `Database.executemany`** 批量写入
> `announcement_record.final_name`（独立短连接＝独立事务、best-effort：失败只记 debug，不影响分类结果与后续归档；
> 标准号在公告表中无对应行时 UPDATE 影响 0 行属正常，静默跳过）。
> 该列由**迁移 v66** 引入（并从 `pending_lookup.final_name` 关联回填、只填空行）；DB 后消费方
> （下载通知族等）经 `pilotstd/core/name_resolution.py::fetch_resolved_name()` 按 **③决策 → ②查询 → ①解析** 读取。

## 架构

```
StandardManager (BaseFacade)
│
├── ManagerCore (@dataclass 依赖容器，30 字段)
│   ├── cfg: ConfigManager
│   ├── db: Database
│   ├── parser: StandardParser
│   ├── scanner: FileScanner
│   ├── query_engine: QueryEngine
│   ├── cache: CacheManager
│   ├── quota_tracker: DailyQuotaTracker
│   ├── download_engine: DownloadEngine
│   ├── session_mgr: SessionManager
│   ├── task_queue: TaskQueue
│   ├── router: PipelineRouter
│   └── ... (共 30 个字段/依赖)
│
├── facade/ (Handler 层)
│   ├── _scan.py      — ScanHandler
│   ├── _query.py     — QueryHandler
│   ├── _download.py  — DownloadHandler
│   ├── _organize.py  — OrganizeHandler
│   ├── _file_index.py — FileIndexHandler
│   ├── _auto.py      — AutoPipeline
│   ├── _base.py      — BaseFacade 依赖组装
│   └── _core.py      — ManagerCore 容器定义
│
└── Service 层
    ├── AnnounceService     — 公告抓取与匹配
    ├── PendingService      — 待处理队列
    ├── ScheduledService    — 定时任务
    ├── OrganizerService    — 文件归档
    ├── ValidityService     — 标准有效性检查
    ├── UserService         — 用户管理
    ├── SettingsManager     — 设置持久化
    ├── AdapterManager      — 适配器注册
    ├── ExportService       — 导出
    ├── QualityService      — 质量检查
    ├── MonitorService      — 监控
    ├── SystemService       — 系统信息（`_init_services` 接线，供 `/api/system/health` 使用）
    └── WechatIPService     — 企业微信 IP
```

> 变更记录（2026-09）：原 `ArchiveRetryService`（`archive_retry_service.py`）为死代码——自 v54 起
> `auto_archive_retry` 由 `favorite_chain_processor.process_chain()` 承担，该服务无任何调度方，
> 已删除；其 `archive_abandoned` 通知职责迁入收藏下载链。`SystemService` 由
> `BaseFacade._init_services()` 实例化后暴露为 `mgr.system_service`。

## 门面模式

- `StandardManager` 是唯一对外暴露的业务入口
- `BaseFacade.__init__()` 执行"依赖组装"：创建空的 `ManagerCore` → 逐一初始化子系统 → 构造 Handler 实例填入 `_core`
- 三端（CLI/WinUI/Docker）通过同一门面调用，确保逻辑一致
- Handler 之间通过 `ManagerCore` 共享依赖，不直接通信

## 废止类状态判定（#32-A / R14-4a，2026-10-01）

本模块内原先**各自硬编码**废止类状态集合的 4 处定义已收敛到权威字典 `pilotstd/core/status.py`
（`ABOLISHED_STATUSES` 4 值 / `ABOLISHED_STATUSES_WITH_EXPIRED` 5 值），**取值集合与重构前逐一等价**：

| 位置 | 原字面量 | 现引用 |
|---|---|---|
| `pilotstd/manager/classifier.py`（`QueryClassifier._EXPIRE_STATUSES`） | `{废止, 已废止, 作废, 被代替}` | `status.ABOLISHED_STATUSES` |
| `pilotstd/manager/facade/_query.py`（`QueryHandler._EXPIRE_STATUSES`） | 同上 4 值 | `status.ABOLISHED_STATUSES` |
| `pilotstd/manager/facade/_query_subsystem.py`（`QuerySubsystem._EXPIRE_STATUSES`） | 同上 4 值 | `status.ABOLISHED_STATUSES` |
| `pilotstd/manager/facade/_organize.py`（`archive_standards` 内局部变量） | 5 值（含 `过期`） | `status.ABOLISHED_STATUSES_WITH_EXPIRED` |

> A 阶段只做"建字典 + 容器收敛"：**不替换**业务逻辑中的状态字面量（B 阶段）、不改 API 返回字符串、
> 不改 DB 迁移脚本。等价性由 `tests/unit/core/test_status.py` 断言（含"容器与命名集合为同一对象"）。
>
> **B 阶段（R14-4b，2026-10-01）**：本模块业务代码中的状态字面量已改引 `Status.*.value`——`standard_service.py`（状态统计聚合）、`facade/_download.py`（下载后状态回写判定）、`facade/_file_index.py`、`facade/_organize.py`、`facade/_query_subsystem.py`、`organize/organizer.py`、`wechat_ip_service.py`，共 32 处，**逐处等价**（`Status.*.value` 与原中文字面量逐字相同，API 返回与 DB 落库行为不变）。**C 阶段补充（R14-4c）**：`wechat_ip_service.get_status()` 新增 `current_ip_known` 布尔键（`bool(now_ip)`），取代前端 `current_ip !== '未知'` 的中文文案比较——该字段属 IP 检测域，与标准状态字典同批收口。

## 关键接口

| 方法 | 说明 |
|------|------|
| `scan(path)` | 触发目录扫描，返回标准条目列表 |
| `query(entries)` | 批量查询标准号，返回查询结果 |
| `download(results)` | 批量下载标准文件 |
| `organize(paths)` | 按标准号归档文件 |
| `check_announcements()` | 检查公告更新 |
| `get_settings()` / `update_settings()` | 设置读写 |

## 依赖关系

- `pilotstd/scan/` — 文件扫描与解析
- `pilotstd/query/` — 查询引擎与适配器
- `pilotstd/download/` — 文件下载引擎
- `pilotstd/organizer/` — 文件归档
- `pilotstd/announcement/` — 公告抓取
- `pilotstd/core/` — 配置、数据库、日志、通知等基础设施
- `pilotstd/task/` — 任务队列与调度

## 相关文档

- [UI 模块](ui.md) — MainWindow 通过 `self._mgr` 调用本模块
- [查询适配器](query.md) — 适配器注册与路由
- [解析器模块](parser.md) — 标准号解析

## 近期变更

- **2026-10-02**：`facade/_base.py` 的通知收件人改为**构造时注入**（通知架构重设计阶段 1a 顺手项）。`BaseFacade.__init__` 新增关键字参数 `user_id: int = 1`，`_init_services()`（`:250` 附近）与 `_init_notification()` 的 `NotificationManager(..., user_id=1)` 硬编码改为 `user_id=self._facade_user_id`。**默认仍为 1，全部调用点（`StandardManager()` 的 12 处生产 + 22 处测试）零改动，`send_event` 签名与 51 个调用点不改**——当前为单用户部署，此举仅为将来多用户留门，属已登记技术债而非阻塞项（裁决 Q6）。背景与边界见 [06-阶段0-1实施方案.md](../../plans/notification-redesign/06-阶段0-1实施方案.md) §1.4。
- **2026-09-26**：`facade/_download.py::download_stream` 补齐 `batch_download_complete` 通知接线。此前该流式路径手工累加 `BatchDownloadStats`，从不传 `notification_mgr`（同文件 `download()` 则显式传入），导致 Web `/api/download` 与桌面 `DownloadWorker` 的批量下载结束零通知，而收藏链经 `download_engine.run_paced_batches()` 自建汇总——两条路径行为不一致。修复含两处细节：`stats.total` 在循环内累加（`_notify_download_complete` 读该字段，原为 0）；通知口径的 `skipped` 映射自本方法的 `skipped_exists`（引擎侧读 `skipped_adopted`，两字段不同）。通知失败仅 `logger.warning`，不阻断下载。契约由 `tests/unit/manager/facade/test_download_handler.py::TestDownloadStream` 四例锁定（成功/失败/跳过/零任务）。设计方案见 [通知重构设计](../../plans/notification-refactor-design.md)。
