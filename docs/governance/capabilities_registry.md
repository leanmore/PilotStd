# 能力登记簿

> PilotStd 项目非功能性能力清单。任何重构、归档、模块重写前必须查阅本簿。
> 最后更新：2026-06-22

---

## 后台线程与定时器

| 模块路径 | 能力名称 | 描述 | 实现位置 | 类型 | 必需性 | 登记日期 | 状态 |
|----------|---------|------|---------|------|--------|---------|------|
| `docker/scheduler.py` | APScheduler 定时调度器 | cron 式定时任务（auto_scan/auto_query/auto_announce/auto_backup），含 DB 互斥锁防止多 worker 重复执行 | `scheduler.py:16 BackgroundScheduler()` | 后台线程（调度器） | required | 2026-06-22 | active |
| `docker/scheduler.py` | 心跳线程（scheduler-heartbeat） | 每 30s 更新 `scheduler_lock.heartbeat_at`，标记 worker 存活；超时 90s 则其他 worker 可接管 | `scheduler.py:129-162 _heartbeat_loop()` | 后台线程（心跳） | required | 2026-06-22 | active |
| `docker/scheduler.py` | 公告任务独立线程包装 | 公告类 cron 任务触发时包装为独立 daemon 线程（`sched-{job_id}`），不占用调度器线程池 | `scheduler.py:44` | 后台线程 | recommended | 2026-06-22 | active |
| `pilotstd/query/engine.py` | 60s 进度心跳 | 批量查询时每 60s 输出 `[PROGRESS]` 日志（完成数/总数/成功率/速率/ETA），CLI/WinUI 共用 | `engine.py:390-410 _progress_heartbeat()` | 后台线程（心跳） | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | 8-worker 桶间并行线程池 | `ThreadPoolExecutor(max_workers=8)` 并行执行各查询桶，桶内串行+桶间并行 | `engine.py:787 executor.submit(_bucket_worker)` | 线程池 | required | 2026-06-22 | active |
| `pilotstd/task/queue.py` | 任务队列异步执行 | 后台 daemon 线程执行异步任务（含超时控制 `join(timeout)`） | `queue.py:57-113` | 后台线程 | required | 2026-06-22 | active |
| `pilotstd/core/file_index.py` | 文件索引延迟校验 | 启动后延迟 5-30s（自适应），daemon 线程逐条校验索引路径是否存在，清理失效记录 | `file_index.py:61-62` | 后台线程 | recommended | 2026-06-22 | active |
| `pilotstd/ui/main_window.py` | 软件更新下载线程 | daemon 线程后台下载更新包并校验 SHA256，主线程 `join(timeout=300)` | `main_window.py:829-831` | 后台线程 | recommended | 2026-06-22 | active |
| `pilotstd/ui/main_window.py` | 跨线程暂停信号 | `threading.Event` 跨线程暂停/继续控制，Worker 循环中检查 | `main_window.py:356` | Event（同步） | required | 2026-06-22 | active |
| `pilotstd/download/engine.py` | 下载线程池 | `ThreadPoolExecutor(max_workers=N)` 并行下载标准文件，含重试 | `engine.py:172-174` | 线程池 | required | 2026-06-22 | active |
| `pilotstd/announcement/base.py` | 公告附件下载线程池 | 1-worker 线程池异步下载公告附件，不阻塞主流程 | `base.py:161-162` | 线程池 | recommended | 2026-06-22 | active |
| `pilotstd/announcement/base.py` | 公告详情并行处理 | `_MAX_DETAIL_WORKERS` 线程池并行抓取/解析公告详情页 | `base.py:259-262` | 线程池 | required | 2026-06-22 | active |
| `pilotstd/ui/workers.py` | 日志缓冲 QTimer | 200ms 单次触发，将缓冲日志批量写入 QTextEdit，防信号洪峰 | `workers.py:78-81` | QTimer | required | 2026-06-22 | active |
| `pilotstd/ui/pending_query_dialog.py` | 冷却倒计时刷新 | 1000ms 持续触发 QTimer，每秒更新"等待冷却"按钮状态 | `pending_query_dialog.py:113-115` | QTimer | recommended | 2026-06-22 | active |
| `tests/stress_driver.py` | 进度看门狗线程 | 每 30s 检查子进程是否输出 `[PROGRESS]`，超时 180s 则告警"可能卡死" | `stress_driver.py:335-344 _progress_watchdog()` | 后台线程（心跳） | required | 2026-06-22 | active |
| `tests/stress_driver.py` | stdout/stderr 双流读取 | 两个 daemon 线程并行读取子进程输出，防管道缓冲区死锁 | `stress_driver.py:346-353` | 后台线程 | required | 2026-06-22 | active |
| `tests/stress_web.py` | 60s 进度心跳（Web 端） | Web API 压测时每 60s 输出 `[PROGRESS]` 日志，与 engine 层格式统一 | `stress_web.py:103-122 _progress_heartbeat()` | 后台线程（心跳） | required | 2026-06-22 | active |
| `tests/stress_01_pipeline_archived.py` | `ProgressReporter` 定时进度报告 | 每 30s 或每 50 条输出查询进度（速率/ETA/内存/冷却），含 `heartbeat()` 函数用于下载/归档长耗时阶段的卡死防护 | → `query/engine.py:390-410` (60s 心跳) + `tests/stress_web.py:103-122` (Web 端心跳) + `tests/stress_driver.py:335-344` (看门狗) | 后台线程（心跳） | recommended | 2026-05-31 | active |
| `tests/stress_01_pipeline_archived.py` | `heartbeat()` 通用心跳函数 | 返回 `(start, stop)` 闭包，在后台线程定时输出 `[心跳]` 日志，供下载/归档等阻塞阶段使用 | → `query/engine.py:388-410` (`_prog_stop` + `_progress_heartbeat`) + `tests/stress_web.py:92-122` (同模式) | 后台线程（心跳） | recommended | 2026-05-31 | active |

