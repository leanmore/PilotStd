# CI 修复经验总结

> 最后更新：2026-09-26
> 基于 2026-07-16 CI 综合修复（12 轮迭代）提炼；2026-09-21 追加第七节（mock 掩盖真实调用链）；2026-09-26 追加第八节（QThread 运行中被析构 → Qt qFatal）

---

## 总览

| 问题类别 | 问题数 | 典型症状 | 核心教训 |
|----------|--------|---------|---------|
| 依赖管理 | 2 | `ModuleNotFoundError` | 测试依赖必须在 CI 使用的 requirements 文件中显式声明 |
| 跨平台测试 | 4 | Linux CI 运行 Windows 测试 / 外部站点超时 | CI 环境与本地环境差异必须通过 skip/xfail 明确处理 |
| 测试设计 | 3 | 断言字段名过时 / 代码重构后测试未同步 | 测试写源码字符串的断言极易腐烂 |
| 测试盲区 | 1 | mock 覆盖了出错层（`AttributeError` 存活 3 个月、业务 0 成功） | 只有真实执行到下一层的测试才算验证（见第七节） |
| 静态检查 | 3 | vulture/G-010/G-011 阻断 CI | 静态检查工具需持续维护白名单和规则 |
| 退出清理 | 1 | `RuntimeError: wrapped C/C++ object has been deleted` | Qt 对象生命周期 vs Python atexit 顺序需显式管理 |
| Qt 生命周期 | 1 | CI `exit code 134`(SIGABRT)、**无汇总**、崩点漂移 | QThread 运行中被 GC 析构即 qFatal；测试基建空转会掩盖崩溃（见第八节） |
| 文件管理 | 1 | `tests/fixtures/` 被 gitignore 忽略 | `.gitignore` 误伤需定期审计 |

---

## 一、依赖管理

### 1.1 `responses` 缺失导致 WechatIP 测试失败

- **现象**: `ModuleNotFoundError: No module named 'responses'`，`test-backend` job 失败
- **根因**: `responses` 库用于 mock HTTP 请求，仅在 `tests/test_final_complete.py` 的 `TestWechatIP` 中使用，但未在任何 `requirements*.txt` 中声明
- **修复**: 在 `docker/requirements-docker.txt` 和 `desktop/requirements-win.txt` 中分别添加 `responses>=0.25.0`
- **预防**:
  - 新增测试依赖时，必须同步更新 CI 使用的 `requirements*.txt`
  - CI 环境禁止依赖隐式可用的系统包

### 1.2 `tests/fixtures/` 被 `.gitignore` 忽略

- **现象**: `ImportError: No module named 'tests.fixtures'`，所有 CI job 失败
- **根因**: `.gitignore:34` 存在规则 `tests/fixtures/`，整个目录未纳入版本控制；CI 克隆后目录缺失
- **修复**: 从 `.gitignore` 删除该行，将 5 个 fixture 文件纳入 git 跟踪
- **预防**:
  - 周期性审计 `.gitignore` 规则是否误伤了需要跟踪的文件
  - `.gitignore` 规则应尽可能精确（`tests/fixtures/*.html` 优于 `tests/fixtures/`）

---

## 二、跨平台测试

### 2.1 外部站点测试在 CI 中超时

- **现象**: `test-backend` job 中 ahbz/std_gov/hbba/dbba/iso_gov/njbz365 测试超时
- **根因**: CI 环境（GitHub Actions ubuntu-latest）无法访问国内标准站点
- **修复**: 在 `tests/test_e2e_adapters.py` 中为 8 个测试类添加 `@unittest.skipIf(CI, ...)`，`CI` 由 `os.environ.get("CI")` 检测
- **预防**:
  - 所有涉及外部网络请求的测试必须包裹 `CI` 环境检测
  - E2E 适配器测试统一使用 `_CI = os.environ.get("CI", "").lower() in ("true", "1")` 模式

### 2.2 PyQt6 导入在 Linux CI 中失败

