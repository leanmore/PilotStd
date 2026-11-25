# 模块文档：管理模块（Manager）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/manager/` |
| G-031 映射 | `pilotstd/manager/` |
| 核心类 | `StandardManager(BaseFacade)` |
| 子模块数 | 32 个文件；facade 7 个处理类/子系统（另为包入口、基类、容器）|
| 总行数 | 4,991（2026-10-17 实测，32 个 .py 换行符计数）|
| 状态 | 活跃 |

## 模块职责

PilotStd 的业务逻辑中枢，作为 CLI / WinUI / Docker 三端的统一后端。所有用户操作（扫描、查询、下载、归档、公告检查、设置管理）均通过 `StandardManager` 门面路由到对应的 Handler 或 Service。三端通用逻辑必须在此层实现，禁止在各端各自实现。

> **名称决策结果落库（2026-10-05，名称解析统一批次二）**：`manager/classifier.py::QueryClassifier.classify()`
> 在 `_dispatch_by_router()`（＝`PipelineRouter.apply_actions` ⇒ `_resolve_names`，即名称决策出口）**之后**调用
> `_persist_final_names()`，把决策产出的 `final_name` 用**单次 `Database.executemany`** 批量写入
> `announcement_record.final_name`（独立短连接＝独立事务、best-effort：失败只记 debug，不影响分类结果与后续归档；
> 标准号在公告表中无对应行时 UPDATE 影响 0 行属正常，静默跳过）。
> **v67-a 解耦（2026-10-05）**：`manager/pending_service.py::record_pending()` 的 INSERT **不再写**
> `pending_lookup.final_name`（③ 权威落点已在 `announcement_record.final_name`）；该旧列自此**运行时零读写**，
> 仅作历史数据保留（物理删除属 v67-b，需先实测迁移链兼容性）。
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
    ├── ValidityService     — 标准有效性检查 + validity_check_queue 消费
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

- **适配器状态读取的失败可见性（2026-10-17，体检 D-8/D-9）**：`AdapterManager.get_adapter_status` 读 `adapter_state` 失败、`frozen_until` 解析失败、`get_all_health` 读失败原先 `except: pass`（状态会误报 `normal`、全量健康返回空列表）；现统一记 warning 后再回退，**接口语义不变**。契约由 `tests/test_silent_error_observability_batch2.py` 锁定。

- **归档/扫描路径的失败可见性（2026-10-17，体检 D-8 第 6 批）**：`expire`/`mirror`/`organizer` 的文件清理 `OSError`、`_backfill_std_name` 的缓存查询与 `result_json` 解析失败、`scan_directory(_stream)` 的缓存失效失败，均由 `pass` 改为 debug（行为不变）；契约由 `tests/test_silent_error_observability_batch6.py` 锁定。

