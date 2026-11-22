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

- **文件树失败可见性（2026-10-17，体检 D-8 第 5 批）**：`_file_tree_ops` 的驱动器就绪回调在 sip 不可用/树已析构时直接 return（原实现无任何痕迹）、图标设置失败与单条目 `OSError` 被 `pass`；现统一补 debug 日志。契约由 `tests/gui/test_file_tree_ops_logging.py` 锁定。

- **UI 关闭/主题/事件总线的失败可见性（2026-10-17，体检 D-8 第 8 批）**：`_ui_setup_ops` 的 SIGTERM 注册失败、聚合器关闭失败，`event_bus` 的 reset 期 `processEvents` 与重复取消订阅，`_cleanup` 的目录扫描/清只读，`themes` 的 DWM 深色标题栏，均由 `pass` 改 debug/warning；契约由 `tests/gui/test_event_bus_logging.py` 锁定。

- **UI 处理器失败可见性（2026-10-17，体检 D-8 第 11 批）**：`_settings` 读取 `auto_pause_enabled` 失败、`scan_flow_engine` 的结构化解析失败、`_export_ops` 导出文件列表的单条失败，均由 `pass` 改 debug。

- **D-16（同日）**：`qt_lifecycle.is_qt_alive` 的 `isdeleted is None` 防御分支去掉 `# pragma: no cover`，由 `tests/gui/test_qt_lifecycle_logging.py` 增例覆盖（无 PyQt6/sip 时视为存活）。

- **D-17 完全收口（2026-10-18）**：删除 `pilotstd.ui.main_window` 的 mypy 豁免。`_WindowLifecycleMixin` 在 `TYPE_CHECKING` 期以 `QMainWindow` 为基类（运行时仍 `object`，MRO 不变），并显式声明 `_mgr/_tray/_project` 等属性与 `_save_*` 方法类型；`QMenu.addAction` 统一经 `_add_action()` 收窄 Optional；事件签名改为 `QEvent | None` / `QCloseEvent | None`。`mypy --platform=linux pilotstd docker` 0 errors。**补（同日）**：CI 使用 Python 3.12 typeshed，`_pick_folder` 与 `_confirm_update_available` 各有一处 `no-any-return`（本地 3.14 不可见），分别用 `isinstance(path, str)` 与 `bool(...)` 收窄。**D-16 收口（同日）**：`_run_main.run()` 与 `_query_ops._do_pending_query` 的 `# pragma: no cover` 已移除，分别由 `tests/gui/test_run_main.py`（替身验证启动顺序）与 `tests/gui/test_pending_query_flow.py`（就绪/取消/无标准号三分支）覆盖；生产代码 pragma 归零（仅保留 5 处 `TYPE_CHECKING` 类型专用豁免）。**D-16 收尾**：`_actions_ops` 的 watchdog 分支与更新检查异常分支、`qt_lifecycle._sip_isdeleted` 的 ImportError 分支去 pragma；更新失败路径由 `tests/gui/test_actions_ops_update.py` 覆盖。**D-3（2026-10-18）**：`_TrayEventBridge._show` 把 `event_type` 传给 `NotifyService.show_event`，托盘分档节流与聚合分组改用事件键优先的主题（`topic_of(..., event_type)`），不再丢弃事件名。

## Windows 端事件分流（W2，2026-10-03）

> 设计见 [notification-system-design/00-framework.md](../../.local/archive/2026-11-08/docs/plans/notification-system-design/00-framework.md) §3.5 与
> [02-framework-update.md](../../.local/archive/2026-11-08/docs/plans/notification-system-design/02-framework-update.md)（W2 行）。

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

> 旧版 28 个 Mixin 已在 2026-07-11 全部重构为 Handler 组合模式。参见 [通知系统索引](../notification-system.md)。

- `MainWindow.__init__()` 中构造 `MainWindowCore` 容器
- 每个 Handler 通过 callback 回调 MainWindow 的 UI 方法
- Handler 之间不直接通信，通过 `MainWindowCore` 共享状态
- `parts/` 目录下的方法片段通过 `from .parts._xxx import method` 注入为 MainWindow 实例方法

## 信号与错误通道（W1-U1，2026-11-08）

