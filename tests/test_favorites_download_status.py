# tests/test_favorites_download_status.py — 收藏下载状态接口契约与"取最新一条"守卫
"""覆盖（2026-09-21 下载状态改造前置排查结论的落地验证）：

1. `GET /api/favorites` 返回下载队列四字段，且队列行不存在时为 None（LEFT JOIN 保留收藏行）
2. **守卫**：同一 favorite_id 存在多行时，返回 last_attempt 最大那条；并列时取 id 最大那条
3. `GET /api/favorites/{record_id}/status` 语义归位到 favorite_downloads，
   查询键为 record_id（= announcement_record.id）+ user_id
4. 多用户隔离：他人同 record_id 的队列行不得串到当前用户
5. `POST /api/favorites/batch-status` 同步返回下载四字段（公告详情页据它显示进度）

数据库用生产迁移链建表（`Database(path)`），测试数据用原生 SQL 构造，专门制造
"同一 favorite_id 多行"的脏数据，以验证 API 层行为而非 ORM/约束。
"""

from __future__ import annotations

import os
import sys

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from docker.api.favorites import (  # noqa: E402
    BatchStatusRequest,
    batch_get_favorite_status,
    get_favorite_status,
    list_favorites,
)
from pilotstd.core.db.database import Database  # noqa: E402

USER_A, USER_B = 9101, 9102
REC_DUP, REC_PLAIN, REC_EMPTY, REC_OTHER_USER, REC_TIE2 = 91001, 91002, 91003, 91004, 91005
FAV_ONE, FAV_TIE, FAV_EMPTY, FAV_OTHER_USER = 92001, 92002, 92004, 92005


@pytest.fixture()
def db(tmp_path):
    """独立库（生产迁移链建表）+ 脏数据：同一 favorite_id 多行 / 并列 last_attempt。"""
    database = Database(str(tmp_path / "favorites_status.db"))
    _seed(database)
    yield database
    database.close_all()


def _seed(db: Database) -> None:
    for uid, name in ((USER_A, "fav_user_a"), (USER_B, "fav_user_b")):
        db.execute(
            "INSERT INTO users (id, username, password_hash, salt, role) VALUES (?, ?, 'x', 'y', 'user')",
            (uid, name),
        )
    for rid, std_no in (
        (REC_DUP, "GB/T 91001-2026"),
        (REC_PLAIN, "GB/T 91002-2026"),
        (REC_EMPTY, "GB/T 91003-2026"),
        (REC_OTHER_USER, "GB/T 91004-2026"),
        (REC_TIE2, "GB/T 91005-2026"),
    ):
        db.execute(
            "INSERT INTO announcement_record (id, source_site, pid, announce_no, standard_number,"
            " std_name, publish_date, fetched_at) VALUES (?, 'announcement_gb', ?, '2026年第99号',"
            " ?, '测试标准', '2026-01-01', '2026-01-02')",
            (rid, f"pid-{rid}", std_no),
        )
    for fav_id, uid, rid in (
        (FAV_ONE, USER_A, REC_DUP),
        (FAV_TIE, USER_A, REC_PLAIN),
        (FAV_EMPTY, USER_A, REC_EMPTY),
        (FAV_OTHER_USER, USER_B, REC_OTHER_USER),
    ):
        db.execute(
            "INSERT INTO user_favorites (id, user_id, record_id, status) VALUES (?, ?, ?, 'pending')",
            (fav_id, uid, rid),
        )

    # ── 脏数据 1：同一 favorite_id（FAV_ONE）两行，last_attempt 不同 ──
    # UNIQUE(favorite_id, record_id) 只拦"同收藏同记录"，不同 record_id 的多行是允许的
    db.execute(
        "INSERT INTO favorite_downloads (id, favorite_id, user_id, record_id, status,"
        " error_message, retry_count, last_attempt, updated_at)"
        " VALUES (93001, ?, ?, ?, 'failed', '旧行的错误', 3, '2026-01-01', '2026-01-01 00:00:00')",
        (FAV_ONE, USER_A, REC_PLAIN),
    )
    db.execute(
        "INSERT INTO favorite_downloads (id, favorite_id, user_id, record_id, status,"
        " error_message, retry_count, last_attempt, updated_at)"
        " VALUES (93002, ?, ?, ?, 'done', NULL, 0, '2026-03-01', '2026-03-01 00:00:00')",
        (FAV_ONE, USER_A, REC_DUP),
    )
    # ── 脏数据 2：同一 favorite_id（FAV_TIE）两行 last_attempt 并列，应取 id 更大者 ──
    db.execute(
        "INSERT INTO favorite_downloads (id, favorite_id, user_id, record_id, status,"
        " retry_count, last_attempt, updated_at)"
        " VALUES (93003, ?, ?, ?, 'failed', 1, '2026-05-01', '2026-05-01 00:00:00')",
        (FAV_TIE, USER_A, REC_PLAIN),
    )
    db.execute(
        "INSERT INTO favorite_downloads (id, favorite_id, user_id, record_id, status,"
        " retry_count, last_attempt, updated_at)"
        " VALUES (93004, ?, ?, ?, 'done', 0, '2026-05-01', '2026-05-02 00:00:00')",
        (FAV_TIE, USER_A, REC_TIE2),
    )
    # ── 隔离用：他人对同一 record_id 的队列行，且时间更新（查漏 user_id 就会被它串到） ──
    db.execute(
        "INSERT INTO favorite_downloads (id, favorite_id, user_id, record_id, status,"
        " retry_count, last_attempt, updated_at)"
        " VALUES (93005, ?, ?, ?, 'failed', 9, '2026-09-01', '2026-09-01 00:00:00')",
        (FAV_OTHER_USER, USER_B, REC_DUP),
    )
    assert db.fetchone("SELECT COUNT(*) AS c FROM favorite_downloads")["c"] == 5


