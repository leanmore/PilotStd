# PilotStd 双端架构实测报告

> 任务性质：**只读侦察**（不写方案、不改代码）
> 代码基线：工作区 HEAD `6b6fff68`（`docs(plans): 用户视角通知需求推导 + MoviePilot 聚合复查`）
> 证据纪律：所有结论附 `路径:行号`；行号经脚本回读校验；未确认项显式标注
> 关联材料：[通知架构重设计](../notification-redesign/)（7 份）、[MoviePilot 调查](../moviepilot-investigation/)（3 份，**仅对 Docker 端有效**）

---

## 摘要（给决策者）

**三问的核心答案**

1. **`pilotstd/` 与 `docker/` 是"库 + 宿主"的单向关系**：`pilotstd/` 零处 import `docker`（实测 0 个文件），`docker/` 通过 `from pilotstd...` 复用其 62+ 个模块；`docker/` 零处 import `pilotstd.ui` 或 PyQt。两端跑**同一份 `pilotstd/` 代码**，靠**依赖集**区分（`docker/requirements-docker.txt:2` 明写"无 GUI/桌面组件"，`desktop/requirements-win.txt` 才装 `PyQt6`）。
2. **Windows 端没有"推送"，它的信号呈现是三层**：① 应用内进度条与状态栏（`ui/core/unified_progress.py` + `main_window/__init__.py:42-43` 信号）；② **系统托盘气泡**（`platform/notify.py::NotifyService`，4 个 handler 在用）；③ **任务中心**（`ui/pages/task_page.py`，表格 + 详情，**手动刷新**）。**没有"消息中心/事件列表"这种以事件为单位的聚合呈现**；也没有任何推送渠道配置界面（`pilotstd/ui/` 对 `notification.*` 配置键**零引用**）。
3. **41 个事件的分端归属：Docker 专属 25 / 两端共享 15 / Windows 专属 1**。只有 **`worker_error`** 一个事件产出点在 `pilotstd/ui/`；且它在 Windows 端**发不出去**（见第四节）。

**关键数字**

| 指标 | 值 |
|---|---|
| `pilotstd/` → `docker/` 的 import | **0 个文件** |
| `docker/` → `pilotstd.ui` / PyQt 的 import | **0 个文件** |
| `docker/` 依赖的 `pilotstd` 子包 | `core`(62 文件)、`query`(6)、`manager`(3)、`announcement`(3)、`i18n`(3)、`task`(2)、`constants`(2)、`models`(2)、`services`(1)、`monitor`(1)、`tasks`(1) |
| 定时任务（APScheduler）代码位置 | **只在 `docker/scheduler.py`**（`pilotstd/` 无 `apscheduler` import） |
| 41 事件分端 | Docker 专属 **25**、两端共享 **15**、Windows 专属 **1**（另有 CLI 第三上下文可达） |
| 默认渠道规则条数 | **16**（`defaults.py:62-80`），**不含 `worker_error`** |
| `notification.enabled` 默认 | **False**（`defaults.py:54`），唯一写入点在 Docker Web API |

---

## 一、`pilotstd/` 与 `docker/` 的代码关系

### 1.1 目录职责

| 项 | 结论 | 证据 |
|---|---|---|
| **仓根入口** | `main.py` — 默认启动 GUI，`--cli` 进命令行 | `main.py:94-95`（`--cli` 参数）、`main.py:98-105`（`--cli` → `pilotstd.cli.commands.main`）、`main.py:107`（else → `pilotstd.ui.main_window.run`） |
| **`pilotstd/` 是否独立可运行** | **是**（Windows 端即"独立运行"）：`main.py` → `pilotstd/ui/main_window.run`，不 import `docker` | `main.py:107`；实测 `pilotstd/` + 仓根 **0 个文件** import `docker` |
| **`pilotstd/` 内部有无自己的入口** | 无 `__main__.py`；顶层只有 `__init__.py`(32 行) 与 `models.py`(102 行) | `pilotstd/` 一级列表实测 |
| **`docker/` 入口** | `docker/app.py`（FastAPI `app`），由 uvicorn 拉起 | `docker/entrypoint.sh` 末行：`exec [gosu appuser] uvicorn docker.app:app --host 0.0.0.0 --port 9028` |
| **`docker/` 如何 import `pilotstd/`** | 常规包导入 `from pilotstd.<sub> import ...`；容器内两者同处 `/app` | `docker/app.py:19`（`from pilotstd.services.favorite_chain_processor import process_chain`）、`:176`、`docker/scheduler.py:209`；`docker/Dockerfile:37-38,55`（`COPY pilotstd/`、`COPY main.py`、`COPY docker/`） |
| **`docker/` 有无独立业务实现** | 有：36 个 `docker/api/*.py`（HTTP 薄层）+ `auth.py`/`users.py`/`middleware.py`/`session_store.py`/`health_check_service.py`/`scheduler.py`（调度与进程级能力，`pilotstd/` 中无对应物） | `docker/` 一级 + `docker/api/` 列表实测 |

### 1.2 共享层

**共享层的判定**：被两端同时依赖的目录/模块（依据 = `docker/` 的 import 集合 + `pilotstd/ui/` 的 import 集合）。

