# CI 修复经验总结

> 最后更新：2026-11-21
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
- **2026-11-10 复发（U37）**: `tests/test_remaining_batch3_logs.py` 在模块顶层 import `pilotstd.ui`（`DownloadFlowEngine` / `_export_ops`），`test-backend` 无 PyQt6 → collection error；同一文件又不在 G-029 认可的 `tests/gui/` 路径，含 UI 变更的旧 run 的 `repo-compliance` 也红。
  - **修复**: 纯逻辑 3 条留在 `tests/test_remaining_batch3_logs.py`；UI 2 条移到 `tests/gui/test_ui_logs.py`（顶部 `pytest.importorskip("PyQt6")`）。
  - **新守卫**: `scripts/check_backend_test_imports.py` 扫描 `tests/test_*.py` 的**模块级** import（排除 `tests/gui/` 与 `test-backend` 的 `--ignore` 集），发现 `pilotstd.ui`/`PyQt6` 直接 fail；CI 在 `Run backend tests` 前增加该守卫 + `pytest --collect-only`（同 `--ignore` 参数）。
  - **预防**: 新增 UI 测试必须放 `tests/gui/`；根目录测试只放纯逻辑，不得在模块级 import UI。

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
- **与 §8.8 同源**（`docs/technical-debt.md` 七、操作记录 7.8（2026-09-27 编号收敛前为「八、操作记录 8.8」）：`test-gui-unit` 因
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

## 2026-10-23 Node 安全基线

CI 的 NODE_VERSION 从浮动 22 固定到 22.23.4，修复 2026-10-21 Node.js 安全公告（Brotli RCE、DNS/TLS 等）；生产镜像无 Node 运行时。

## 门禁实际入口（2026-10-31）
- core.hooksPath = .husky；pre-commit hook 在 .husky/pre-commit，不是 .git/hooks。
- check_all.sh 是另一套入口（子集），与 husky 独立。
- 定位门禁失败：ash .husky/pre-commit > log 2>&1，不要用 git commit（包装层会截断）。
## 本地全量 ≠ CI 全量（2026-10-31）
- CI 用 `CI=true` 跳过国内站点 e2e（GitHub runner 访问国内站点被阻断）。
- 办公室做代码回归用 `CI=true pytest ...` 对齐 CI 集合；国内站点适配器验证单独跑 `test_e2e_adapters.py`。
- 不要把 CI 绿当作“国内站点已验”；也不要把本地站点 e2e 红当代码问题。
## 探测外部接口：必须用适配器真实请求方式（2026-10-31）
- 不要裸测 URL；先看适配器代码的 params/headers，再用同样方式请求。
- 裸测返回 1KB 空壳不代表接口坏了，可能只是缺参数（A-38 误报即此）。
- 空结果与解析失败要能区分，避免“查无此标准”掩盖结构变化。

> **2026-11-05 教训：CI 步骤插入误删相邻步骤的 `- name`**。给 `repo-compliance` 增 G-051 时，
> 用字符串替换插在 `- name: Upload coverage data` 之前，却把该行一起替换掉，留下孤立的 `uses:`，
> 工作流直接 0 job 失败（GitHub 只报 run failure，不展示 job）。
> 规则：改 workflow 必须本地 `yaml.safe_load` + 检查相邻 `- name` 完整；优先在目标步骤后插入并用
> `git diff` 复核上下文。

---

## 2026-11-11 模块文档映射门禁切阻断（P2-07）

- **变更**：`check_module_doc_mappings.py` 从 `--strict`（告警）切 `--strict-block`（阻断），与 `docs_sync_check.py` 同口径。
- **原因**：此前核心模块变更即使未同步架构文档也只告警，`docs-compliance` 可长期“PASS: 无变更文件”；P2-07 要求把“文档存在+映射齐全”变成真门禁。
- **验证**：`python scripts/check_module_doc_mappings.py --strict-block` PASS；`check_all --ci` 必须 0。
- **注意**：切阻断后，改 `pilotstd/core/`、`docker/api/`、`pilotstd/query/`、`pilotstd/ui/` 必须同批改对应文档，否则本地/CI 都会被拦。

