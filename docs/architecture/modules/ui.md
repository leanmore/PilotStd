# 模块文档：UI 主窗口（MainWindow）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/ui/main_window/` |
| G-031 映射 | `pilotstd/ui/main_window/` |
| 核心类 | `MainWindow(QMainWindow)` |
| 子模块数 | 14 个 parts + 14 个 Handler |
| 总行数 | ~1,700（main_window + parts） |
| 状态 | 活跃 |

## 模块职责

PilotStd 桌面端的主窗口界面，提供三段式布局（文件树 / 工作表 / 操作日志），作为所有用户操作的视觉入口和结果展示层。通过 Handler 组合模式（非 Mixin 继承）将业务逻辑委托给 `MainWindowCore` 及 14 个 Handler。

## 架构

```
MainWindow (QMainWindow)
├── 布局
│   ├── 左侧: 文件导航树 (200px)
│   ├── 中间: 工作表格 (stretch)
│   └── 右侧: 操作日志 (240px)
├── MainWindowCore (组合容器)
│   ├── ScanUIHandler        — 扫描触发与进度
│   ├── QueryUIHandler       — 查询结果展示
│   ├── DownloadUIHandler    — 下载队列管理
│   ├── ArchiveUIHandler     — 归档操作
│   ├── AutoHandler          — 自动流水线
│   ├── AnnounceUIHandler    — 公告界面
│   ├── SettingsHandler      — 设置面板
│   ├── ExportHandler        — 导出
│   ├── CleanupHandler       — 清理
│   ├── DialogHandler        — 对话框
│   ├── FileDialogHandler    — 文件选择
│   ├── ThemeHandler         — 主题/语言/图标
│   └── UISetupHandler       — UI 组装
└── parts/ (方法注入)
    ├── _actions_ops.py      — 菜单动作；`_init_manager()` 是门面就绪点（W2 在此接托盘事件出口）
    ├── _delegate_ops.py     — 业务委托
    ├── _table_ops.py        — 表格操作
    ├── _file_tree_ops.py    — 文件树操作
    ├── _query_ops.py        — 查询操作
    ├── _theme_ops.py        — 主题操作
    ├── _ui_setup_ops.py     — UI 组装/托盘；`_TrayEventBridge` + `_wire_tray_event_sink()`（W2 按端分流）
    └── ... (共 14 个)
```

## Windows 端事件分流（W2，2026-10-03）

> 设计见 [notification-system-design/00-framework.md](../../plans/notification-system-design/00-framework.md) §3.5 与
> [02-framework-update.md](../../plans/notification-system-design/02-framework-update.md)（W2 行）。

- **分流点**：`NotificationManager.set_local_sink()`（核心只认一个回调，**不 import** UI/PyQt）；
  `_dispatcher.send_event` 在 `_enabled` 早退**之前**调用它 —— 渠道开关与"本端是否可见"是两件事。
- **接线**：`_init_manager()`（门面就绪）→ `_wire_tray_event_sink()`；开关
  `notification.windows_tray_events`（默认开）关闭即回退；Docker 端不调用 ⇒ 渠道链路不变。
- **线程亲和**：事件可能来自工作线程，托盘是 GUI 对象 ⇒ 经 `_TrayEventBridge.tray_event_occurred`
  信号切回主线程再弹（`warning`/`error` → `show_warning`，其余 → `show`）。
  信号名有两个约束：**不能**叫 `event`（遮蔽 `QObject.event(QEvent)` 虚函数）；后缀须落在
  G-011 认可的 `_changed` / `_ready` / `_occurred` 内。

### 分档节流（W3）

- 节流只加在**已分流到托盘**的事件上（`NotifyService.show_event`）：警告档（`warning`/`error`）
  **立即发射**；其余同一**主题**每 `LONG_STAGE_WINDOW`（60 秒）只弹一条。