- `MainWindow.query_result_ready` 已删除：查询结果由 `QueryUIHandler.on_result_ready` 直接回调表格更新（`core/handlers/_query.py`）；旧 `_query_ops._on_query_result_ready` 仅保留给测试直接调用，生产链路不再经过 MainWindow 信号。
- `FileMoveWorker.error_occurred` 已接到 `CleanupHandler._status`（构造注入的 `status_callback` → 主窗口 `status_changed` → 状态栏），搬迁失败不再只发进空处；回归测试 `tests/gui/test_cleanup_error_channel.py` 钉住该链路。

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

> **2026-11-14（P2-10 批 4）**：UI 层静默错治理口径落地——只有"**用户主动操作 + 失败后界面看起来正常**"的路径才升 `warning`，Qt 生命周期竞态（对象已销毁/信号已断开）与逐条热路径保持原级别。本批升 warning 两处：`core/handlers/_cleanup.py::CleanupHandler.scan_empty_dirs`（点"清理空目录"时扫描失败，界面只显示"没有可清理目录"）、`pages/rules_page.py::RulesPage._get_rules`（`sites.rules` JSON 损坏时静默按空表展示，用户再保存一次就把坏串覆盖成空表）。其余 26 处 allowlist 理由见 `docs/debt/p2-10-silent-errors-triage.md` §九；G-050 基线同步收紧为 162。

- UI 层统一使用模块级 `logger`（`logger.debug/info/warning/exception`），**生产路径不 `print`**；已清理：`core/handlers/_archive.py::on_normalize`、`main_window/parts/_query_ops.py::_do_pending_query`（改前/改后各一条）、`main_window/parts/_ui_setup_ops.py::_setup_scanner`。
- **有意保留的 stderr 输出**（非调试残留，改动会破坏其契约）：
  - `main_window/parts/_run_main.py` 的 `_qt_message_handler` —— 把 Qt C++ 层 WARNING/CRITICAL/FATAL 写 stderr（`flush=True`），是 Qt 消息的唯一出口，改成 `logging` 有重入风险；
  - `core/_self_check.py` —— 可选架构自检工具（`PILOTSTD_SELF_CHECK=1` 才启用），按设计输出到 stderr；
  - `pilotstd/cli/commands/*.py` —— CLI 的用户输出通道（`tests/cli/test_execution.py` 用 `capsys` 断言其 stdout）；
  - `pilotstd/templates/adapter/**` —— cookiecutter 生成钩子与探针脚本（生成期/开发者工具）。
- **G-005 与本节的关系（2026-10-16 对齐）**：G-005（`scripts/check_g_005_log_tags.py`）的规则是"禁止 `_log()` / 裸 `print` / `print(stderr)`"，与本节前两条**本就冲突**——该门禁此前**从未被任何入口调用**（`check_all.sh` / CI / husky 三处零命中），所以冲突一直没暴露。本次处置：**保留本节的既有决定**（不改那两处代码），把例外**编码进门禁**——`EXCLUDED_ALLOWED_STDERR` 具名登记上述两文件（**不是**按目录放行；同目录同名的其它文件出现 `print(stderr)` 仍判违规），并把该门禁接进 `check_all.sh` 的 `run_fast()`。⚠️ 增删这两个例外**必须同步改本节**，受控测试 `tests/test_check_g_005_log_tags.py` 会锁死清单（改动清单即红）。

## i18n 约定

- UI 运行期文案一律走 `_()`（`pilotstd/i18n/{zh_CN,en,zh_TW}.json`），**不再接受"行内中文拼接 + `i18n-allow` 豁免"**；新增文案必须在三语文件同时加键，`check_i18n_key_count` 会比对键数一致。
- 2026-11-14（C-6 遗留）：pending 弹窗里"另有 N 条因发布日期格式异常，未加入等待队列"从行内拼接迁到 `download_skipped_bad_date`（`{count}` 占位），`pilotstd/ui/core/handlers/_download.py` 里对应的豁免注释已删除。这是该约定的第一个样板：**数字用占位符，不用 f-string 拼中文**。

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