## 2026-11-12 frontend-e2e 的 Playwright `--with-deps` 被 apt DNS 拖死

- **现象**：`frontend-e2e` 在 `pnpm exec playwright install --with-deps chromium` 失败；`Temporary failure resolving 'azure.archive.ubuntu.com'`，字体包下载失败，`Installation process exited with code: 100`。测试还没开始。
- **根因**：`--with-deps` 触发 apt 更新/安装字体；GitHub 托管 Runner 到 Ubuntu 镜像的 DNS 瞬时故障，apt 等待 3+ 分钟后失败。
- **修复**：`ubuntu-24.04` Runner 已带 Chromium 运行库，改为 `pnpm exec playwright install chromium`，跳过 apt；缺库问题会在浏览器 launch 时直接暴露，不再被 apt DNS 卡死。
- **注意**：若未来 Runner 基础镜像真的缺库，应显式安装固定包或使用 Playwright 官方镜像，不要恢复无重试的 `--with-deps`。

## Agent 工作教训（2026-11-07 从 AGENTS.md 迁入）

> 这些是“为什么会犯错”的案例，不放进自动加载的 AGENTS；需要时再查阅。

| # | 教训 |
|---|---|
| P-101 | 调查任务只读不改，`git status` 零差异 |
| P-102 | 每条结论附文件路径 + 行号 + 实测输出，不空泛 |
| P-103 | 用户列了“做/不做”清单时，严格跟，不越界 |
| P-104 | 门禁不绕过：`noqa` / `any` / `skipif` / `continue-on-error` 一律禁止 |
| P-105 | 提示词中的路径/行数/预期值都是假设，执行前先实测 |
| P-106 | 已执行迁移函数源码不可变（`inspect.getsource` 哈希）；只能移到新迁移文件 |
| P-107 | 预存问题告知但不越界修，单独排工单 |
| P-108 | 交付四要素：差异表 + 文件清单 + 验证结果 + 自审清单 |
| P-109 | 改全局状态前先 GET 快照，结束时恢复快照值（不是默认值） |

## 2026-11-14：前端覆盖率门禁 G-054 接入（三次踩坑）

- **`pnpm run <script> -- <args>` 的 `--` 会被原样传给 vitest**：CI 写成
  `pnpm run test -- --coverage` 时，实际执行的是 `npx vitest run "--" "--coverage"`，
  覆盖率根本没开 → `coverage-summary.json` 不存在 → G-054 以 exit 2 失败（表现为
  `test-frontend` 红）。正确写法是 **`pnpm run test --coverage`**（不带 `--`）。
  本地复刻 CI 命令时用 `pnpm.cmd run test --coverage` 验证过：生成 summary、366 passed。
- **改了 CI 工作流必须同批改 `docs/ci-lessons.md`**：`docs_sync_check.py --strict-block`
  的"CI/CD 工作流变更"规则会阻断；本地 `check_all --local` 不跑严格模式，所以
  "本地全绿、CI 红"。
- **改了 `pilotstd/ui/` 必须同批改 `docs/architecture/modules/ui.md`**：
  `check_module_doc_mappings.py --strict-block` 按模块映射阻断，同样不在本地 `--local` 口径里。
- **超时不要全局放宽**：v8 插桩会让个别 jsdom 用例变慢，正确做法是给**单个用例**
  标 `30_000`，其余保持默认 5s；否则所有卡住的测试都要等 60s 才失败，超时信号失效。
- **棘轮的"收紧"必须写进规则**：覆盖率上涨若没人同 PR 改基线，下一批删掉 fixture
  覆盖率掉回旧水位也不会触发——G-054 因此在"上涨"时直接打印建议基线值。
- **门禁的失败模式救了它自己**：`--` 坑让 `coverage-summary.json` 从未生成，G-054 的
  "报告缺失 exit 2" 当场把假绿变成红，而不是静默 PASS。**新增门禁时要先设计"产物缺失时
  怎么失败"**，别让缺输入等价于通过。
