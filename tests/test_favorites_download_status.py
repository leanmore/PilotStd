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

import asyncio
import json
import logging
import os
import sys

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from docker.api.favorites import (  # noqa: E402
    BatchStatusRequest,
    batch_get_favorite_status,
    export_favorites,
    get_favorite_status,
    list_favorites,
)
from pilotstd.core.db.database import Database  # noqa: E402

USER_A, USER_B = 9101, 9102
REC_DUP, REC_PLAIN, REC_EMPTY, REC_OTHER_USER, REC_TIE2 = 91001, 91002, 91003, 91004, 91005
FAV_ONE, FAV_TIE, FAV_EMPTY, FAV_OTHER_USER = 92001, 92002, 92004, 92005


class _FakeURL:
    """只暴露 path（模拟 Starlette URL：不含查询参数）。"""

    def __init__(self, path: str) -> None:
        self.path = path


class _FakeRequest:
    """最小 Request 替身：仅提供 headers 与 url.path（供 _log_status_api_call 使用）。"""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers
        self.url = _FakeURL(f"/api/favorites/{REC_DUP}/status")


def _fake_request(ua: str | None = "pytest-agent", referer: str | None = "http://nas/favorites") -> _FakeRequest:
    """构造带 UA/Referer 的请求替身（None 表示头缺失）。"""
    headers: dict[str, str] = {}
    if ua is not None:
        headers["user-agent"] = ua
    if referer is not None:
        headers["referer"] = referer
    return _FakeRequest(headers)


