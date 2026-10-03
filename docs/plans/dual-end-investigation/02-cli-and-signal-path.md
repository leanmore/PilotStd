# 双端报告澄清：CLI 定位 + Windows 端信号链路 + 共享事件定义

> 性质：**只读澄清**（不写方案、不裁决定位、不改代码）
> 前序：[01-architecture-recon.md](01-architecture-recon.md)（双端架构实测）
> 代码基线：工作区 HEAD `d0816c92`
> **本轮只给事实 + 推断 + 置信度**；CLI 的最终定位、Windows 端是否需要通知系统，均由决策者裁定。

---

## 摘要（给决策者，28 行）

**一、CLI 定位（事实 → 推断，置信度 中）**
1. CLI 的依赖闭包**不含 PyQt、不含 `pilotstd.ui`、不含 `docker`**（226 个项目模块），是一条**独立第三入口**，复用共享引擎。
2. **代码层证实了决策者的观察**：非打包模式下配置/数据目录由**包位置**反推（`pilotstd/core/config/paths.py:29-30,46` → 仓库根 `data/`），即**必须源码状态下执行**。
3. 但它**不是打包交付物**：`pyproject.toml` 无命令行入口声明；Windows exe **`console=False`**（`desktop/PilotStd.spec:116`）而 CLI 结果**只写 stdout** → 打包形态下不可用；Docker 镜像里**有 CLI 代码但无任何调用**。
4. 文档立场相反：**用户帮助文档**把它写成"九、命令行模式"（11 条示例），人工测试方案把它列为测试用例组，但 README 的交付表**只列 PyGUI + Docker**。
5. **推断**：面向"能跑源码的人"——**开发者 / 运维 / 自动化 + 人工测试验收接口**；不属于双端任一端的运行时。**置信度 中**（正反证据同时成立，方向相反）。

**二、Windows 端任务中心 = 「进行中 + 历史」两者都有**，但它是**任务队列视图**（task_type/status/progress），不是"通知/事件历史"；且「清除已完成」**不删记录**（只把状态改成 CANCELLED，列表照旧显示）。

**三、共享事件信号链路（关键）**：Windows 端有**两条互不相干的链路**——
- **业务事件链路**：`send_event` → 默认 **`notification.enabled=False` 在第一步早退，只留一行 `logger.debug`**；且**WS 广播已在阶段 0 删除**（`pilotstd/core/notification/manager.py:580-581`），所以连"Web 端能看到"都没有；
- **UI 直呼链路**：`NotifyService.show()` → 3 秒同标题去重 / 桌面聚合器 → **托盘气泡**，**完全绕过 `NotificationManager`**（不写日志、不用渠道）。
两条链路**唯一共享的是 `notification/aggregate_buffer`**。

**四、重统计（"共享"有两种口径）**：产出侧共享 **15**；**投递侧（Windows 默认）0**；手工开启 `notification.enabled` 后，15 个共享事件中**仅 4 个**有默认渠道规则，`worker_error` **0/1**。

**五、战略问题**：正反证据各 5 条，见 §四，**不裁决**；需决策者拍板 3 个问题（§4.3）。

---

## 一、CLI 定位推断（事实 + 推断，不裁决）

### 1.1 入口与依赖