| 共享目录 | 说明 | 证据 |
|---|---|---|
| `pilotstd/core/` | 两端都重度依赖（`docker/` 62 个文件引用、`ui/` 18 个文件引用） | 导入统计实测 |
| `pilotstd/manager/` | 业务门面 `StandardManager`（含 `facade/_*.py` 处理器）；`docker/manager.py:7` 直接用它 | `pilotstd/manager/facade/_base.py:227`（`TaskQueue`）、`:256`（`NotificationManager`）、`:269-275`（监控/可信 IP 服务） |
| `pilotstd/task/` | 任务实体与队列（`models.py`/`queue.py`/`scheduler.py`） | `docker/app.py:176-179`（Docker 起任务调度器）；`pilotstd/ui/main_window/parts/_dialog_ops.py:118`（桌面写队列） |
| `pilotstd/i18n/` | 三语（`pilotstd/i18n/*.json`） | `docker/` 3 个文件引用 |
| `pilotstd/models.py`、`pilotstd/constants/` | 数据模型与常量 | `docker/` 各 2 个文件引用 |
| `pilotstd/services/favorite_chain_processor.py` | 收藏下载链（**仅 Docker 调用**，见 1.4） | `docker/app.py:19,161`（唯一调用点） |
| `pilotstd/download/`、`pilotstd/query/`、`pilotstd/announce*/` | 业务引擎 | 通过门面被两端间接使用 |
| `pilotstd/monitor/`（**仅 `docker/` 直接引用**） | 目录监视（watchdog） | `docker/app.py:185`（启动）、`:211`（统计） |

### 1.3 分离层

| 目录 | 归属 | 依据 |
|---|---|---|
| `pilotstd/ui/`（35+17+7+10 个 py） | **Windows 专属** | `docker/` 对它 **0 处** import；PyQt 依赖集中于此 |
| `pilotstd/platform/` | **Windows 专属**（显式声明） | `pilotstd/platform/__init__.py:2`：`# 桌面平台专属模块 — 允许依赖 PyQt6 等桌面框架`；`platform/notify.py:7`（`QSystemTrayIcon`）、`platform/updater.py` |
| `docker/`（含 `docker/api/`） | **Docker 专属** | `pilotstd/` 对它 0 处 import |
| `desktop/` | Windows 打包资产 | `desktop/PilotStd.spec`（122 行）、`desktop/requirements-win.txt`（`PyQt6==6.11.0`） |

**一个边界泄漏（已防护）**：`pilotstd/core/notification_aggregator.py:498` 在**共享层** `core/` 里 import `PyQt6.QtCore`——但它是**惰性 + try/except ImportError**（`:497-505`），且职责实为桌面（文档自述"桌面端通知聚合适配层"）。Docker 未装 PyQt 也不会崩。

**PyQt 依赖分布（实测）**：`pilotstd/ui/**`（13+12+9+5+3+2+2+2 个文件）+ **`pilotstd/core/`(1)** + **`pilotstd/platform/`(1)**。

### 1.4 独立部署时的模块集合

**A. 只装 Windows 端（不装 Docker）**

| 在跑 | 不在跑 |
|---|---|
| `main.py` → `pilotstd.ui.main_window.run`（`main.py:107`） | `docker/**` 全部（0 处被 import） |
| 门面 `StandardManager` 及其处理器（`manager/facade/**`） | **APScheduler 定时任务全部**（`docker/scheduler.py` 是唯一实现；`pilotstd/` 无 `apscheduler` import） |
| 任务队列写入与任务中心展示（`_dialog_ops.py:118`） | **任务调度器**（`pilotstd/task/scheduler.py` 的 `start()` 只被 `docker/app.py:179` 调用） |
| 桌面托盘气泡（`platform/notify.py`） | **文件监控**（`MonitorService.start_scheduler()` 只被 `docker/app.py:185` 调用） |
| 本地通知事件产出（15 个共享事件 + `worker_error`） | **可信 IP 定时检查**（`docker/app.py:196`） |
| — | 收藏下载链（`process_chain` 唯一调用点 `docker/app.py:161`） |

**结论**：Windows 端**没有 cron、没有文件监控、没有任务调度器、没有收藏链**；它的"后台"只存在于用户当次操作的 Worker 线程里。

**B. Docker 端容器里跑什么**

| 在跑 | 证据 |
|---|---|
| FastAPI（36 个 router 挂载） | `docker/app.py:21-57`（import 列表）；`entrypoint.sh` 末行（uvicorn） |
| APScheduler 9 类定时任务 | `docker/scheduler.py:338-389`（`start_scheduler`）、`:344-364`（job × cron × 默认启用表）、`:373-378`（validity） |
| 任务调度器 | `docker/app.py:176-179` |
| **文件监控（watchdog）** | `docker/app.py:185`（`_cron_mgr.monitor_service.start_scheduler()`）、`:209`（stop） |
| 可信 IP 服务 | `docker/app.py:196` |
| 收藏下载链（cron 04:00） | `docker/app.py:161`；`favorite_chain_processor.py:4` |
| **是否 import PyQt** | **否**：`docker/` 对 `pilotstd.ui` 与 PyQt 均 0 处 import；`requirements-docker.txt:2` 声明"无 GUI/桌面组件"；唯一 PyQt 引用在共享层且已 try/except 保护 |

