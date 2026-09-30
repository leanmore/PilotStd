#!/usr/bin/env python
"""最小复现器（纯 PyQt6，不含本项目任何代码）：QMutex/QMutexLocker × 线程反复创建 = 访问违例。

结论（R12-7 二分定位，2026-09-27）
-------------------------------
| 变体 | 锁 | 线程模式 | 结果 |
|---|---|---|---|
| A | `QMutex`+`QMutexLocker` | 4 个长寿命线程 × 20000 次 | 0/6 崩 |
| B | 同上 + `QApplication`/`QObject`/字典追加 | 长寿命线程 | 0/6 崩 |
| **C** | 同上 | **每轮新建 4 线程 × 200 轮** | **5/8 崩（62.5%）** |
| **D** | **`threading.Lock`** | 同 C | **0/8 崩** |

崩溃栈（WER 转储 + pefile 导出符号解析）：
`ExceptionCode=0xC0000005`，`ExceptionAddress=python312.dll+0x54484 → PyWeakref_NewRef+0x114`，
访问参数 `READ @ 0x8`（即 `PyWeakref_NewRef(NULL, ...)` 读空对象的 `ob_type` 字段）。

用法
----
    python scripts/probe_mutexlocker_race.py                # 变体 C（Qt 锁，可复现，退出码非 0 即复现）
    python scripts/probe_mutexlocker_race.py --lock python  # 变体 D（threading.Lock，应恒为 0）

诊断工具，不参与 pytest 收集（位于 `scripts/`）。
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

from PyQt6.QtCore import QMutex, QObject, QThreadPool, qVersion
from PyQt6.QtWidgets import QApplication


class Holder(QObject):
    """最小载体：一个 QObject + 一把被多线程争用的锁 + 一个字典。"""

    def __init__(self, use_qt_lock: bool) -> None:
        super().__init__()
        # 唯一变量：Qt 的 QMutex（走 sip）vs Python 原生锁
        self._lock: object = QMutex() if use_qt_lock else threading.Lock()
        self.data: dict[str, list[object]] = {}

    def add(self, key: str, value: object) -> None:
        if isinstance(self._lock, QMutex):
            from PyQt6.QtCore import QMutexLocker  # 局部导入：仅在 Qt 锁分支用

            with QMutexLocker(self._lock):
                self.data.setdefault(key, []).append(value)
            return
        with self._lock:  # type: ignore[attr-defined] - threading.Lock
            self.data.setdefault(key, []).append(value)

    def clear(self) -> None:
        if isinstance(self._lock, QMutex):
            from PyQt6.QtCore import QMutexLocker

            with QMutexLocker(self._lock):
                self.data.clear()
            return
        with self._lock:  # type: ignore[attr-defined] - threading.Lock
            self.data.clear()


def main() -> int:
    parser = argparse.ArgumentParser(description="QMutexLocker × 线程 churn 竞态最小复现器")
    parser.add_argument("--lock", choices=("qt", "python"), default="qt", help="qt=QMutexLocker（可复现）；python=threading.Lock（对照）")
    parser.add_argument("--rounds", type=int, default=200, help="轮数（每轮新建 --threads 个线程）")
    parser.add_argument("--threads", type=int, default=4, help="每轮线程数")
    parser.add_argument("--subs", type=int, default=100, help="每线程加锁+追加次数")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("probe_mutexlocker_race")
    holder = Holder(use_qt_lock=args.lock == "qt")

    started = time.monotonic()
    for _ in range(args.rounds):

        def worker(prefix: str) -> None:
            for _ in range(args.subs):
                holder.add("k", lambda d=None, p=prefix: None)

        workers = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(args.threads)]
        for t in workers:
            t.start()
        for t in workers:
            t.join()
        QThreadPool.globalInstance().waitForDone(2000)
        app.processEvents()
        holder.clear()

    print(
        f"OK lock={args.lock} rounds={args.rounds} threads={args.threads} subs={args.subs} "
        f"elapsed={time.monotonic() - started:.2f}s qt={qVersion()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
