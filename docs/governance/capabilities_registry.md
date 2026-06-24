# 能力登记簿 v2.1

> PilotStd 项目非功能性能力清单。任何重构、归档、模块重写前必须查阅本簿。
> 最后更新：2026-06-23
> 行号由 `scripts/update_capabilities.py` 自动维护，每次 pre-commit 时刷新。

## 能力登记表

| 功能模块 | 文件路径 | 标识符/关键点 | 行号范围 | 状态 | 描述 |
|---------|---------|-------------|---------|------|------|
| 调度器实例 | `docker/scheduler.py` | L16 | L16 | active | APScheduler 后台调度器实例，管理所有 cron 定时任务 |
| 调度器公告包装 | `docker/scheduler.py` | L41 | L41 | active | 将 announce 任务放入独立 daemon 线程执行，避免阻塞调度器线程池 |
| 调度器心跳循环 | `docker/scheduler.py` | `_heartbeat_loop()` | L129-140 | active | 心跳线程，每 30s 更新 `scheduler_lock.heartbeat_at`，标记 worker 存活 |
| 调度器互斥锁 | `docker/scheduler.py` | `_acquire_scheduler_lock()` | L85-126 | active | DB 级互斥锁，防止多 worker 重复执行定时任务；超时 90s 可接管 |
| 调度器优雅关闭 | `docker/scheduler.py` | `stop_scheduler()` | L166-174 | active | 停止心跳 → 等待任务完成 → 释放 DB 锁 |
| FastAPI 生命周期 | `docker/app.py` | `lifespan()` | L44-63 | active | 启动时注册定时任务 + 启动调度器；关闭时停止调度器 + shutdown mgr |
| 引擎进度心跳 | `pilotstd/query/engine.py` | `_progress_heartbeat()` | L425-442 | active | 独立 daemon 线程，每 60s 输出 `[PROGRESS]` 进度日志（CLI/WinUI 共用） |
| 引擎线程池 | `pilotstd/query/engine.py` | L845 | L846 | active | 8 worker 并发执行各查询桶，桶内串行 + 桶间并行 |
| 引擎 PROGRESS 日志 | `pilotstd/query/engine.py` | L434, 1126 | L461, 1115 | active | 输出已完成/总数/成功/速率/预计剩余；完成时 eta=0s |
| 引擎 BUCKET 日志 | `pilotstd/query/engine.py` | L452, 1009 | L479, 1002 | active | 分桶分配时输出总数；完成后输出 total/done/overflow/elapsed |
| 引擎 FUNNEL 日志 | `pilotstd/query/engine.py` | L1099 | L1088 | active | 汇总输出 total/ok/overflow/pending 四维漏斗 |
| 引擎 TIMELINE 日志 | `pilotstd/query/engine.py` | L1017, 1106 | L1010, 1095 | active | 桶并发耗时 + 逐桶查询完成总耗时 |
| 引擎 BASELINE 日志 | `pilotstd/query/engine.py` | L1111 | L1100 | active | FUNNEL 同款字段 + 总耗时，供压测驱动对比基线 |
| 引擎 CACHE 日志 | `pilotstd/query/engine.py` | L1090 | L809, 1079 | active | 批量查询结束后输出 hit/miss/rate% |
| 引擎 QUOTA/WATER 日志 | `pilotstd/query/engine.py` | L926, 936, 1024, 1061, 1067 | L922, 931, 1017, 1050, 1056 | active | 站点溢出不可用/配额耗尽/各站已用量/水位剩余/冷却跳过 |
| 引擎 SCORE 日志 | `pilotstd/query/engine.py` | L1046 | L1035 | active | 各站点 exact/fuzzy/older/mismatch 评分分布 |
| 引擎 OVERFLOW 日志 | `pilotstd/query/engine.py` | L1032 | L1024 | active | 溢出事件计数 + 链分布 |
| 引擎 CHAIN/PENDING 日志 | `pilotstd/query/engine.py` | L1051, 1055 | L1040, 1044 | active | 每条标准的查询站点链 + 待确认归因 |
| 引擎缓存优先查询 | `pilotstd/query/engine.py` | `query_parsed()` → `self.cache.get()` | — | active | 先查 `standard_info_cache` 再发起网络请求；实际缓存逻辑在 `cache.py` |
| 缓存仓库 | `pilotstd/query/cache.py` | L19 | L19 | active | 双层缓存：`standard_info_cache` → `announcement_cache` 回退，事件驱动失效 |
| 轮转器里程碑日志 | `pilotstd/query/rotator.py` | L170, 215 | L170, 215 | active | 请求量达 50%/75%/90%/100% 阈值时输出（中文标签，非 `[ROTATOR]`） |
| 轮转器冷却日志 | `pilotstd/query/rotator.py` | 冷却倒计时日志 | L103-113 | active | 冷却进入时输出剩余秒数（中文"冷却剩余"，无固定标签） |
| 日配额追踪 | `pilotstd/query/daily_quota.py` | L22 | L22 | active | 站点日配额管理，`threading.RLock` 线程安全，跨天自动重置 |
| 任务队列执行 | `pilotstd/task/queue.py` | L103, 107, 113 | L95, 99, 105 | active | daemon 线程异步执行任务，含超时控制 `join(timeout)` |
| 下载线程池 | `pilotstd/download/engine.py` | L172 | L156 | active | 并行下载标准文件，含重试 + 采标跳过 |
| 公告引擎调度 | `pilotstd/announcement/engine.py` | L13 | L13 | active | 公告适配器注册/调度 + OCR 集成，公告同步核心 |
| 公告基础并行 | `pilotstd/announcement/base.py` | L163 | L325, 427 | active | 附件下载 1-worker；详情抓取 `_MAX_DETAIL_WORKERS=3` 并行 |
| 公告阶段耗时 | `pilotstd/announcement/monitor.py` | L38, 42, 56 | L38, 42, 56 | active | 分阶段追踪抓取耗时：fetch_list / fetch_detail / parse / write_db |
| OCR 取消事件 | `pilotstd/announcement/ocr.py` | L753 | L731 | active | threading.Event 跨线程取消信号，传递给所有 OCR Slot |
| 文件索引清理线程 | `pilotstd/core/file_index.py` | L61 | L59 | active | 启动后延迟 5-30s，daemon 线程逐条校验索引路径并清理失效记录 |
| 文件索引缓存恢复 | `pilotstd/core/file_index.py` | 双层缓存回填 | L228-358 | active | 从 network/announcement 双层缓存回填文件索引的元数据字段 |
| 文件监控 | `pilotstd/scan/watcher.py` | L92 | L90 | active | watchdog Observer 后台监控文件系统变更，事件驱动增量索引 |
| 软件自更新 | `pilotstd/core/updater.py` | 下载+校验+提权替换 | — | active | 下载 ZIP → SHA256 校验 → PowerShell 提权替换 exe；压测期间应禁用 |
| 定时任务编排 | `pilotstd/manager/scheduled_service.py` | `ScheduledService` | — | active | scan_and_index / recheck_updates / query_by_numbers 供 Docker cron 调用 |
| LoggerManager | `pilotstd/core/logger.py` | `LoggerManager` | — | active | 全局日志入口 + `RotatingFileHandler`（256KB/1备份）；压测 I/O 关键 |
| JWT + API Key | `docker/auth.py` | JWT 生成/验证 + Key 写库 | — | active | JWT 令牌 + 静态 API Key 自动写入 `api_keys` 表；压测认证依赖 |
| Web 公告缓存回退 | `pilotstd/manager/facade.py` | `lookup_or_query()` | L342-371 | active | 先查 Web 端 `announcement_cache`，未命中降级到标准查询引擎 |
| 离线双表回退 | `pilotstd/manager/pending_service.py` | 离线查询 | L168-212 | active | 无网络时优先 `standard_info_cache` → `announcement_cache` |
| API 公告缓存 | `docker/api/announce.py` | `_cache` 字典 | L15, L40-43 | active | 内存缓存公告结果（last_check/results/summary/failures），供 `/api/announce/results` |
| 主窗口 atexit | `pilotstd/ui/main_window.py` | L634 | L606 | active | 退出时触发自动保存 |
| 主窗口 SIGTERM | `pilotstd/ui/main_window.py` | L636 | L608 | active | 捕获终止信号触发自动保存 |
| 主窗口自动保存 | `pilotstd/ui/main_window.py` | `_on_auto_save()` | L640 | active | 退出时保存窗口状态和配置 |
| 主窗口暂停信号 | `pilotstd/ui/main_window.py` | L362 | L350 | active | `threading.Event` 跨线程暂停/继续控制 |
| 主窗口下载线程 | `pilotstd/ui/main_window.py` | L834 | L804 | active | daemon 线程后台下载更新包并校验 SHA256，主线程 `join(timeout=300)` |
| 主窗口公告按钮 | `pilotstd/ui/main_window.py` | `_on_check_announcements()` | L356-358 | active | 工具栏"公告检查"按钮，点击触发公告抓取 + OCR + 匹配 |
| 工作者 QTimer | `pilotstd/ui/workers.py` | L81 | L75 | active | 200ms 单次触发，将缓冲日志批量写入 QTextEdit，防信号洪峰 |
| 待确认冷却刷新 | `pilotstd/ui/pending_query_dialog.py` | L113 | L113 | active | 1000ms 持续触发，每秒更新冷却倒计时状态 |
| 节流进度发射器 | `pilotstd/ui/controllers/auto_run_mixin.py` | L26 | L26 | active | 500ms 节流，防止 Qt 事件循环合并高频信号导致进度条跳变 |
| 压力测试看门狗 | `tests/stress_driver.py` | `_progress_watchdog()` | L313-319 | active | 每 30s 检查子进程 `[PROGRESS]`，超时 180s 则告警 |
| 压力测试双流读取 | `tests/stress_driver.py` | L322-323 | L569-570 | active | 两个 daemon 线程并行读取子进程输出，防管道缓冲区死锁 |
| 压力测试 Web 心跳 | `tests/stress_web.py` | L112, 784 | L111, 821 | active | 与 engine 层格式统一的 60s 进度日志；完成消息在 L784 |
| 已废弃-旧管道 ProgressReporter | `tests/stress_01_pipeline_archived.py` | （文件已删除） | — | deprecated | 已迁移至 `query/engine.py` + `stress_web.py` + `stress_driver.py` |
| 已废弃-旧管道 heartbeat() | `tests/stress_01_pipeline_archived.py` | （文件已删除） | — | deprecated | 已迁移至 `query/engine.py` + `stress_web.py` |
| 已废弃-API Key 退出清理 | `tests/stress_driver.py` | `_cleanup_api_key()` （已删除） | — | deprecated | API 令牌方案已简化为静态令牌，不再需要动态创建/吊销 |