**注意**：容器内 `COPY pilotstd/` + `COPY docker/`（`Dockerfile:37,55`），即**容器里同时存在两端的代码**，但只有 `docker/app.py` 会被执行。

### 1.5 定时任务归属（逐项）

| 任务 | 跑在哪端 | 证据 |
|---|---|---|
| `auto_scan` / `auto_announce` / `auto_backup` / `date_reminder` / `auto_archive_retry` / `auto_health_check` | **Docker** | `docker/app.py:150-165`（注册）；`docker/scheduler.py:344-364`（cron 与默认启用） |
| `validity_check` | **Docker** | `docker/scheduler.py:373` |
| `notification_cleanup` / `release_suppressed` | **Docker** | `docker/scheduler.py:366-369` |
| 文件监控（非 cron，watchdog 常驻） | **Docker**（且桌面端不启动） | `docker/app.py:185`；`pilotstd/manager/monitor_service.py:94-98`（唯一调用方是 app.py） |
| 收藏下载链（cron 04:00） | **Docker** | `docker/app.py:161`；`favorite_chain_processor.py:4` |
| 可信 IP 定时检查 | **Docker** | `docker/app.py:196` |
| 桌面端定时任务 | **无** | `pilotstd/ui/` 对 `start_scheduler`/`monitor_service`/`wechat_ip_service`/`task.scheduler` **零引用**（实测） |

---

## 二、Windows 端的用户信号呈现机制

### 2.1 UI 层结构

```
pilotstd/ui/
├── main_window/    (17 py)  主窗口与 parts/（UI 装配、表/树/菜单/对话框操作）
├── core/
│   ├── handlers/   (21 py)  流程编排：_scan/_query/_download/_archive/_auto/_announce/_cleanup/_settings…
│   ├── unified_progress.py  统一进度管道（缓动 + 信号）
│   └── event_bus.py         应用内事件总线
├── workers/        (10 py)  后台线程：scan/query/download/archive/normalize/announce/auto/update_download
├── pages/          (7 py)   task_page（任务中心）/ rules_page / settings_page(+settings/)
├── widgets/        (1 py)
├── dialogs.py              ConfigPageDialog / ExportFileListDialog
├── pending_query_dialog.py (357) 待确认查询对话框
└── welcome_dialog.py / themes.py / qt_lifecycle.py / drive_enumerator.py
```
证据：`pilotstd/ui/` 目录与文件行数实测；关键类位置 `main_window/__init__.py`、`core/handlers/__init__.py`、`pages/task_page.py:30`。

### 2.2 任务状态呈现（用户看到什么）

| 阶段 | 用户看到 | 证据 |
|---|---|---|
| **执行中（进度）** | 进度条 + 百分比：统一管道 `push(cur,total)`/`push_pct(pct)` 经 50ms 缓动后 `progress_updated` 发出；主窗口转发 `progress_changed` | `ui/core/unified_progress.py:18-54,92-106`（`_step` 指数逼近、值未变不 emit）；`ui/main_window/__init__.py:42`（`progress_changed = pyqtSignal(int)`） |
| **执行中（状态文字）** | 状态栏文本 | `ui/main_window/__init__.py:43`（`status_changed = pyqtSignal(str)`）；各 handler 的 `status_callback`（如 `_auto.py:44` 注入） |
| **执行中（表格流式）** | 结果表格边跑边填 | 各 Worker 的 `batch_ready` 信号：`ui/workers/scan.py:20`、`query.py:32`、`download.py:24`、`archive.py:37`、`normalize.py:17`、`auto.py:20` |
| **一键自动（阶段）** | 阶段切换（扫描→查询→下载→归档） | `ui/workers/auto.py:27`（`stage_changed`）、`ui/core/handlers/_auto.py:118`（连接） |
| **完成时** | ① **托盘气泡**（按成功/失败比例分三种文案）；② 结果表格；③ 任务中心记录；④ 非抑制模式下弹摘要对话框 | `ui/core/handlers/_download.py:279`（写任务中心）、`:284-297`（全成功 `show` / 部分失败 `show_warning` / 全失败 `show_warning`）、`:299-307`（摘要对话框，受 `_suppress_dialogs()` 控制） |
| **失败时** | ① 托盘警告气泡（`show_warning`）；② 对话框；③ 表格内错误列/状态 | `_download.py:290,295`（警告气泡）；`_query_summary.py:332`（完成气泡）；`_announce.py:161`、`_archive.py:109`、`_download.py:328`（异常气泡"工作线程异常"） |
| **查询汇总** | 汇总气泡 | `ui/core/handlers/_query_summary.py:328-332` |

### 2.3 有没有"通知中心"类聚合呈现

**有"任务中心"，但没有"通知中心"**（两者本质不同）：

| 项 | 任务中心（存在） | 通知中心（不存在） |
|---|---|---|
| 位置 | `pilotstd/ui/pages/task_page.py:30`（`TaskPage`）、`:126`（`TaskCenterDialog`） | — |
| 数据源 | `TaskQueue.list_all(limit=100)`（`:94`） | — |
| 展示字段 | 任务ID / **task_type** / **status** / 进度 / 创建时间 / 错误（`:56-66`） | 无"事件名 / 级别 / 文案"维度 |
| 刷新 | **手动**（`btn_refresh`，`:46-47`），无定时刷新 | — |
| 入口 | 主窗口菜单 → `_actions_ops.py:181-183`（`TaskCenterDialog(self._mgr.task_queue, self)`） | 无 |
| 写入方 | 桌面自己在操作完成时写（`_dialog_ops.py:107-121` `_register_task`） | — |

