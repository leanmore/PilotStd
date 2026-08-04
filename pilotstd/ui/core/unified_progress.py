# 模块：pilotstd/ui/core/unified_progress.py
"""统一进度管道 — 所有 Handler 共用一套缓动 + 信号发射。

两个入口：
- push(cur, total)：接收原始计数，内部算百分比
- push_pct(pct)：接收已算好的百分比，钳制到 [0, 100]

辅助方法：
- reset()：立即归零
- finish()：立即跳到 100
"""

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class UnifiedProgressPipeline(QObject):
    """接收原始进度数据，经缓动后通过 progress_updated 信号输出 0-100 百分比。"""

    progress_updated = pyqtSignal(int)

    def __init__(self, parent: QObject | None = None, easing_factor: float = 0.3):
        super().__init__(parent)
        self._target = 0
        self._current = 0.0
        self._easing_factor = easing_factor
        self._last_emitted = -1  # 防抖：值未变时不重复 emit
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._step)

    # ── 公开入口 ─────────────────────────────────────────────

    def push(self, cur: int, total: int) -> None:
        """接收原始 (current, total) 计数，内部算百分比。

        total <= 0 时 target 为 0（防御除零）。
        cur > total 时钳制到 100（防御上游数据异常）。
        """
        if total <= 0:
            self._target = 0
        else:
            self._target = min(int(cur / total * 100), 100)
        self._start_if_needed()

    def push_pct(self, pct: int) -> None:
        """接收已算好的百分比，钳制到 [0, 100]（防御上游数据异常）。"""
        self._target = max(0, min(100, pct))
        self._start_if_needed()

    def reset(self) -> None:
        """立即重置进度为 0，停止缓动定时器。"""
        self._timer.stop()
        self._target = 0
        self._current = 0.0
        self._last_emitted = 0
        self.progress_updated.emit(0)

    def finish(self) -> None:
        """立即完成进度到 100，停止缓动定时器。"""
        self._timer.stop()
        self._target = 100
        self._current = 100.0
        self._last_emitted = 100
        self.progress_updated.emit(100)

    # ── 内部缓动 ─────────────────────────────────────────────

    def _start_if_needed(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def _step(self) -> None:
        """缓动单步：指数逼近目标值。收敛后停止定时器以节省 CPU。
        仅在新百分比与上次发射值不同时才 emit，防止高频信号阻塞 UI 线程。"""
        diff = self._target - self._current
        if abs(diff) < 0.5:
            self._current = float(self._target)
            self._timer.stop()
        else:
            self._current += diff * self._easing_factor
        new_pct = int(self._current)
        if new_pct != self._last_emitted:
            self._last_emitted = new_pct
            self.progress_updated.emit(new_pct)
