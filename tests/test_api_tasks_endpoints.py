"""D-13 补测：/api/tasks 与 /api/tasks/runs（此前函数级零覆盖）。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from jose import jwt
from starlette.requests import Request

from docker.auth import ADMIN_ROLE, COOKIE_NAME, SECRET


def _req(path: str = "/api/tasks") -> Request:
    token = jwt.encode({"sub": "1", "role": ADMIN_ROLE}, SECRET, algorithm="HS256")
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [(b"cookie", f"{COOKIE_NAME}={token}".encode())],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )


def _row(task_id: str = "t1", status: str = "pending") -> dict:
    return {
        "task_id": task_id,
        "task_type": "query",
        "status": status,
        "created_at": "2026-10-18T00:00:00",
    }


def test_list_tasks_paginates_and_filters() -> None:
    from docker.api.tasks import list_tasks

    mgr = MagicMock()
    mgr.task_queue.get_all.return_value = [_row("t1", "pending"), _row("t2", "failed")]
    result = list_tasks(_req(), status="failed", page=1, page_size=10, mgr=mgr)
    assert result["total"] == 1
    assert [i["task_id"] for i in result["items"]] == ["t2"]

    result_all = list_tasks(_req(), status=None, page=1, page_size=1, mgr=mgr)
    assert result_all["total"] == 2
    assert len(result_all["items"]) == 1


def test_get_task_404_and_success() -> None:
    from docker.api.tasks import get_task
    from pilotstd.task.models import TaskStatus, TaskType

    mgr = MagicMock()
    mgr.task_queue.get.return_value = None
    assert get_task(_req(), "t1", mgr=mgr).status_code == 404

    mgr.task_queue.get.return_value = SimpleNamespace(
        task_id="t1",
        task_type=TaskType.QUERY,
        status=TaskStatus.PENDING,
        total_items=10,
        completed_items=3,
        failed_items=1,
        error_log="",
        result_json="",
        created_at="c",
        updated_at="u",
    )
    payload = get_task(_req(), "t1", mgr=mgr)
    assert payload["task_id"] == "t1"
    assert payload["task_type"] == "query"
    assert payload["status"] == "pending"


def test_create_task_rejects_unknown_type_and_enqueues() -> None:
    from docker.api.tasks import create_task
    from pilotstd.task.models import TaskStatus, TaskType

    mgr = MagicMock()
    resp = create_task(_req(), {"task_type": "no-such-type"}, mgr=mgr)
    assert resp.status_code == 400
    mgr.task_queue.enqueue.assert_not_called()

    mgr.task_queue.enqueue.return_value = SimpleNamespace(
        task_id="t9", status=TaskStatus.PENDING
    )
    payload = create_task(_req(), {"task_type": "query", "total_items": 5}, mgr=mgr)
    assert payload == {"ok": True, "task_id": "t9", "status": "pending"}
    mgr.task_queue.enqueue.assert_called_once_with(TaskType.QUERY, total_items=5)


def test_retry_task_state_machine() -> None:
    from docker.api.tasks import retry_task
    from pilotstd.task.models import TaskStatus

    mgr = MagicMock()
    mgr.task_queue.get.return_value = None
    assert retry_task(_req(), "t1", mgr=mgr).status_code == 404

    running = SimpleNamespace(status=TaskStatus.RUNNING)
    mgr.task_queue.get.return_value = running
    assert retry_task(_req(), "t1", mgr=mgr).status_code == 400

    failed = SimpleNamespace(status=TaskStatus.FAILED, updated_at="old")
    mgr.task_queue.get.return_value = failed
    assert retry_task(_req(), "t1", mgr=mgr) == {"ok": True}
    assert failed.status is TaskStatus.PENDING
    mgr.task_queue._persist.assert_called_once_with(failed)


def test_cancel_task_delegates() -> None:
    from docker.api.tasks import cancel_task

    mgr = MagicMock()
    mgr.task_queue.cancel.return_value = True
    assert cancel_task(_req(), "t1", mgr=mgr) == {"ok": True}
    mgr.task_queue.cancel.assert_called_once_with("t1")


def test_get_pipeline_run_parses_step_results() -> None:
    from docker.api.tasks import get_pipeline_run

    mgr = MagicMock()
    mgr.pipeline_store.get.return_value = None
    assert get_pipeline_run(_req(), "r1", mgr=mgr).status_code == 404

    mgr.pipeline_store.get.return_value = {
        "run_id": "r1",
        "current_step": "scan",
        "status": "running",
        "progress": 10,
        "step_results": "{bad json",
        "error_message": "",
        "created_at": "c",
        "updated_at": "u",
    }
    payload = get_pipeline_run(_req(), "r1", mgr=mgr)
    assert payload["step_results"] == {}

    mgr.pipeline_store.get.return_value["step_results"] = json.dumps({"scan": {"ok": 1}})
    assert get_pipeline_run(_req(), "r1", mgr=mgr)["step_results"] == {"scan": {"ok": 1}}
