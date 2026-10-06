"""阶段 2 · P4b-2 投影入口测试（`pilotstd/core/task/manager.py`）。

覆盖三条硬约束与两个审核关注点：
1. **防 N+1**：`list_tasks()` 必须**只调一次** `get_all()`（用调用计数替身证明），且**绝不**逐条调 `get()`；
2. **`limit` 语义**：把调用方 `limit` 原样透传（本模块不额外截断），默认值＝100（既有口径）；
3. **`result_json` 容错**：空串 / 非字符串 / 非法 JSON / JSON 非字典 —— 四种情况**一律回退 `{}` 且不抛**；
4. **只读**：替身上**没有任何写方法被调用**（`enqueue`/`start`/`cancel`/`_persist` 全零调用）；
5. **形状归一**：`get_all()` 的行字典与 `get()` 的 `TaskInfo` 数据类都能投影成 `Task`。
"""

from __future__ import annotations

from dataclasses import dataclass

from pilotstd.core.task.manager import DEFAULT_LIST_LIMIT, TaskManager, _loads_result_json
from pilotstd.core.task.model import TERMINAL_STATUSES


@dataclass
class _FakeInfo:
    """`TaskQueue.get()` 的返回形状（`TaskInfo` 数据类）。"""

    task_id: str = "t-1"
    task_type: object = "scan"
    status: object = "completed"
    total_items: int = 10
    completed_items: int = 7
    failed_items: int = 3
    started_at: str = "2026-10-05T10:00:00"
    finished_at: str = "2026-10-05T10:05:00"
    result_json: str = ""


class _FakeQueue:
    """只读替身：记录调用次数，并提供**写方法探针**以证明"只读"。"""

    def __init__(self, rows: list[dict] | None = None, info: _FakeInfo | None = None) -> None:
        self._rows = rows if rows is not None else []
        self._info = info
        self.get_all_calls: list[int] = []
        self.get_calls: list[str] = []
        self.write_calls: list[str] = []

    # 读
    def get_all(self, status_filter: str | None = None, limit: int = 100) -> list[dict]:
        self.get_all_calls.append(limit)
        return list(self._rows)

    def get(self, task_id: str):  # noqa: ANN201 - 替身保持与 DAO 同形
        self.get_calls.append(task_id)
        return self._info

    # 写（探针：若被调用则说明越界）
    def enqueue(self, *a, **k):
        self.write_calls.append("enqueue")

    def start(self, *a, **k):
        self.write_calls.append("start")

    def cancel(self, *a, **k):
        self.write_calls.append("cancel")

    def _persist(self, *a, **k):
        self.write_calls.append("_persist")


def _row(**over: object) -> dict:
    base = {
        "task_id": "t-1",
        "task_type": "scan",
        "status": "running",
        "total_items": 10,
        "completed_items": 5,
        "failed_items": 0,
        "started_at": "2026-10-05T10:00:00",
        "finished_at": "",
        "result_json": "{}",
    }
    base.update(over)
    return base


def test_list_tasks_is_single_batch_call_and_read_only() -> None:
    """防 N+1：3 行任务 ⇒ `get_all()` **只调 1 次**、`get()` **0 次**、**无任何写调用**。"""
    q = _FakeQueue(rows=[_row(task_id="t-1"), _row(task_id="t-2"), _row(task_id="t-3")])
    tasks = TaskManager(q).list_tasks()

    assert len(tasks) == 3
    assert q.get_all_calls == [DEFAULT_LIST_LIMIT], "必须一次批量读（默认 limit 透传）"
    assert q.get_calls == [], "不得在循环里逐条 get（N+1）"
    assert q.write_calls == [], "投影入口必须是只读的"


def test_list_tasks_passes_limit_through_without_extra_truncation() -> None:
    """`limit` 原样透传：本模块自身不额外截断（截断只来自调用方传入值）。"""
    q = _FakeQueue(rows=[_row()])
    TaskManager(q).list_tasks(limit=250)
    assert q.get_all_calls == [250]


def test_get_task_normalizes_info_shape() -> None:
    """`get()` 返回数据类时也要能投影（形状归一），且状态/类型取自枚举的 `value`。"""
    q = _FakeQueue(info=_FakeInfo())
    task = TaskManager(q).get_task("t-1")

    assert task is not None
    assert (task.task_id, task.task_kind, task.status) == ("t-1", "scan", "completed")
    assert (task.total, task.completed, task.failed) == (10, 7, 3)
    assert task.is_terminal is True, "实际词表的 completed 必须被判为终局（两套词表都要认）"
    assert TaskManager(_FakeQueue(info=None)).get_task("nope") is None


def test_progress_of_marks_terminal_from_actual_vocabulary() -> None:
    """进度快照：终局标记必须来自**实际词表**（`completed`/`cancelled`）也能识别。"""
    for raw in ("completed", "cancelled", "failed"):
        row = _row(status=raw, completed_items=10)
        task = TaskManager(_FakeQueue(rows=[row])).list_tasks()[0]
        prog = TaskManager(_FakeQueue(rows=[row])).progress_of(task)
        assert prog.percent == 100
        assert prog.is_terminal is True
        assert prog.should_push is True
    assert {"completed", "cancelled"} <= TERMINAL_STATUSES


def test_result_json_is_defensive() -> None:
    """四种坏输入 ⇒ 一律 `{}` 且**不抛**（历史 schema 不一致的保底）。"""
    assert _loads_result_json("") == {}
    assert _loads_result_json(None) == {}
    assert _loads_result_json(123) == {}
    assert _loads_result_json("{半截") == {}
    assert _loads_result_json("[1, 2]") == {}
    assert _loads_result_json('{"ok": true}') == {"ok": True}


def test_result_of_handles_both_shapes() -> None:
    """`result_of` 兼容行字典与数据类两种形状。"""
    row = _row(result_json='{"count": 3}')
    assert TaskManager.result_of(row) == {"count": 3}
    assert TaskManager.result_of(_FakeInfo(result_json="oops")) == {}