- **基线数字必须交代来源**：74.56 / 9.09 / 87.5 是本地 `npx vitest run --coverage` 生成的，
  CI 直到 `491b1175` 才按同口径校验过一次（run `43584408939`）。以后新增覆盖率类基线，
  在基线 `_meta` 里写 `generated_by` + `generated_at`，并在台账注明"CI 何时首次生效"。
- **同类传参风险已排查**：全仓 `.github/workflows/*.yml` 与 `scripts/*.sh` 中
  `pnpm run <script> -- <args>` 只剩注释一条（即本坑），无第二处；`web/package.json`
  的 scripts 也不含吞参数写法。**下次给 pnpm 传参一律不带 `--`**，并本地复刻验证。
- **G-052 第二阶段接入 CI 的代价（2026-11-14）**：`repo-compliance` 新增
  `audit_count_claims.py --strict`——**近 3 个月改动过的文档里，凡含"N 个 router 模块 /
  N 个唯一 API 路径 / N 张表 / N 个迁移模块"等计数声明，必须登记 `COUNT_CLAIMS`
  或在 `count_claims_exempt.json` 写明理由**，否则 CI 红。豁免过期（窗口内不再命中）
  会给 WARN 提示删除。教训：**给文档加"听起来像规模数字"的句子时，先想它会不会被这条
  审计扫到**；确实属于历史记录的，加豁免并写清"为什么这个数字不用跟代码变"。

- **验证命令**：`pnpm.cmd run test --coverage`；`python scripts/check_gui_coverage_ratchet.py`；
  `bash scripts/check_all.sh --fast --guards --local`。

## 2026-11-14：清理 `ci.yml` 的过期 grep 豁免（A-33）

- `Forbid production imports from test modules` 步骤里排除 `_get_mock_adapter` 的条件，是为
  已删除的懒加载 getter 设的；A-33 删掉 20 个 getter 后该豁免已无对象。
- **教训**：豁免条件要跟着被豁免对象一起走——对象删除后豁免仍在，会让规则"看起来更宽"，
  下一个读 CI 的人会误以为 grep 有额外合法用例。删代码时顺手 `git grep` 豁免里的符号。

---

## 九、统计/日志类修复必须用触发案例复跑（2026-11-18）

- **现象**：GB 50016-2014 日志显示 [CSRES] 找到 评分=100，API stats.found=0；据此误判为“csres 结果被丢弃”，改了合并逻辑仍未改变 stats。
- **根因**：csres 日志 if result: 即打印“找到”，把 error_message=未找到匹配结果 的 not-found 结果也标成找到；**stats 本身正确**。
- **教训**：
  - 统计/日志类问题不能只靠单测（单测验证的是代码分支，不验证“日志文案是否误导”）；
  - 修复后必须用**原始触发案例**复跑（同一标准号、同一入口），比对“日志三态 / API stats / 结果行”三者一致；
  - 先证伪“统计错”还是“日志错”，再改代码；两者修复方向相反。
- **落地**：csres_state_text() 按 is_found() 输出；	ests/test_csres_state.py 锁定；总表 G-01 记录“先前修复不是根因”。
- **PowerShell 写文件编码坑**：Windows PowerShell 的 Set-Content -Encoding utf8 会写 BOM，CI 解析器报 U+FEFF 并拒绝；请用 [System.IO.File]::WriteAllText() 或 PS7 的 -Encoding utf8NoBOM。此前 27 #56~59 的 UTF-8/GBK 乱码同源，均按编码问题处理。

### 1.1 用户可感知问题的“闭合”判据（2026-11-18 加）

- UI 定位/渲染/通知内容/行为结果：闭合必须**真实操作复现验证通过**（浏览器/真机点验），不能只凭“测试断言 + CI 绿”。
- 仅有测试断言时，状态写“已修复（待真实验证）”，不算闭合。
- 反例：铃铛弹层偏左，单测只断言 `alignOverlay()` 被调用 → CI 绿但问题仍在；真实 Playwright 点验发现弹层仍从 x=623 跳到 x=11.5。