- **抓取失败历史读侧（2026-11-09，P1-03）**：`AnnounceService.get_fetch_failures(limit, unresolved_only)` 读 `fetch_failures`，返回 `total/unresolved/items`；`GET /api/announce/fetch-failures` 供公告页/诊断读取；`AnnounceView` 显示“抓取失败 N 条未解决”面板。此前该表只写不读，失败只有即时通知、没有历史/恢复状态出口。
- **公告抓取回看（2026-11-07；2026-11-10 U38 补强）**：`AnnounceService.check_announcements` 读取 `announcement.lookback_days`（默认 7），从 checkpoint 向前多回看；定时入口用 `_missed_gap_hours` 检测超过 `announcement.missed_after_hours`（默认 36）的漏跑，**并按实际 gap 向上取整扩大 lookback**（覆盖版本更新/停机超过 7 天），再写入完成通知。
- **可信 IP 自动更新（2026-11-10 U39）**：升级 CloakBrowser 0.7.2 + 钉 Playwright 1.64.1；`WechatIPUpdater.close()` 同时 stop Playwright driver；Docker 预装 Playwright Chromium（`/ms-playwright`）供回退路径使用；构建期 `RUN python -c "from cloakbrowser import launch, launch_persistent_context"` fail-fast。
- **下载任务持久化（2026-11-07）**：`DownloadEngine` 把任务状态写入 `task_queue`（task_type=download）；启动补跑未完成任务，`retry_count >= max_retries` 停止。
- **归档预览名与冲突（2026-11-07）**：`FileMover.normalize_filename` 优先使用 `ParsedStdInfo.final_name`；`OrganizerCore` 对同名不同内容写入 `pending_lookup`（reason=archive_conflict），不覆盖、不自动改名。
- **auto_run 报告（2026-11-07）**：`_auto_run_impl` 增加 `organize_failed`，monitor 据此把主链归档失败计入 `failed`，不再把“解析到但搬不动”记成成功。
- **归档通知正文（2026-11-07）**：`archive_standards` 的 payload 增加 `total` / `skipped_exists` / `failed`；`archive_complete` 构建器据此写正文，零搬移也保留可读说明。
- **选中文件检查队列（2026-11-07）**：`ValidityService.enqueue_files` 写 `validity_check_queue`（v75）；`process_pending()` 将 `file_index.file_path` 映射为标准号，调用 `ValidityChecker.check_standard`，并把 success/failed/error 写回队列；调度器每 60 秒 drain 一次并在启动时补跑。前端按钮只负责入队，不再显示“已检查”。
- **入队/状态读取的失败可见性（2026-10-17，体检 D-8 第 10 批）**：`ValidityService.enqueue_files` 单条入队失败、`AnnounceService` 的 `result_data` 非法 JSON、`WechatIPService` 的 cookie 解密/校验失败、`StandardManager` 的缓存 `result_json` 解析失败，均由 `pass` 改为 warning/debug；契约由 `tests/test_silent_error_observability_batch10.py` 锁定。

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

- **2026-11-08（失败日志升级 · U34-C2）**：`announce_service.get_task_results` 的 `result_data` 脏 JSON
  由 `debug` 升 `warning`（**行为不变**：仍按 `success` 返回，只是 `data` 为空——文案已明确写出这一点，
  不再让人误以为"本来就没数据"）；**C6 补充**：脏 JSON 时返回体额外带 `message`（"结果数据损坏（invalid
  JSON），已返回空结果"），`status`/`data` 不变——**只增字段、不换语义**，消费方据此可区分"本来没数据"
  与"数据损坏"；端点契约由 `tests/test_announce_results_endpoint.py` 三例锁定；
  **C6 续**：`pending_service.enqueue_download_wait` 由 `-> None` 改为 **`-> bool`**
  （无发布日期 / 日期格式非法 → `False`，幂等命中或插入成功 → `True`）；`facade/_download.py` 两行透传；
  UI 侧改为「入队成功才计入 `too_new_set`」，失败的进 `skipped_set` 并在汇总里**单列**——
  `failed_count = total - success - too_new - skipped`，不再把"没排队"混进失败数；弹窗在 M>0 时追加
  「另有 M 条因发布日期格式异常，未加入等待队列，请手动检查」，M=0 不出这句。
  契约由 `tests/test_c2_log_levels.py` 与 `tests/test_manager_unit.py` 锁定；
  `announce_service._acquire_manual_lock` 的锁写入异常补 `warning`（原为裸 `return False`，被上层
  当成"锁被占用"⇒ 手动抓取静默不执行）；`pending_service.enqueue_download_wait` 的发布日期解析失败补
  `warning`（原静默跳过等待队列，该标准不进队列也无痕）。