def _read_streaming_json(response) -> dict:
    """同步消费 StreamingResponse 的 JSON 分支（Starlette 可能把同步迭代器包成异步）。"""
    iterator = response.body_iterator
    chunks: list[bytes] = []

    def _append(chunk: object) -> None:
        chunks.append(chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8"))

    if hasattr(iterator, "__anext__"):

        async def _consume() -> None:
            async for chunk in iterator:
                _append(chunk)

        asyncio.run(_consume())
    else:
        for chunk in iterator:
            _append(chunk)
    return json.loads(b"".join(chunks).decode("utf-8"))


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
        result = get_favorite_status(record_id=REC_DUP, request=_fake_request(), user_id=USER_A, db=db)

        assert result["favorite_id"] == FAV_ONE
        assert result["status"] == "done"
        assert result["download_status"] == "done", "标准键与旧键同值"
        assert result["last_attempt"] == "2026-03-01"

    def test_status_endpoint_isolates_users(self, db):
        """他人对同一 record_id 的更新行不得串入（隔离键缺 user_id 时此断言会失败）。"""
        result = get_favorite_status(record_id=REC_DUP, request=_fake_request(), user_id=USER_A, db=db)

        assert result["status"] != "failed", "串到了 USER_B 的队列行"
        assert result["retry_count"] == 0, "串到了 USER_B 的重试计数 9"

    def test_status_endpoint_returns_none_without_queue_row(self, db):
        result = get_favorite_status(record_id=REC_EMPTY, request=_fake_request(), user_id=USER_A, db=db)

        assert result["status"] is None
        assert result["download_status"] is None
        assert result["favorite_id"] is None

    def test_status_endpoint_key_contract(self, db):
        """响应键集合契约（8 键）：标准键 + favorite_id/status + favorited，旧键不得回流。

        第三轮 #16：旧键（local_path/error_message/in_cooldown/abandoned/
        archive_retry_count）已删除；第三轮 #19：新增 `favorited`。
        """
        result = get_favorite_status(record_id=REC_DUP, request=_fake_request(), user_id=USER_A, db=db)

        assert set(result) == {
            "status",
            "favorite_id",
            "favorited",
            "download_status",
            "download_error",
            "last_attempt",
            "download_updated_at",
            "retry_count",
        }
        for removed in ("local_path", "in_cooldown", "abandoned", "archive_retry_count"):
            assert removed not in result, f"旧键 {removed} 不应再返回"

    def test_status_endpoint_key_contract_without_row(self, db):
        """无队列行时同样不得出现旧键；`favorited` 必须存在（否则两态不可区分）。"""
        result = get_favorite_status(record_id=REC_EMPTY, request=_fake_request(), user_id=USER_A, db=db)

        assert set(result) == {"status", "favorite_id", "download_status", "favorited"}


class TestStatusFavoritedSemantics:
    """#19 方案②：`favorited` 让"未收藏"与"收藏但无队列行"可区分。"""

    def test_favorited_true_with_queue_row(self, db):
        result = get_favorite_status(record_id=REC_DUP, request=_fake_request(), user_id=USER_A, db=db)

        assert result["favorited"] is True
        assert result["status"] == "done", "收藏且已归档"

    def test_favorited_true_without_queue_row(self, db):
        """收藏存在但无队列行（历史遗留，如技术债 #18）——修复前与"未收藏"返回完全相同。"""
        result = get_favorite_status(record_id=REC_EMPTY, request=_fake_request(), user_id=USER_A, db=db)

        assert result["favorited"] is True
        assert result["status"] is None
        assert result["download_status"] is None
        assert result["favorite_id"] is None

    def test_favorited_false_when_not_favorited(self, db):
        """USER_B 对 REC_PLAIN 既无收藏也无队列行 → favorited=False、status=None。"""
        result = get_favorite_status(record_id=REC_PLAIN, request=_fake_request(), user_id=USER_B, db=db)

        assert result["favorited"] is False
        assert result["status"] is None
        assert result["download_status"] is None

    def test_favorited_false_even_if_queue_row_exists_without_favorite(self, db):
        """脏数据边界：队列行存在但该用户没有收藏行 → favorited 以 user_favorites 为准。

        夹具里 (USER_B, REC_DUP) 恰是这种形态（隔离行 93005 的 favorite_id 指向 USER_B
        的另一条收藏），用于固化"favorited ≠ 队列行存在"这一语义。
        """
        result = get_favorite_status(record_id=REC_DUP, request=_fake_request(), user_id=USER_B, db=db)

        assert result["favorited"] is False
        assert result["status"] == "failed", "队列行本身存在（数据脏，非 API 缺陷）"

    def test_favorited_true_for_abandoned(self, db):
        """收藏且已放弃：favorited=true 且 status='abandoned'。"""
        db.execute(
            "INSERT INTO favorite_downloads (id, favorite_id, user_id, record_id, status,"
            " retry_count, last_attempt, updated_at)"
            " VALUES (93500, ?, ?, ?, 'abandoned', 7, '2026-08-01', '2026-08-01 00:00:00')",
            (FAV_EMPTY, USER_A, REC_EMPTY),
        )
        result = get_favorite_status(record_id=REC_EMPTY, request=_fake_request(), user_id=USER_A, db=db)

        assert result["favorited"] is True
        assert result["status"] == "abandoned"

    def test_favorited_matches_user_favorites_row_by_row(self, db):
        """`favorited` 必须与 user_favorites 表逐条一致（防查询键写错）。"""
        cases = [
            (USER_A, REC_DUP, True),
            (USER_A, REC_PLAIN, True),
            (USER_A, REC_EMPTY, True),
            (USER_A, REC_OTHER_USER, False),  # 他人收藏对本用户不可见
            (USER_B, REC_OTHER_USER, True),
            (USER_B, REC_DUP, False),
        ]
        for uid, rid, expected in cases:
            got = get_favorite_status(record_id=rid, request=_fake_request(), user_id=uid, db=db)["favorited"]
            assert got is expected, f"user={uid} record={rid}: {got} != {expected}"


class TestStatusDefensiveLogging:
    """/status 防御性日志：留调用来源线索，但不落敏感信息与查询参数。"""

    def test_logs_status_api_prefix_with_user_agent(self, db, caplog):
        with caplog.at_level(logging.INFO, logger="docker.api.favorites"):
            get_favorite_status(
                record_id=REC_DUP,
                request=_fake_request(ua="PilotStdClient/1.0", referer="http://nas/favorites"),
                user_id=USER_A,
                db=db,
            )

        records = [r.getMessage() for r in caplog.records if "[STATUS_API]" in r.getMessage()]
        assert records, "必须留下 [STATUS_API] 日志"
        message = records[-1]
        assert "PilotStdClient/1.0" in message, "必须记录 User-Agent（清理时的关键线索）"
        assert "http://nas/favorites" in message, "必须记录 Referer"
        assert f"/api/favorites/{REC_DUP}/status" in message

    def test_log_has_no_query_params(self, db, caplog):
        """只记路径：查询参数（可能含标准号等业务信息）一律不入日志。"""
        with caplog.at_level(logging.INFO, logger="docker.api.favorites"):
            get_favorite_status(record_id=REC_DUP, request=_fake_request(), user_id=USER_A, db=db)

        message = [r.getMessage() for r in caplog.records if "[STATUS_API]" in r.getMessage()][-1]
        assert "?" not in message, f"日志不得包含查询参数: {message}"

    def test_log_redacts_sensitive_headers(self, db, caplog):
        """UA / Referer 命中敏感关键字时整段脱敏，避免把凭证写进日志。"""
        with caplog.at_level(logging.INFO, logger="docker.api.favorites"):
            get_favorite_status(
                record_id=REC_DUP,
                request=_fake_request(
                    ua="curl/8.0 Authorization: Bearer abc123token",
                    referer="http://nas/favorites?api_key=secret-value",
                ),
                user_id=USER_A,
                db=db,
            )

        message = [r.getMessage() for r in caplog.records if "[STATUS_API]" in r.getMessage()][-1]
        lowered = message.lower()
        for forbidden in ("password", "token", "authorization", "secret", "api_key"):
            assert forbidden not in lowered, f"日志泄露敏感关键字 {forbidden}: {message}"
        assert "[redacted]" in message

    def test_log_survives_missing_headers(self, db, caplog):
        """无 UA / Referer 时不得抛异常，用占位符。"""
        with caplog.at_level(logging.INFO, logger="docker.api.favorites"):
            result = get_favorite_status(
                record_id=REC_DUP,
                request=_fake_request(ua=None, referer=None),
                user_id=USER_A,
                db=db,
            )

        assert result["favorited"] is True
        message = [r.getMessage() for r in caplog.records if "[STATUS_API]" in r.getMessage()][-1]
        assert "ua=- referer=-" in message


class TestFavoritesExportStandardNumber:
    """导出兜底（#18 补充项）：user_favorites.standard_number 为 NULL 时回退公告记录。

    v57 只加列不回填 → 历史行该列为 NULL → 导出标准号空白（现场实测 36 行）。
    数据已补，代码再加 COALESCE 兜底，防止未来再次出现空白列。
    """

    def test_export_falls_back_to_record_standard_number(self, db):
        db.execute("UPDATE user_favorites SET standard_number = NULL WHERE id = ?", (FAV_ONE,))

        response = export_favorites(user_id=USER_A, format="json", standard_type=None, db=db)
        payload = _read_streaming_json(response)

        row = next(f for f in payload["favorites"] if f["id"] == FAV_ONE)
        assert row["standard_number"] == "GB/T 91001-2026", "必须回退到 announcement_record.standard_number"

    def test_export_prefers_favorites_column_when_present(self, db):
        db.execute("UPDATE user_favorites SET standard_number = 'GB/T 自定义-2026' WHERE id = ?", (FAV_ONE,))

        response = export_favorites(user_id=USER_A, format="json", standard_type=None, db=db)
        payload = _read_streaming_json(response)

        row = next(f for f in payload["favorites"] if f["id"] == FAV_ONE)
        assert row["standard_number"] == "GB/T 自定义-2026", "有值时以 user_favorites 为准，不被回退覆盖"


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