| 项 | 事实 | 证据 |
|---|---|---|
| **入口 A** | `main.py --cli` → `pilotstd.cli.commands.main` | `main.py:94-95`（`--cli` 参数）、`:98-105`（转发 `remaining` 后 `return cli_main()`） |
| **入口 B** | `python -m pilotstd.cli.commands`（模块入口） | `pilotstd/cli/commands/__main__.py:1-7`（`from pilotstd.cli.commands import main; sys.exit(main())`） |
| **子命令规模** | **12 个**，分三组（核心流程 / 管线类 / 文件操作） | `pilotstd/cli/commands/__init__.py:43`（`_add_core_subparsers`：scan/query/download/organize）、`:65`（`_add_pipeline_subparsers`：auto/pending/normalize/announce/task）、`:96`（`_add_file_ops_subparsers`：move/expire/validity）、`:115`（`build_parser`） |
| **依赖闭包（实测）** | **226 个项目模块**；外部顶层包 54 个（`argparse`/`requests`/`httpx`/`playwright`/`cloakbrowser`/`ddddocr`/`cryptography`/`pypdf`/`docx`/`bs4`/`watchdog`/`yaml`…） | 脚本 `C:/Temp/mp_probe/cli_closure.py`（从 `pilotstd.cli.commands` 做模块级闭包） |
| **是否 import PyQt** | **否** | 同上（`PyQt 是否可达: 否`）；对比 GUI 闭包 295 模块**可达 PyQt** |
| **是否 import `pilotstd.ui`** | **否** | 同上 |
| **是否 import `docker`** | **否** | 同上；对比 `docker.app` 闭包 275 模块含 docker |
| **是否依赖完整 `pilotstd/` 源码** | **是（非打包模式）**：配置目录与数据目录都由**包位置**反推 | `pilotstd/core/config/paths.py:29-30`（`_get_config_dir` → `os.path.join(os.path.dirname(__file__), "..","..","..","data")`）、`:46`（`get_data_dir` 同款） |
| **打包模式的路径** | 走 `is_frozen()` 分支：`exe_dir/config`（失败回退 `%APPDATA%/PilotStd`） | `pilotstd/core/config/paths.py:13-28`（config）、`:35-45`（data）、`:8`（`from ..frozen import is_frozen`） |
| **并需要运行时目录** | `config.json`（`pilotstd/core/config/manager.py:260`）、`data/pilotstd.db`（`pilotstd/core/config/paths.py:49-51`）、`logs/`（`pilotstd/cli/commands/__init__.py:9,130` 初始化 `LoggerManager`） | 同上 |
| **是否有命令行入口声明** | **没有**：`pyproject.toml` 无 `[project.scripts]` / `console_scripts`（实测 0 命中） | `pyproject.toml` 全文检索 |
| **CLI 会构造什么** | `StandardManager(config=ConfigManager())`——与 GUI/Docker 同一门面 | `pilotstd/cli/commands/_shared.py:10-19`（`_make_manager`） |

**一条关键自述**：`pilotstd/cli/commands/_shared.py:11` 的 docstring 是"创建 `StandardManager` 实例——**CLI 和测试的统一入口**" → 代码把 CLI 与**测试**并列。

### 1.2 打包产物中的存在性

| 产物 | CLI 代码是否在 | 是否可用 | 证据 |
|---|---|---|---|
| **Windows exe** | **在**：`collect_submodules("pilotstd")` 会把 `pilotstd.cli.*` 一并收进 | **否（主输出无处可去）** | `desktop/PilotStd.spec:22`（`hiddenimports = collect_submodules("pilotstd")`）、`:52`（入口 `["../main.py"]`）、`:96-122`（单一 `EXE`，**`:116 console=False`**） |
| Windows exe 的能力边界 | 打包时 **excludes** 掉服务端与调度依赖 | exe **无定时任务**能力 | `desktop/PilotStd.spec:60-87`（排除 `uvicorn`/`fastapi`/`starlette`/`apscheduler`/`jose`/`passlib`/`psutil`/`tkinter`） |
| **CLI 输出去向** | 全部写 **stdout**（CSV / JSON） | 无控制台的 exe 里等于丢弃 | `pilotstd/cli/commands/scan.py:18-31`（`json.dump(..., sys.stdout)`）、`:32-46`（`csv.writer(sys.stdout)`） |
| **Docker 镜像** | **在**：镜像复制了 `pilotstd/` 与 `main.py` | **无调用**：容器只起 uvicorn；`docker/` 与 `docker-compose.yml` **零处**引用 CLI（唯一命中是 `COPY main.py`） | `docker/Dockerfile:37`（`COPY pilotstd/`）、`:38`（`COPY main.py .`）、`:55`（`COPY docker/`）；`docker/entrypoint.sh` 末行（`uvicorn docker.app:app`） |
| Docker 内 CLI 依赖 | 齐备（CLI 依赖来自共享 `requirements.txt`，镜像已装） | 理论可行（`docker exec … python main.py --cli …`）——**本轮未实测运行** | `docker/requirements-docker.txt:6`（`-r ../requirements.txt`） |

### 1.3 代码里的定位证据

