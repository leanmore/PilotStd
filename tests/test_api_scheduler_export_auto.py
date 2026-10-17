"""端点级测试：调度器状态/历史/统计、数据导出、一键处理（体检 D-13）。

静态普查（2026-10-17）显示这三个模块的 6 条路由在 `tests/` 中零命中：
`/api/scheduler/status|history|history/stats`、`/api/export/standards`、`/api/auto`。
本文件用依赖覆盖 + 目标模块打桩覆盖其正常/异常分支。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.auto import router as auto_router
from docker.api.export import router as export_router
from docker.api.scheduler import router as scheduler_router
from docker.manager import get_manager_dep


@pytest.fixture()
def mgr() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def client(mgr: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(scheduler_router)
    app.include_router(export_router)
    app.include_router(auto_router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    return TestClient(app)


# ── 调度器 ───────────────────────────────────────────────────────────


def test_scheduler_status_reports_jobs(client: TestClient, monkeypatch) -> None:
    from pilotstd.core import task_status

    job = SimpleNamespace(
        id="auto_backup",
        next_run_time=None,
        trigger="cron[hour='4']",
        pending=False,
    )
    fake_scheduler = SimpleNamespace(get_jobs=lambda: [job], running=True)
    monkeypatch.setattr("docker.scheduler.scheduler", fake_scheduler)
    status_map = {
        "auto_backup": {
            "last_run_time": "2026-10-17T04:00:00",
            "last_run_status": "success",
            "last_error_message": None,
        }
    }
    monkeypatch.setattr(task_status, "get_all_task_status", lambda: status_map)

    r = client.get("/api/scheduler/status")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is True
    assert body["job_count"] == 1
    assert body["jobs"][0]["id"] == "auto_backup"
    assert body["jobs"][0]["next_run_time"] is None
    assert body["jobs"][0]["last_run_status"] == "success"


def test_scheduler_history_passes_filters(client: TestClient, monkeypatch) -> None:
    from pilotstd.core import task_history

    calls: list[dict] = []

    def fake_history(**kwargs):
        calls.append(kwargs)
        return {"items": [], "total": 0}

    monkeypatch.setattr(task_history, "get_task_history", fake_history)

    r = client.get("/api/scheduler/history", params={"task_name": "  ", "page": 2, "size": 5})
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}
    # 现状：未传 → None；传空白串 → strip 后为空串（不是 None），由底层决定是否过滤
    assert calls == [{"task_name": "", "page": 2, "size": 5}]

    r = client.get("/api/scheduler/history")
    assert r.status_code == 200
    assert calls[-1] == {"task_name": None, "page": 1, "size": 20}


def test_scheduler_history_rejects_out_of_range_size(client: TestClient) -> None:
    r = client.get("/api/scheduler/history", params={"size": 101})
    assert r.status_code == 422


def test_scheduler_history_stats(client: TestClient, monkeypatch) -> None:
    from pilotstd.core import task_history

    monkeypatch.setattr(task_history, "get_task_stats", lambda: [{"task": "auto_backup", "success_rate": 1.0}])
    r = client.get("/api/scheduler/history/stats")
    assert r.status_code == 200
    assert r.json() == {"tasks": [{"task": "auto_backup", "success_rate": 1.0}]}


# ── 导出 ─────────────────────────────────────────────────────────────


def _seed_export(mgr: MagicMock) -> None:
    mgr.get_status_stats.return_value = {"total": 1}
    mgr.export_service.get_standards_data.return_value = {
        "items": [{"standard_number": "GB/T 1-2020", "status": "现行"}]
    }


def test_export_json(client: TestClient, mgr: MagicMock) -> None:
    _seed_export(mgr)
    r = client.get("/api/export/standards")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "standards.json" in r.headers["content-disposition"]
    body = r.json()
    assert body["items"] == [{"standard_number": "GB/T 1-2020", "status": "现行"}]
    assert body["stats"] == {"total": 1}


def test_export_csv(client: TestClient, mgr: MagicMock) -> None:
    _seed_export(mgr)
    r = client.get("/api/export/standards", params={"format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "standards.csv" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "standard_number,status"
    assert lines[1] == "GB/T 1-2020,现行"


def test_export_error_is_reported_not_raised(client: TestClient, mgr: MagicMock) -> None:
    mgr.get_status_stats.side_effect = RuntimeError("db down")
    r = client.get("/api/export/standards")
    assert r.status_code == 200
    assert r.json() == {"ok": False, "error": "db down"}


# ── 一键处理 ─────────────────────────────────────────────────────────


def test_auto_run_success(client: TestClient, mgr: MagicMock) -> None:
    mgr.auto_run.return_value = {"scanned": 3}
    r = client.post("/api/auto")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "results": {"scanned": 3}, "message": "一键处理完成"}


def test_auto_run_failure_returns_500(client: TestClient, mgr: MagicMock) -> None:
    mgr.auto_run.side_effect = RuntimeError("boom")
    r = client.post("/api/auto")
    assert r.status_code == 500
    assert r.json() == {"ok": False, "error": "boom"}
