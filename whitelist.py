# vulture 白名单 — 排除框架级误报
# mypy: ignore-errors
# 用法: python -m vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100
#       （与 ci.yml:196 / G-020 同口径：只报 100% 置信项）

# ── @patch/@patch.object 注入的 mock（装饰器自动注入，不在函数体内引用） ──
mock_rmdir  # unused variable (tests/test_docker_api.py:174)

# ── 覆写 `datetime.now` 的签名参数（必须保留：改名或删除都会破坏签名兼容） ──
# 起因（2026-10-03 工具调用收口）：修好 Vulture 的 PATH 调用后，G-020 首次真正执行并报出
# 这两处 `unused variable 'tz' (100% confidence)`。`tz` **不是**死代码：它是在测试中
# 覆写 `datetime.now(cls, tz=None)` 时必须存在的形参——调用方可能以关键字参数传入
# （`now(tz=...)`），改名会挂、删除则签名不匹配。作者已用 ruff 行内抑制 `ARG003`，
# 而 **vulture 不读该注释**，故此处按项目既有机制（本白名单文件）做**精确豁免**；
# 不使用 `--ignore-names tz`——那会全局放行同名变量，范围过宽。
tz  # unused variable (tests/test_notification_stage2b_enable_grey.py:171)
tz  # unused variable (tests/test_notification_stage2b_enable_grey.py:542)

# ── 2026-10-17 实测清理：以下对象不再需要本文件豁免 ──
# exc_type / exc_val / exc_tb：由 pyproject.toml 的 [tool.vulture] ignore_names 统一覆盖，
#   不再重复登记（现定义于 pilotstd/core/db/database.py:37 的 __exit__；原注释指向已删除的
#   pilotstd/core/db.py）。
# user：docker/api/settings.py 已无 user 形参（仅剩字符串常量与 docstring），豁免对象不存在。
# qapp：tests/gui/conftest.py:231/259 与 tests/stress_winui.py:55 均在函数体内实际使用，
#   vulture 已不报告。
# mock_start：tests/test_docker_scheduler.py:90/99 已在函数体内实际使用，vulture 已不报告。