| 项 | 结果 | 证据 |
|---|---|---|
| 模块 docstring | 仅"CLI 命令行接口模块"，**无受众说明** | `pilotstd/cli/__init__.py:2` |
| 是否出现"仅供开发/调试/运维"字样 | **未找到**（实测） | `pilotstd/cli/**` 全文检索 |
| 会话级痕迹 | 启动即写 `[CLI] 会话开始 PID=… 命令=…` → 设计上按"管理员会话来用" | `pilotstd/cli/commands/__init__.py:128-133` |
| 是否内置"测试"定位 | `pilotstd/cli/commands/_shared.py` docstring 明写"CLI 和测试的统一入口" | `pilotstd/cli/commands/_shared.py:11` |
| 向后兼容类 | 保留 `class CLI` 做静态方法转发（包化前的旧接口） | `pilotstd/cli/commands/__init__.py:144-159` |
| **git 历史** | **CLI 在初始提交就有**：`9256b383 Initial commit: PilotStd - 标准文件管理工具`（2026-06-17）；后由 `87de5d02 refactor: 拆分 cli/commands.py 为 12 个独立子命令文件` 结构化 | `git log --diff-filter=A -- pilotstd/cli/__init__.py`；`git log --oneline -- pilotstd/cli/`（共 20 次提交） |
| 提交信息里的定位表述 | **未找到**说明受众的提交信息（均为 refactor/style/gate 类） | 同上 |

### 1.4 使用痕迹

| 场合 | 性质 | 证据 |
|---|---|---|
| **用户帮助文档** | 有独立章节"**九、命令行模式**"，11 条用法示例（`python -m pilotstd.cli.commands scan/query/download/auto/normalize/move/expire/announce/task …`） | `docs/guides/用户帮助文档.md:205-229` |
| **人工测试方案** | 作为**测试用例组 §3.6**（`3.6.1`~ 逐条给"命令 + 预期结果"） | `docs/guides/人工测试方案.md:269-271` |
| **README** | 目录结构里称 `main.py` 为"程序入口（**GUI / CLI**）"、`pilotstd/cli/` 为"命令行接口"；但同文件的技术/交付表**只列「桌面 GUI（PyInstaller exe）」与「Web 前端/后端（Docker）」** | `README.md:72`、`:80`；对照 `README.md:60-66` |
| **单元测试** | 有：`tests/cli/test_argparse.py`（≥20 处调用 `build_parser()`） | `tests/cli/test_argparse.py:3,8,14,…` |
| **端到端/脚本调用** | **未找到**：`tests/`、`scripts/` 无 `--cli` 或 `pilotstd.cli` 的调用（实测，仅 `tests/cli/test_argparse.py` 是 import 单测） | 检索 `tests,scripts` 的 `pilotstd.cli\|--cli\|cli_main` |
| **其他文档** | `docs/.local/压力测试方案.md`（1 处）、归档文档 4 处 | 检索 `docs/**` 聚合结果 |

### 1.5 推断与置信度

**推断（不是裁决）**

- **面向谁**：**面向"能跑源码的人"**——即**开发者 / 运维 / 自动化调用者**，并兼任**人工测试与验收接口**（依据：`pilotstd/cli/commands/_shared.py:11` 把 CLI 与测试并列、`docs/guides/人工测试方案.md:269-271` 把它编成用例组、无 console 入口、exe 无控制台、输出绑 stdout、路径绑源码树）。
- **是否属于双端中的任一端**：**不属于**。它是**独立第三入口**：与两端共享同一业务引擎（`pilotstd/manager` + `pilotstd/core`），但**排除** `pilotstd/ui`（无 PyQt）与 `docker/`。
- **与决策者表述的一致性**：**代码层可证**——`pilotstd/core/config/paths.py:29-30,46` 的源码模式分支确实把配置/数据目录绑在**包相对位置**，因此"要在源码状态下直接命令行执行"成立。

**置信度：中**

| 理由 | 说明 |
|---|---|
| 支持面 | 文档把它写成用户功能（用户帮助文档 §九、11 例）；12 个子命令覆盖完整业务流程；有单测；与项目同龄（初始提交） |
| 反对面 | 无命令行入口声明；打包 exe `console=False` 而输出只走 stdout；必须源码 + Python；交付表不含 CLI；无任何 E2E/脚本调用痕迹 |
| 为何不是"高" | 正反证据**同时成立且方向相反**，且**代码无法表达意图**——只能说明"两种读法都有代码支撑" |
| 为何不是"低" | 关键事实（依赖闭包、路径解析、console 标志、交付表）都是**实测**，不是推断 |

**仍不确定的点**

1. **是否有人在真实工作流中使用**——无使用日志/遥测证据。
2. **CI 或发布流程是否调用**——`tests/scripts` 中未见；`.github/workflows/` 未逐一核（**未确认**）。
3. **Docker 内 `docker exec … --cli` 是否可用**——依赖齐备、代码在镜像内，但**未实测运行**。
4. CLI 里 `--format json` 之类输出是否被外部系统消费（无调用方证据）。