> **2026-11-05 线程生命周期（B1）**：设置对话框在 OCR 模型下载线程运行期间拒绝关闭；
> 关闭时统一 `requestInterruption()` + `wait()`（禁止 terminate）。未识别文件搬移改用 `QEventLoop`
> 等待 `FileMoveWorker`，不再 `processEvents()` 空转。更新下载线程由主窗口持有并在 `_stop_workers()`
> 中优雅停止。桌面端后台任务通知统一改为 `NotificationContext(scope="system")`（不再硬编码 user_id=1）。

> **2026-11-05 文件占用与错误提示**：`safe_move` 在源文件被占用且重试耗尽时回滚目标副本、保留源文件并返回 False；
> `pilotstd/ui/errors.py::format_ui_error()` 把 `WinError 32/5`、`ENOSPC` 映射为中文提示（含文件名），
> 全部 7 个 worker 与归档/清理 handler 统一走该出口，不再向用户展示英文堆栈。

> **2026-11-09 导出截断可见化（U-3/U-4 批 3）**：`main_window/parts/_export_ops._collect_folder_tree`
> 对 `os.scandir` 的 `PermissionError/OSError` 由「静默 return」改为 `warning`（文案带目录路径）——
> 导出内容会缺整棵子树，用户却以为导出完整；返回值/递归结构不变。
> 同批 `ui/core/handlers/download_flow_engine.parse_download_csv` 的 CSV 解析失败也由无日志升 `warning`
> （该路径未进 DOC_SYNC_MAP，记录于此便于追溯）。

## 注释语言规范化（2026-11-19）

- G-012 [LANG] 改为按词判定后，本模块注释里的英文普通词改为中文、裸标识符加反引号；
  仅注释与 docstring 变更，AST 比对无代码变化（全仓 504 行，见 27 日志 #81）。

## 跨端设计系统（DS）阶段一（2026-11-22）

- 规范：docs/reference/ui-system.md（按钮四层级 / 三档尺寸 / 圆角与图标 / 跨端令牌）。
- 令牌：pilotstd/ui/tokens_generated.py 由 scripts/gen_win_tokens.py 从 Web 源生成（勿手改）；
  --check 已接入 check_all.sh --fast，产物与源不一致即失败。
- 骨架：pilotstd/ui/widgets/base_button.py 的 BaseButton（kind=primary/secondary/danger/ghost，size=l/m/s），
  样式全部取自生成令牌，缺令牌抛错而非静默降级。
- 阶段一不替换既有 QPushButton 调用点；替换在阶段二分批进行。

## 按钮统一：BaseButton 全量替换（2026-11-22，DS 阶段二）

- `pilotstd/ui/**` 内 **46 处** `QPushButton(...)` 构造已全部替换为 `BaseButton(..., kind=...)`：
  `primary` 20 / `secondary` 15 / `ghost` 9 / `danger` 2（按语义判定）。
- 受影响模块（13 个）：`dialogs`、`pages/rules_page`、`pages/task_page`、`pages/settings/_dialog`、
  `pending_query_dialog`、`welcome_dialog`、`main_window/parts/_ui_setup_ops`、`main_window/parts/_dialog_ops`、
  `core/handlers/{_announce,_auto,_cleanup,_query_summary,_settings}`。
- 样式来源统一为 `pilotstd/ui/tokens_generated.py`（由 `scripts/gen_win_tokens.py` 从 Web 源生成），
  **不再使用** `themes.py` 的 `COLOR_SCHEMES` 作为按钮色值来源。
- 13 个模块在 `QT_QPA_PLATFORM=offscreen` 下全部导入通过；`ruff --fix` 清理 24 个未用导入。
- 后续新增 Win 按钮：直接用 `BaseButton`，不要再用 `QPushButton`。

## 输入控件统一：BaseInput / BaseSelect（2026-11-22，DS 阶段三 · 模块一）

- 令牌：pilotstd/ui/tokens_generated.py 新增 input_height_lg/md/sm（40/34/28）与
  input_textarea_min_height，由 scripts/gen_win_tokens.py 从 web/src/styles/design-tokens.css
  解析生成；仍禁止手改产物，--check 不一致即失败。
- A-53 收口：disabledBg / disabledText 此前只声明未消费（死键），现由 BaseButton /
  BaseInput / BaseSelect 的禁用态统一消费，不再用 borderLight + textDim 顶替。