**结论**：Windows 端的"聚合呈现"是**工程视角的任务队列**（task_type/status/progress），**不是**"用户消息/事件流"视角；且**一次性操作完成后只有一个瞬时气泡**（3 秒同标题去重，见 2.4），**没有可回看的事件列表**。

### 2.4 系统托盘与最小化行为

| 项 | 行为 | 证据 |
|---|---|---|
| 有无托盘 | **有**：图标 + 右键菜单（显示主窗口 / 退出）+ 双击恢复 | `ui/main_window/parts/_ui_setup_ops.py:37-51`（`_setup_tray`：`QSystemTrayIcon`、`tray_menu.addAction`、`activated.connect`）；`:57-60`（双击恢复） |
| 最小化行为 | **最小化 → 隐藏到托盘**，并弹一条 2 秒气泡提示 | `ui/main_window/_window_lifecycle.py:59-75`（`changeEvent`：`self.hide()` + `self._tray.showMessage("PilotStd", _("tray_minimized_msg"), …, 2000)`） |
| 关闭行为 | **关闭 = 退出应用**（不是最小化到托盘）：备份 DB → `mgr.shutdown()` → 隐藏托盘 → `app.quit()` | `_window_lifecycle.py:77-85`（`closeEvent`）、`:38-53`（`_quit_app`） |
| 托盘气泡来源 | 两道：① `NotifyService`（业务完成/异常，4 个 handler 用）；② 主窗口自身（最小化提示） | `platform/notify.py`；`_window_lifecycle.py:67` |
| 气泡去重/聚合 | **两条互斥路径**：`auto_pause_enabled=False` → 3 秒同标题防抖直发；`True` → 走 `NotificationAggregator.should_show()`（主题分组 + 熔断暂停） | `platform/notify.py:48-65`（`show`）、`:93-111`（`_check_dedup`，`_DEDUP_WINDOW = 3.0`）、`:96-104`（职责边界注释） |

### 2.5 桌面端触发的事件去了哪里

**桌面端只触发 1 个专属事件 + 15 个共享事件。** 分两种情况：

**A. 共享事件（15 个）**：产出点在 `pilotstd/manager/facade/**` 或 `pilotstd/core/**`，**产出即调用 `notification_mgr.send_event(...)`**，因此在桌面端也会走完整的通知链路（聚合 → 策略 → 渠道）。**但链路首行是门控**：

```
NotificationManager.__init__ → self._enabled = config.get("notification.enabled", False)   # manager.py:144
send_event() → if not self._enabled: return                                                # manager.py:294
```
`notification.enabled` 默认 **False**（`core/config/defaults.py:54`），且**唯一写入点在 Docker Web API**（`docker/api/notification.py:272,275`）→ **Windows 端默认状态下，共享事件在桌面端触发后不会投递到任何渠道**，仅落通知日志/WS（若有）。

**B. `worker_error`（Windows 专属）**：`pilotstd/ui/pending_query_dialog.py:289-290` → `self._mgr.notification_mgr.send_event("worker_error", {...})`。它同样受 `notification.enabled` 门控；**即使门控打开，也没有收件渠道**——`policy` 查 `notification.rules.worker_error` 为空即返回 `[]`（`_policy.py:57-59`），而 16 条默认规则里**没有 `worker_error`**（`core/config/defaults.py:62-80` 实测）。

**结论（用户视角）**：桌面端用户在任务完成/失败时看到的**只是应用内气泡与对话框**；`send_event` 在桌面端的实际效果**约等于"写一条通知日志"**，不产生对外推送。

### 2.6 是否有推送渠道配置

**没有。** 已搜索范围与结果：

| 搜索范围 | 关键词 | 结果 |
|---|---|---|
| `pilotstd/ui/**`（全部 .py） | `notification.channel` / `notification_channel` / `wechat_url` / `dingtalk` / `feishu` / `telegram` / `webhook` | **0 命中** |
| `pilotstd/ui/**` | `notification.enabled` / `channel` / `aggregate` / `rules` / `silent` / `quiet` | **0 命中** |
| `pilotstd/core/config/settings_schema.py` | `notification.` | **0 命中**（该 schema 是给 Web 设置页用的） |
| `web/src/**`（Docker 端 Web UI） | `notification/config` / `NotificationConfig` | **有**：`web/src/api/notification.ts:34,86`（类型与 `GET /notification/config`）、`web/src/components/NotificationConfig.vue` |

**结论**：推送渠道的配置界面**只存在于 Docker 端的 Web UI**（`web/src/components/NotificationConfig.vue`，含渠道实例、事件订阅、开关），后端写入点 `docker/api/notification.py:205,272,275`。Windows 端**没有任何入口**——但它的 `platform/notify.py:52-58` 会去读同一套聚合器配置（`NotificationAggregator`），即**存在"读了 Docker 侧配置但无本端口径"的可能**（未确认部署时是否共用同一 `data/` 配置）。

---

## 三、41 事件分端归属

### 3.1 判定方法说明