---

## 二、Windows 端任务中心实测

### 2.1 数据源与查询条件

| 项 | 事实 | 证据 |
|---|---|---|
| 控件 | `TaskPage`（表格 + 详情）；`TaskCenterDialog` 包装 | `pilotstd/ui/pages/task_page.py:30`、`:126-140` |
| 数据源 | `self._queue.list_all(limit=100)` | `pilotstd/ui/pages/task_page.py:94` |
| 查询语句 | `SELECT * FROM task_queue ORDER BY updated_at DESC LIMIT ?` —— **无 status 过滤** | `pilotstd/task/queue.py:91-95` |
| 表 | `TASK_TABLE = "task_queue"`；DDL 见迁移 | `pilotstd/task/queue.py:15`；`pilotstd/core/db/_migrate_v16_v49.py:166-175`（建表 + 3 个索引） |
| 持久化 | `_persist` 做 UPSERT（存在则 UPDATE，否则 INSERT） | `pilotstd/task/queue.py:166-190` |
| 桌面写入方 | 操作完成后 `_register_task(label, total, completed, failed)` 把"扫描/查询/下载/规范化"映射为 `TaskType` 并入队 | `pilotstd/ui/main_window/parts/_dialog_ops.py:107-121`（`type_map` 在 `:112-117`） |
| 菜单入口 | 主窗口 → `TaskCenterDialog(self._mgr.task_queue, self)` | `pilotstd/ui/main_window/parts/_actions_ops.py:181-183` |

### 2.2 展示范围（进行中 vs 历史）

| 维度 | 事实 | 证据 |
|---|---|---|
| 表格列 | 任务ID / 任务类型 / 状态 / 进度(`completed/total (pct%)`) / 创建(更新时间) / 错误 | `pilotstd/ui/pages/task_page.py:56-66`、`:97-106` |
| 状态覆盖面 | 不做过滤 ⇒ **全部状态都在一张表里**：`PENDING`(`pilotstd/task/queue.py:41`)、`RUNNING`(`:55`)、`PAUSED`(`:63`)、`CANCELLED`(`:73`)、`COMPLETED`(`:107`)、`FAILED`(`:132`) | `pilotstd/task/queue.py:91-95` + 各状态赋值点 |
| 刷新方式 | **手动**（`btn_refresh`），无定时刷新 | `pilotstd/ui/pages/task_page.py:46-47`、`:89-106` |
| 排序 | 按 `updated_at DESC`（最近活动在前） | `pilotstd/task/queue.py:93` |
| **"清除已完成"的语义** | **只把状态改成 `CANCELLED`，不删记录**；而 `list_all` 无过滤 ⇒ **点完列表照旧显示这些任务**（状态变成 CANCELLED） | `pilotstd/ui/pages/task_page.py:110-120`（对 COMPLETED/CANCELLED/FAILED 调 `self._queue.cancel(...)`，注释写 "marks for cleanup"）；`pilotstd/task/queue.py:72-73`（`cancel` → `_set_status(CANCELLED)`）；`pilotstd/task/queue.py:155-164`（`_set_status` 会 `_persist`） |
| 是否存在清理任务 | **未找到**：全库无 `DELETE FROM task_queue`（实测命中 0） | 检索 `pilotstd,docker,scripts` |

### 2.3 判定

**判定：Windows 端任务中心是「进行中 + 历史」两者都有的视图**（无状态过滤的 `SELECT *`，含 COMPLETED/FAILED/CANCELLED）。

**但它不是"通知中心/事件历史"**，三点差异（均有代码证据）：

| 差异 | 任务中心 | 通知/事件历史（不存在） |
|---|---|---|
| 记录单位 | **任务**（`task_id` / `task_type`） | 事件 |
| 展示维度 | 状态、进度、错误——**工程视角** | 事件名、级别、文案、渠道、已读 |
| 清除语义 | **改名不删行**（`CANCELLED`），且列表仍显示 | — |

---

## 三、Windows 端共享事件信号链路

### 3.1 单条链路追踪（以 `scan_complete` 为例）

```
[用户] 点"扫描" → ui/core/handlers/_scan.py:78  run_scan(root_path)
  → ui/workers/scan.py:35  ScanWorker.run()
      → :64  self._mgr.scan_stream(self._root_path, on_progress=…, on_batch=…)
  → manager/facade/_scan.py:239  ScanHandler.scan_stream(...)
      → :249  self.scan_directory_stream(...)
  → manager/facade/_scan.py:99   scan_directory_stream(...)   ← 解析完成
      → :157-159  if self._core.notification_mgr: notification_mgr.send_event("scan_complete", {...})
  → core/notification/manager.py:294  if not self._enabled:
      → :295  logger.debug("通知功能未启用，跳过事件 %s 的发送", event_type); return   ★ 默认在此终止
```