---

## 观测日志

| 模块路径 | 能力名称 | 描述 | 实现位置 | 类型 | 必需性 | 登记日期 | 状态 |
|----------|---------|------|---------|------|--------|---------|------|
| `pilotstd/query/engine.py` | `[PROGRESS]` 进度心跳日志 | 每 60s 输出：completed/total/ok/rate/eta，查询结束输出 `(done)` 最终行 | `engine.py:390-410, 1054-1066` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[BUCKET]` 分桶统计日志 | 分组分配 + 完成后统计：total/done/overflow/elapsed | `engine.py:417, 943` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[FUNNEL]` 漏斗汇总日志 | total/ok/overflow/pending 四维漏斗 | `engine.py:1033` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[TIMELINE]` 时序日志 | 桶间并行总耗时 + 单次查询完成标记 | `engine.py:951, 1040` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[BASELINE]` 基线汇总日志 | 同 FUNNEL + 总耗时，供压测驱动对比 | `engine.py:1045` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[CACHE]` 缓存命中率日志 | hit/miss/rate%，批量查询结束后统计 | `engine.py:1024` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[QUOTA]` 配额日志 | 各站点实际用量 + 溢出配额水位 + 冷却跳过计数 | `engine.py:862, 872, 958, 1001` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[SCORE]` 站点评分卡 | 各适配器查询策略得分分布（exact/fuzzy/older/mismatch） | `engine.py:980` | 观测日志 | recommended | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[OVERFLOW]` / `[WATER]` 溢出/水位 | 溢出事件计数 + 链分布 + ahbz/njbz365 溢出资额剩余 | `engine.py:966, 995` | 观测日志 | recommended | 2026-06-22 | active |
| `pilotstd/query/engine.py` | `[CHAIN]` / `[PENDING]` 链路追踪 | 每条标准的查询站点链 + 待确认归因 | `engine.py:985, 989` | 观测日志 | recommended | 2026-06-22 | active |
| `pilotstd/query/rotator.py` | `[ROTATOR]` 站点里程碑日志 | 请求量达 50%/75%/90%/100% 阈值时输出 | `rotator.py:172` | 观测日志 | required | 2026-06-22 | active |
| `pilotstd/query/rotator.py` | `[COOLDOWN]` 冷却状态日志 | 冷却进入/退出/状态变更/重置 | `rotator.py:108-235` | 观测日志 | required | 2026-06-22 | active |
| `tests/stress_web.py` | `[PROGRESS]` 进度心跳（Web） | 与 engine 层格式统一的 60s 进度日志 | `stress_web.py:103-122, 798-812` | 观测日志 | required | 2026-06-22 | active |

---

## 缓存

