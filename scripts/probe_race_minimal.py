#!/usr/bin/env python
"""最小化复现器：#34 EventBus「并发订阅 + reset()」访问违例（脱离 pytest）。

背景
----
`tests/gui/test_event_bus_integration.py::TestThreadSafety::test_concurrent_subscribe`
（4 线程 × 100 次 `subscribe`）之后，autouse fixture `_reset_event_bus` 的 teardown 调用
`EventBus.reset()`，在 `pilotstd/ui/core/event_bus.py:86`（`with QMutexLocker(cls._lock):`）
触发 `Windows fatal exception: access violation`（退出码 0xC0000005）。

本脚本把该场景**脱离 pytest** 复刻（无 fixture、无 pytest 插件、无报告机制），
目的是：① 排除 pytest teardown 机制干扰；② 把单轮耗时从 ≈100s 压到 < 5s，
以便开启 Windows PageHeap（gflags.exe）做精准定位。

用法（R12-6 建立的 CI 同口径环境：Python 3.12.10 + PyQt6 6.11.0 + PyQt6-Qt6 6.11.2）
----
    C:\\Temp\\pilotstd-probe\\venv312\\Scripts\\python.exe scripts/probe_race_minimal.py
    # 自定义规模：
    ... scripts/probe_race_minimal.py --rounds 200 --threads 4 --subs 100

退出码
------
    0   本轮全部通过
    非 0（如 3221225477 = 0xC0000005）  复现成功（进程被访问违例终止）

注意：本脚本是**诊断工具**，不参与 pytest 收集（位于 `scripts/`，非 `tests/`）。
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

# scripts/ 直接运行时要能 import pilotstd（sys.path[0] 是 scripts/，不含仓库根）
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from PyQt6.QtCore import QCoreApplication, QThreadPool, qVersion  # noqa: E402 - 需先修正 sys.path
from PyQt6.QtWidgets import QApplication  # noqa: E402 - 同上

from pilotstd.ui.core.event_bus import EventBus  # noqa: E402 - 同上


def quiet_non_main_threads(timeout: float = 2.0) -> bool:
    """等待非主线程退出并等 Qt 全局线程池收敛（等价于测试里的 `_wait_for_threads`）。"""
    deadline = time.monotonic() + timeout
    while any(t.is_alive() for t in threading.enumerate() if t is not threading.main_thread()):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.005)
    QThreadPool.globalInstance().waitForDone(2000)
    return not any(t.is_alive() for t in threading.enumerate() if t is not threading.main_thread())


def one_round(threads: int, subs: int) -> None:
    """复刻 test_concurrent_subscribe + fixture teardown 的最小等价流程。"""
    bus = EventBus.instance()

    def subscriber(prefix: str) -> None:
        for _ in range(subs):
            bus.subscribe("concurrent.event", lambda d, p=prefix: None)

    workers = [threading.Thread(target=subscriber, args=(f"t{i}",)) for i in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()

    # fixture teardown 等价动作：等静止 → 排空事件队列 → reset（历史崩溃点）
    if quiet_non_main_threads():
        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()
    EventBus.reset()


def main() -> int:
    parser = argparse.ArgumentParser(description="EventBus 并发订阅 + reset() 最小化复现器（#34）")
    parser.add_argument("--rounds", type=int, default=200, help="进程内重复轮数（默认 200）")
    parser.add_argument("--threads", type=int, default=4, help="每轮并发订阅线程数（默认 4，同测试）")
    parser.add_argument("--subs", type=int, default=100, help="每线程订阅次数（默认 100，同测试）")
    args = parser.parse_args()

    # 必须持有 QApplication 引用：无 Python 引用时 Qt 对象会被回收，后续 Qt 调用即崩
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("probe_race_minimal")
    EventBus.reset()
    started = time.monotonic()
    for _ in range(args.rounds):
        one_round(args.threads, args.subs)
    elapsed = time.monotonic() - started
    print(
        f"OK rounds={args.rounds} threads={args.threads} subs={args.subs} elapsed={elapsed:.2f}s "
        f"python={sys.version.split()[0]} qt={qVersion()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