**若 `_enabled=True`（需手工改配置）后续：**
```
 :298  _policy.get_channels_for_event(user_id, event_type)      # 无规则 → :299-301 logger.info + return
 :303  _build_message(event_type, event_data)                   # 构建 i18n 文案
 :306  ops.apply_mapping(msg, event_type, event_data)           # 三层模型投影
 :308-312 _validate_message（空消息拦截，失败仅记 error 后 return）
 :313  _do_send(msg, target_channels, bypass_aggregation=…)
   → :340-342  静音时段命中 → _enqueue_notification → 写通知队列表，延后
   → :343-346  非静音且聚合开启 → aggregator.enqueue(msg, …, target_id=…)
   → :347-348  否则 → _send_now(msg, target_channels)
        → :353-379  逐渠道 channel.send(msg) + self._log(...)（写 notification_log）+ _record_delivery(...)
```
（`_log` 委托 `pilotstd/core/notification/_manager_ops.py:58` 的 `NotificationOps.log`，`:70` 执行 `INSERT INTO notification_log (...)`；`_record_delivery` 见 `pilotstd/core/notification/manager.py:383-398`。）

### 3.2 `send_event` 在 Windows 端的下游分类

| 条件 | 下游效果 | 证据 |
|---|---|---|
| **`notification.enabled=False`（默认）** | **仅一行 `logger.debug`**——不建消息、不写 `notification_log`、不进聚合器、不投渠道 | `pilotstd/core/notification/manager.py:294-296`；默认值 `pilotstd/core/config/defaults.py:54`（`False`）；`_enabled` 解析 `pilotstd/core/notification/manager.py:144-148`（config 值，`user_preferences` 有记录则覆盖）；**`_enabled=False` 时渠道根本不初始化**（`:153-154`） |
| `_enabled=True`，事件无渠道规则 | 一行 `logger.info`（"无订阅渠道，跳过发送"） | `pilotstd/core/notification/manager.py:299-301`；规则来源 `pilotstd/core/notification/_policy.py:56-62`（DB 策略表 → 回退 `notification.rules.<event>`） |
| `_enabled=True`，命中静音时段 | 写通知队列表，**延后补发**（不丢） | `pilotstd/core/notification/manager.py:340-342` |
| `_enabled=True`，正常 | 建消息 → 写 `notification_log` → 渠道 `send()` → 记录投递健康度 | `pilotstd/core/notification/manager.py:303-313`、`:350-379`、`pilotstd/core/notification/_manager_ops.py:58-70` |

**一个必须纠正的事实**：**通知链路已无 WS 广播**。`pilotstd/core/notification/manager.py:580-581` 注释原文："（原 `_broadcast_to_ws` 与之并列，随 **WebSocket 死代码清理于阶段 0** 删除，见 `docs/plans/notification-redesign/06-阶段0-1实施方案.md` §1.2。）"；全库在 `pilotstd/core/notification/` 与 `docker/api/` 内检索 `websocket|broadcast|ConnectionManager` **0 命中**（实测）。
⇒ **"禁用通知后事件仍能在 Web 端看到"这条兜底不存在**：`_enabled=False` 时该事件在系统里**不留任何痕迹**（除一行 debug 日志）。

### 3.3 第二条链路：UI 直呼（不经 `NotificationManager`）

```
UI Handler（_download / _announce / _archive / _query_summary）
  → platform/notify.py:48  NotifyService.show(title, message)     或 :67 show_warning(...)
      → :52-57  若 aggregator.auto_pause_enabled 为假：
                  :54 _check_dedup(title)（3 秒同标题防抖）→ :56 tray.showMessage(...)
      → :58-65  否则 agg.should_show("info", title, message, on_show=→tray.showMessage)
  → core/notification_aggregator.py:511 should_show(...) → :525 self._on_show = on_show
      → 内部 :165-166 self._new = NewAggregator(sender_func=self._on_new_flush, …)
          → core/notification/aggregate_buffer.py（主题分组 + 熔断暂停 + 窗口合并）
      → :469-507 _on_new_flush → _on_show(...) → 托盘气泡（含 QTimer 回主线程）
```
**关键边界**：本链路**不经过 `NotificationManager`**——不写 `notification_log`、不查策略表、不使用任何渠道；它与 `send_event` 链路**唯一共享的是 `notification/aggregate_buffer` 模块**（桌面聚合器持其实例）。代码注释也明确把两者定义为不同层次：`pilotstd/platform/notify.py:96-104`（"3 秒同标题瞬时防抖"与"主题分组"是**不同层次的去重**，两条路径**互斥**）。