判定分三步，**不按"看起来像后台任务"归类**：

1. **产出点定位**：脚本扫描全部 `send_event(` 调用点，取其后首个事件名字面量（兼容 `EVENT_*` 常量）；动态事件名（3 个安全事件）人工补录。
2. **直接归属**：产出点在 `docker/**` → Docker 专属；在 `pilotstd/ui/**` → Windows 专属。
3. **共享层归属 → 反向调用链 BFS 到入口**：从产出点所属函数向上追溯调用者，直到触达入口文件，按入口分类：
   - `docker/**` → Docker 触发；
   - `pilotstd/ui/**` → Windows 触发；
   - `pilotstd/cli/**` → **CLI 第三上下文**（见下）；
   - `pilotstd/monitor/**`、`pilotstd/tasks/**`、`pilotstd/services/favorite_chain_processor.py` → 其唯一启动方在 Docker（1.5 节），归 Docker。

**去噪**：BFS 对泛用函数名（`run`/`start`/`on_finished`）会过连通，故对 6 处存疑项做了**定向人工核验**（`_resolve_replaces`、`download_to_inbox` 链、`_notify`(可信IP)、`capture_task_error`、`archive_failed` 产出点、`notification_delivery_failed` 产出点）。**人工核验结论优先于 BFS**，凡与自动首轮不一致的在下表"判断依据"里注明。

**第三上下文（新发现）**：`main.py --cli` → `pilotstd/cli/commands/**`。实测多个事件可经 CLI 触发（如 `cli/commands/scan.py:16` → `scan_complete`）。本表按任务口径只分"Windows / Docker / 两端"，CLI 在"判断依据"里标注；**CLI 是否算 Windows 端的一部分需决策者定义**（未确认项）。

### 3.2 完整表格（41 行）

