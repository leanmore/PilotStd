"""公告详情/记录必须按 source_site 消歧：同一 announce_no/PID 可能来自 HB/DB。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api import announce_detail
from docker.manager import get_manager_dep


@pytest.fixture()
def client(tmp_path):
    from pilotstd.core.db import Database

    db = Database(str(tmp_path / "announce_source.db"))
    now = "2026-01-01T00:00:00"
    for source_site, pid, title, code in (
        ("announcement_hb", "same-pid", "行业标准备案", "GA/T 1-2020"),
        ("announcement_db", "same-pid", "地方标准备案", "DB11/T 1-2020"),
    ):
        db.execute(
            "INSERT INTO announcements"
            " (source_site, pid, announce_no, title, publish_date, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_site, pid, "2014年第4号(总第172号)", title, "2014-05-16", now, now),
        )
        db.execute(
            "INSERT INTO announcement_record"
            " (source_site, pid, announce_no, standard_number, std_name, publish_date, fetched_at, standard_count)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source_site, pid, "2014年第4号(总第172号)", code, title, "2014-05-16", now, 1),
        )
    mgr = MagicMock()
    mgr.db = db
    app = FastAPI()
    app.include_router(announce_detail.router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    yield TestClient(app)
    db.close()


def test_records_filtered_by_hb_source(client: TestClient) -> None:
    resp = client.get("/api/announcements/2014年第4号(总第172号)/records", params={"source": "annc_hb"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["standard_number"] == "GA/T 1-2020"


def test_detail_filtered_by_db_source(client: TestClient) -> None:
    resp = client.get("/api/announcements/2014年第4号(总第172号)", params={"source": "annc_db"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["announcement"]["title"] == "地方标准备案"
    assert len(body["records"]) == 1
    assert body["records"][0]["standard_number"] == "DB11/T 1-2020"