### 3.4 "共享"定义与重统计

**两种口径必须分开**（这是对 01 报告口径的必要澄清）：

| 口径 | 定义 | 判据 | 结果 |
|---|---|---|---|
| **A. 产出侧可达**（01 报告用法） | 该事件的**产出点**能从两端入口走到 | 反向调用链 BFS + 人工核验（见 01 报告 §3.1） | **15 个** |
| **B. 投递侧可达（Windows）** | 该事件在 Windows 端**能真正投递出去** | `_enabled` 门控 + 渠道规则 | **默认 0 个**；手工开启后 **4 个** |

**重统计（全 41 个，实测脚本）**

| 归属 | 数量 | 有默认渠道规则（`notification.rules.*`，共 16 条） |
|---|---|---|
| Docker 专属 | **25** | **12**：`standard_status_changed`、`announcement_fetch_complete`、`auto_backup`、`announcement_check_complete`、`auto_scan_failed`、4×`validity_*`、`date_reminder`、`favorite_abandoned_summary`、`security_login_failed` |
| 产出侧共享（A 口径） | **15** | **4**：`archive_complete`、`standard_first_registered`、`batch_download_complete`、`notification_delivery_failed` |
| Windows 专属 | **1**（`worker_error`） | **0** |
| 合计 | **41** | 16 |

⇒ **在 Windows 端"投递可达"口径下：默认 0 个事件能投递；把 `notification.enabled` 手工改成 True 后，也只有 4 个共享事件有默认收件渠道。**

---

## 四、战略问题呈现：Windows 端是否需要通知系统？

> **本节只呈现证据，不裁决。** 两个概念在证据里都出现，必须先分开：**(i) 托盘气泡机制**（已存在、在用）与 **(ii) 渠道推送能力**（代码存在但默认关闭、无配置入口）。

### 4.1 支持"需要"的证据

| # | 证据 | `路径:行号` |
|---|---|---|
| 1 | 桌面端**确实产生**事件：15 个共享事件 + 1 个专属事件，覆盖扫描/查询/下载/归档/规范化/公告/配额等全部桌面操作 | 01 报告 §3.2（产出点表）；`pilotstd/ui/workers/` 信号与 handler 链路如 `pilotstd/ui/core/handlers/_scan.py:78`→`pilotstd/ui/workers/scan.py:64`→`pilotstd/manager/facade/_scan.py:159-160` |
| 2 | **长耗时操作**存在（一键自动 4 阶段、批量查询/下载/归档），用户可能**离席**；托盘气泡是唯一离席通道 | `pilotstd/ui/core/handlers/_auto.py:94`（`start_auto_pipeline`）；`pilotstd/ui/workers/auto.py:27`（`stage_changed`）；`pilotstd/platform/notify.py:48` |
| 3 | 桌面端已建成一条**独立通知管线**：3 秒同标题去重 + 主题分组 + **熔断暂停**（30 秒内 3 条警告/错误 → 暂停 5 分钟） | `pilotstd/platform/notify.py:93-111`；`pilotstd/core/notification_aggregator.py:165-166`、模块 docstring（"30 秒内累计 3 条警告/错误 → 暂停 5 分钟"） |
| 4 | 已有"桌面端也要发事件"的既成代码 | `ui/pending_query_dialog.py:289-290`（`worker_error`） |
| 5 | 共享事件里**已有 4 个配了默认渠道**（含 `archive_complete`、`batch_download_complete`）——设计上认为这些值得推送 | `pilotstd/core/config/defaults.py:62-80`（16 条规则）；交集见 §3.4 |
| 6 | 模型层已预留"进度型通知"的载体 | `pilotstd/core/notification/mapping.py:70-77`（`CONTENT_TYPES` 含 `task_progress`，实测 0 个事件使用）；`pilotstd/core/notification/channel.py:62`（`task_id` 注释即"进度型通知的原地更新锚点"） |

### 4.2 支持"不需要"的证据