- 60 秒这个数字必须 **> 桌面熔断的"30 秒内 3 条"**，否则进度气泡会自己触发熔断暂停（5 分钟）。
- 设计原文的"每 25% 且间隔 ≥60 秒"里，**25% 检查点不适用于托盘路径**：托盘事件只带标题/正文，
  没有进度百分比，故以时间为准（应用内进度条仍承担百分比呈现）。
- 开关 `notification.windows_tray_throttle`（默认开）关闭即回退为不节流的 `show`/`show_warning`；
  **既有 UI 直呼链路（`show`/`show_warning`）不经节流**，行为不变。

## Handler 组合模式

> 旧版 28 个 Mixin 已在 2026-07-11 全部重构为 Handler 组合模式。参见 [STATUS.md](../../../STATUS.md)。

- `MainWindow.__init__()` 中构造 `MainWindowCore` 容器
- 每个 Handler 通过 callback 回调 MainWindow 的 UI 方法
- Handler 之间不直接通信，通过 `MainWindowCore` 共享状态
- `parts/` 目录下的方法片段通过 `from .parts._xxx import method` 注入为 MainWindow 实例方法

## 状态值引用（R14-4b / #32-B，2026-10-01）

UI 层的状态判定与展示不再硬编码中文：`main_window/parts/_query_ops.py`（结果状态着色）、
`core/handlers/archive_flow_engine.py`、`core/handlers/query_flow_engine.py`（不可覆盖状态集合）、
`core/handlers/_query.py`、`core/handlers/_scan.py`、`workers/archive.py`（归档目录判定）
共 39 处已统一引用权威字典 `pilotstd/core/status.py` 的 `Status.*.value`。
**取值与判定顺序不变**，API/DB 侧字符串不变；前端（`web/src/`）本批未触碰。

## Qt 对象生命周期约定

> 来源：CI 事故 `test_buttons_enabled_after_cancel` —— 点击取消后控件已被 Qt 析构，后台 worker 的排队信号仍被投递，槽函数抛 `RuntimeError: wrapped C/C++ object of type QTableWidget/QTimer has been deleted`。

- 跨线程信号是**队列投递**：`disconnect()` 只能拦住之后的发射，已经排进主线程事件队列的调用照样会执行。因此取消 / 关闭窗口时必须**先断开 worker 信号，再停线程**。
- 统一入口 [`pilotstd/ui/qt_lifecycle.py`](../../../pilotstd/ui/qt_lifecycle.py)：
  - `is_qt_alive(obj)` —— 封装 `sip.isdeleted`（PyQt6 的 `sip` 是子模块，顶层 `import sip` 在本仓库不可用）；
  - `stop_worker_gracefully(worker, signals, timeout_ms)` —— 先断信号 → 置停止标志 → `requestInterruption()` → `wait()`；**禁用 `QThread.terminate()`**，超时改为脱离父对象并保活，等线程自然结束；
  - `orphan_timeout_total()` / `orphaned_worker_count()` —— 超时未退出的累计次数与当前滞留数；累计达阈值（3）时告警从 `warning` 升级为 `error` 并列出滞留线程。保活不是无限容忍："永不退出"的线程必须能被发现。
