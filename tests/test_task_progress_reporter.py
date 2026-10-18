"""D-2：长任务周期进度汇报（全任务 / 阶段即时 / 5 分钟兜底 / 全渠道统一事件）。"""

from __future__ import annotations

from datetime import datetime

from pilotstd.core.notification.progress_reporter import TaskProgressReporter


class _Clock:
    def __init__(self, value: float = 1_000_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).isoformat()


def test_task_reports_every_interval() -> None:
    clock = _Clock()
    sent: list[tuple[str, dict]] = []
    rows = [
        {
            "task_id": "t1",
            "task_type": "query",
            "completed_items": 3,
            "total_items": 10,
            "started_at": _iso(clock.value),
        }
    ]
    reporter = TaskProgressReporter(
        send_event=lambda e, d: sent.append((e, d)),
        task_rows=lambda: rows,
        pipeline_rows=lambda: [],
        interval_seconds=300,
        clock=clock,
    )

    reporter.tick()
    assert sent == []  # 刚启动，未到 5 分钟

    clock.value += 299
    reporter.tick()
    assert sent == []

    clock.value += 1
    reporter.tick()
    assert len(sent) == 1
    event, payload = sent[0]
    assert event == "task_progress"
    assert payload["task_id"] == "t1"
    assert payload["percent"] == 30
    assert payload["elapsed_minutes"] == 5

    clock.value += 1
    reporter.tick()
    assert len(sent) == 1  # 周期内去重

    clock.value += 300
    reporter.tick()
    assert len(sent) == 2


def test_task_state_cleared_when_finished() -> None:
    clock = _Clock()
    sent: list[tuple[str, dict]] = []
    rows = [
        {"task_id": "t1", "task_type": "scan", "completed_items": 0, "total_items": 0, "started_at": _iso(clock.value)}
    ]
    reporter = TaskProgressReporter(
        send_event=lambda e, d: sent.append((e, d)),
        task_rows=lambda: rows,
        pipeline_rows=lambda: [],
        interval_seconds=300,
        clock=clock,
    )
    clock.value += 300
    reporter.tick()
    assert len(sent) == 1
    rows.clear()
    clock.value += 300
    reporter.tick()
    assert len(sent) == 1


def test_pipeline_stage_change_is_immediate_and_percent_from_progress() -> None:
    clock = _Clock()
    sent: list[tuple[str, dict]] = []
    rows = [
        {
            "run_id": "r1",
            "current_step": "scan",
            "progress": 10,
            "created_at": _iso(clock.value),
        }
    ]
    reporter = TaskProgressReporter(
        send_event=lambda e, d: sent.append((e, d)),
        task_rows=lambda: [],
        pipeline_rows=lambda: rows,
        interval_seconds=300,
        clock=clock,
    )

    reporter.tick()  # 首次出现：阶段视为变化 → 立即报
    assert len(sent) == 1
    assert sent[0][1]["step"] == "scan"
    assert sent[0][1]["percent"] == 10

    clock.value += 30
    reporter.tick()
    assert len(sent) == 1  # 同阶段、未到周期

    rows[0]["current_step"] = "query"
    rows[0]["progress"] = 40
    reporter.tick()  # 阶段切换 → 立即报
    assert len(sent) == 2
    assert sent[1][1]["step"] == "query"
    assert sent[1][1]["percent"] == 40

    clock.value += 300
    reporter.tick()  # 同阶段但到周期 → 兜底报
    assert len(sent) == 3


def test_interval_clamped_to_5_10_minutes() -> None:
    reporter = TaskProgressReporter(
        send_event=lambda e, d: None,
        task_rows=lambda: [],
        pipeline_rows=lambda: [],
        interval_seconds=60,
    )
    assert reporter._interval == 300
    reporter = TaskProgressReporter(
        send_event=lambda e, d: None,
        task_rows=lambda: [],
        pipeline_rows=lambda: [],
        interval_seconds=3600,
    )
    assert reporter._interval == 600


def test_task_progress_event_registered_and_built() -> None:
    from pilotstd.core.notification._builders_task_results import _build_task_progress_message

    message = _build_task_progress_message(
        {
            "task_id": "t1",
            "task_name": "query",
            "completed": 3,
            "total": 10,
            "percent": 30,
            "elapsed_minutes": 6,
            "step": "query",
        }
    )
    assert "query" in message.body
    assert "3/10" in message.body
    assert message.event_type == "task_progress"
    assert message.task_id == "t1"