- **2026-10-16（查询统计口径单源化 + `force_refresh` 透传）**：`scheduled_service.py::query_by_numbers`
  此前只填 `BatchQueryStats` 的 `total/found`，而 `/api/query` 会**原样透出** `downloadable`/`not_found`
  ⇒ 这两项恒为 0，与逐条 `is_downloadable=true` 自相矛盾（现场实测 `2026-10-16T21:22:27+08:00`：
  `GB 2894-2025` 与 `GB 2894-2008` 两条结果均 `is_downloadable=true`、`is_adopted=false`，
  而 `stats.downloadable=0`）。同一处还把 `force_refresh` **静默丢弃**
  （`query_engine.query_standards` 明确支持该参数）⇒ `POST /api/query?force_refresh=true` 从未生效。
  现改为：统计统一由 `pilotstd/query/models.py::BatchQueryStats.from_results(results)` 产出（**唯一**口径），
  `facade/_query_subsystem.py::_finalize_query` 亦改用它（原先内联同一套计数），`force_refresh` 已透传。
  契约由 `tests/unit/manager/test_scheduled_service_query_stats.py` 四例锁定。

- **2026-10-05（B1 · E1 批次键 + 跨阶段共用）**：批次键改为经 `core/notification/batch.py` 的**上下文**
  取用（`ensure_batch_key(prefix)`）——**导入入口用 `with batch_scope("imp")` 包住整段流程**时，查询/下载/
  规范化/存档四个阶段**自动共用同一个键** ⇒ 一次导入的四类通知被聚合器收敛成**一条**（需求①"一次导入 = 1 条"）；
  没有外层作用域时退化为"一次操作 = 一个批次"（与接线前行为一致，零行为变更）。上下文用 `contextvars`
  实现（线程/异步任务隔离，不串批次）。
  **边界（2026-10-05 已接线，更新）**：**已打开作用域的入口**＝`_auto.py::auto_run` 与 `auto_run_stream`
  （一键处理：扫描→查询→下载→规范化→归档 ⇒ **四阶段合成一条**）、`docker/api/download.py::import_downloads`
  与 `ui/core/handlers/_download.py::on_import_download`（导入 ⇒ 查询+下载合成一条）。
  **未包作用域**的路径（如单独触发归档/规范化、定时任务）仍是"一次操作一个批次"（零行为变更）。
- **2026-10-05（B1 · E1 批次键）**：三条路径的**批次标识**在入口生成并随 payload 透传——
  `facade/_organize.py::archive_standards` ⇒ `arch-<uuid8>`；`facade/_organize.py::normalize_files_stream`
  ⇒ `norm-<uuid8>`；`facade/_query_subsystem.py::_finalize_query` ⇒ `qry-<uuid8>`（一次操作 = 一个批次）。
- **2026-10-24（Q11 管道级终局汇总）**：`_auto.py::_auto_run_impl` 与流式版收尾各调用一次
  `_notify_auto_pipeline_summary(report)`，发 `auto_pipeline_summary`（扫描/查到/下载/归档四行统计）；
  与四阶段通知同处 `batch_scope("imp")`，故仍收敛为一条，不新增消息条数。
  该键经 `notification._dispatcher.send_event` 搬到 `NotificationMessage.correlation_id`，驱动聚合器走
  **①批次键**（`correlation_id × notify_event`）把本次操作的通知收敛成一条；为空则走 **②日常键**。
  **注意**：这三处是"各自操作一个批次"；跨阶段（导入→查询→下载→规范化→存档）共用同一批次键尚未接线。
- **2026-10-05（B1-3 同批）**：把已采集的失败明细**接入各汇总事件的 payload**，满足 G-045 契约（"声明的 key 必须由触发方提供"）。
  - `facade/_organize.py`：`archive_complete` 的 payload 追加 `"failed_items": result.get("failed_items", [])`；
    `normalize_complete` 的 payload 追加 `"failed_items"`（该路径按整批一条发送；逐条采集见 `organize_stream` 失败分支）。
  - `facade/_query_subsystem.py`：`batch_query_summary` 的 payload 追加 `"failed_items"`（查询失败为**整批一条**，明细暂为空列表）。
  - 契约表 `tests/test_notification_e2e.py::TRIGGER_KEYS` 已同批补 4 条；`archive_complete` 按实现对齐为
    `{"category_stats","count","directories","failed_items"}`。
