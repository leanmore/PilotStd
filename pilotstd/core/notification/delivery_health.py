# 模块：项目/核心/通知//投递健康度
# 通知**投递健康度**监控：渠道投递失败达阈值时告警（P0 修复）。
#
# 缺陷背景（生产实测，32 天窗口）：
#   1,148 条通知里 **629 条发送失败（54.8%）**，其中 599 条是 Telegram 限流。
#   而这一切**用户完全不可见**——通知系统自己坏了，只能靠人偶然发现。
#   最糟的一周（2026-09-14~09-20）每天失败 25~151 条，持续 7 天无人知晓，
#   而那正是"收藏集中下载失败、61 条被永久冻结"的窗口。
#
# 设计要点：
#   1. **双触发**：连败（渠道彻底不通）**或**窗口失败率超阈（渠道在丢消息）。
#      两者判据不同、处置不同，故分别计数；同时成立时**只报连败**，不发两条。
#   2. **告警去重**：同一（渠道 + 原因）在冷却期内只告警一次，避免风暴。
#   3. **不回环**：告警自身的投递结果**不再计入健康度**（否则告警失败又会触发新告警）。
#   4. **线程安全**：`send_event` 可能被多个线程（调度器 + API）并发调用。
#   5. **内存态**：部署为单进程 uvicorn（`docker/entrypoint.sh` 无 `--workers`），
#      故用进程内状态；重启后计数归零——对"连续失败"语义可接受（重试即重建）。

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

# 告警原因（同时作为去重键的一部分与文案选择依据）
REASON_CONSECUTIVE = "consecutive"
REASON_RATE = "rate"

# 单渠道窗口内最多保留的结果数（防止长期运行内存无界增长）
_MAX_OUTCOMES = 5000


@dataclass
class _ChannelState:
    """单渠道的投递状态（滚动窗口内的结果序列）。"""

    outcomes: deque = field(default_factory=lambda: deque(maxlen=_MAX_OUTCOMES))
    consecutive_failures: int = 0
    last_alert_at: dict = field(default_factory=dict)


class NotificationDeliveryHealth:
    """按渠道统计投递成败，并在越过阈值时给出告警判定。

    参数（来自配置，见 `pilotstd/core/config/defaults.py`）：
        rate_threshold         窗口内失败率阈值（0~1）
        min_samples            窗口内样本数下限（不足则不判失败率，避免冷启动误报）
        consecutive_threshold  连败阈值（连续失败达此值即告警）
        window_seconds         失败率统计窗口
        alert_cooldown_seconds 同一（渠道 + 原因）的告警最小间隔
    """

    def __init__(
        self,
        *,
        rate_threshold: float = 0.5,
        min_samples: int = 10,
        consecutive_threshold: int = 5,
        window_seconds: float = 3600.0,
        alert_cooldown_seconds: float = 3600.0,
    ) -> None:
        self._rate_threshold = float(rate_threshold)
        self._min_samples = int(min_samples)
        self._consecutive_threshold = int(consecutive_threshold)
        self._window = float(window_seconds)
        self._cooldown = float(alert_cooldown_seconds)
        self._lock = threading.Lock()
        self._states: dict = {}
        # 时间源可替换（测试注入假时钟，避免 sleep）
        self._now = time.monotonic

    # ── 记录 ────────────────────────────────────────────────────────────────

    def record(self, channel: str, ok: bool) -> None:
        """记录一次投递结果。渠道名为空时忽略（防御式）。"""
        if not channel:
            return
        with self._lock:
            st = self._states.setdefault(channel, _ChannelState())
            st.outcomes.append((self._now(), bool(ok)))
            st.consecutive_failures = 0 if ok else st.consecutive_failures + 1

    # ── 只读查询（各自加锁，供外部与测试使用）────────────────────────────────

    def snapshot(self, channel: str) -> tuple[int, int]:
        """返回窗口内 `(样本数, 失败数)`。"""
        with self._lock:
            return self._counts(self._states.get(channel))

    def consecutive(self, channel: str) -> int:
        """返回当前连败次数。"""
        with self._lock:
            st = self._states.get(channel)
            return st.consecutive_failures if st else 0

    # ── 判定 ────────────────────────────────────────────────────────────────

    def evaluate(self, channel: str) -> tuple[str, int, int] | None:
        """判断是否应告警。返回 `(原因, 样本数, 失败数)`；无需告警返回 `None`。

        **优先级**：连败优先于失败率——连败说明渠道彻底不通，是更严重也更确定的信号；
        两者同时成立时只报连败，不发两条。冷却期内的重复判定返回 `None`。
        """
        with self._lock:
            st = self._states.get(channel)
            if st is None:
                return None
            samples, failures = self._counts(st)
            if st.consecutive_failures >= self._consecutive_threshold:
                reason = REASON_CONSECUTIVE
            elif samples >= self._min_samples and failures / samples >= self._rate_threshold:
                reason = REASON_RATE
            else:
                return None
            last = st.last_alert_at.get(reason)
            if last is not None and (self._now() - last) < self._cooldown:
                return None
            st.last_alert_at[reason] = self._now()
            return reason, samples, failures

    def _counts(self, st: _ChannelState | None) -> tuple[int, int]:
        """窗口内 `(样本数, 失败数)`；超窗记录不计。调用方须持锁。"""
        if st is None:
            return 0, 0
        cutoff = self._now() - self._window
        samples = failures = 0
        for ts, success in st.outcomes:
            if ts < cutoff:
                continue
            samples += 1
            if not success:
                failures += 1
        return samples, failures

    # ── 测试辅助 ────────────────────────────────────────────────────────────

    def set_clock(self, now) -> None:
        """替换时间源（测试用假时钟，避免真实 sleep）。"""
        self._now = now

    def reset(self) -> None:
        """清空全部状态（测试用）。"""
        with self._lock:
            self._states.clear()