| # | 事件 | 产出点（`路径:行号`） | 触发端 | 判断依据 |
|---|---|---|---|---|
| 1 | `archive_complete` | `pilotstd/manager/facade/_organize.py:219` | **两端** | 共享门面 `archive_standards`；调用者含 Windows `pilotstd/ui/workers/archive.py:107` 与 Docker `docker/api/archive.py:58`（另 CLI 可达） |
| 2 | `standard_status_changed` | `pilotstd/core/validity_checker.py:99` | **Docker** | `update_status` 的调用者只有 `core/_validity_pipeline.py:87`（← `docker/scheduler.py:411`、`docker/api/validity.py:195`）与 `services/favorite_chain_processor.py:307,336`（← `docker/app.py:161`）；**Windows 端不在链上** |
| 3 | `standard_first_registered` | `pilotstd/core/validity_checker.py:61` | **两端** | ← `manager/facade/_organize.py:197`；再上溯达 Windows 归档 Worker 与 `docker/api/archive.py:58` |
| 4 | `announcement_fetch_complete` | `pilotstd/announce/notifier.py:109`、`docker/api/announce.py:80` | **Docker** | 其中一处产出点直接在 `docker/api/`；另一处的唯一调用者 `announce/notifier.py:27` 属 announce 服务，入口 `docker/api/announce.py:107,159` 与 `docker/app.py:153` |
| 5 | `auto_backup` | `docker/scheduler.py:163,176`（成功/失败两分支） | **Docker** | 产出点即在 `docker/` |
| 6 | `announcement_check_complete` | `pilotstd/announce/notifier.py:63`、`docker/api/announce.py:68` | **Docker** | 同 #4 |
| 7 | `batch_download_complete` | `manager/facade/_download.py:164`、`download/engine.py:225`、`services/favorite_chain_processor.py:239` | **两端** | `_download.py:164` 的调用者含 Windows `ui/workers/download.py:67` 与门面自动流程；另两处在 Docker 链 |
| 8 | `auto_scan_failed` | `manager/facade/_scan.py:210` | **Docker** | `scan_and_index` 的调用者只有 `docker/app.py:150`（cron）与 `docker/api/scan.py:123`；**无 UI 调用者** |
| 9 | `validity_batch_report` | `core/_validity_pipeline.py:100`、`:222` | **Docker** | 管线入口 `run_validity_check` 的调用者只有 `docker/scheduler.py:411` 与 `docker/api/validity.py:195` |
| 10 | `validity_round_summary` | `core/_validity_pipeline.py:167` | **Docker** | 同上（`_finalize_validity_round` ← `run_validity_check`） |
| 11 | `validity_standard_failed` | `core/_validity_pipeline.py:116` | **Docker** | 同上（`_process_validity_batch` ← `run_validity_check`） |
| 12 | `validity_system_failed` | `core/_validity_pipeline.py:248` | **Docker** | 产出点即在 `run_validity_check` 的异常分支 |
| 13 | `image_update_available` | `docker/api/system.py:144`、`:185` | **Docker** | 产出点即在 `docker/api/` |
| 14 | `batch_query_summary` | `manager/facade/_query_subsystem.py:250` | **两端** | 调用者含 Windows `ui/workers/query.py`、`ui/workers/auto.py` 与 Docker `docker/api/auto.py:15`、`docker/api/query.py` |
| 15 | `trust_ip_update` | `manager/wechat_ip_service.py:28` | **Docker** | `_notify` 的调用者：`wechat_ip_service.py:105`（`update_config`）、`:122`（`run_check`）、`:164`（`start_scheduler`）；其入口全在 Docker（`docker/api/wechat_ip.py:29,36`、`docker/app.py:196`）。**注**：自动首轮 BFS 曾判"两端"，实测为**假阳性** |
| 16 | `worker_error` | `pilotstd/ui/pending_query_dialog.py:290` | **Windows** | 产出点在 `pilotstd/ui/`；全库仅此一处触发 |
| 17 | `date_reminder` | `pilotstd/tasks/date_reminder.py:111` | **Docker** | `_process_record` ← `:154` ← `docker/scheduler.py:223` |
| 18 | `download_failed` | `pilotstd/tasks/favorite_download.py:145` | **Docker** | `_notify_download_failed` ← `favorite_download.py:391,405`（均在 `download_to_inbox` 内）← `services/favorite_chain_processor.py:271` ← `docker/app.py:161`；`pilotstd/ui/` 对整条链 **0 引用**。**且在唯一路径上被 `notify=False` 抑制**（详见 4.3） |
| 19 | `archive_abandoned` | `services/favorite_chain_processor.py:382` | **Docker** | `_notify_abandoned` ← `:324,:359` ← `process_chain` ← `docker/app.py:161` |
| 20 | `normalize_complete` | `manager/facade/_organize.py:393` | **两端** | 调用者含 Windows `ui/workers/normalize.py:51` 与 Docker `docker/api/normalize.py:86` |
| 21 | `scan_complete` | `manager/facade/_scan.py:75,159,192` | **两端** | `scan_directory`/`_stream`/`scan_and_index` 的调用者含 Windows scan/auto Worker 与 `docker/api/scan.py:50,123`；另 `monitor/scheduler.py:156`（Docker 常驻）与 CLI |
| 22 | `task_execution_failed` | `core/task_status.py:78`、`docker/scheduler.py:325` | **Docker** | 装饰器 `capture_task_error` 的**唯一挂载点**是 `docker/scheduler.py:54`；另一产出点直接在 `docker/` |
| 23 | `scan_empty` | `manager/facade/_scan.py:85,169,202` | **两端** | 同 #21 |
| 24 | `query_failed` | `manager/facade/_query_subsystem.py:229` | **两端** | 同 #14 |
| 25 | `query_empty` | `manager/facade/_query_subsystem.py:245` | **两端** | 同 #14 |
| 26 | `archive_failed` | `manager/organize/organizer.py:254` | **两端** | 产出在共享 organizer（`archive_standards` 内），调用者含 Windows 归档 Worker 与 `docker/api/archive.py:58`；另 CLI。**注**：自动首轮未检出（调用里夹了 `# type: ignore` 注释），已人工补录 |
| 27 | `announcement_fetch_failed` | `pilotstd/announce/notifier.py:83` | **Docker** | 同 #4 的入口分析 |
| 28 | `normalize_failed` | `manager/facade/_organize.py:381` | **两端** | 同 #20 |
| 29 | `expire_standard_moved` | `manager/facade/_organize.py:203` | **两端** | 调用者含 Windows 归档 Worker 与 `docker/api/archive.py:58`；另 CLI |
| 30 | `replacement_not_found` | `manager/classifier.py:181` | **两端** | `resolve_replaces` ← `classifier.py:114`(`_resolve_cross_site_replaces`) ← `:87`；上溯达 `docker/api/auto.py:15`、Windows `ui/core/handlers/_query.py:347`、`ui/workers/query.py:95`、CLI。**注**：自动首轮漏了 `docker/api/auto.py` 边，已人工补 |
| 31 | `quota_exhausted` | `pilotstd/query/daily_quota.py:91` | **两端** | 调用者含 Windows `ui/core/handlers/_query.py:138,141,286` 与 Docker `docker/api/query.py:43`、`docker/api/download.py:32,112` |
| 32 | `announce_fetch_summary` | `pilotstd/announce/notifier.py:101` | **Docker** | 同 #4 |
| 33 | `favorite_created` | `docker/api/favorites.py:175` | **Docker** | 产出点即在 `docker/api/` |
| 34 | `download_started` | `pilotstd/tasks/favorite_download.py:173` | **Docker** | 同 #18 的链条；**且在唯一路径被抑制** |
| 35 | `download_complete` | `pilotstd/tasks/favorite_download.py:202` | **Docker** | 同 #18；**注**：自动首轮判"两端"（假阳性），人工核验：`pilotstd/ui/` 对整条链 0 引用 |
| 36 | `favorite_abandoned_summary` | `services/favorite_chain_processor.py:207` | **Docker** | `_notify_run_summary`/`_notify_abandoned_summary` ← `process_chain` ← `docker/app.py:161` |
| 37 | `notification_delivery_failed` | `core/notification/manager.py:415` | **两端**（有保留） | 产出点是**通知管理器自身的投递失败告警**（`manager.py:412-420`，`target_channels` 旁路 + `bypass_aggregation=True`）；触发条件是"某渠道投递失败"，两端都会投递。**但** Windows 端默认不投递 ⇒ 默认不可能触发此告警（见 4.4） |
| 38 | `notification_credential_changed` | `docker/api/notification.py:216` | **Docker** | 动态事件名产出（`security_notifier.py:174` 传变量），人工核验调用点全在 `docker/api/` |
| 39 | `security_password_changed` | `docker/api/users.py:195` | **Docker** | 同上（事件名以字面量传 `notify_security_event`） |
| 40 | `security_token_refreshed` | `docker/api/settings.py:404` | **Docker** | 同上 |
| 41 | `security_login_failed` | `docker/auth.py:286` | **Docker** | 产出点即在 `docker/auth.py` |

