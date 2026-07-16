# CI 修复经验总结

> 最后更新：2026-07-16
> 基于 2026-07-16 CI 综合修复（12 轮迭代）提炼

---

## 总览

| 问题类别 | 问题数 | 典型症状 | 核心教训 |
|----------|--------|---------|---------|
| 依赖管理 | 2 | `ModuleNotFoundError` | 测试依赖必须在 CI 使用的 requirements 文件中显式声明 |
| 跨平台测试 | 4 | Linux CI 运行 Windows 测试 / 外部站点超时 | CI 环境与本地环境差异必须通过 skip/xfail 明确处理 |
| 测试设计 | 3 | 断言字段名过时 / 代码重构后测试未同步 | 测试写源码字符串的断言极易腐烂 |
| 静态检查 | 3 | vulture/G-010/G-011 阻断 CI | 静态检查工具需持续维护白名单和规则 |
| 退出清理 | 1 | `RuntimeError: wrapped C/C++ object has been deleted` | Qt 对象生命周期 vs Python atexit 顺序需显式管理 |
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

## 防复发检查清单

- [ ] 新增测试依赖 → 检查 `docker/requirements-docker.txt` 和 `desktop/requirements-win.txt`
- [ ] 新增 `.gitignore` 规则 → 确认不会误伤需跟踪的目录
- [ ] 新增测试 → 检查是否需要 CI 跳过条件（网络/PyQt6/平台）
- [ ] 重构 Handler → 同步更新对应的回归测试和 E2E 测试
- [ ] 新增信号 → 检查 G-011 的 `QT_SIGNAL_SUFFIXES` 是否覆盖
- [ ] 新增函数 → 检查 G-010 行数限制
- [ ] 提交前 → 本地运行 `vulture` + `ruff` + `mypy`
