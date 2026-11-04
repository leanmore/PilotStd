"""任务队列：暂停不被轮询器拉起 + 原子认领防重复执行（D6-1 / D6-2）。"""

import threading
import time

from pilotstd.core.db import Database
from pilotstd.task.models import TaskStatus, TaskType
from pilotstd.task.queue import TaskQueue


def _queue(tmp_path):
    db = Database(str(tmp_path / "q.db"))
    return TaskQueue(db, task_timeout=5)


def test_paused_task_is_not_pending(tmp_path):
    q = _queue(tmp_path)
    task = q.enqueue(TaskType.SCAN)
    assert q.pause(task.task_id) is True

    assert q.get_pending() == [], "paused 不得出现在待执行列表（否则 2 秒后会被拉起）"


def test_start_claims_pending_atomically(tmp_path):
    q = _queue(tmp_path)
    calls: list[str] = []
    q.register_handler(TaskType.SCAN, lambda task: calls.append(task.task_id) or task)
    task = q.enqueue(TaskType.SCAN)

    q.start(task)  # 第一次：认领成功
    q.start(task)  # 第二次：已 running，必须 no-op

    deadline = time.time() + 5
    while len(calls) < 1 and time.time() < deadline:
        time.sleep(0.02)
    time.sleep(0.2)
    assert calls == [task.task_id], f"同一任务只能执行一次，实际 {calls}"


def test_paused_task_is_not_started_by_start(tmp_path):
    q = _queue(tmp_path)
    seen: list[str] = []
    q.register_handler(TaskType.SCAN, lambda task: seen.append(task.task_id) or task)
    task = q.enqueue(TaskType.SCAN)
    q.pause(task.task_id)

    q.start(task)  # 状态是 paused → 认领失败
    time.sleep(0.2)
    assert seen == []
    assert q.get(task.task_id).status == TaskStatus.PAUSED


def test_resume_moves_back_to_pending(tmp_path):
    q = _queue(tmp_path)
    done = threading.Event()
    q.register_handler(TaskType.SCAN, lambda task: done.set() or task)
    task = q.enqueue(TaskType.SCAN)
    q.pause(task.task_id)

    q.resume(q.get(task.task_id))

    assert done.wait(3), "resume 后应真正开始执行"