- **2026-10-05**：`facade/_organize.py` 的**失败采集**接入通知聚合 B1-1（需求①「批量导入失败要说明标准号 + 标准名」）。
  `organize_stream` 的失败分支由 `except Exception` 改为 `except Exception as exc`，在累加 `result["failed"]` 的同时向
  `result["failed_items"]` 追加 4 列明细（`standard_number` / `standard_name` / `error_type` / `error_message`）；
  同文件新增模块级工具 **`_fmt_std_number(parsed)`**（按 `ParsedStdInfo` 的 `logical_code` / `raw_number` / `number` / `year`
  拼成可读编号，优先 `raw_number` 以保留前导零；年度缺失时不追加 `-年份`）。`standard_name` 走 ADR-016 回退链
  （`final_name → found_name → std_name → "-"`）；`error_message` 截断 120 字符。数据载体与落库列见
  `pilotstd/core/notification/channel.py` 的 `failed_items` 与迁移 `v67`。
- **2026-10-02**：`facade/_base.py` 的通知收件人改为**构造时注入**（通知架构重设计阶段 1a 顺手项）。`BaseFacade.__init__` 新增关键字参数 `user_id: int = 1`，`_init_services()`（`:250` 附近）与 `_init_notification()` 的 `NotificationManager(..., user_id=1)` 硬编码改为 `user_id=self._facade_user_id`。**默认仍为 1，全部调用点（`StandardManager()` 的 12 处生产 + 22 处测试）零改动，`send_event` 签名与 51 个调用点不改**——当前为单用户部署，此举仅为将来多用户留门，属已登记技术债而非阻塞项（裁决 Q6）。背景与边界见 [notification-redesign/00-README.md](../../.local/archive/2026-11-08/docs/plans/notification-redesign/00-README.md) §1.4。
- **2026-09-26**：`facade/_download.py::download_stream` 补齐 `batch_download_complete` 通知接线。此前该流式路径手工累加 `BatchDownloadStats`，从不传 `notification_mgr`（同文件 `download()` 则显式传入），导致 Web `/api/download` 与桌面 `DownloadWorker` 的批量下载结束零通知，而收藏链经 `download_engine.run_paced_batches()` 自建汇总——两条路径行为不一致。修复含两处细节：`stats.total` 在循环内累加（`_notify_download_complete` 读该字段，原为 0）；通知口径的 `skipped` 映射自本方法的 `skipped_exists`（引擎侧读 `skipped_adopted`，两字段不同）。通知失败仅 `logger.warning`，不阻断下载。契约由 `tests/unit/manager/facade/test_download_handler.py::TestDownloadStream` 四例锁定（成功/失败/跳过/零任务）。设计方案见 [通知重构设计](../../.local/archive/2026-11-08/docs/plans/notification-refactor-design.md)。

**时效性/归档配置（2026-10-24）**：归档目录使用 `storage.expire_folder` 配置作为“过期作废”目录名；时效性到期查询联查 `file_index.file_path`，排除该目录下的标准。

**归档/时效性（2026-10-24）**：storage.expire_folder 同时用于归档路径与时效性排除；过期状态自动移动。

**通知标准名（2026-10-24）**：替代关系补查、查询失败、废止移动等事件同时携带 standard_name，通知构建器统一拼接标准号与名称。

**通知标准名（2026-10-24）**：分类器/查询失败/归档移动事件补齐 standard_name，避免只发标准号。

> **A-21 3b-2（2026-11-01）**：ScanHandler.scan_directory/stream 支持 NotificationContext；API /api/scan 以 admin 身份传入，定时 scan_and_index 固定 system。