- 新增 pilotstd/ui/widgets/base_input.py：BaseInput(QLineEdit) 与 BaseSelect(QComboBox)，
  size l/m/s 映射输入控件高度令牌，圆角取 ds_radius_md，四态（default/hover/focus/disabled）
  全部取自生成令牌，缺令牌抛 KeyError 而非静默降级（与 BaseButton 同风格）。
- 调用点替换：pilotstd/ui 内 **25 处** 裸 `QLineEdit(...)` / `QComboBox(...)` 全部替换为
  `BaseInput` / `BaseSelect`（`_settings.py` 19 处、`rules_page.py` 6 处），
  size 按语义取 m（表单）；7 处密码框改 `BaseInput(password=True)`，不再手工 `setEchoMode`；
  `setPlaceholderText` / 信号连接 / 下拉选项与 `setCurrentText` 逻辑原样保留。
  类型标注仍写 Qt 基类（二者是 QLineEdit/QComboBox 子类），调用侧零改动。
- 聚焦态的等高换算：Qt 的 `min-height` 是内容盒高度，聚焦把描边 1px→2px 会让总高多 2px；
  故 focus 态按 `高度-4` / `内边距-1` 换算，四态外框总高恒等于高度令牌（避免表单控件聚焦时跳高）。
- placeholder 走 QPalette.PlaceholderText（Qt QSS 无 `::placeholder` 伪元素），色值取 textDim。
  **顺序有讲究**：必须排在 `ensurePolished()` 之后 —— polish 会用 QSS 的 `color` 重建调色板，
  先设会被覆盖回正文色（实测 placeholder 变成 text 色）。
- **替换过程中修掉的真实缺陷（有回归用例）**：应用级 QSS 生效时，QComboBox 在首次 polish 前
  `sizeHint()` 返回**未套控件 QSS** 的高度（实测 22px，令牌要求 34px），要等事件循环 polish
  才恢复。首次布局会按 22px 排，表单下拉"矮一截"。修法：`_apply_style()` 末尾立即
  `ensurePolished()` + `updateGeometry()`。回归用例 `TestRenderedHeight::test_rendered_height_under_app_stylesheet`
  （先 `app.setStyleSheet(...)` 再构造控件，断言 sizeHint == 令牌高度）。
- 守护用例：tests/gui/test_base_input.py（27 项）—— 尺寸令牌取值、四态取色、A-53 禁用态四主题、
  非法 size 抛 ValueError、缺令牌抛 KeyError、password echoMode、渲染高度（含应用级 QSS 场景）、
  BaseButton 的 A-53 收口、源码无字面色值、以及「pilotstd/ui 内不得再构造裸 QLineEdit/QComboBox」。
- 后续新增 Win 输入控件：直接用 BaseInput / BaseSelect，不要再用裸 QLineEdit / QComboBox。

## 表格与弹窗统一：BaseTable / BaseDialog（2026-11-22，DS 阶段三 · 模块二）

- 新增 `pilotstd/ui/widgets/base_table.py`：`BaseTable(QTableWidget)`，表头底色 `surfaceRaised` /
  表头文字 `text`（**不是 `textSecondary`**，与 Web 端同一取舍：`textDim` 浅色主题仅 2.4-2.6:1 不达标）、
  斑马纹 `surfaceRaised`、行 hover `selected`、边框 `border` / `borderLight`、圆角 `ds_radius_md`。
- 新增 `pilotstd/ui/widgets/base_dialog.py`：`BaseDialog(QDialog)`，圆角 `ds_radius_lg`、
  内边距 `space_18` / `space_20`、右上关闭按钮（只收敛图标字号到 `size_20`，**不设按钮本体宽高**——
  硬设 20×20 会把点击热区压到 20px，低于 WCAG 2.5.8 的 24px 最小目标；实现只保证 `size_24` 最小边长）。
- 未新增遮罩层颜色令牌：与 Web 端 `AppDialog` 同口径（迁移前从未覆盖遮罩，观感即 Qt/Aura 默认；
  加颜色键会连带触发 `design-tokens.test.ts` 映射断言与令牌同步链，成本高且无视觉需求）。
