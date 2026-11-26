"""pilotstd/manager/standard_service.py 补测 — 状态映射/SQL构建/统计/分页全覆盖。"""
from unittest.mock import MagicMock

import pytest

from pilotstd.core.status import Status
from pilotstd.manager.standard_service import StandardService


@pytest.fixture
def mock_mgr():
    mgr = MagicMock()
    mgr.db.fetchall.return_value = []
    mgr.db.fetchone.return_value = None
    return mgr


@pytest.fixture
def svc(mock_mgr):
    return StandardService(mock_mgr)


class TestMapFilterStatus:
    """_map_filter_status 状态映射 — 正常×2 + 边界×1。"""

    def test_current_returns_exact_match(self):
        """现行 → (["现行"], None) 精确匹配。"""
        vals, op = StandardService._map_filter_status(Status.ACTIVE.value)
        assert vals == [Status.ACTIVE.value]
        assert op is None

    def test_abolished_returns_in_operator(self):
        """已废止 → IN 操作符匹配废止+被代替+作废（废止族含「作废」）。"""
        vals, op = StandardService._map_filter_status(Status.WITHDRAWN_NORMALIZED.value)
        assert Status.WITHDRAWN.value in vals
        assert Status.SUPERSEDED.value in vals
        assert Status.VOIDED.value in vals, "作废 ∈ ABOLISHED_STATUSES，筛选废止族必须包含它"
        assert op == "IN"

    def test_unknown_returns_not_in_operator(self):
        """未知 → NOT IN 操作符排除已知状态，且必须排除「作废」（否则口径自相矛盾）。"""
        vals, op = StandardService._map_filter_status(Status.UNKNOWN.value)
        assert Status.ACTIVE.value in vals
        assert Status.VOIDED.value in vals, "作废属废止族，不得被折叠进未知桶"
        assert op == "NOT IN"

    def test_arbitrary_status_returns_exact(self):
        """未知状态名直接透传为精确匹配。"""
        vals, op = StandardService._map_filter_status("custom_status")
        assert vals == ["custom_status"]
        assert op is None


class TestBuildWhere:
    """_build_where SQL 构建 — 正常×2 + 边界×1 + 状态转换×1。"""

    def test_no_filters_returns_basic_where(self):
        """空 filters 只包含 status IS NOT NULL。"""
        sql, params = StandardService._build_where(None)
        assert "status IS NOT NULL" in sql
        assert params == []

    def test_status_filter_current(self):
        """status=现行 生成 status = ?"""
        sql, params = StandardService._build_where({"status": Status.ACTIVE.value})
        assert "status = ?" in sql
        assert params == [Status.ACTIVE.value]

    def test_status_filter_abolished(self):
        """status=已废止 生成 status IN (?, ?, ?)，含废止/被代替/作废。"""
        sql, params = StandardService._build_where({"status": Status.WITHDRAWN_NORMALIZED.value})
        assert "IN (?, ?, ?)" in sql
        assert len(params) == 3
        assert Status.VOIDED.value in params

    def test_keyword_filter(self):
        """keyword 过滤生成复合 LIKE 条件。"""
        sql, params = StandardService._build_where({"keyword": "GB/T"})
        assert "LIKE ?" in sql
        assert len(params) == 2
        assert "%GB/T%" in params[0]

    def test_combined_status_and_keyword(self):
        """status + keyword 组合过滤。"""
        sql, params = StandardService._build_where({"status": Status.ACTIVE.value, "keyword": "12345"})
        assert "status = ?" in sql
        assert "LIKE ?" in sql
        assert Status.ACTIVE.value in params

    def test_alias_prefix_in_column_refs(self):
        """alias='f' 时所有列引用带 f. 前缀。"""
        sql, _ = StandardService._build_where({"status": Status.ACTIVE.value}, alias="f")
        assert "f.status = ?" in sql

    def test_not_in_operator_for_unknown(self):
        """status=未知 生成 NOT IN 子句，排除 现行/废止/被代替/作废 四类。"""
        sql, params = StandardService._build_where({"status": Status.UNKNOWN.value})
        assert "NOT IN" in sql
        assert len(params) == 4  # 现行, 废止, 被代替, 作废
        assert Status.VOIDED.value in params