---

## 2026-11-21：G-055 设计令牌门禁接入 `test-frontend`

- **背景**：设计令牌全量替换（979 条 A 类 → 令牌）完成后，若无门禁，新代码会立刻把
  硬编码写回去。新增棘轮门禁 G-055：A 类必须为 0，B/C 类不得超出基线次数。
- **接线位置**：`ci.yml` 的 `test-frontend` 在 `Lint (eslint)` 之后、PrimeVue 图标检查之前；
  本地同一脚本挂在 `check_all.sh --fast`（G-047 之后）。零新依赖，纯 Python，单次 ~0.35s。
- **踩到的门禁**：只要改 `.github/workflows/ci.yml`，`docs_sync_check` 的
  "CI/CD 工作流变更" 规则就要求**同批**更新本文件——本次未更新导致
  `check_all.sh --ci` 严格模式 FAIL。教训：**接线 CI 步骤时，ci-lessons 是必须同批的
  文档**，不是可选记录。
- **基线设计取舍**：
  - 基线只由人工提交，脚本只提供 `--suggest-baseline` 打印候选（无写文件分支），
    避免"改完代码顺手刷新基线"把门禁变成橡皮章；
  - 匹配键用 `文件 + 属性 + 值` 而非行号/选择器：行号会被注释与空行整体顶偏，
    选择器会在类名重构时误报；
  - 数量减少只打 `[STALE]` 不阻断：清理是好事，卡住清理会逼人调大基线。
- **反证**：除 9 例受控测试外，在真实仓库临时注入 `#123456`、`font-size: 15px`、
  内联 `height: 21px` 均 exit 1，逐次还原后 exit 0。**只跑单测不做真实反证**，
  无法证明门禁真的接在这棵树上（同 2026-10-17 的"门禁脚本存在但无人调用"教训）。

---

## 2026-11-21：PR 路径暴露的两处既有 CI 配置缺陷（G-029 范围 / deep-gate 缺 pytest）

> 背景：本仓以直推 `main` 为主，PR 路径长期无人走。首个真实 PR（#9）把两处潜伏缺陷同时暴露。

### 缺陷 A：G-029 在 `pull_request` 事件下必然误报"0 变更文件"

- **现象**：PR run `44893174320` 的 `repo-compliance` 红在 `G-029`，日志
  `G029_RANGE: ..2ceeef1… → [G-029] FAIL: 显式范围内 0 个变更文件`。
- **根因**：`ci.yml` 的 `G029_RANGE` 用 `${{ github.event.before }}..${{ github.sha }}`。
  `before` **是 push 载荷字段**，PR 事件下展开为空串 → 范围变 `..<sha>` → 0 文件；
  而 G-029 自 v2.06 起对"显式范围 0 文件"**拒绝静默通过**（见 gates.md v2.06 D-7），于是必然 FAIL。
- **修复**：按事件回落 —— push 保持 `before..sha`；PR 取 `pull_request.base.sha..pull_request.head.sha`：
  `G029_RANGE: ${{ github.event.before || github.event.pull_request.base.sha }}..${{ github.event.pull_request.head.sha || github.sha }}`
- **影响面**：仅 G-029 一个步骤的范围取值；push 行为不变。
- **同类字段盘点（未改，均已各自容错）**：`COMPLIANCE_RANGE`（PR 下曾实测通过）、
  `DOCS_SYNC_RANGE`（非法范围会回退 `origin/<base>...HEAD`）、
  `GOVERNANCE_DOCS_RANGE`（已写 `pull_request.base.sha || event.before`）、
  `EVENT_BEFORE`（run 脚本内 `git rev-parse` 校验后回退）。

### 缺陷 B：deep-gate 未安装 pytest，`--deep` 的自测自查必然失败

- **现象**：PR 的 `Deep Gate` run `44893174379`（该 workflow **首次运行**）红在
  `Run Deep Gate Gate (--deep)`：`python: No module named pytest`。
