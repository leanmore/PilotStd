"""阶段 2 · P4b 任务视角投影测试（`pilotstd/core/task/model.py`）。

覆盖 `02-目标架构.md §2.3` 的四条口径：
1. `Task.derive_correlation_id()`＝`{task_kind}:{started_at[:19]}`，**`started_at` 为空时返回空串**
   （避免未开始的任务被误判成"批次"而走①批次聚合路径）；
2. `TaskProgress.percent`：`total <= 0` 返回 0（不抛）、超界被夹到 0–100；
3. `should_push` 的四种放行条件（首推 / 跨阈值 / 换阶段 / 终局）与两种拦截；
4. `mark_pushed()` 之后同一进度不再重复推送（幂等 ⇒ 支撑"同一 message_id 反复 edit"）。
"""

from __future__ import annotations

from pilotstd.core.task import Task, TaskItem, TaskProgress


def test_correlation_id_derivation_and_empty_guard() -> None:
    """批次键派生；`started_at` 为空 ⇒ 空串（不触发①批次聚合路径）。"""
    t = Task(task_id="t-1", task_kind="scan", started_at="2026-10-05T10:20:30.123456")
    assert t.derive_correlation_id() == "scan:2026-10-05T10:20:30"
    assert Task(task_id="t-2", task_kind="scan").derive_correlation_id() == ""


def test_task_terminal_detection() -> None:
    """终局判定覆盖四个终局态；`running`/`pending` 非终局。"""
    for status in ("succeeded", "partial", "failed", "abandoned"):
        assert Task(task_id="t", status=status).is_terminal is True
    for status in ("pending", "running"):
        assert Task(task_id="t", status=status).is_terminal is False


def test_percent_boundaries_without_exception() -> None:
    """`total=0` ⇒ 0（不抛）；常规/超界均被夹到 0–100。"""
    assert TaskProgress(task_id="t", current=3, total=0).percent == 0
    assert TaskProgress(task_id="t", current=1, total=4).percent == 25
    assert TaskProgress(task_id="t", current=9, total=4).percent == 100
    assert TaskProgress(task_id="t", current=-3, total=4).percent == 0


def test_should_push_four_allow_and_two_block_cases() -> None:
    """节流闸：首推/跨阈值/换阶段/终局放行；小步同阶段、已推送过的同进度拦截。"""
    # ① 首推（无历史）
    first = TaskProgress(task_id="t", current=1, total=100, stage="download")
    assert first.should_push is True
    first.mark_pushed()

    # ② 同阶段小步（+5 < 阈值 10）⇒ 拦截
    small = TaskProgress(
        task_id="t", current=6, total=100, stage="download",
        last_pushed_percent=1, last_pushed_stage="download",
    )
    assert small.should_push is False

    # ③ 同阶段跨阈值（1 → 11）⇒ 放行
    crossed = TaskProgress(
        task_id="t", current=11, total=100, stage="download",
        last_pushed_percent=1, last_pushed_stage="download",
    )
    assert crossed.should_push is True

    # ④ 换阶段（进度只 +1）⇒ 放行
    stage_changed = TaskProgress(
        task_id="t", current=2, total=100, stage="archive",
        last_pushed_percent=1, last_pushed_stage="download",
    )
    assert stage_changed.should_push is True

    # ⑤ 终局：无论进度是否变化都放行
    terminal = TaskProgress(
        task_id="t", current=1, total=100, stage="download",
        last_pushed_percent=1, last_pushed_stage="download", is_terminal=True,
    )
    assert terminal.should_push is True


def test_mark_pushed_is_idempotent() -> None:
    """`mark_pushed()` 后同一进度不再重复推送（幂等）。"""
    p = TaskProgress(task_id="t", current=50, total=100, stage="download")
    assert p.should_push is True
    p.mark_pushed()
    assert p.should_push is False, "已推送过的同一进度不得重复推"
    # 进度前进到下一个阈值才再次放行
    p.current = 60
    assert p.should_push is True


def test_task_item_defaults() -> None:
    """条目默认值（阶段 2 只加数据结构、不接通知；默认值即"待处理"）。"""
    item = TaskItem(item_key="GB/T 1234-2020")
    assert (item.label, item.status, item.error, item.attempts, item.detail_url) == ("", "pending", "", 0, "")