| # | 证据 | `路径:行号` |
|---|---|---|
| 1 | Windows 端**已有一整套当场呈现**：进度条（缓动）+ 状态栏 + 表格流式 + 完成/失败气泡 + 摘要对话框 + 任务中心 | 01 报告 §2.2；`pilotstd/ui/core/unified_progress.py:18-54`；`main_window/__init__.py:42-43`；`pilotstd/ui/core/handlers/_download.py:284-307` |
| 2 | 15 个共享事件在桌面端**默认全部早退**（只留一行 debug 日志），**实际运行中从未投递** ⇒ 现状即"不需要" | `pilotstd/core/notification/manager.py:294-296`；`pilotstd/core/config/defaults.py:54`（默认 `False`） |
| 3 | Windows 端**没有配置入口**（`pilotstd/ui/**` 对 `notification.*` 零引用），即桌面端连"我要推送"都无法表达 | 01 报告 §2.6（实测 0 命中）；唯一写入点在 `docker/api/notification.py:272,275` |
| 4 | 两条链路的**职责边界在代码注释里被反复划清**（"不同层次的去重""两条路径互斥"）——现有设计倾向"两套东西，别混" | `pilotstd/platform/notify.py:96-104`；`pilotstd/core/notification/aggregate_buffer.py` 模块 docstring（"禁止越界"）；`pilotstd/core/notification_aggregator.py` docstring（"独立链路、不共享状态"） |
| 5 | 桌面端**唯一的专属事件发不出去**（无规则 + 无入口），说明"桌面端往渠道推"这条路**从未被真实需求拉动** | `pilotstd/core/notification/_policy.py:56-62` 返空即 return；`pilotstd/core/notification/manager.py:299-301`；`pilotstd/core/config/defaults.py:62-80` 无 `worker_error` |
| 6 | 该专属事件的**触发面极窄**：全库仅 1 处，且只在一个对话框里 | `ui/pending_query_dialog.py:290`（实测全库唯一触发点） |
| 7 | 打包形态**主动排除了调度与服务端依赖**，桌面端被定位为"本地工具"而非"常驻服务" | `desktop/PilotStd.spec:60-87`（excludes uvicorn/fastapi/apscheduler/psutil） |

### 4.3 明确提交决策者

**以下 3 个问题本轮不裁决，请决策者拍板：**

| # | 问题 | 相关的既有事实（供判断用） |
|---|---|---|
| **Q1** | "Windows 端不需要通知系统"——这里的"通知系统"指 **(i) 托盘气泡机制**（已存在且在用），还是 **(ii) 渠道推送能力**（代码在、默认关、无配置入口）？ | (i) 由 `pilotstd/platform/notify.py` + `pilotstd/core/notification_aggregator.py` 提供，与 `NotificationManager` 完全解耦；(ii) 由共享的 `NotificationManager` 提供，两端同一份代码 |
| **Q2** | 若 Windows 端**需要**渠道推送：是否接受"桌面端没有配置入口"（只能手工编辑 `config.json` 或直接改 `user_preferences` 表）？ | `notification.enabled` 读取见 `pilotstd/core/notification/manager.py:144-148`；唯一 GUI 写入点在 Docker Web（`docker/api/notification.py:272,275`） |
| **Q3** | 若 Windows 端**不需要**渠道推送：15 个共享事件在桌面端的 `send_event` 调用是否保留？（现状 = **空转**：默认配置下只产生一行 debug 日志，且无 WS 广播、无日志落库） | `pilotstd/core/notification/manager.py:294-296`；`pilotstd/core/notification/manager.py:580-581`（WS 已删） |

---

## 附：可复算命令