> **A-21 3b-2 query（2026-11-01）**：QueryHandler.query/query_stream 支持 NotificationContext；UI 查询 worker 传 desktop user=1（单用户注释）。


> **A-21 3b-2 download/auto/UI（2026-11-01）**：DownloadHandler/AutoHandler 接收 context 并透传；桌面 scan/query/download/auto worker 固定 user=1（单用户注释）；收藏通知抽 _notify_favorite_created。


> **A-21 3b-4（2026-11-01）**：OrganizeHandler.archive_standards 接收 NotificationContext；UI 归档 worker 固定 user=1；渠道缓存按 user_id，system 投递所有 admin。

> **2026-11-03 `/api/standards/status` JOIN 补年份**：`StandardService.get_list` 与 `standard_validity` 的连接条件由 `代号 + 顺序号` 改为带年份（`year>0` 拼 `-year`，否则退回无年份），修复 `last_checked_at` / `check_count` 恒为空（实测 100 条采样全空）。契约见 `tests/test_batch3_validity_wiring.py::test_join_with_year_returns_last_checked`。


> **A-21 3b-2 修正（2026-11-01）**：QueryHandler.query/query_stream 透传 context（此前 UI 传 context 被 facade 丢弃，GUI 查询测试暴露）。


> **2026-11-04 通知归属（D5-3）**：`StandardManager` 的 `user_id` 默认改为 `0`（系统级）；
> `NotificationManager.send_event` 在无 `NotificationContext` 时按**系统广播**投递给全部管理员
> （旧实现固定投 user 1），用户主动操作仍显式传 `scope="user"`。

> **2026-11-04 归档计数（D1-1）**：`OrganizeHandler.organize_files` 返回 `unparsed`
> 字段并记录 WARNING；无法解析的文件不再静默消失。

> **2026-11-06 时间规范（阶段 6）**：manager 侧任务/待办/公告时间统一用
> `pilotstd.core.time_utils.iso_now()` 写入带偏移量的 ISO 8601；v73 迁移规范化历史裸时间。

> **2026-11-09 归档/索引日志升级（U-3/U-4 批 1）**：6 处 `except` 内 `debug` 升 `warning`——
> `classifier._persist_final_names`（final_name 落库失败，分类/归档主流程不受影响）、
> `facade/_scan` 的 `scan_directory` / `scan_directory_stream`（扫描后 FILE_INDEX 缓存失效失败，
> 调用方可能读到旧索引）、`organize/expire.merge_expire_from_source`（过期目录合并失败，
> 有效性信息可能未入库）、`organize/organizer` 的去重删源（源目录残留重复件）与删旧重复件失败。
> 文案均带失败后果，**控制流与返回值不变**；配合 core.md 的 5 处，G-050 debug 基线 90 → 79。

> **2026-11-13 替代关系补查属性修复（远程实测）**：`classifier.resolve_replaces` 读
> `self._query_engine._use_cache` / `._cache`，而 `QueryEngine` 只暴露 `use_cache` / `cache`
> 属性 → 每次补查都 `AttributeError`（被 `except` 吞成「替代标准查找失败」），远程 825 文件
> 批量时集中暴露。改为正确属性；测试改用 `MagicMock(spec=QueryEngine)`，旧写法会直接失败。

- **零调用清理（2026-11-13，P2-03 批 1）**：删除 AdapterManager.execute_request_interval（零调用）；get_request_interval 保留。

## 归档登记标准号（2026-11-15，P2-11 根因）

`OrganizeHandler.archive_standards` 不再直接拼接 `logical_code + number`：
- 用 `std_utils.build_standard_number` 生成规范键；
- 代号为空时从 `raw_filename` 用 `parse_std_number` 补解析（TSG 等可解析）；
- 仍无法确定 → 跳过 `register_new_standard` 并 WARNING，不写畸形键。
回归：`tests/test_p211_root_cause.py`（含归档从文件名补代号、无代号跳过）。

