"""GET /api/announcements/results/{task_id} 的端点级契约（U34-C6 Commit 2）。

锁定三件事：
1. `result_data` 是脏 JSON → HTTP 200 + `status="success"` + `data` 为空 + `message` 非空
   （B 方案：加字段不改语义，消费方能区分「本来没数据」与「数据损坏」）；
2. 正常 JSON → `message` 不出现（`response_model_exclude_none=True` 生效）；
3. 任务不存在 → 404（既有行为不变）。
"""

import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.announcements import router
from docker.manager import get_manager_dep
from pilotstd.manager.announce_service import AnnounceService


def _client_with_row(row):
    """构造一个只挂了 announcements 路由的最小应用，注入假 fetch_task 行。"""

    class _DB:
        def fetchone(self, *_args, **_kwargs):
            return row

    svc = object.__new__(AnnounceService)
    svc._get_db = lambda: _DB()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_manager_dep] = lambda: types.SimpleNamespace(_announce_svc=svc)
    return TestClient(app)


def test_dirty_json_returns_message_and_empty_data() -> None:
    """脏 JSON：200 + success + data={} + message 非空。"""
    client = _client_with_row({"status": "success", "result_data": "{not json", "id": "t1"})

    resp = client.get("/api/announcements/results/t1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"] == {}
    assert "结果数据损坏" in body["message"]


def test_valid_json_has_no_message() -> None:
    """正常 JSON：message 不出现（None 被 exclude），data 原样透出。"""
    client = _client_with_row(
        {"status": "success", "result_data": '{"ok": true, "count": 3}', "id": "t2"}
    )

    resp = client.get("/api/announcements/results/t2")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == {"ok": True, "count": 3}
    assert "message" not in body


def test_missing_task_still_404() -> None:
    """任务不存在：既有 404 契约不变。"""
    client = _client_with_row(None)

    resp = client.get("/api/announcements/results/nope")

    assert resp.status_code == 404
    assert resp.json()["error"] == "task not found"