```powershell
# ── 一、CLI 定位 ──
python C:\Temp\mp_probe\cli_closure.py                     # 依赖闭包：CLI 是否触达 PyQt / ui / docker
Get-Content main.py | Select-Object -Skip 93 -First 14      # --cli 入口
Get-Content pilotstd\cli\commands\__main__.py               # python -m 入口
Get-Content pilotstd\cli\commands\__init__.py               # 12 个子命令 + main()
Get-Content pilotstd\cli\commands\_shared.py                # "CLI 和测试的统一入口"
Get-Content pilotstd\core\config\paths.py                   # 源码模式 vs frozen 模式的路径解析
Select-String -Path pyproject.toml -Pattern 'scripts|entry_points|console'      # 空 = 无命令行入口声明
Get-Content desktop\PilotStd.spec | Select-Object -Skip 50 -First 67            # Analysis/excludes/EXE(console=False)
Get-Content pilotstd\cli\commands\scan.py | Select-Object -Skip 17 -First 30    # 输出只写 sys.stdout
Select-String -Path docs\guides\用户帮助文档.md -Pattern '命令行模式|python -m pilotstd.cli' -Context 2,3
Select-String -Path docs\guides\人工测试方案.md -Pattern 'python -m pilotstd.cli' -Context 1,2
git log --diff-filter=A --format='%H %ad %s' --date=short -- pilotstd/cli/__init__.py   # 初始提交即存在
Get-ChildItem tests,scripts -Recurse -File | Select-String 'pilotstd\.cli|--cli'       # 仅 tests/cli/test_argparse.py
Get-ChildItem docker -Recurse -File | Select-String 'main\.py|--cli|pilotstd\.cli'     # 仅 Dockerfile 的 COPY main.py

# ── 二、任务中心 ──
Get-Content pilotstd\ui\pages\task_page.py | Select-Object -Skip 88 -First 33   # _refresh / _clear_completed
Get-Content pilotstd\task\queue.py | Select-Object -Skip 90 -First 6            # list_all：SELECT *（无状态过滤）
Get-Content pilotstd\task\queue.py | Select-Object -Skip 154 -First 11          # _set_status → _persist
Get-ChildItem pilotstd,docker,scripts -Recurse -File | Select-String 'DELETE FROM task_queue'   # 空 = 无清理

# ── 三、信号链路 ──
Get-Content pilotstd\ui\workers\scan.py | Select-Object -Skip 34 -First 42      # Worker → mgr.scan_stream
Get-Content pilotstd\manager\facade\_scan.py | Select-Object -Skip 150 -First 12  # send_event("scan_complete")
Get-Content pilotstd\core\notification\manager.py | Select-Object -Skip 284 -First 30  # 门控 → 策略 → 构建 → _do_send
Get-Content pilotstd\core\notification\manager.py | Select-Object -Skip 349 -First 30  # _send_now：渠道 + _log
Get-Content pilotstd\core\notification\manager.py | Select-Object -Skip 575 -First 8   # WS 死代码清理说明
Get-ChildItem pilotstd\core\notification,docker\api -Recurse -File | Select-String 'websocket|broadcast|ConnectionManager'  # 空
Get-Content pilotstd\core\notification\_manager_ops.py | Select-Object -Skip 57 -First 16  # notification_log INSERT
Get-Content pilotstd\platform\notify.py                                        # UI 直呼链路（去重 / 聚合 / 托盘）
Get-Content pilotstd\core\notification_aggregator.py | Select-Object -Skip 160 -First 10  # _new = NewAggregator(sender_func=…)
python -c "import sys;sys.path.insert(0,'.');from pilotstd.core.config.defaults import FACTORY_DEFAULTS as D;r={k[19:] for k in D if k.startswith('notification.rules.')};print(len(r), sorted(r))"
```

### 自检结果

| 检查项 | 结果 |
|---|---|
| 引用回读校验（文件存在 + 行号在范围内） | **65 处唯一引用，0 处越界**（`C:/Temp/mp_probe/check_dualend2.py`） |
| 引用**内容**抽检（行号处是否确为所引内容） | **44 处抽查，44 处通过，0 处不符**（`C:/Temp/mp_probe/verify_dualend2.py`）；抽检曾抓出 3 处行号错位（`cli/commands/__init__.py` 的 `class CLI`/`LoggerManager`/子命令分组行号、`_scan.py:159` 的跨行调用）并已修正 |
| 与 01 报告不一致处 | **2 处**（本轮**只在本报告内声明修正，按纪律不改动 01 报告**）：① 01 报告 §2.5 写"共享事件在桌面端触发后不会投递到任何渠道，**仅落通知日志/WS（若有）**"——本轮实测 **WS 广播已于阶段 0 删除**（`pilotstd/core/notification/manager.py:580-581`），且默认门控在最前，**连 `notification_log` 都不落**（`pilotstd/core/notification/manager.py:294-296`）；② 01 报告 §2.3 未覆盖任务中心"**清除已完成**"的行为——本轮补充实测：**只改状态不删行**（`pilotstd/ui/pages/task_page.py:110-120` + `pilotstd/task/queue.py:91-95`） |
| 未确认项 | **3 处**：① CLI 是否有真实使用者（无遥测）；② `.github/workflows/` 是否调用 CLI（未逐一核）；③ Docker 内 `docker exec --cli` 未实测运行 |