## pending 核销与归档明细（2026-11-15，P1/P3）

- `OrganizeHandler.archive_standards`：`moved>0` 后调用 `_resolve_archived_pending`，按
  `std_utils.build_standard_number` 同键把 `pending_lookup` 置 `resolved`（源文件仍在则不核销），
  避免“已归档仍待确认”；回归 `tests/test_p211_root_cause.py`（+2 例）。
- `AutoPipeline._auto_run_impl`：归档后打印
  `归档明细: moved/failed/skipped_exists/conflict_pending/skipped_source/dedup_skipped`，
  用于区分“查到但没搬”是目标同名同内容还是同名冲突。

## M1 工具补充（2026-11-15，续）

- `OrganizeHandler._register_moved_standards` 的键构造带 `num_prefix`；`_resolve_archived_pending`
  对“同键 + 带前缀变体”双试（Z 前缀 pending 可核销）。
- `AutoPipeline` 归档明细日志（moved/failed/skipped_exists/conflict_pending/skipped_source/
  dedup_skipped）见上节；本批未再改 manager 逻辑。
## 可信 IP 配置掩码（2026-11-19）

- update_config 对 cookiecloud_key/password 的 *** 掩码值跳过写入，避免 GET→PUT 覆盖真实凭据；get_config 在 CookieCloud 模式下按 key 显示“已配置 (CookieCloud)/未配置 CookieCloud Key”，不再误报“未配置密钥”。

## 注释语言规范化（2026-11-19）

- G-012 [LANG] 改为按词判定后，本模块注释里的英文普通词改为中文、裸标识符加反引号；
  仅注释与 docstring 变更，AST 比对无代码变化（全仓 504 行，见 27 日志 #81）。

## 公告起始日期偏好（2026-11-20）

- nnounce_service._get_user_since_date() 读 pp_preferences.announce_since_date，定时任务只用它做**一次性**回填并清空；
- 清空改为 upsert（原 UPDATE 在行缺失时静默无效，会导致每周期重复回填）；
- 注意：Web 端存的 nnounce_since_date 走 user_preferences 表，与定时任务读的 pp_preferences 不是同一张表（已知差异，未接线，见 27 #89）。

## 待确认清单的“文件缺失”判定（A-46，2026-11-21）

- `pending_service.resolve_reason(record, exists)`：空路径 → `no_file`；有路径但不存在 → `file_missing`；
  存在则保留原 reason（纯函数，便于用临时目录测试）。
- `pending_service.mark_missing_files(db, limit)`：幂等扫描 pending 行，只把 reason 改成 `file_missing`，
  不删行、不移动文件；默认不接任何定时任务或 API，调用点后续单独评审。
- 背景：生产 33 条 `file_missing` 的路径全在 `/inbox` 且文件已不存在；此前代码里没有任何写入点。

- 入口：定时任务 `pending_missing_check`（每日 03:30 UTC）与 `POST /api/pending/mark-missing`（admin）都调用
  `mark_missing_files()`；命中挂载异常（≥50 行且缺失 ≥90%）时整轮跳过并返回 `skipped=true`。

## pending_service 写入：批量查重替代逐条 SELECT（2026-11-23，NEW-04）

`PendingService.record_pending` 原对每条 item 先
`SELECT id FROM pending_lookup WHERE standard_number=?` 再决定是否 INSERT。
批量 500 条 = **500 次 SELECT** + 最多 500 次 INSERT。

**修法**：新增 `_existing_pending_numbers(numbers)`，分批
`SELECT standard_number FROM pending_lookup WHERE status='pending' AND standard_number IN (...)`
一次拿到已存在集合，再只对不在集合里的 INSERT。按 500 一批
（SQLite 单语句变量上限 999，留余量给其它占位符）。500 条从 500 次 SELECT 降到 **1 次**。