### 3.3 汇总统计

| 归属 | 数量 | 事件 |
|---|---|---|
| **Docker 专属** | **25** | `standard_status_changed`、`announcement_fetch_complete`、`auto_backup`、`announcement_check_complete`、`auto_scan_failed`、`validity_batch_report`、`validity_round_summary`、`validity_standard_failed`、`validity_system_failed`、`image_update_available`、`trust_ip_update`、`date_reminder`、`download_failed`、`archive_abandoned`、`task_execution_failed`、`announcement_fetch_failed`、`announce_fetch_summary`、`favorite_created`、`download_started`、`download_complete`、`favorite_abandoned_summary`、`notification_credential_changed`、`security_password_changed`、`security_token_refreshed`、`security_login_failed` |
| **两端共享** | **15** | `archive_complete`、`standard_first_registered`、`batch_download_complete`、`batch_query_summary`、`normalize_complete`、`scan_complete`、`scan_empty`、`query_failed`、`query_empty`、`archive_failed`、`normalize_failed`、`expire_standard_moved`、`replacement_not_found`、`quota_exhausted`、`notification_delivery_failed` |
| **Windows 专属** | **1** | `worker_error` |
| **未确认** | **0** | （自动首轮有 7 个未确认，均已人工定案；CLI 是否计入 Windows 端待决策者定义） |
| 合计 | **41** | — |

**Docker 专属中，有 3 个在唯一产出链上被 `notify=False` 抑制**（`download_started`/`download_failed`/`download_complete`，见 4.3）。

---

## 四、暴露的问题

> 以下均为**代码层可证的矛盾/风险**，不含处置建议。

### 4.1 Windows 端唯一的专属事件，在 Windows 端发不出去

`worker_error` 是全库**唯一**产出点在 `pilotstd/ui/` 的事件（`ui/pending_query_dialog.py:290`）。但它：
- 受 `notification.enabled` 门控，默认 **False**（`core/config/defaults.py:54` + `core/notification/manager.py:144,294`）；
- **即使打开门控也没有收件渠道**：`notification.rules.worker_error` 不在 16 条默认规则中（`defaults.py:62-80` 实测），`_policy.py:57-59` 查不到即返回 `[]`；
- Windows 端**没有配置入口**（2.6 节：`pilotstd/ui/` 对 `notification.*` 零引用）。

⇒ 该事件在桌面端的实际效果 ≈ 一次函数调用 + 日志。

### 4.2 "事件在 A 端产生，投递配置只在 B 端"

15 个共享事件在 Windows 端**也会产出**（UI Worker → 门面 → `send_event`），但**启用开关与渠道配置只在 Docker 端**（唯一写入点 `docker/api/notification.py:272,275`；配置界面 `web/src/components/NotificationConfig.vue`）。⇒ 桌面端用户无法决定"我在桌面端做的事要不要推送到 IM"，也无法看到本端通知是否可用。

### 4.3 3 个 Docker 事件在唯一产出链上被"批量抑制"，且该抑制是默认值

`download_started` / `download_failed` / `download_complete` 的完整链条：
```
docker/app.py:161  lambda: process_chain(_cron_mgr.download_engine)
  → favorite_chain_processor.py:395  process_chain(..., notify_per_record=False)   ← 默认 False
  → :413  process_pending_downloads(download_engine, notify_per_record)
  → :271  download_to_inbox(favorite_id, user_id, record_id, notify=notify)        ← notify=False
  → tasks/favorite_download.py:167/196/139  if not notify: return
```
`process_chain` 的**唯一调用点**就是那一处 cron（另有 `docker/app.py:263` 的关闭路径）；`process_pending_downloads` 也**只**被 `process_chain:413` 调用。⇒ 这三个事件在生产路径上**恒被抑制**，只有"手工以 `notify_per_record=True` 调 `process_pending_downloads`"才会发出——而这样的调用点在代码里不存在。它们仍保留在 G-045 覆盖度基线里（i18n 三语 + e2e `trigger_file`）。

### 4.4 `notification_delivery_failed` 在 Windows 端不可能触发

该事件是"通知投递失败"的告警（`manager.py:412-420`）。Windows 端默认不投递（4.1/4.2），因此**不投递就没有投递失败**，该告警在桌面端是自我消解的。⇒ 桌面端若真出现"通知不工作"，没有任何反馈回路。

### 4.5 Docker 端也启动文件监控，与桌面端语义重叠

`docker/app.py:185` 启动 `MonitorService`（watchdog）——而桌面端**不**启动（1.5 节）。若同一 `inbox` 目录同时被桌面端与容器监视（取决于部署），`pilotstd/monitor/scheduler.py:132` 的 `_on_file` 会被两边各触发一次；代码里未见跨进程互斥（`pilotstd/monitor/scheduler.py` 无锁/锁表；对比：调度器有 `scheduler_lock` 表互斥，`docker/scheduler.py:249-285`）。**该冲突是否真实存在取决于部署方式，未确认。**

