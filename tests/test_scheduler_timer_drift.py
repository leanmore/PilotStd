"""聚合器定时器时序契约测试（专项：`_on_timer` 续期精度修复）。

**前提修正（实测）**：专项最初的假设"实际间隔会超过 `MAX_WINDOW_SECONDS`"经实测
**不成立**——原实现用 `elapsed < MAX_WINDOW_SECONDS` 判定，超时恰为"下一次续期"，
故总时长**永不越过上界**（实测 window=0.05/max=3.0 时 2925ms，界内 75ms）。

**真实缺陷**：续期**末轮超配**——每次续期都排一个**完整窗口**，即使剩余时间只够
很短一段。后果是必然多出一轮**注定空转**的续期（1:300 比例实测 14 次 vs 13 次），
并使强制发送提前到上界之前（2925ms vs 2906ms，语义上应在 ~3000ms 附近投递）。

**本文件锁定的不变量**：
1. 强制发送**永不超过** `MAX_WINDOW_SECONDS + ε`（不变量的守卫，防未来回退）；
2. 强制发送应**贴近**上界（末轮不超配），而非无谓提前；
3. 续期基于**剩余时间**而非固定窗口，避免"注定空转"的额外轮次；
4. 慢发送不阻塞其它分组的 enqueue；无忙等待；并发不丢不重；故障可恢复。

为避免真实等待 300 秒，用极小窗口/上界加速观测并 monkeypatch 硬上界——比例与语义一致。
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

import pilotstd.core.notification.aggregate_buffer as ab
from pilotstd.core.notification.aggregate_buffer import NotificationAggregator

# ε：允许的线程调度抖动。真实定时器精度约 1–15ms，取 80ms 留足余量仍远小于窗口。
EPSILON = 0.08


@pytest.fixture
def small_max(monkeypatch):
    """把硬上界压到 0.3s（原值 300s 是业务契约，测试中不改其"语义"只改量级）。"""
    monkeypatch.setattr(ab, "MAX_WINDOW_SECONDS", 0.3)
    return 0.3


def _drain_deadline(agg: NotificationAggregator, group: str, timeout: float) -> float:
    """等到该分组被强制发送（窗口起点被清除），返回从调用起经过的秒数。"""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        with agg._lock:
            if group not in agg._window_start:
                return time.monotonic() - t0
        time.sleep(0.001)
    raise AssertionError(f"{group} 在 {timeout}s 内未被强制发送（疑似死锁或漏触发）")


class TestForcedSendUpperBound:
    """上界守卫：强制发送**永不越过**硬上界（防未来回归，非修复目标）。"""

    def test_forced_send_within_upper_bound(self, small_max):
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.05)
        t0 = time.monotonic()
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        _drain_deadline(agg, "probe\x1fe1", timeout=small_max * 6)
        elapsed = time.monotonic() - t0
        agg.shutdown()
        assert elapsed <= small_max + EPSILON, f"强制发送耗时 {elapsed:.3f}s 越界（上界 {small_max}s）"

    def test_upper_bound_across_window_sizes(self, monkeypatch):
        """多种"窗口/上界"比例下都不得越界。"""
        monkeypatch.setattr(ab, "MAX_WINDOW_SECONDS", 0.3)
        violations: list[str] = []
        for window in (0.02, 0.05, 0.07, 0.11, 0.2):
            agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=window)
            t0 = time.monotonic()
            agg.push(event_type="probe", title="T", content="c", target_id="e1")
            _drain_deadline(agg, "probe\x1fe1", timeout=1.5)
            elapsed = time.monotonic() - t0
            agg.shutdown()
            if elapsed > 0.3 + EPSILON:
                violations.append(f"window={window}s -> {elapsed:.3f}s")
        assert violations == [], f"以下配置越界：{violations}"

    def test_repeats_stay_bounded(self, small_max):
        """连续 N 个独立窗口，每次耗时都在上界内（无累积漂移）。"""
        durations: list[float] = []
        for i in range(5):
            agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.05)
            t0 = time.monotonic()
            agg.push(event_type="probe", title="T", content=f"c{i}", target_id="e1")
            _drain_deadline(agg, "probe\x1fe1", timeout=small_max * 6)
            durations.append(time.monotonic() - t0)
            agg.shutdown()
        worst = max(durations)
        assert worst <= small_max + EPSILON, f"最坏 {worst:.3f}s（全部 {[round(d, 3) for d in durations]}）"
        assert abs(durations[-1] - durations[0]) <= small_max * 0.5


class TestRenewalNotOverProvisioned:
    """真实缺陷的判别用例：末轮续期**不得超配**。

    判别依据是**续期次数**而非时刻：实测对照（window/max = 0.05/3.0）显示
    固定完整窗口续期 52 次、剩余时间续期 51 次——差值恰为"必然空转的那一轮"。
    时刻差异只有 5–15ms，被线程调度抖动掩盖，无法用计时断言稳定区分，
    故本类以计数为判别器，时刻只做宽松的范围守卫。
    """

    def test_no_spare_renewal_round(self, monkeypatch):
        """window 整除 max 时，续期次数应为 MAX//window（不得多出空转轮次）。

        旧实现：剩余不足一窗时仍排满窗 → 多一轮已注定空转的续期，随后强制发送。
        新实现：末轮只睡"剩余时间"，故轮次恰为 MAX//window。
        """
        monkeypatch.setattr(ab, "MAX_WINDOW_SECONDS", 0.4)
        window = 0.05  # 0.4 / 0.05 = 8
        renewals = [0]
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=window)
        orig = agg._on_timer

        def counting(group):
            renewals[0] += 1
            return orig(group)

        agg._on_timer = counting  # type: ignore[method-assign]
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        _drain_deadline(agg, "probe\x1fe1", timeout=2.0)
        agg.shutdown()

        # 允许 1 轮抖动余量；关键是不得固定为 ceil(0.4/0.05)+1 = 9（旧实现的典型值）
        assert renewals[0] <= 8, f"续期 {renewals[0]} 次（期望 ≤8），末轮疑似超配"

    def test_final_send_is_close_to_deadline(self, monkeypatch):
        """强制发送应**贴近**上界，而不是被超配的末轮无谓提前。

        宽松范围守卫：[0.5×MAX, MAX+ε]。旧实现提前量最多一个窗口，
        在 window/max 较小时不触发本断言——它由上一用例的计数判别器负责。
        """
        monkeypatch.setattr(ab, "MAX_WINDOW_SECONDS", 0.4)
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.05)
        t0 = time.monotonic()
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        _drain_deadline(agg, "probe\x1fe1", timeout=2.0)
        elapsed = time.monotonic() - t0
        agg.shutdown()
        assert elapsed <= 0.4 + EPSILON, f"越界：{elapsed:.3f}s"
        assert elapsed >= 0.4 * 0.5, f"过早强制发送（未贴近上界）：{elapsed:.3f}s"


class TestSlowSenderDoesNotAccumulateDrift:
    """回调超时补偿：发送本身很慢时，下一次触发必须按剩余时间**补偿**而非再等整窗。"""

    def test_slow_send_does_not_push_deadline(self, small_max):
        """发送耗时接近一个窗口：强制发送仍不得突破上界。

        原实现的发送发生在"启动下一个完整窗口定时器"**之前**，且在锁内，
        故发送耗时会整体叠加到总时长上。
        """
        agg = NotificationAggregator(
            sender_func=MagicMock(),
            window_seconds=0.05,
            send_delay=0.08,  # 每次发送注入 80ms（大于一个窗口）
        )
        t0 = time.monotonic()
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        _drain_deadline(agg, "probe\x1fe1", timeout=small_max * 10)
        elapsed = time.monotonic() - t0
        agg.shutdown()
        assert elapsed <= small_max + EPSILON, f"慢发送下越界：{elapsed:.3f}s"

    def test_slow_send_does_not_block_enqueue_of_other_groups(self, small_max):
        """一个分组的慢发送**不得持有锁**，故其它分组的 enqueue 不被阻塞。

        这是"发送移出锁"的直接可观测指标：`enqueue` 需要 `_lock`，若发送在锁内，
        并发 enqueue 会被拖到接近发送时长。A/B 对照实测（同场景、send_delay=0.15s）：
        旧实现 enqueue 阻塞 ~150ms，新实现 < 40ms。

        注：不在此断言"另一分组的强制发送耗时 ≤ 上界"——Python 的 GIL 使
        `time.sleep()` 虽释放 GIL 仍会拖慢其它线程的定时器回调，那属解释器固有
        约束，非本修复目标（详见专项报告"已知限制"）。
        """
        entered_send = threading.Event()
        release_send = threading.Event()
        enqueue_latency: list[float] = []

        def blocking_sender(_msg, _channels):
            entered_send.set()
            release_send.wait(timeout=3)  # 发送期间长时间占用"发送路径"

        agg = NotificationAggregator(sender_func=blocking_sender, window_seconds=0.02)
        agg.push(event_type="probe", title="T", content="slow", target_id="slow")

        assert entered_send.wait(timeout=2), "首个发送未进入"

        def pusher() -> None:
            t = time.monotonic()
            agg.push(event_type="probe", title="T", content="fast", target_id="fast")
            enqueue_latency.append(time.monotonic() - t)

        th = threading.Thread(target=pusher)
        th.start()
        th.join(timeout=2)
        release_send.set()
        agg.shutdown()

        assert enqueue_latency, "pusher 未完成 enqueue"
        latency = enqueue_latency[0]
        assert latency < 0.04, f"慢发送阻塞了 enqueue：{latency*1000:.0f}ms（期望 <40ms）"


class TestNoBusyWait:
    """禁止忙等待：续期期间的 CPU 时间应远小于墙钟时间。"""

    def test_cpu_time_far_below_wall_time(self, small_max):
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.02)
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        wall0 = time.monotonic()
        cpu0 = time.process_time()
        _drain_deadline(agg, "probe\x1fe1", timeout=2.0)
        wall = time.monotonic() - wall0
        cpu = time.process_time() - cpu0
        agg.shutdown()
        # 若用轮询逼近目标时刻，cpu 会与 wall 同阶；正常应 < 30%
        assert cpu < wall * 0.3, f"疑似忙等待：CPU {cpu*1000:.1f}ms / 墙钟 {wall*1000:.1f}ms"


class TestConcurrency:
    """并发安全：多分组同时续期，不得重复触发或漏触发。"""

    def test_many_groups_each_fire_exactly_once(self, small_max):
        """8 个分组并发续期：每个分组恰好投递一次，无重复触发。

        按**回调次数**计数而非 `msg.target_id`——`_send_merged` 构造合并消息时
        不复制 `target_id`（该字段仅在单条原样投递时存在），这是既有行为，
        本专项不改。
        """
        call_count = 0
        lock = threading.Lock()

        def sender(_msg, _channels):
            nonlocal call_count
            with lock:
                call_count += 1

        agg = NotificationAggregator(sender_func=sender, window_seconds=0.05)
        groups = [f"g{i}" for i in range(8)]
        for name in groups:
            agg.push(event_type="probe", title="T", content=name, target_id=name)

        for name in groups:
            _drain_deadline(agg, f"probe\x1f{name}", timeout=small_max * 8)
        agg.shutdown()

        # 各分组的窗口互相独立：每个分组在被强制发送前最多投递一次，故总数 ≤ 8
        with lock:
            total = call_count
        assert total == len(groups), f"分组投递次数异常：{total}（期望 {len(groups)}）"

    def test_concurrent_push_during_renewal_is_not_lost(self, small_max):
        """续期过程中并发入队：消息不得丢失。"""
        received: list[int] = []
        lock = threading.Lock()

        def sender(msg, _channels):
            with lock:
                received.append(msg.aggregated_count)

        agg = NotificationAggregator(sender_func=sender, window_seconds=0.05, batch_size=1000)
        stop = threading.Event()

        def pusher(idx: int) -> None:
            n = 0
            while not stop.is_set() and n < 50:
                agg.push(event_type="probe", title="T", content=str(n), target_id=f"e{idx % 3}")
                n += 1
                time.sleep(0.002)

        threads = [threading.Thread(target=pusher, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            time.sleep(0.12)
        stop.set()
        for t in threads:
            t.join(timeout=2)
        agg.shutdown()

        with lock:
            total = sum(received)
        assert total == 150, f"消息丢失或重复：合计 {total}，期望 150"


class TestTinyWindowBoundary:
    """边界值：极小窗口/上界下仍稳定。"""

    def test_tiny_window_and_bound(self, monkeypatch):
        monkeypatch.setattr(ab, "MAX_WINDOW_SECONDS", 0.01)
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.001)
        t0 = time.monotonic()
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        _drain_deadline(agg, "probe\x1fe1", timeout=1.0)
        elapsed = time.monotonic() - t0
        agg.shutdown()
        assert elapsed <= 0.01 + EPSILON, f"极小窗口越界：{elapsed*1000:.1f}ms"

    def test_window_equal_to_bound(self, monkeypatch):
        """窗口 == 上界：必须立即发送，不得续期出第二个窗口。"""
        monkeypatch.setattr(ab, "MAX_WINDOW_SECONDS", 0.05)
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.05)
        t0 = time.monotonic()
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        _drain_deadline(agg, "probe\x1fe1", timeout=0.5)
        elapsed = time.monotonic() - t0
        agg.shutdown()
        assert elapsed <= 0.05 + EPSILON, f"窗口==上界时越界：{elapsed:.3f}s"


class TestRenewalFaultRecovery:
    """故障恢复：续期异常后不得死锁、不得静默停止。"""

    def test_renewal_failure_clears_window_start(self, small_max):
        """续期抛错时清除窗口起点（不静默滞留），并保持可再次聚合。

        注意：**不要**用 `monkeypatch.undo()` 恢复——它会连同 fixture 对
        `MAX_WINDOW_SECONDS` 的 patch 一并撤销，使硬上界回到真实的 300s，
        于是"强制发送"永不触发。此处显式保存/恢复 `threading.Timer`。
        """
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.05)
        agg.push(event_type="probe", title="T", content="c", target_id="e1")

        original_timer = threading.Timer

        def boom(*_args, **_kwargs):
            raise RuntimeError("timer unavailable")

        threading.Timer = boom
        try:
            # 触发一次回调：续期失败应走兜底分支而非向外抛
            agg._on_timer("probe\x1fe1")
        finally:
            threading.Timer = original_timer

        with agg._lock:
            assert "probe\x1fe1" not in agg._window_start, "续期失败后窗口起点未清除"
            assert "probe\x1fe1" not in agg._timers
        # 仍可继续使用：新入队会重新起算窗口
        agg.push(event_type="probe", title="T", content="c2", target_id="e2")
        _drain_deadline(agg, "probe\x1fe2", timeout=small_max * 8)
        agg.shutdown()

    def test_shutdown_after_recovery_is_clean(self, small_max):
        """经历过续期失败后 shutdown 仍能干净排空。"""
        agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=0.05)
        agg.push(event_type="probe", title="T", content="c", target_id="e1")
        original_timer = threading.Timer

        def boom(*_args, **_kwargs):
            raise RuntimeError("x")

        threading.Timer = boom
        try:
            agg._on_timer("probe\x1fe1")
        finally:
            threading.Timer = original_timer

        agg.shutdown()
        with agg._lock:
            assert agg._buffers == {}
            assert agg._timers == {}