- **根因**：`deep-gate.yml` 只装 `docker/requirements-docker.txt` + `ruff vulture mypy`；
  而 `check_all.sh --deep` 会无条件执行 `run_gate_selftests`，其中调用
  `python -m pytest tests/test_check_i18n_hardcoded*.py -q`。
- **修复**：安装行补 `pytest`（已核对调用参数：无 `-n`/`--timeout`，故不需要 xdist/timeout 插件）。
- **影响面**：仅 PR 的 deep-gate job；不改任何判定逻辑与自测内容。

### 教训

1. **"只在 pull_request 触发"的配置必须真跑一次**：本仓 G-029 表达式与 deep-gate 依赖都是
   写下来就没人走过，直到首个 PR 才同时爆雷。新增 workflow 或改触发条件时，应主动用一个
   draft PR 冒烟。
2. **事件上下文字段要按事件分开写**：`github.event.before`（push）、
   `github.event.pull_request.base.sha`（PR）互不存在；用 `||` 回落比写两个分支步骤更省事。
3. **门禁脚本的"拒绝静默通过"设计是对的**：正是它把空范围从"假绿"变成"显式红"，
   才让这次缺陷被看见，而不是被当作通过。

### 2026-11-21：G-013 规则 0 的“纯文档提交”误判

- **现象**：提交信息里出现 `fix` 字样、改动全是文档时，规则 0 仍要求“必须带 tests/ 变更”，
  迫使为纯文档提交补无意义测试（或改措辞绕过）。
- **根因**：规则 0 只匹配消息关键词，不看改动路径组成。
- **处置**：新增 `is_docs_only()` 豁免——**必须同时满足**“消息命中 fix/bug 词 + 改动非空 + 全部在 `docs/` 或 `*.md`”；
  含任一代码/脚本/配置路径仍阻断；空改动列表不豁免。
- **教训**：门禁的“豁免”要按**路径集合**判定，不能只按消息关键词；且必须显式排除空列表。

## 2026-11-23 方向 C 批次 3-8：CI 严格模式的两个真实拦截点

本轮改了 `.github/workflows/ci.yml`（3 个无主 TODO 认领）与 `scripts/`（G-050 补
continue/break 识别、新增 G-056 死链扫描），CI 严格模式拦了两次，都是**真问题**：

### 1. `docs_sync_check.py --strict-block` 要求「测试文件数大幅变化」同步 `testing-baseline.md`

- **现象**：新增 10 个 Python 测试文件后，`repo-compliance` job 的 Docs sync 步骤 exit 1，
  报 `docs/testing/testing-baseline.md` 未与本次变更同批更新。
- **教训**：**加测试文件不是"只加代码"** —— CI 严格模式把「测试基线文档」视为
  测试规模事实的承载体，新增测试必须同批登记，否则文档会静默过时。
- **处置**：在 `testing-baseline.md` 追加增量段，列出全部新增测试文件与用例数。

### 2. `docs_sync_check.py --strict-block` 要求「CI/CD 工作流变更」同步 `ci-lessons.md`

- **现象**：改 `.github/workflows/ci.yml` 后，同一 job 报 `docs/ci-lessons.md` 未同步。
- **教训**：工作流变更必须留下"为什么改"的经验记录，否则下次有人踩同样的坑。
- **处置**：本条即记录（见下）。

### 3. 本地 `--guards --local` 覆盖不到这两条

`bash scripts/check_all.sh --fast --guards --local` **exit 0**，但 CI 仍红 ——
因为 `--local` 下 `docs_sync_check.py` 走的是**告警期**（exit 0），
只有 CI 的 `--strict-block` 才阻断。

> **推论**：本地门禁绿 ≠ CI 绿。涉及 `scripts/`、`.github/`、`docs/`、测试文件数的改动，
> 提交前应手动跑一次严格模式：
> ```bash
> BASE_BRANCH=main DOCS_SYNC_RANGE=<before>..<sha> \
>   python scripts/docs_sync_check.py --strict-block
> python scripts/check_module_doc_mappings.py --strict-block
> ```