class TestGetStats:
    """get_stats 统计 — 正常×2 + 边界×1。"""

    def test_normal_stats_with_mixed_statuses(self, mock_mgr, svc):
        """混合状态数据返回正确分组统计。"""
        mock_mgr.db.fetchall.return_value = [
            {"status": Status.ACTIVE.value, "cnt": 100},
            {"status": Status.WITHDRAWN.value, "cnt": 20},
            {"status": Status.SUPERSEDED.value, "cnt": 5},
            {"status": "custom", "cnt": 3},
        ]
        result = svc.get_stats()
        assert result["total"] == 128
        assert result["by_status"][Status.ACTIVE.value] == 100
        assert result["by_status"][Status.WITHDRAWN_NORMALIZED.value] == 25
        assert result["by_status"][Status.UNKNOWN.value] == 3

    def test_empty_stats(self, mock_mgr, svc):
        """空数据库返回全部为零的统计。"""
        mock_mgr.db.fetchall.return_value = []
        result = svc.get_stats()
        assert result["total"] == 0
        assert result["by_status"][Status.ACTIVE.value] == 0

    def test_only_current_status(self, mock_mgr, svc):
        """仅有现行状态时其他分组为零。"""
        mock_mgr.db.fetchall.return_value = [{"status": Status.ACTIVE.value, "cnt": 50}]
        result = svc.get_stats()
        assert result["total"] == 50
        assert result["by_status"][Status.WITHDRAWN_NORMALIZED.value] == 0
        assert result["by_status"][Status.UNKNOWN.value] == 0

    def test_voided_counted_in_abolished_not_unknown(self, mock_mgr, svc):
        """生产口径复现：「作废」58 条必须计入已废止、并从未知中剔除。

        数据来源：docs/plans/2026-11-24-p1-unknown-standards.md 附录 B
        （现行 572 / 废止 95 / 作废 58 / 被代替 21 / 即将实施 20 / 未生效 10）。
        期望：已废止 95+21+58=174，未知 20+10=30，total 仍为 776（守恒）。
        """
        mock_mgr.db.fetchall.return_value = [
            {"status": Status.ACTIVE.value, "cnt": 572},
            {"status": Status.WITHDRAWN.value, "cnt": 95},
            {"status": Status.VOIDED.value, "cnt": 58},
            {"status": Status.SUPERSEDED.value, "cnt": 21},
            {"status": Status.UPCOMING.value, "cnt": 20},
            {"status": "未生效", "cnt": 10},
        ]
        result = svc.get_stats()
        assert result["total"] == 776
        assert result["by_status"][Status.ACTIVE.value] == 572
        assert result["by_status"][Status.WITHDRAWN_NORMALIZED.value] == 174
        assert result["by_status"][Status.UNKNOWN.value] == 30

    def test_voided_alone_never_lands_in_unknown(self, mock_mgr, svc):
        """仅「作废」时：已废止=58、未知=0（作废不得被折叠进未知桶）。"""
        mock_mgr.db.fetchall.return_value = [{"status": Status.VOIDED.value, "cnt": 58}]
        result = svc.get_stats()
        assert result["by_status"][Status.WITHDRAWN_NORMALIZED.value] == 58
        assert result["by_status"][Status.UNKNOWN.value] == 0


