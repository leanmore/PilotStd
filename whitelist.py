# vulture 白名单 — 排除框架级误报
# mypy: ignore-errors
# 用法: vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=80

# ── FastAPI 依赖注入参数（Depends 有副作用，不可删除） ──
user  # unused variable (docker/api/api_keys.py:15)
user  # unused variable (docker/api/api_keys.py:24)
key_id  # unused variable (docker/api/api_keys.py:33)
user  # unused variable (docker/api/api_keys.py:33)
key_id  # unused variable (docker/api/api_keys.py:42)
user  # unused variable (docker/api/api_keys.py:42)
key_id  # unused variable (docker/api/api_keys.py:52)
user  # unused variable (docker/api/api_keys.py:52)
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