### 4.6 第三执行上下文（CLI）未被两端模型覆盖

`main.py --cli` → `pilotstd/cli/commands/**`，实测多个事件可经 CLI 触发（`cli/commands/scan.py:16`、`cli/commands/organize.py:15,17,19`、`cli/commands/query.py:58`、`cli/commands/auto.py:14` 等）。当前"双端"模型（Windows / Docker）**没有为 CLI 定义归属**——例如 CLI 触发 `archive_complete` 时，它算 Windows 端还是独立第三端？

### 4.7 共享层中的桌面专属文件

`pilotstd/core/notification_aggregator.py`（文档自述"桌面端通知聚合适配层"）位于**共享层 `core/`**，且内含 PyQt 惰性导入（`:498`）。而"桌面专属"的声明位置是 `pilotstd/platform/__init__.py:2`。⇒ 目录边界与职责声明不一致（该 PyQt 导入已用 `try/except ImportError` 防护，Docker 不装 PyQt 也不会崩）。

### 4.8 MoviePilot 调查的适用面

`docs/plans/moviepilot-investigation/` 的 3 份报告结论（渠道能力矩阵、消息编辑、i18n 接线、聚合器缺口等）**只对 Docker 端有效**：MoviePilot 没有桌面端，其"用户离场"前提与 Windows 端"用户在桌前"前提相反。本轮已按决策者要求**不重复调查 MoviePilot**，仅在此标注适用边界。

---

## 附：可复算命令

```powershell
# ── 一、代码关系（导入图）──
python C:\Temp\mp_probe\dualend_imports.py      # A: pilotstd→docker 0 例；B: docker→ui/PyQt 0 例；C/D/E: 依赖与 PyQt 分布
Get-Content main.py | Select-Object -Skip 93 -First 15                 # GUI/CLI 分发
Get-Content docker\entrypoint.sh | Select-Object -Last 6               # 容器真正启动 uvicorn docker.app:app
Get-Content docker\requirements-docker.txt -TotalCount 4               # 明写"无 GUI/桌面组件"
Get-Content desktop\requirements-win.txt                               # PyQt6 只在此
Get-Content docker\app.py | Select-Object -Skip 147 -First 54          # 定时任务注册 + 文件监控 + 任务调度器
Get-Content pilotstd\manager\monitor_service.py | Select-Object -Skip 93 -First 6
Get-ChildItem pilotstd -Recurse -Filter *.py | Select-String 'apscheduler'   # 仅注释，无实现
# ── 二、Windows 端信号呈现 ──
Get-Content pilotstd\ui\core\unified_progress.py -TotalCount 55        # 进度管道 API
Get-Content pilotstd\ui\main_window\parts\_ui_setup_ops.py | Select-Object -Skip 36 -First 16   # 托盘
Get-Content pilotstd\ui\main_window\_window_lifecycle.py | Select-Object -Skip 58 -First 28     # 最小化→托盘 / 关闭→退出
Get-Content pilotstd\ui\pages\task_page.py | Select-Object -Skip 29 -First 40                    # 任务中心
Get-Content pilotstd\ui\core\handlers\_download.py | Select-Object -Skip 278 -First 20          # 完成/失败的气泡分支
Get-ChildItem pilotstd\ui -Recurse -Filter *.py | Select-String 'notification\.(enabled|channel|aggregate|rules)'  # 空
# ── 三、41 事件归属 ──
python C:\Temp\mp_probe\dualend_bfs.py        # 反向 BFS 到入口（首轮，含假阳性）
python C:\Temp\mp_probe\dualend_callers.py    # 严格调用者目录分布（逐事件）
# 关键人工核验（本报告 3.2 的依据）
Get-ChildItem pilotstd,docker -Recurse -Filter *.py | Select-String 'process_chain\(|process_pending_downloads\('
Get-ChildItem pilotstd,docker -Recurse -Filter *.py | Select-String '_resolve_replaces\('
Get-ChildItem pilotstd,docker -Recurse -Filter *.py | Select-String 'capture_task_error'
Get-ChildItem pilotstd,docker -Recurse -Filter *.py | Select-String 'notify_credential_change\(|notify_security_event\('
Get-Content pilotstd\core\notification\manager.py | Select-Object -Skip 140 -First 8   # _enabled 读取
Get-Content pilotstd\core\notification\manager.py | Select-Object -Skip 290 -First 8   # enabled 门控
python -c "import sys;sys.path.insert(0,'.');from pilotstd.core.config.defaults import FACTORY_DEFAULTS as D;print(D['notification.enabled']);print(len([k for k in D if k.startswith('notification.rules.')]))"
```

### 自检结果

| 检查项 | 结果 |
|---|---|
| 引用回读校验（文件存在 + 行号在范围内） | 见提交前脚本输出（本报告全部 `路径:行号` 均由脚本产出或人工核验后录入） |
| 与自动化首轮结论不一致处 | **4 处**，均已在 3.2 表内注明（`trust_ip_update`、`download_complete`、`archive_failed`、`replacement_not_found`） |
| 未确认项 | **2 处**：① 同一 `inbox` 是否被两端同时监视（4.5，部署相关）；② CLI 是否计入 Windows 端（4.6，需决策者定义） |