- 取消/关闭路径**全部 7 处**已统一走该原语：`core/handlers/` 的 scan / download / archive（normalize + archive 两个 worker）/ announce / auto / query、`main_window/_window_lifecycle.py`（drive 线程）、`pending_query_dialog.py`。
- 唯一没有 `stop()` 的 worker 是 `DriveEnumerator`（仅枚举盘符、任务极短）：helper 通过 `getattr(worker, "stop", None)` 跳过停止标志，只走 `requestInterruption()` + `wait()`，通常自然退出；若真超时则进保活列表并计入 `orphan_timeout_total()`。
- 现有落点：`parts/_table_ops.py::_find_row_by_seq`（表格已析构返回 `-1`）、`core/handlers/_query.py` 的查询槽函数（进度 / 结果 / 完成）、`core/unified_progress.py` 的进度管道。
- **覆盖 worker 引用之前必须先停旧线程**（2026-09-26 CI 事故：`test-gui-coverage` 连续 3 个 run `exit 134`/SIGABRT、无 pytest 汇总）。`core/handlers/_query.py::on_query()` 直接 `self._query_worker = create(...)`，而 `_archive.on_normalize()` 的补名分支会经 `_run_query_cb()` 再次发起查询 → 上一个 QueryWorker 失去引用且从未被 stop/wait → GC 析构运行中的 QThread → Qt `qFatal` → `abort()`。现在覆盖前先 `self.stop_workers()`。
- **"是否已结束"的判据必须是 `isFinished()`，不能用 `isRunning()`**：`QThread.start()` 之后存在"已启动但尚未进入 `run()`"的窗口（实测数十毫秒），此时 `isRunning()` 仍为 `False`；旧实现据它提前返回、并让保活对象当场出列，等于**没保活**。`qt_lifecycle._thread_finished()` 封装该判据（无 `isFinished` 的鸭子类型替身才退回 `isRunning()`）。
- 排查入口：CI 报 `exit code 134`（Linux SIGABRT）/ `0xC0000409`（Windows fail-fast，WER 定位到 `Qt6Core.dll`）且**无汇总**时，faulthandler 会打印**全部**线程——先看 `Current thread`（abort 发起方）与仍在运行的 worker 栈。完整教训链见 [`docs/ci-lessons.md`](../../ci-lessons.md) 第八节。

## 日志与诊断

> 来源：2026-09-26 清理调试输出（`chore: 清调试输出 + ci-lessons 补 Qt qFatal 教训链`）——生产路径上前一版残留 4 处 `print(f"[TRACE] …")`。

- UI 层统一使用模块级 `logger`（`logger.debug/info/warning/exception`），**生产路径不 `print`**；已清理：`core/handlers/_archive.py::on_normalize`、`main_window/parts/_query_ops.py::_do_pending_query`（改前/改后各一条）、`main_window/parts/_ui_setup_ops.py::_setup_scanner`。
- **有意保留的 stderr 输出**（非调试残留，改动会破坏其契约）：
  - `main_window/parts/_run_main.py` 的 `_qt_message_handler` —— 把 Qt C++ 层 WARNING/CRITICAL/FATAL 写 stderr（`flush=True`），是 Qt 消息的唯一出口，改成 `logging` 有重入风险；
  - `core/_self_check.py` —— 可选架构自检工具（`PILOTSTD_SELF_CHECK=1` 才启用），按设计输出到 stderr；
  - `pilotstd/cli/commands/*.py` —— CLI 的用户输出通道（`tests/cli/test_execution.py` 用 `capsys` 断言其 stdout）；
  - `pilotstd/templates/adapter/**` —— cookiecutter 生成钩子与探针脚本（生成期/开发者工具）。

## 工作流

```
扫描 → 查询 → 下载 → 规范化 → 归档
  │       │       │        │        │
  v       v       v        v        v
ScanUI  QueryUI DownloadUI NormalizeUI ArchiveUI
Handler Handler  Handler    (worker)   Handler
```

## 依赖关系

- `pilotstd/manager/` — `StandardManager` 门面（`self._mgr`），所有业务操作的入口
- `pilotstd/ui/core/_core.py` — `MainWindowCore` 依赖容器
- `pilotstd/ui/core/_core_adapters.py` — 协议适配器（`ITableOps` 等），懒加载 `pilotstd.ui.workers` 的类型（如 `RowUpdate`）
- `pilotstd/core/config/` — 配置管理
- `pilotstd/core/project.py` — 项目管理

## 相关文档

- [管理模块](manager.md) — `StandardManager` 门面架构
- [ADR-001](../../adr/ADR-001-modal-dialog-auto-clicker.md) — 模态对话框自动处理