class TestGetList:
    """get_list 分页列表 — 正常×2 + 边界×1 + 状态转换×1。"""

    def test_normal_paginated_list(self, mock_mgr, svc):
        """分页查询返回 items + total + page + size。"""
        mock_mgr.db.fetchone.return_value = {"cnt": 42}
        mock_rows = [
            {"id": 1, "standard_number": "GB/T 1.1", "status": Status.ACTIVE.value,
             "std_name": "标准1", "last_checked_at": None, "check_count": 0},
            {"id": 2, "standard_number": "ISO 9001", "status": Status.ACTIVE.value,
             "std_name": "标准2", "last_checked_at": "2026-01-01", "check_count": 3},
        ]
        mock_mgr.db.fetchall.return_value = mock_rows
        result = svc.get_list(page=1, size=2)
        assert result["total"] == 42
        assert result["page"] == 1
        assert result["size"] == 2
        assert len(result["items"]) == 2

    def test_page_two_offset(self, mock_mgr, svc):
        """第二页 offset = (page-1)*size。"""
        mock_mgr.db.fetchone.return_value = {"cnt": 100}
        mock_mgr.db.fetchall.return_value = []
        svc.get_list(page=2, size=20)
        call_args = mock_mgr.db.fetchall.call_args[0]
        # 确认 LIMIT ? OFFSET ? 参数正确
        assert call_args[1][-2] == 20  # size
        assert call_args[1][-1] == 20  # offset = (2-1)*20

    def test_boundary_empty_result_zero_total(self, mock_mgr, svc):
        """空结果 total=0 不崩溃。"""
        mock_mgr.db.fetchone.return_value = None
        mock_mgr.db.fetchall.return_value = []
        result = svc.get_list()
        assert result["total"] == 0

    def test_state_filtered_query_includes_where(self, mock_mgr, svc):
        """带 status 过滤的列表查询 SQL 包含过滤条件。"""
        mock_mgr.db.fetchone.return_value = {"cnt": 5}
        mock_mgr.db.fetchall.return_value = []
        svc.get_list(filters={"status": Status.WITHDRAWN_NORMALIZED.value})
        sql_called = mock_mgr.db.fetchall.call_args[0][0]
        assert "IN (?, ?)" in sql_called or "status" in sql_called

    def test_count_query_includes_table_alias(self, mock_mgr, svc):
        """COUNT 查询必须带表别名 f，否则 where 子句的 f.status 列引用无法解析。"""
        mock_mgr.db.fetchone.return_value = {"cnt": 0}
        mock_mgr.db.fetchall.return_value = []
        svc.get_list()
        count_sql = mock_mgr.db.fetchone.call_args[0][0]
        assert "FROM file_index f" in count_sql


