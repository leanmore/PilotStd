"""tests/test_system_update_nonblocking.py — update 端点不得阻塞事件循环（NEW-03，2026-11-23）。

背景：`async def update_container()` 里直接调用 `_get_current_digest` / `_pull_and_compare` /
`_restart_via_compose`，这些内部都是同步 `subprocess.run(timeout=300)`。
在 async 端点里同步跑 5 分钟的 subprocess 会**完全阻塞事件循环** ——
期间所有其它请求（健康检查、其它用户读操作）全部挂起。

修法：三处调用包进 `fastapi.concurrency.run_in_threadpool`。

本测试锁住：源码里这三处必须是 `await run_in_threadpool(...)`，不得退回直接调用。
（用源码断言而非运行时断言 —— 运行时测"是否阻塞"需要并发计时，脆弱且慢；
 源码形态是更强的约束：任何人改回直接调用都会红。）
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docker" / "api" / "system.py"


def _source() -> str:
    return SRC.read_text(encoding="utf-8")


def test_imports_run_in_threadpool():
    """必须 import run_in_threadpool。"""
    assert "from fastapi.concurrency import run_in_threadpool" in _source()


def test_digest_calls_go_through_threadpool():
    """_get_current_digest 与 _pull_and_compare 必须走线程池。"""
    src = _source()
    assert "await run_in_threadpool(_get_current_digest" in src, (
        "_get_current_digest 必须包进 run_in_threadpool（否则阻塞事件循环）"
    )
    assert "await run_in_threadpool(_pull_and_compare" in src, (
        "_pull_and_compare 必须包进 run_in_threadpool"
    )


def test_restart_goes_through_threadpool():
    """_restart_via_compose 必须走线程池。"""
    assert "await run_in_threadpool(_restart_via_compose" in _source()


def test_no_bare_blocking_calls_remain():
    """不得存在「直接调用这三个阻塞函数」的残留（去掉 await run_in_threadpool 包装后）。"""
    src = _source()
    # 把已正确包装的调用抹掉，再找裸调用
    stripped = re.sub(r"await run_in_threadpool\(\s*_\w+[^)]*\)", "", src)
    for fn in ("_get_current_digest", "_pull_and_compare", "_restart_via_compose"):
        # 允许出现在 def 定义行与注释里，只禁止「裸调用」
        bare = re.search(rf"(?<!def )\b{fn}\s*\(", stripped)
        assert bare is None, f"{fn} 仍有未包装的裸调用（会阻塞事件循环）"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
