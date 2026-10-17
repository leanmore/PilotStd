"""端点级测试：公告解析/编辑/批量确认写路径（体检 D-14）。

体检记录这些写路径"无端点级测试"。本文件用**真实 Database**（迁移链建表）+
FastAPI TestClient + `get_manager_dep` 覆盖，覆盖：

1. `POST /api/announcements/{no}/parse`：无附件 400 / 已解析返回计数 /
   正常派发后台任务 / 仅 record 有数据时自愈（并因无附件 400）；
2. `GET /api/announcements/{no}/parse-status`：404 / pending / completed；
3. `PATCH /api/announcement-record/{id}`：404 / 已确认不可编辑 / 无有效字段 /
   字段白名单 + draft→pending_review；
4. `POST /api/announcement-record/batch-approve`：空 ids / 不存在 / 缺标准号 /
   成功批量置 approved。

后台解析任务被 monkeypatch 成记录器，测试不发网络请求。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api import announce_detail
from docker.manager import get_manager_dep


@pytest.fixture()
def db(tmp_path):
    from pilotstd.core.db import Database

    database = Database(str(tmp_path / "announce.db"))
    yield database
    database.close()


@pytest.fixture()
def mgr(db) -> MagicMock:
    manager = MagicMock()
    manager.db = db
    return manager


@pytest.fixture()
def client(mgr: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(announce_detail.router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    return TestClient(app)


def _insert_announcement(db, no: str = "ANNOUNCE-2026-001", attachment: str = "") -> int:
    db.execute(
        "INSERT INTO announcements"
        " (source_site, pid, announce_no, title, publish_date, source_url,"
        "  attachment_url, raw_data, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ahbz", "pid-001", no, "2026年第1号公告", "2026-06-01", "https://x/1",
         attachment, "{}", "2026-06-15", "2026-06-15"),
    )
    row = db.fetchone("SELECT id FROM announcements WHERE announce_no = ?", (no,))
    assert row is not None
    return int(row["id"])


def _insert_record(
    db,
    announce_no: str = "ANNOUNCE-2026-001",
    standard_number: str = "GB/T 19001-2016",
    std_name: str = "质量管理体系",
    status: str = "draft",
    announcement_id: int | None = None,
) -> int:
    db.execute(
        "INSERT INTO announcement_record"
        " (source_site, pid, announce_no, standard_number, std_name, publish_date,"
        "  fetched_at, announcement_title, status, announcement_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ahbz", "pid-001", announce_no, standard_number, std_name, "2026-06-01",
         "2026-06-15", "2026年第1号公告", status, announcement_id),
    )
    row = db.fetchone(
        "SELECT id FROM announcement_record WHERE announce_no = ? ORDER BY id DESC LIMIT 1",
        (announce_no,),
    )
    assert row is not None
    return int(row["id"])


# ── parse ────────────────────────────────────────────────────────────


def test_parse_without_attachment_returns_400(client: TestClient, db) -> None:
    _insert_announcement(db)
    r = client.post("/api/announcements/ANNOUNCE-2026-001/parse")
    assert r.status_code == 400
    assert "没有附件" in r.json()["detail"]


def test_parse_dispatches_background_task(
    client: TestClient, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(announce_detail, "_parse_attachment_bg", lambda *a: calls.append(a))
    ann_id = _insert_announcement(db, attachment="https://x/a.pdf")

    r = client.post("/api/announcements/ANNOUNCE-2026-001/parse")
    assert r.status_code == 200
    assert r.json() == {"status": "parsing_started", "announce_no": "ANNOUNCE-2026-001"}
    assert len(calls) == 1
    assert calls[0][0] == ann_id
    assert calls[0][2] == "https://x/a.pdf"


def test_parse_already_parsed_returns_count(client: TestClient, db) -> None:
    ann_id = _insert_announcement(db, attachment="https://x/a.pdf")
    _insert_record(db, announcement_id=ann_id)

    r = client.post("/api/announcements/ANNOUNCE-2026-001/parse")
    assert r.status_code == 200
    assert r.json() == {"status": "already_parsed", "record_count": 1}


def test_parse_self_heals_from_record_but_still_needs_attachment(client: TestClient, db) -> None:
    """公告只在 announcement_record 中：自愈写入 announcements，但因无附件仍 400。"""
    _insert_record(db)

    r = client.post("/api/announcements/ANNOUNCE-2026-001/parse")
    assert r.status_code == 400
    assert "没有附件" in r.json()["detail"]
    row = db.fetchone("SELECT announce_no, title FROM announcements WHERE announce_no = ?",
                      ("ANNOUNCE-2026-001",))
    assert row is not None
    assert row["title"] == "2026年第1号公告"


# ── parse-status ─────────────────────────────────────────────────────


def test_parse_status_missing_announcement_returns_404(client: TestClient) -> None:
    r = client.get("/api/announcements/NOPE/parse-status")
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]


def test_parse_status_pending_and_completed(client: TestClient, db) -> None:
    ann_id = _insert_announcement(db)
    r = client.get("/api/announcements/ANNOUNCE-2026-001/parse-status")
    assert r.json() == {"status": "pending", "record_count": 0}

    _insert_record(db, announcement_id=ann_id)
    _insert_record(db, announcement_id=ann_id, standard_number="GB/T 2-2020")
    r = client.get("/api/announcements/ANNOUNCE-2026-001/parse-status")
    assert r.json() == {"status": "completed", "record_count": 2}


# ── PATCH 单行编辑 ───────────────────────────────────────────────────


def test_patch_missing_record_returns_404(client: TestClient) -> None:
    r = client.patch("/api/announcement-record/999", json={"std_name": "x"})
    assert r.status_code == 404


def test_patch_approved_record_is_readonly(client: TestClient, db) -> None:
    rid = _insert_record(db, status="approved")
    r = client.patch(f"/api/announcement-record/{rid}", json={"std_name": "x"})
    assert r.status_code == 400
    assert "不可编辑" in r.json()["detail"]


def test_patch_without_allowed_fields_returns_400(client: TestClient, db) -> None:
    rid = _insert_record(db)
    r = client.patch(f"/api/announcement-record/{rid}", json={"ignored": "x", "std_name": None})
    assert r.status_code == 400
    assert "无有效更新字段" in r.json()["detail"]


def test_patch_updates_allowed_fields_and_moves_draft_to_review(client: TestClient, db) -> None:
    rid = _insert_record(db, status="draft")
    r = client.patch(
        f"/api/announcement-record/{rid}",
        json={"standard_number": "GB/T 2-2020", "ignored": "不要写库"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == rid
    assert body["status"] == "pending_review"

    row = db.fetchone("SELECT standard_number, std_name, status FROM announcement_record WHERE id = ?", (rid,))
    assert row is not None
    assert row["standard_number"] == "GB/T 2-2020"
    assert row["std_name"] == "质量管理体系"  # 未提交的字段保持原值
    assert row["status"] == "pending_review"


# ── 批量确认 ─────────────────────────────────────────────────────────


def test_batch_approve_empty_ids_returns_400(client: TestClient) -> None:
    r = client.post("/api/announcement-record/batch-approve", json={"ids": []})
    assert r.status_code == 400
    assert "未选择" in r.json()["detail"]


def test_batch_approve_unknown_ids_returns_400(client: TestClient) -> None:
    r = client.post("/api/announcement-record/batch-approve", json={"ids": [999]})
    assert r.status_code == 400
    assert "未找到有效记录" in r.json()["detail"]


def test_batch_approve_missing_fields_reports_errors(client: TestClient, db) -> None:
    rid = _insert_record(db, std_name="")
    r = client.post("/api/announcement-record/batch-approve", json={"ids": [rid]})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["approved_count"] == 0
    assert any("名称为空" in e for e in detail["errors"])


def test_batch_approve_success_sets_approved(client: TestClient, db) -> None:
    rid1 = _insert_record(db, standard_number="GB/T 1-2020")
    rid2 = _insert_record(db, standard_number="GB/T 2-2020", status="draft")

    r = client.post("/api/announcement-record/batch-approve", json={"ids": [rid1, rid2]})
    assert r.status_code == 200
    assert r.json() == {"status": "completed", "approved_count": 2, "errors": []}

    rows = db.fetchall(
        "SELECT status, approved_at FROM announcement_record WHERE id IN (?, ?)", (rid1, rid2)
    )
    assert [row["status"] for row in rows] == ["approved", "approved"]
    assert all(row["approved_at"] for row in rows)
