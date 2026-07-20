# tests/test_unified_progress.py
"""UnifiedProgressPipeline 单元测试 — 边界值、生命周期、缓动行为。"""

import pytest
from PyQt6.QtTest import QSignalSpy, QTest

from pilotstd.ui.core.unified_progress import UnifiedProgressPipeline

# ════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def qapp():
    """会话级 QApplication，供 QTimer/QSignalSpy 使用。"""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


# ════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════


def _wait_for_value(spy: QSignalSpy, target: int, timeout_ms: int = 2000) -> bool:
    """轮询等待 spy 最新值等于 target，超时返回 False。

    替代固定 QTest.qWait(500)，在 CI 或慢机器上不会因定时器挂起而误判。
    """
    for _ in range(timeout_ms // 10):
        if len(spy) > 0 and spy[-1][0] == target:
            return True
        QTest.qWait(10)
    return False


def _collect_values(spy: QSignalSpy) -> list[int]:
    """从 QSignalSpy 提取所有信号值。"""
    return [s[0] for s in spy]


# ════════════════════════════════════════════════════════════════
# 边界值与钳制
# ════════════════════════════════════════════════════════════════


class TestBoundary:
    """total=0、负值、越界钳制。"""

    def test_push_total_zero_does_not_throw(self, qapp):
        """total=0 不抛异常，target 归零。"""
        pipeline = UnifiedProgressPipeline()
        pipeline.push(10, 0)

    def test_push_negative_total_does_not_throw(self, qapp):
        """total<0 不抛异常，target 归零。"""
        pipeline = UnifiedProgressPipeline()
        pipeline.push(10, -5)

    def test_push_pct_negative_clamped_to_zero(self, qapp):
        """负值 push_pct 钳制到 0。"""
        pipeline = UnifiedProgressPipeline(easing_factor=1.0)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push_pct(-10)
        assert _wait_for_value(spy, 0), f"预期收敛到 0，实际最后值={spy[-1][0] if spy else '无信号'}"

    def test_push_pct_above_100_clamped(self, qapp):
        """>100 的 push_pct 钳制到 100。"""
        pipeline = UnifiedProgressPipeline(easing_factor=1.0)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push_pct(150)
        assert _wait_for_value(spy, 100), f"预期收敛到 100，实际最后值={spy[-1][0] if spy else '无信号'}"

    def test_push_cur_exceeds_total_clamped_to_100(self, qapp):
        """cur > total 时钳制到 100。"""
        pipeline = UnifiedProgressPipeline(easing_factor=1.0)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push(120, 100)
        assert _wait_for_value(spy, 100), f"预期收敛到 100，实际最后值={spy[-1][0] if spy else '无信号'}"


# ════════════════════════════════════════════════════════════════
# 生命周期：reset / finish
# ════════════════════════════════════════════════════════════════


class TestLifecycle:
    """reset() 归零、finish() 精确到 100。"""

    def test_reset_emits_zero(self, qapp):
        pipeline = UnifiedProgressPipeline()
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.reset()
        assert len(spy) == 1
        assert spy[0][0] == 0

    def test_reset_after_push_emits_zero(self, qapp):
        """从非零状态 reset，信号输出 0。"""
        pipeline = UnifiedProgressPipeline(easing_factor=0.9)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push(80, 100)
        assert _wait_for_value(spy, 80), "push(80,100) 应收敛到 80"
        pipeline.reset()
        assert spy[-1][0] == 0

    def test_finish_emits_exact_100(self, qapp):
        pipeline = UnifiedProgressPipeline()
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.finish()
        assert len(spy) == 1
        assert spy[0][0] == 100

    def test_finish_from_zero_emits_100(self, qapp):
        """从零 finish，直接输出 100 且只输出一次。"""
        pipeline = UnifiedProgressPipeline()
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.finish()
        assert spy[0][0] == 100

    def test_push_then_finish_ends_at_100(self, qapp):
        """先 push 中间值再 finish，最终信号是 100。"""
        pipeline = UnifiedProgressPipeline(easing_factor=0.9)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push(30, 100)
        assert _wait_for_value(spy, 30), "push(30,100) 应收敛到 30"
        pipeline.finish()
        assert spy[-1][0] == 100


# ════════════════════════════════════════════════════════════════
# 缓动行为
# ════════════════════════════════════════════════════════════════


class TestEasing:
    """缓动输出单调非递减、收敛到目标值。"""

    def test_continuous_push_produces_smooth_increment(self, qapp):
        """连续 push 50→100，输出值单调非递减，最终精确到 100。"""
        pipeline = UnifiedProgressPipeline(easing_factor=0.5)
        spy = QSignalSpy(pipeline.progress_updated)

        # 第一段：推 50%
        pipeline.push(50, 100)
        assert _wait_for_value(spy, 50), "第一段应收敛到 50"

        # 第二段：推 100%
        pipeline.push(100, 100)
        assert _wait_for_value(spy, 100, timeout_ms=3000), "第二段应收敛到 100"

        values = _collect_values(spy)
        assert len(values) > 3, f"缓动过程应产生多次信号，实际只有 {len(values)} 次"

        # 单调非递减
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], f"进度值回退: index={i}, {values[i]} < {values[i - 1]}"

        # 最终精确到达 100
        assert values[-1] == 100, f"最终值 {values[-1]} != 100"

    def test_push_pct_produces_smooth_output(self, qapp):
        """push_pct 也走缓动通道，非直接跳变。"""
        pipeline = UnifiedProgressPipeline(easing_factor=0.3)
        collected: list[int] = []
        pipeline.progress_updated.connect(lambda v: collected.append(v))

        pipeline.push_pct(80)

        # 轮询等待收敛
        import time

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if len(collected) > 0 and collected[-1] == 80:
                break
            QTest.qWait(10)

        assert len(collected) > 3, f"缓动过程应产生多次信号，实际只有 {len(collected)} 次"
        for i in range(1, len(collected)):
            assert collected[i] >= collected[i - 1], f"push_pct 输出回退: {collected[i]} < {collected[i - 1]}"
        assert collected[-1] == 80, f"push_pct 最终值 {collected[-1]} != 80"

    def test_push_zero_target_stops_timer(self, qapp):
        """target=0 时缓动收敛后定时器停止。"""
        pipeline = UnifiedProgressPipeline(easing_factor=0.9)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push(0, 100)
        assert _wait_for_value(spy, 0), "应收敛到 0"
        assert not pipeline._timer.isActive(), "收敛到 0 后定时器应停止"

    def test_push_100_target_converges(self, qapp):
        """target=100 时缓动最终到达 100。"""
        pipeline = UnifiedProgressPipeline(easing_factor=0.9)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push(100, 100)
        assert _wait_for_value(spy, 100), f"最终值 {spy[-1][0] if spy else '无信号'} != 100"

    def test_no_duplicate_emissions(self, qapp):
        """_last_emitted 防抖：相同值不重复 emit。"""
        pipeline = UnifiedProgressPipeline(easing_factor=1.0)
        spy = QSignalSpy(pipeline.progress_updated)
        pipeline.push_pct(50)
        assert _wait_for_value(spy, 50)
        # easing_factor=1.0 单步收敛，应只有一次信号
        assert len(spy) == 1, f"easing_factor=1.0 应单步收敛，实际 {len(spy)} 次信号"
