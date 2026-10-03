# vulture 白名单 — 排除框架级误报
# mypy: ignore-errors
# 用法: vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=80

# ── FastAPI 依赖注入参数（Depends 有副作用，不可删除） ──
user  # unused variable (docker/api/settings.py:79)
user  # unused variable (docker/api/settings.py:119)
user  # unused variable (docker/api/settings.py:125)

# ── Python 上下文管理器协议（__exit__ 必须接受三个异常参数） ──
exc_type  # unused variable (pilotstd/core/db.py:50)
exc_val  # unused variable (pilotstd/core/db.py:50)
exc_tb  # unused variable (pilotstd/core/db.py:50)

# ── pytest fixture 依赖（qapp 确保 QApplication 初始化） ──
qapp  # unused variable (tests/gui/conftest.py:36)
qapp  # unused variable (tests/gui/conftest.py:109)
qapp  # unused variable (tests/stress_winui.py:52)

# ── @patch/@patch.object 注入的 mock（装饰器自动注入，不在函数体内引用） ──
mock_rmdir  # unused variable (tests/test_docker_api.py:144)
mock_start  # unused variable (tests/test_docker_scheduler.py:81)

# ── 覆写 `datetime.now` 的签名参数（必须保留：改名或删除都会破坏签名兼容） ──
# 起因（2026-10-03 T-36 收口）：修好 Vulture 的 PATH 调用后，G-020 首次真正执行并报出
# 这两处 `unused variable 'tz' (100% confidence)`。`tz` **不是**死代码：它是在测试中
# 覆写 `datetime.now(cls, tz=None)` 时必须存在的形参——调用方可能以关键字参数传入
# （`now(tz=...)`），改名会挂、删除则签名不匹配。作者已用 ruff 行内抑制 `ARG003`，
# 而 **vulture 不读该注释**，故此处按项目既有机制（本白名单文件）做**精确豁免**；
# 不使用 `--ignore-names tz`——那会全局放行同名变量，范围过宽。
tz  # unused variable (tests/test_notification_stage2b_enable_grey.py:165)
tz  # unused variable (tests/test_notification_stage2b_enable_grey.py:523)