def _item(result: dict, record_id: int) -> dict:
    for fav in result["favorites"]:
        if fav["record_id"] == record_id:
            return fav
    raise AssertionError(f"收藏列表里没有 record_id={record_id}: {result['favorites']}")


class TestLatestDownloadSelection:
    """守卫：同一 favorite_id 多行时必须取最新一条（而不是任意一条/第一行）。"""

    def test_favorites_api_returns_latest_download_when_multiple_records_exist(self, db):
        """last_attempt 更大的那行胜出，且四字段同源（不串行）。"""
        result = list_favorites(user_id=USER_A, db=db)
        fav = _item(result, REC_DUP)

        assert fav["download_status"] == "done", "应取 last_attempt=2026-03-01 的那行"
        assert fav["last_attempt"] == "2026-03-01"
        assert fav["download_error"] is None, "不得串到旧行的错误信息"
        assert fav["download_updated_at"] == "2026-03-01 00:00:00"

    def test_favorites_api_breaks_ties_by_row_id(self, db):
        """last_attempt 并列时按 id 倒序兜底，取值确定。"""
        result = list_favorites(user_id=USER_A, db=db)
        fav = _item(result, REC_PLAIN)

        assert fav["last_attempt"] == "2026-05-01"
        assert fav["download_status"] == "done", "并列应取 id 更大的 93004 行"

    def test_favorites_api_download_fields_none_without_queue_row(self, db):
        """没有队列行的收藏：四字段为 None，但收藏行本身仍在列表里（LEFT JOIN）。"""
        result = list_favorites(user_id=USER_A, db=db)
        fav = _item(result, REC_EMPTY)

        assert fav["id"] == FAV_EMPTY
        assert fav["download_status"] is None
        assert fav["download_error"] is None
        assert fav["last_attempt"] is None
        assert fav["download_updated_at"] is None


class TestStatusEndpointSemantics:
    """/status 语义归位：查 favorite_downloads，键为 record_id + user_id。"""

    def test_status_endpoint_reads_download_queue_by_record_and_user(self, db):
        result = get_favorite_status(record_id=REC_DUP, user_id=USER_A, db=db)

        assert result["favorite_id"] == FAV_ONE
        assert result["status"] == "done"
        assert result["download_status"] == "done", "标准键与旧键同值"
        assert result["last_attempt"] == "2026-03-01"

    def test_status_endpoint_isolates_users(self, db):
        """他人对同一 record_id 的更新行不得串入（隔离键缺 user_id 时此断言会失败）。"""
        result = get_favorite_status(record_id=REC_DUP, user_id=USER_A, db=db)

        assert result["status"] != "failed", "串到了 USER_B 的队列行"
        assert result["retry_count"] == 0, "串到了 USER_B 的重试计数 9"

    def test_status_endpoint_returns_none_without_queue_row(self, db):
        result = get_favorite_status(record_id=REC_EMPTY, user_id=USER_A, db=db)

        assert result["status"] is None
        assert result["download_status"] is None
        assert result["favorite_id"] is None


class TestBatchStatusContract:
    """批量接口（公告详情页用）与列表/单条同名同义。"""

    def test_batch_status_includes_download_fields(self, db):
        req = BatchStatusRequest(record_ids=[REC_DUP, REC_EMPTY, REC_OTHER_USER])
        result = batch_get_favorite_status(req=req, user_id=USER_A, db=db)
        statuses = result["statuses"]

        assert statuses[str(REC_DUP)]["download_status"] == "done"
        assert statuses[str(REC_DUP)]["last_attempt"] == "2026-03-01"
        assert statuses[str(REC_EMPTY)]["download_status"] is None, "已收藏但无队列行"
        assert statuses[str(REC_OTHER_USER)] is None, "他人收藏对当前用户不可见"

    def test_batch_status_empty_request(self, db):
        result = batch_get_favorite_status(req=BatchStatusRequest(record_ids=[]), user_id=USER_A, db=db)
        assert result == {"statuses": {}}