**兼容性**：若注入的 db 没有 `fetchall`（部分测试替身只实现 `fetchone`），
自动回退到逐条 `fetchone` —— 正确性一致，只是失去批量收益。

**守护**：`tests/test_pending_record_no_n_plus_one.py`（4 例）——
SELECT 次数与批次相关（不是 N）/ 已存在跳过 / 空列表零查询 / 1200 条分 3 批。

## scan_and_index 的跳过原因分类（2026-11-24，G-27）

生产实测 `indexed=0 / skipped=825 / failed=0`。原实现把三种**完全不同**的跳过原因
都记进同一个 `skipped`：

1. 文件名解析失败（`parse()` 返回 None）
2. 四要素（`sha256` / `code` / `name` / `size`）查询无命中
3. 命中但 `scan_status != 'pending'`（已索引过）

汇总日志只有 `skipped=825`，**无法判断是哪一类**，排查只能靠猜。

**修法**：三类分别计数（`skip_parse_failed` / `skip_no_match` / `skip_not_pending`），
汇总日志打出细分，并记录**第一条**未匹配样本的四要素值 —— 下次生产复跑即可
直接定位断在哪一环。

**已证伪的假设**（避免下次重复排查）：曾怀疑「归档重命名后 `std_name` 漂移导致
四要素永不匹配」。用 5 个真实文件名做 `normalize_filename` → 重新解析的往返实测，
`std_name` **漂移 0/5**，该假设不成立。

**G-010 拆分**：`scan_and_index` 由 58 涨到 98 逻辑行（超 80 阻断线），
已拆出 `_index_one_file()` 与 `_log_scan_summary()`。

**守护**：`tests/test_scan_and_index_diagnostics.py`（5 例）。

## scan_and_index：先廉价排除再算全文哈希（2026-11-24，NEW-23）

**原流程**（顺序反了）：
```
hash_file_content(path)      ← 读全文（数 MB）
  → SELECT ... WHERE sha256/code/name/size
  → parse(basename)          ← 廉价
```
文件名解析失败的文件**白读一次全文**；三要素本就不可能命中的文件同样白读。

**新流程**（先廉价后昂贵）：
```
getsize → parse(basename)                              ← 都廉价
  → SELECT id, sha256 WHERE code/name/size（fetchall）  ← 不读全文
     ├─ 无候选 → 直接判 skip_no_match，**不算哈希**
     └─ 有候选 → hash_file_content() → 在候选中精确比对 sha256
```

**语义等价性**：四要素（sha256/code/name/size）的匹配条件未变 ——
只是把「sha256 参与 SQL 过滤」改成「在 code/name/size 的候选集里比对 sha256」。
候选集由 `(code, name, size)` 限定，通常只有 0~2 行。

**守护**：`tests/test_scan_and_index_diagnostics.py`（5 例）。

## 注释中的代码标识符用反引号包裹（2026-11-24，NEW-46）

`scan_and_index` 相关注释里的英文词（`px` 类单位、方法名等）统一用反引号包裹，
以通过 G-012 的 `[LANG]` 检查。属注释规范化，无行为变更。

## 标准状态统计与筛选口径：作废计入废止族（2026-11-24，P1-5）

`Status.VOIDED`（作废）在 `core/status.py` 的 `ABOLISHED_STATUSES` 中已属废止族，
但 `standard_service` 的聚合与筛选只认「废止 + 被代替」，导致生产状态页出现
**「未知 88」= 作废 58 + 即将实施 20 + 未生效 10** 的假象（数据/解析问题为 0）。

修法（`pilotstd/manager/standard_service.py`）：
- `_map_filter_status(已废止)` 的 `IN` 增加 `Status.VOIDED.value`；
- `_map_filter_status(未知)` 的 `NOT IN` 增加 `Status.VOIDED.value`（列表与卡片口径互补）；
- `get_stats()` 的「已废止」加 `s.get(Status.VOIDED.value, 0)`。