class TestExplicitStatusBuckets:
    """N2：`unknown` 从「四值之外即未知」的补集机制改为**显式枚举分桶**。

    背景：`docs/plans/2026-11-25-p1-unknown-refresh.md` §5.2 —— A1 只修了 `作废` 这个
    具体值，没有修机制；任何枚举外新值都会被静默吞进「未知」、既不报错也不告警。
    """

    def test_every_status_member_belongs_to_exactly_one_bucket(self):
        """守卫：新增 `Status` 枚举值必须显式进统计分桶，否则本测试红。"""
        from pilotstd.manager.standard_service import _STATUS_BUCKETS, _STATUS_TO_BUCKET

        all_bucketed = [member.value for members in _STATUS_BUCKETS.values() for member in members]
        assert len(all_bucketed) == len(set(all_bucketed)), "同一状态值不得重复归桶"
        assert set(all_bucketed) == {member.value for member in Status}, "每个枚举值必须且只能归一个桶"
        assert set(_STATUS_TO_BUCKET) == {member.value for member in Status}

    def test_bucket_mapping_matches_caliber(self):
        """分桶口径：现行→active；废止族→已废止；其余（即将实施/过期/待确认/未知）→未知。"""
        from pilotstd.manager.standard_service import _STATUS_TO_BUCKET

        assert _STATUS_TO_BUCKET[Status.ACTIVE.value] == Status.ACTIVE.value
        for abolished in (Status.WITHDRAWN.value, Status.WITHDRAWN_NORMALIZED.value,
                          Status.VOIDED.value, Status.SUPERSEDED.value):
            assert _STATUS_TO_BUCKET[abolished] == Status.WITHDRAWN_NORMALIZED.value
        for unknown_bucket in (Status.UPCOMING.value, Status.EXPIRED.value,
                               Status.PENDING.value, Status.UNKNOWN.value):
            assert _STATUS_TO_BUCKET[unknown_bucket] == Status.UNKNOWN.value

    def test_unknown_filter_derived_from_explicit_buckets(self):
        """`未知` 筛选的 NOT IN 取值来自显式分桶（而非手写四值清单）。"""
        from pilotstd.manager.standard_service import _STATUS_FILTER_VALUES, _STATUS_TO_BUCKET

        vals, op = StandardService._map_filter_status(Status.UNKNOWN.value)
        assert op == "NOT IN"
        expected = [
            value
            for bucket, values in _STATUS_FILTER_VALUES.items()
            if bucket != Status.UNKNOWN.value
            for value in values
        ]
        assert vals == expected
        assert all(_STATUS_TO_BUCKET[v] != Status.UNKNOWN.value for v in vals)

    def test_junk_status_counted_in_unknown_and_warned_once(self, mock_mgr, caplog):
        """枚举外脏值 → 计入未知 + `logger.warning` 一次（带取值与样本），不重复刷屏。"""
        import logging

        from pilotstd.manager.standard_service import StandardService as _Svc

        mock_mgr.db.fetchall.side_effect = [
            [
                {"status": Status.ACTIVE.value, "cnt": 572},
                {"status": "custom_dirty", "cnt": 3},
            ],
            [{"standard_number": "GB/T 99999-2020"}],  # 样本查询
            [  # 第二次 get_stats 只查分布（同一枚举外值不再重复告警/查样本）
                {"status": Status.ACTIVE.value, "cnt": 572},
                {"status": "custom_dirty", "cnt": 3},
            ],
        ]
        svc = _Svc(mock_mgr)
        caplog.set_level(logging.WARNING, logger="pilotstd.manager.standard_service")

        first = svc.get_stats()
        second = svc.get_stats()

        assert first["by_status"][Status.UNKNOWN.value] == 3, "枚举外值必须计入未知桶"
        assert first["total"] == 575
        assert second["by_status"][Status.UNKNOWN.value] == 3
        warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
        assert len(warnings) == 1, "同一枚举外值只告警一次"
        message = warnings[0].getMessage()
        assert "custom_dirty" in message
        assert "GB/T 99999-2020" in message, "告警必须带样本，便于定位脏数据"

    def test_known_statuses_do_not_warn(self, mock_mgr, caplog):
        """合法枚举值不触发告警（只有枚举外值才告警）。"""
        import logging

        mock_mgr.db.fetchall.return_value = [
            {"status": Status.ACTIVE.value, "cnt": 1},
            {"status": Status.UPCOMING.value, "cnt": 1},
            {"status": Status.UNKNOWN.value, "cnt": 1},
        ]
        svc = StandardService(mock_mgr)
        caplog.set_level(logging.WARNING, logger="pilotstd.manager.standard_service")
        svc.get_stats()
        assert [rec for rec in caplog.records if rec.levelno == logging.WARNING] == []


class TestGetStatsUpcoming:
    """2026-11-26：`get_stats()` 增加 `upcoming`（即将实施），供 API 拆 4 桶。"""

    def test_upcoming_returned_separately(self, tmp_path):
        """即将实施既进「未知」桶（既有口径），也单独回传 `upcoming`。"""
        from unittest.mock import MagicMock

        from pilotstd.core.db.database import Database
        from pilotstd.manager.standard_service import StandardService

        db = Database(str(tmp_path / "s.db"))
        db.execute("INSERT INTO file_index (status, file_path) VALUES ('即将实施', '/x/a.pdf')")
        db.execute("INSERT INTO file_index (status, file_path) VALUES ('现行', '/x/b.pdf')")
        mgr = MagicMock()
        mgr.db = db
        stats = StandardService(mgr).get_stats()
        assert stats["upcoming"] == 1
        assert stats["by_status"]["现行"] == 1
        assert stats["total"] == 2