| 模块路径 | 能力名称 | 描述 | 实现位置 | 类型 | 必需性 | 登记日期 | 状态 |
|----------|---------|------|---------|------|--------|---------|------|
| `pilotstd/query/cache.py` | CacheRepository 双层缓存 | `standard_info_cache`（网络结果）→ `announcement_cache`（公告比对）双表回退，事件驱动失效 | `cache.py:19 class CacheRepository` | 缓存（SQLite） | required | 2026-06-22 | active |
| `pilotstd/query/engine.py` | 缓存优先查询 | `query_parsed()` 先查缓存再发起网络请求，`query_batch_parsed()` 结束后验证命中率 | `engine.py:120-125, 1011-1027` | 缓存 | required | 2026-06-22 | active |
| `pilotstd/manager/facade.py` | Web 公告缓存回退 | `lookup_or_query()` 先查 Web 端公告缓存，未命中降级到标准查询引擎 | `facade.py:342-371` | 缓存 | recommended | 2026-06-22 | active |
| `pilotstd/core/file_index.py` | 文件索引缓存字段恢复 | 从 network/announcement 双层缓存回填文件索引的元数据字段 | `file_index.py:228-358` | 缓存 | recommended | 2026-06-22 | active |
| `pilotstd/manager/pending_service.py` | 离线双表回退查询 | 无网络时优先查 `standard_info_cache` → `announcement_cache` | `pending_service.py:168-212` | 缓存 | recommended | 2026-06-22 | active |
| `docker/api/announce.py` | 公告结果内存缓存 | `_cache: dict` 暂存上次公告检查结果，供 `/api/announce/results` 查询 | `announce.py:15` | 缓存（内存） | optional | 2026-06-22 | active |

---

## 生命周期管理

| 模块路径 | 能力名称 | 描述 | 实现位置 | 类型 | 必需性 | 登记日期 | 状态 |
|----------|---------|------|---------|------|--------|---------|------|
| `pilotstd/ui/main_window.py` | SIGTERM 自动保存 | `signal.signal(SIGTERM, ...)` 捕获终止信号触发自动保存 | `main_window.py:629` | 信号处理 | required | 2026-06-22 | active |
| `pilotstd/ui/main_window.py` | atexit 退出清理 | `atexit.register()` 注册退出回调保存状态 | `main_window.py:627` | 退出清理 | required | 2026-06-22 | active |
| `tests/stress_driver.py` | API Key 退出清理 | atexit 注册 `_cleanup_api_key()` 吊销临时 Key | `stress_driver.py:1972` (已删除) | 退出清理 | recommended | 2026-06-22 | **deprecated** |
| `docker/scheduler.py` | 调度器优雅关闭 | `stop_scheduler()`：停止心跳→等待任务→释放 DB 锁 | `scheduler.py:166-174` | 退出清理 | required | 2026-06-22 | active |
| `docker/app.py` | FastAPI 生命周期钩子 | `startup` 启动调度器，`shutdown` 停止调度器 | `app.py:54-57` | 生命周期 | required | 2026-06-22 | active |
| `pilotstd/announcement/ocr.py` | OCR 取消信号 | `_threading.Event` 作为 OCR 处理停止信号，传递给所有 OCR Slot | `ocr.py:565-752` | Event（同步） | recommended | 2026-06-22 | active |
| `pilotstd/ui/main_window.py` | 自动保存（编辑器失焦 + 5min 间隔） | 编辑器内容变更后自动保存到备份文件 | `main_window.py` | 其他 | recommended | 2026-06-22 | active |

---

## 迁移完成记录

| 模块路径 | 能力名称 | 迁移前 | 迁移后 | 完成日期 |
|----------|---------|--------|--------|---------|
| `tests/stress_01_pipeline_archived.py` | `ProgressReporter` | `stress_01_pipeline_archived.py:86-133` (已删除) | `query/engine.py:390-410` + `tests/stress_web.py:103-122` + `tests/stress_driver.py:335-344` | 2026-06-22 |
| `tests/stress_01_pipeline_archived.py` | `heartbeat()` | `stress_01_pipeline_archived.py:139-158` (已删除) | `query/engine.py:388-410` (`_prog_stop` + `_progress_heartbeat`) + `tests/stress_web.py:92-122` | 2026-06-22 |

迁移说明：旧实现基于直接调用 Manager API 的 `progress_callback` 回调模式；新架构（子进程驱动）下改为引擎层 daemon 线程输出 `[PROGRESS]` 结构化日志，`stress_driver.py` 的 `_progress_watchdog` 提供卡死检测。功能等价，实现模式适配新架构。

---

## 状态说明

| 状态 | 含义 |
|------|------|
| `active` | 当前活跃使用中 |
| `deprecated` | 计划移除，不再维护 |