效果：`inactive 116 → 174`、`unknown 88 → 30`、`?status=voided` 仍单独返回 58 条、总数守恒 776。
**口径修正非数据变化**，发布说明需注明。回归：`tests/test_standard_service.py`。

## 状态口径收口：`unknown` 显式分桶 + 写入端归一（2026-11-25，批次 11）

A1（上节）只修了 `作废` 这个**具体值**，没有修「四值之外即未知」的**补集机制**（P1-5 §5.2）。
本批把口径收敛成显式枚举，并把洞堵在写入端：

| 项 | 修前 | 修后 |
|---|---|---|
| `get_stats()` 分桶 | 四值之外全部计入「未知」（静默、无告警） | `_STATUS_BUCKETS` 显式枚举三桶（现行 / 已废止 / 未知；废止族含双拼写）；枚举外值仍计入「未知」但 **`logger.warning` 一次**（带取值计数 + 最多 3 条样本标准号，按服务实例去重） |
| `_map_filter_status()` | 手写四值 `IN`/`NOT IN` | 由 `_STATUS_BUCKETS` 派生 `_STATUS_FILTER_VALUES`（排除展示拼写 `已废止`）；「未知」筛选 = 非未知桶的补集 |
| 写入端 `file_index.status` | `organizer.py` 原样写 `effect_status`（`未生效` 透传） | `normalize_status_for_write()` 统一归一：`未生效 → 即将实施`、`已废止 → 废止`；枚举外且无别名的值原样保留（存量治理属批次 12） |
| 新增枚举值 | 会被静默吞进「未知」 | 必须显式进 `_STATUS_BUCKETS`，否则 `TestExplicitStatusBuckets` 红 + 生产告警 |

**不变**：`unknown` 卡片数字仍含 `即将实施`（20）+ 存量 `未生效`（10）= 30，直到批次 12 清洗；
本次修的是「机制可见性」与「不再再生」，不是立刻归零。

**回归**：`tests/test_standard_service.py::TestExplicitStatusBuckets`（枚举归桶守卫 / 分桶口径 /
筛选同源 / 枚举外告警一次带样本 / 合法值不告警）、
`tests/unit/manager/organize/test_organizer_status_normalize.py`（写入端归一 11 例）。

## 通知事件补对象（2026-11-24，P1-6 P1-5）

5 个事件此前只说「失败/未命中/没新增」，缺少可定位的对象，已补 payload 与渲染：
`scan_empty`（扫描根路径）、`query_empty`（查询标准号清单，正文列前 10 条）、
`archive_failed`（单条给标准号 / 多条给失败明细，二选一）、`normalize_failed`（失败明细）、
`auto_pipeline_summary`（批次键 `task_id` + 处理范围 `path`）。
生产者侧只新增字段采集，不改变控制流与计数；`event_spec_data.payload_keys` 同批同步
（e2e 的 `builder_keys` 由 spec 派生，不同步会让新契约不可见）。
回归：`tests/unit/core/notification/test_message_builders_snapshot.py::TestObjectInMessage`、
`tests/integration/test_notification_high_value_events.py`。

## 本地缓存离线查询：批量化（2026-11-25，方向 C 深度扫描）

`PendingService.query_local_cache`（GUI 离线查询）原实现**逐标准**点查 1~2 次 DB
（`standard_info_cache` → 未命中再查 `announcement_match`）——典型 N+1。
**修法**：新增 `_fetch_result_json_map`，按批 `IN (...)`（批 500）**预取**到
`standard_number → result_json` 字典，循环内全内存查找；语义不变（先网络缓存、后公告缓存、
未命中仍返回「本地数据库未找到」）。

**回归**：`tests/unit/core/test_n_plus_one_batching.py::TestQueryLocalCacheBatched`
（结果等价 + 查询次数为常数 2，而不是 2N）。
