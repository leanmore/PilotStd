"""公告抓取失败读侧 API（P1-03）：GET /api/announce/fetch-failures。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api import announce
from docker.manager import get_manager_dep


@pytest.fixture()
def client() -> TestClient:
    mgr = MagicMock()
    mgr._announce_svc.get_fetch_failures.return_value = {
        "total": 2,
        "unresolved": 1,
        "items": [
            {
                "id": 2,
                "task_type": "scheduled",
                "source_site": "samr_hb",
                "error_message": "第二次失败",
                "retry_count": 0,
                "resolved": False,
                "created_at": "2026-11-09 21:00:00",
                "last_retry_at": None,
            }
        ],
    }
    app = FastAPI()
    app.include_router(announce.router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    return TestClient(app)


def test_fetch_failures_returns_history(client: TestClient) -> None:
    r = client.get("/api/announce/fetch-failures?limit=5&unresolved_only=true")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["unresolved"] == 1
    assert body["items"][0]["source_site"] == "samr_hb"
    assert body["items"][0]["resolved"] is False


def test_fetch_failures_forwards_limit_and_filter(client: TestClient) -> None:
    client.get("/api/announce/fetch-failures?limit=7&unresolved_only=false")
    mgr = client.app.dependency_overrides[get_manager_dep]()
    mgr._announce_svc.get_fetch_failures.assert_called_once_with(
        limit=7, unresolved_only=False
    )