- 调用点替换（数字均以 `git grep QDialog HEAD -- pilotstd/ui` 为准，共 35 行文本）：
  - `QTableWidget(...)` 构造 **2 处 → 0**（`_ui_setup_ops._setup_work_table`、`task_page.TaskPage`）；
  - `QDialog` **7 处基类继承 → 0**：`ConfigPageDialog` / `ExportFileListDialog` / `RuleEditDialog` /
    `SettingsDialog` / `TaskCenterDialog` / `PendingQueryDialog` / `WelcomeDialog`；
  - `QDialog(...)` **5 处直接构造 → 0**：`_announce` / `_auto` / `_cleanup` / `_query_summary` / `_dialog_ops`；
  - 其余 14 行 import + 6 行 `DialogCode` 枚举比较 + 2 行类型标注（`parent: QDialog`、
    `-> QDialog`）+ 1 行 `themes.py` 全局 QSS 选择器，随上述替换一并收敛。
  全部改为继承/使用 `BaseDialog`，业务信号槽与 `exec()` 语义原样保留
  （`BaseDialog.DialogCode` 与 `QDialog.DialogCode` 是同一个枚举，`exec()`/`accept()`/
  `reject()`/`closeEvent()`/`setWindowTitle()`/`resize()` 一律不覆写）。
- 保留的 `QDialog` 引用是**语义性**的、不参与替换：`themes.py` 的全局 QSS 选择器
  `QDialog, QWidget {...}`（对子类同样生效）、`_cleanup.move_unrecognized_files(parent: QDialog)`
  的类型标注，以及 `QTableWidget.EditTrigger/SelectionBehavior/SelectionMode` 枚举常量
  （`BaseTable` 是 `QTableWidget` 子类，这些常量照旧可用）。
- 表格窄列的局部代价（实测）：Web 的 `--space-14` 水平内边距套到 Win 端会把 34px「序号」列
  整列挤成空白（表头与单元格都被省略到 0 像素，8px 时已开始被挤扁）。故 `BaseTable` 的
  item/表头**水平**内边距交给 Qt 委托默认值（约 4px），**竖直**方向保留 `--space-9`/`--space-10`；
  行高（38px）与表头高（37px）由 QSS 之外的 `setDefaultSectionSize`/`setFixedHeight` 显式设，
  因为 QSS 的 `::item padding` 只影响 `sizeHintForRow()`、不改 `rowHeight()`。
- `--selected` 是 rgba，Qt 的 item 委托**不会**按行底色合成半透明 `::item` 背景（实测直接写
  rgba 会渲染成明显偏深的主色）。故 `BaseTable` 先用 `_composite()` 把 alpha 令牌按 `surface`
  压成 `#rrggbb` 再交给 QSS；四主题渲染实测与合成值逐位一致。
- `BaseDialog` 的内边距在首次 `showEvent` 里套到 layout：`QWidget.setContentsMargins()` 只内缩
  窗口内容区、不改布局 margin；而 `QLayout.setContentsMargins()` 在 `show()` 前会被 QDialog 的
  默认布局重排覆盖回 11px（两者叠加还会翻倍成 (40,36)）。
- `BaseDialog(closable=)` 默认 **False**（与 Web 的 `closable` 默认 true 有意不同）：存量弹窗
  全部自带页脚「关闭/确定/取消」，再加浮动关闭按钮 = 同一弹窗两个关闭入口，属业务行为变更。
  需要右上角关闭按钮的新弹窗显式传 `closable=True`。
- 守护用例：`tests/gui/test_base_table.py`（27 项）+ `tests/gui/test_base_dialog.py`（27 项）——
  令牌取值（表头底/字色、斑马纹、hover/选中、边框、圆角、内边距、标题、关闭按钮）、四主题不崩、
  非法 theme 抛 ValueError、缺令牌抛 KeyError、`--selected` 合成算法、源码与运行期 QSS 无字面色值；
  `tests/test_ui/test_win_table_dialog_unification.py`（7 项）——「`pilotstd/ui` 内不得再构造裸
  `QTableWidget`/`QDialog`」、各弹窗公开面（标题/尺寸/closeEvent/信号）保留、列行为语义保留。
- 后续新增 Win 表格/弹窗：直接用 `BaseTable` / `BaseDialog`，不要再用裸 `QTableWidget` / `QDialog`。