## 状态说明

| 状态 | 含义 |
|------|------|
| `active` | 当前活跃使用中 |
| `deprecated` | 已废弃，不再维护，保留记录供追溯 |

## 迁移完成记录

| 原模块 | 能力名称 | 迁移前 | 迁移后 | 完成日期 |
|--------|---------|--------|--------|---------|
| `stress_01_pipeline_archived.py` | `ProgressReporter` | 旧文件（commit `3d966a1` 已删除） | `query/engine.py:425-442` + `stress_web.py:103-122` + `stress_driver.py:313-319` | 2026-06-22 |
| `stress_01_pipeline_archived.py` | `heartbeat()` | 旧文件（commit `3d966a1` 已删除） | `query/engine.py:425-442` + `stress_web.py:103-122` | 2026-06-22 |
| `stress_driver.py` | API Key 清理 | `stress_driver.py:1972`（已删除） | 静态令牌方案（`fbce972`） | 2026-06-22 |

## 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-06-23 | v2.1 | 重构为平表格式；修正全部行号为当前代码实际值；新增 `update_capabilities.py` 自动维护脚本 |
| 2026-06-23 | v2.0 | 新增 9 条遗漏能力；2 条归档记录改为 deprecated；覆盖率 86%→~100% |
| 2026-06-22 | v1.0 | 初始版本 |
