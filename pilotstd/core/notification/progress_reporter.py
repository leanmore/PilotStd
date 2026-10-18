"""长任务周期进度汇报（D-2）。

设计（用户 2026-10-18 确认）：
- **范围**：所有运行中任务（`task_queue` 的 running 记录）+ 管道运行（`pipeline_runs` 的 running）；
- **节奏**：默认每 5 分钟一条；管道任务**阶段切换立即报**，其余按周期兜底；
- **渠道**：只调用 `notification_mgr.send_event("task_progress", payload)`，
  由既有策略表统一分发到 Web / Webhook / 企微 / 桌面托盘——本模块不碰渠道；
- **去重**：同一实体同一周期只报一次；任务离开 running 后清理计时。

这样长查询（可能几十分钟）每 5 分钟有进度，短任务通常只在完成时通知，不会刷屏。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# 时长阈值（秒）：默认 5 分钟；调度器每分钟 tick 一次，因此实际间隔 5~6 分钟。
# 上限 10 分钟、下限 5 分钟为用户约定，超出范围一律夹紧，避免配置写错导致刷屏或永不汇报。
DEFAULT_INTERVAL_SECONDS = 300
MIN_INTERVAL_SECONDS = 300
MAX_INTERVAL_SECONDS = 600


def _parse_ts(value: Any, *, assume_utc: bool = False) -> float | None:
    """把数据库时间串解析为 epoch 秒。

    任务表用本地时间（`datetime.now()`），管道表用 UTC 字符串（`pipeline_store._now`），
    两者都可能是 naive 字符串；由调用方用 `assume_utc` 指明语义，避免统一按本地解析
    导致管道“已运行 8 小时”的假进度。
    """
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if assume_utc and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        # 时间字段格式异常：本周期跳过（不是致命错误），但要留痕便于发现脏数据
        logger.warning("task progress: invalid timestamp %r", value)
        return None


def _percent(completed: Any, total: Any, fallback: Any = 0) -> int:
    """计算 0~100 的整数百分比；无总数时回退到给定的 progress。"""
    try:
        completed_i = max(0, int(completed or 0))
        total_i = int(total or 0)
        if total_i > 0:
            return max(0, min(100, round(completed_i * 100 / total_i)))
        return max(0, min(100, int(fallback or 0)))
    except (TypeError, ValueError):
        # 计数/百分比是外部数据：解析失败按 0 处理，但记 warning 避免静默
        logger.warning("task progress: percent parse failed (completed=%r total=%r)", completed, total)
        return 0


class TaskProgressReporter:
    """按任务运行时长周期汇报进度的公共组件。"""

    def __init__(
        self,
        *,
        send_event: Callable[[str, dict[str, Any]], None],
        task_rows: Callable[[], list[dict[str, Any]]],
        pipeline_rows: Callable[[], list[dict[str, Any]]],
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.send_event = send_event
        self._task_rows = task_rows
        self._pipeline_rows = pipeline_rows
        self._interval = self._clamp_interval(interval_seconds)
        self._clock = clock
        self._last_task_report: dict[str, float] = {}
        self._last_pipeline_report: dict[str, float] = {}
        self._last_pipeline_step: dict[str, str] = {}

    @staticmethod
    def _clamp_interval(seconds: int) -> int:
        """把周期限制在 5~10 分钟（用户约定），非法值回落 5 分钟。"""
        try:
            value = int(seconds)
        except (TypeError, ValueError):
            return DEFAULT_INTERVAL_SECONDS
        return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))

    def tick(self) -> None:
        """扫描一次运行中实体；由调度器每分钟调用。"""
        # 两类实体分开 try：一类查询失败不应拖垮另一类汇报
        now = self._clock()
        try:
            self._tick_tasks(now)
        except Exception as exc:  # 汇报失败不得影响调度器
            logger.warning("task progress report failed: %s", exc, exc_info=True)
        try:
            self._tick_pipelines(now)
        except Exception as exc:
            logger.warning("pipeline progress report failed: %s", exc, exc_info=True)

    def _tick_tasks(self, now: float) -> None:
        rows = self._task_rows() or []
        # alive 用于清理"已结束/已取消"任务的计时状态，防止内存随历史任务增长
        alive = {str(row.get("task_id") or "") for row in rows}
        for row in rows:
            task_id = str(row.get("task_id") or "")
            if not task_id:
                continue
            started = _parse_ts(row.get("started_at") or row.get("created_at")) or now
            last = self._last_task_report.get(task_id, started)
            if now - last < self._interval:
                continue
            self._last_task_report[task_id] = now
            total = row.get("total_items", 0)
            completed = row.get("completed_items", 0)
            self.send_event(
                "task_progress",
                {
                    "task_id": task_id,
                    "task_name": str(row.get("task_type") or task_id),
                    "completed": int(completed or 0),
                    "total": int(total or 0),
                    "percent": _percent(completed, total),
                    "elapsed_minutes": int((now - started) / 60),
                    "step": "",
                },
            )
        for gone in set(self._last_task_report) - alive:
            self._last_task_report.pop(gone, None)

    def _tick_pipelines(self, now: float) -> None:
        rows = self._pipeline_rows() or []
        # 管道用 current_step 判"阶段切换"：切换即报，不等待 5 分钟周期
        alive = {str(row.get("run_id") or "") for row in rows}
        for row in rows:
            run_id = str(row.get("run_id") or "")
            if not run_id:
                continue
            step = str(row.get("current_step") or "")
            started = _parse_ts(row.get("created_at"), assume_utc=True) or now
            step_changed = self._last_pipeline_step.get(run_id) != step
            last = self._last_pipeline_report.get(run_id, started)
            if not step_changed and now - last < self._interval:
                continue
            self._emit_pipeline(row, step, now)
        for gone in set(self._last_pipeline_report) - alive:
            self._last_pipeline_report.pop(gone, None)
            self._last_pipeline_step.pop(gone, None)

    def notify_pipeline_step(self, run_id: str, step: str) -> None:
        """阶段切换即时回调：由 `PipelineRunStore.update_step` 在步骤变化后调用。"""
        now = self._clock()
        for row in self._pipeline_rows() or []:
            if str(row.get("run_id") or "") == str(run_id):
                self._emit_pipeline(row, step, now)
                return

    def _emit_pipeline(self, row: dict[str, Any], step: str, now: float) -> None:
        """发送一条管道进度；同时刷新去重状态（tick 与即时回调共用）。"""
        run_id = str(row.get("run_id") or "")
        if not run_id:
            return
        started = _parse_ts(row.get("created_at"), assume_utc=True) or now
        self._last_pipeline_step[run_id] = step
        self._last_pipeline_report[run_id] = now
        progress = row.get("progress", 0)
        self.send_event(
            "task_progress",
            {
                "task_id": run_id,
                "task_name": "pipeline",
                "completed": int(progress or 0),
                "total": 100,
                "percent": _percent(progress, 100),
                "elapsed_minutes": int((now - started) / 60),
                "step": step,
            },
        )