- **现象**: `test-backend` job（Linux）中 `ModuleNotFoundError: No module named 'PyQt6'`
- **根因**: `tests/test_scan_misc.py`、`tests/test_groups23_remaining.py`、`tests/test_last_push.py` 中导入了 `pilotstd.platform.notify.NotifyService`，其依赖链最终导入 `QSystemTrayIcon`
- **修复**:
  - 为 3 个 `test_notify_service` 方法添加 `@unittest.skipIf(CI, ...)`
  - `test-backend` CI 配置新增 `--ignore-glob="*test_ui*.py"` 排除所有 UI 测试
- **预防**:
  - Handler 层不应直接导入 `PyQt6` 模块，应通过依赖注入延迟导入
  - `test-backend` job 应仅运行非 GUI 测试

### 2.3 Windows 长路径测试在 Linux 中无效

- **现象**: `tests/test_file_utils.py` 的 `TestEnsureLongPath`、`TestStripLongPath` 使用 `\\?\` 前缀，Linux 无此概念
- **根因**: 这些测试是 Windows 平台特性，在 Linux 上无意义
- **修复**: 添加 `@pytest.mark.skipif(sys.platform != "win32", ...)`
- **预防**: 平台特定测试应显式声明 `sys.platform` 条件

### 2.4 文件权限测试在 Linux CI /tmp 中失败

- **现象**: `TestFileMover`、`TestFileMoverComplete`、`test_process_expired` 出现 `PermissionError`
- **根因**: CI 的 `/tmp` 目录权限行为与本地 `tempfile.mkdtemp()` 不同
- **修复**: 为文件移动测试添加 `@unittest.skipIf(CI, ...)` 或 `@pytest.mark.xfail`
- **预防**: 文件操作测试应使用项目工作目录而非依赖 `/tmp` 行为

---

## 三、测试设计

### 3.1 源码字符串断言因重构失效

- **现象**: `test_regression_architecture.py` 中 `assertIn("error.connect", source)` 失败
- **根因**: P9 事件总线重构后，Handler 不再直接 `.connect` 信号，而是通过 `ArchiveCallbacks`/`QueryCallbacks` 对象传递回调。测试扫描源码字符串检查旧 API
- **修复**: 更新断言匹配新的 `Callbacks` 模式
- **预防**:
  - 避免在测试中检查源码字符串（`inspect.getsource`），此类断言极易因重构腐烂
  - 优先测试行为（调用方法、检查结果），而非实现细节

### 3.2 报告字段名与实现不同步

- **现象**: `test_auto_pipeline.py` 断言 `"query" in report`、`"download" in report`、`"archive" in report` 失败
- **根因**: `_auto.py` 中实际字段名为 `query_found`、`download_success`、`organize_moved` 等
- **修复**: 对齐至实际字段名（6 个字段）
- **预防**: 测试中引用的 dict key 应与生产代码的字段名保持同步；考虑使用常量定义共享字段名

---

## 四、静态检查

### 4.1 Vulture 未使用变量/导入

- **现象**: `vulture` 退出码 3，阻断 `test-backend` job
- **根因**: 15 处未使用的 mock 参数（`mock_load`、`mock_init`）和未使用的导入（`ANY`、`FIELD_TIME`、`_EN_MARK`）
- **修复**: 未使用的 mock 参数改为 `_` 前缀（`_mock_load`）；删除未使用的导入
- **预防**:
  - 提交前运行 `vulture` 本地检查
  - 未使用的 `@patch` 参数统一加 `_` 前缀表示有意忽略

### 4.2 G-010 函数行数超限

- **现象**: `_init_query`(126行) 和 `_load_advanced`(85行) 超出门禁阈值
- **根因**: 函数随功能迭代逐渐膨胀，未及时拆分
- **修复**: `_init_query` 拆为 3 个函数（入口+UI+连接+状态）；`_load_advanced` 拆为 2 个（读取+应用）
- **预防**: 新增逻辑时评估是否应抽取为独立方法；G-010 门禁在 CI 中持续生效

### 4.3 G-011 动态属性完整性

- **现象**: `self.move_done` 和 `self.progress_msg` 被标记为未定义
- **根因**: G-011 的 `QT_SIGNAL_SUFFIXES` 列表中缺少 `_done` 和 `_msg` 后缀，`pyqtSignal` 定义的类级信号未被识别
- **修复**:
  - 在 `QT_SIGNAL_SUFFIXES` 中添加 `_done` 和 `_msg`
  - **反模式教训**: 切勿通过 `__init__` 中赋值字符串来"预声明"信号属性，这会覆盖 `pyqtSignal` 描述符导致运行时 `AttributeError`
- **预防**: 新增信号命名时检查后缀是否在 G-011 白名单中；信号始终定义为类属性

---

## 五、退出清理

### 5.1 LogHandler 在 atexit 阶段访问已析构 Qt 对象

- **现象**: `RuntimeError: wrapped C/C++ object of type QTextEdit has been deleted`
- **根因**: `logging.shutdown()` 在 Python atexit 时调用，此时 Qt C++ 对象已被销毁，`LogHandler.widget` 仍是悬空引用
- **修复**:
  - `LogHandler` 增加 `close()` 方法：置 `_closed=True`，`widget=None`，从 root logger 移除自己
  - `_run_main.py` 中 `app.aboutToQuit.connect(_close_log_handlers)` 在 Qt 销毁前主动清理
  - 所有 `emit`/`flush`/`_flush` 方法增加 `_closed` 守卫
- **预防**:
  - Qt + Python 混合应用中，所有持有 Qt 对象引用的 Python 对象必须在 `aboutToQuit` 时释放
  - 不依赖 `atexit` 清理 Qt 相关资源

---

## 六、CI 离线网络硬阻断（2026-08-20）

### 6.1 背景

- **现象**：测试可能真实访问外部标准站点（std.samr.gov.cn / www.csres.com / www.cssn.net.cn / openstd.samr.gov.cn / jjg.spc.org.cn），导致 CI 不稳定、测试不可复现，并对目标站点产生真实请求。
- **修复**：`ci.yml` test-backend job 中三层防护：
  1. **iptables 硬阻断（主防线）**：自定义链 `PILOTSTD_BLOCK`，放行回环 / ESTABLISHED,RELATED / DNS(udp:53)，其余 OUTPUT 一律 `-j REJECT`（默认 icmp-port-unreachable，nf_tables 兼容）
  2. **门禁脚本 fail-fast**：阻断后立即运行 `python scripts/check_ci_offline.py`，探测 5 个站点确认已不可连通，避免 3000+ 测试白跑
  3. **conftest socket guard（兜底）**：`tests/conftest.py` 的 `_ci_network_guard` fixture，CI 下 patch `socket.socket.connect`，非 localhost 连接直接抛 `ConnectionRefusedError`；即使 iptables 失效也绝不真实出网
- **预防**：
  - 阻断必须严格包住 pytest 一步，测试后立即恢复（`if: always()` 的 Restore step），否则后续 `pip install vulture` / artifact 上传等外网操作会被误伤
  - 阻断链最后一条规则必须是 `-j REJECT`/`-j DROP`；跳转到**空链**等于没阻断（空链 return 后继续走默认 ACCEPT）
  - **GitHub Actions 的 iptables 是 nf_tables 后端，REJECT target 不接受 `--reject-with tcp-reset`**（仅 legacy iptables 支持）：会报 `RULE_APPEND failed (Invalid argument)` 并以 exit 4 失败。必须使用不带参数的 `-j REJECT`（默认 icmp-port-unreachable）或 `-j DROP`（CI-FIX-20260820-001：run #733/#734 test-backend step 8，首次误判为 xtables 锁竞争，加 `-w` 后仍失败，最终经 stderr 定位为 tcp-reset 不兼容）
  - 本地验证注意：`CI=true` 下门禁脚本会真实探测站点，可连通时返回 1 属预期行为（说明阻断未生效），不是脚本 bug

---

## 七、测试盲区：mock 掩盖真实调用链（2026-09-21）

### 7.1 背景

- **现象**：收藏下载链连续 7 天 0 成功，62 条收藏各重试 7 次后 abandoned；容器日志 427 条
  `AttributeError: 'super' object has no attribute 'request'`。
- **根因**：`pilotstd/download/session.py` 用 `s.request = lambda ...: super(requests.Session, s).request(...)`
  注入默认超时。`super(requests.Session, s)` 是在 `type(s).__mro__` 中 `requests.Session` **之后**查找属性，
  而 `s` 就是 `requests.Session` 实例，其后只有 `object` → 任何请求都抛 `AttributeError`。
  该写法自 2026-06-18 起存在约 3 个月，所有下载（`manager/facade/_base.py` 唯一构造点）无一例外失败。
- **为什么 CI 全绿**：`tests/test_download.py` 覆盖了 `create_session()` 的 header/UA 断言，其余用例全部
  mock 掉适配器，**没有任何一条测试真实执行过 `session.get()`** —— 被 mock 替换掉的正是出错的那一层。

### 7.2 教训

- 断言 mock 的行为 ≠ 验证真实调用链；只要出错层被 mock 覆盖，测试永远是绿的。
- 委派（`super()` / 替换方法属性）必须至少有一条测试**真实执行到下一层**（例：mock 到
  `HTTPAdapter.send`，而不是把 adapter 整个替换掉）。
- 替换库对象的方法属性属于高危操作：优先用子类覆盖方法，让 `super()` 沿 MRO 正确定位。

### 7.3 预防

- 新增/修改网络会话、适配器、委派链 → 补一条"真实走到 transport 层"的测试。
- 发现"业务成功率恒为 0"时先看**真实运行日志**，不要用 mock 测试通过来推断生产可用。

---

## 八、QThread 运行中被析构 → Qt qFatal → 进程 abort（2026-09-26）

### 8.1 现象

- `test-gui-coverage` **连续三个 run** 报 `exit code 134`（Linux `SIGABRT`；Windows 同形态为
  `0xC0000409` fail-fast，WER 记录 faulting module = `Qt6Core.dll`）：
  `36248502182`（`5a78b193`）、`36250148643`（`59376e59`）、修复后 `36253266299`（`8cee0678`，已不再 abort）。
- **无 pytest 汇总**（进程在套件中途死亡），**崩前所有测试 PASSED**。
- **崩点漂移**：本地第 4 个（`test_cancel_button_enabled_during_query`）/ 第 15 个
  （`test_status_bar_shows_cancel_message`）测试；CI 固定在第 15 个 —— 典型"孤儿对象何时被 GC"决定崩点。
- CI 转储（`59376e59`）：12 个线程块，其中一个是**仍在跑的 QueryWorker**
  （`ui/workers/query.py:95 run → … → scorer.get_profile → core/config/manager.py:98 save`），
  `Current thread` = 主线程，栈为 `pytestqt qt_compat.exec → qtbot.wait → helpers/__init__.py:123 wait_for_worker_and_ui`。

### 8.2 根因

- **直接原因**：一个仍在运行的 `QThread` 丢掉了唯一 Python 引用后被 GC 析构 → Qt
  `qFatal("QThread: Destroyed while thread is still running")` → `abort()`。
- **两处缺陷叠加**：
  1. `pilotstd/ui/core/handlers/_query.py` 的 `on_query()` 直接覆盖 `self._query_worker`，
     **不停/不等旧线程**；而 `_archive.on_normalize()` 的补名分支会经 `_run_query_cb()` **再次发起查询**
     → 上一个 QueryWorker 失去引用且从未被 stop/wait。
  2. `pilotstd/ui/qt_lifecycle.py` 的判据用了 `isRunning()`：`QThread.start()` 之后存在
     "已启动但尚未进入 `run()`"的窗口（实测数十毫秒），此时 `isRunning()` 仍为 `False`
     → `stop_worker_gracefully()` 直接返回、`_keep_alive_until_finished()` 当场释放，等于**没保活**。
- **与 §8.8 同源**（`docs/technical-debt.md` 八、操作记录 8.8：`test-gui-unit` 因
  `QThread: Destroyed while thread is still running` 触发 qFatal 中止套件）——同一类问题第二次发生。

### 8.3 为什么长期逃过测试（教训链）

1. `tests/gui/helpers/__init__.py` 的 `wait_for_worker_and_ui(qtbot, window, "_scan_worker"|"_query_worker", …)`
   取的是**窗口属性**，而真实 MainWindow 上**没有**这些属性（worker 在各 UI handler 上：
   `window._core.scan._scan_worker` 等）→ `getattr` 恒取到 `None` → **静默跳过线程等待**（只记一条 debug）。
2. `tests/gui/helpers/predicates.py` 的 `worker_done()` **恒返回 True**（注释自称 "Universal fallback"）。
3. 结果：`test_manual_workflow.py` 的 15 处"等待"（全套件 53 处调用）**全部是空操作**——
   测试在 worker 还在跑的时候就往下走，孤儿线程从未被任何断言观察到。

### 8.4 后续发现（同主题的另一类假等待）

- 修好崩溃后 CI `36253266299` 跑完全部用例，**唯一失败**是
  `test_query.py::test_query_mock_changes_effect_status`：`assert has_status`（`test_query.py:64`）失败。
- 机制：该测试用 **固定 sleep** 等 worker（`qtbot.wait(300)` + `qtbot.wait(1000)`），而 QueryWorker
  实测耗时 **CI 1.0s / 本地 0.6–1.7s**（CI 日志 `[QueryWorker] elapsed=1.0s results=0`）→ **余量为负**。
- 同批扫描出 21 处"固定 sleep 等 worker"（HIGH 1 / MEDIUM 2 / LOW 18）；HIGH/MEDIUM 与 3 处前置
  扫描等待已改用 `wait_for_worker_and_ui` + 真实 predicate（如"第 4 列生效状态已有值"）。

### 8.5 教训

1. **Qt 对象生命周期必须显式管理**，不能靠 GC：停线程要"断信号 → 置停止标志 → `wait()` → 超时才保活"，
   且在**覆盖引用之前**先停旧对象。
2. **判据用 `isFinished()`，不用 `isRunning()`**——`QThread.start()` 后有"已启动未 run"窗口，
   用 `isRunning()` 会把仍在运行的线程判成已结束。
3. **测试基建空转会掩盖崩溃**：等待函数取错属性 + 恒真谓词 = 53 处等待形同虚设，
   让一个必然 abort 的缺陷长期"通过"。
4. **固定 sleep 等 worker 是另一类假等待**：余量为负时必然 flaky，且只在更慢的环境（CI）暴露。
5. **CI 环境（coverage 插桩 + 更慢机器）会放大竞态**：本地默认不跑 `tests/gui/`，
   同类问题只在 CI 复现；排查时应先在本地用 `--cov` 复刻 CI 的慢速环境。
6. **崩溃转储要读全**：`Fatal Python error: Aborted` 之后 faulthandler 会把**所有**线程打出来，
   "哪个线程是 Current、孤儿线程停在哪个调用栈"就是根因线索。

### 8.6 引用

- 修复提交：`a7225689`（`_query.py` 覆盖前先停旧线程 + `qt_lifecycle` 判据改 `isFinished()`）、
  `3e69b039`（测试基建：`wait_for_worker_and_ui` 真正解析并等待、`worker_done` 改哨兵）、
  `dcfe8f5c`（4 处固定 sleep 竞态改用真实等待）
- CI：abort 转储 run `59376e59`（job `108427000555`）、失败 traceback run `36253266299`（job `108435684660`）

---

## 防复发检查清单

- [ ] 新增测试依赖 → 检查 `docker/requirements-docker.txt` 和 `desktop/requirements-win.txt`
- [ ] 新增 `.gitignore` 规则 → 确认不会误伤需跟踪的目录
- [ ] 新增测试 → 检查是否需要 CI 跳过条件（网络/PyQt6/平台）
- [ ] 重构 Handler → 同步更新对应的回归测试和 E2E 测试
- [ ] 新增信号 → 检查 G-011 的 `QT_SIGNAL_SUFFIXES` 是否覆盖
- [ ] 新增函数 → 检查 G-010 行数限制
- [ ] 提交前 → 本地运行 `vulture` + `ruff` + `mypy`
- [ ] 新增会真实出网的测试 → 确认 CI 离线阻断覆盖（iptables + check_ci_offline.py + socket guard）
- [ ] 改网络会话/适配器/委派链 → 补一条不 mock 该层的测试（真实走到 `HTTPAdapter.send`）
- [ ] 新增/改动 QThread worker → 覆盖引用前先 `stop_worker_gracefully()`；判据用 `isFinished()` 不用 `isRunning()`
- [ ] 新增 GUI 等待 → 用 `wait_for_worker_and_ui` + 真实 predicate；**禁用固定 `qtbot.wait(N)` 等 worker**
- [ ] CI GUI 套件变红且**无汇总**（exit 134 / 0xC0000409）→ 先读 faulthandler 全线程转储，找"Current thread"与孤儿线程
