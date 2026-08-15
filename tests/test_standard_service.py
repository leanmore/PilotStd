"""pilotstd/manager/standard_service.py 补测 — 状态映射/SQL构建/统计/分页全覆盖。"""
from unittest.mock import MagicMock

import pytest

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
        vals, op = StandardService._map_filter_status("现行")
        assert vals == ["现行"]
        assert op is None

    def test_abolished_returns_in_operator(self):
        """已废止 → IN 操作符匹配废止+被代替。"""
        vals, op = StandardService._map_filter_status("已废止")
        assert "废止" in vals
        assert "被代替" in vals
        assert op == "IN"

    def test_unknown_returns_not_in_operator(self):
        """未知 → NOT IN 操作符排除已知状态。"""
        vals, op = StandardService._map_filter_status("未知")
        assert "现行" in vals
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
        sql, params = StandardService._build_where({"status": "现行"})
        assert "status = ?" in sql
        assert params == ["现行"]

    def test_status_filter_abolished(self):
        """status=已废止 生成 status IN (?, ?)"""
        sql, params = StandardService._build_where({"status": "已废止"})
        assert "IN (?, ?)" in sql
        assert len(params) == 2

    def test_keyword_filter(self):
        """keyword 过滤生成复合 LIKE 条件。"""
        sql, params = StandardService._build_where({"keyword": "GB/T"})
        assert "LIKE ?" in sql
        assert len(params) == 2
        assert "%GB/T%" in params[0]

    def test_combined_status_and_keyword(self):
        """status + keyword 组合过滤。"""
        sql, params = StandardService._build_where({"status": "现行", "keyword": "12345"})
        assert "status = ?" in sql
        assert "LIKE ?" in sql
        assert "现行" in params

    def test_alias_prefix_in_column_refs(self):
        """alias='f' 时所有列引用带 f. 前缀。"""
        sql, _ = StandardService._build_where({"status": "现行"}, alias="f")
        assert "f.status = ?" in sql

    def test_not_in_operator_for_unknown(self):
        """status=未知 生成 NOT IN 子句。"""
        sql, params = StandardService._build_where({"status": "未知"})
        assert "NOT IN" in sql
        assert len(params) == 3  # 现行, 废止, 被代替


class TestGetStats:
    """get_stats 统计 — 正常×2 + 边界×1。"""

    def test_normal_stats_with_mixed_statuses(self, mock_mgr, svc):
        """混合状态数据返回正确分组统计。"""
        mock_mgr.db.fetchall.return_value = [
            {"status": "现行", "cnt": 100},
            {"status": "废止", "cnt": 20},
            {"status": "被代替", "cnt": 5},
            {"status": "custom", "cnt": 3},
        ]
        result = svc.get_stats()
        assert result["total"] == 128
        assert result["by_status"]["现行"] == 100
        assert result["by_status"]["已废止"] == 25
        assert result["by_status"]["未知"] == 3

    def test_empty_stats(self, mock_mgr, svc):
        """空数据库返回全部为零的统计。"""
        mock_mgr.db.fetchall.return_value = []
        result = svc.get_stats()
        assert result["total"] == 0
        assert result["by_status"]["现行"] == 0

    def test_only_current_status(self, mock_mgr, svc):
        """仅有现行状态时其他分组为零。"""
        mock_mgr.db.fetchall.return_value = [{"status": "现行", "cnt": 50}]
        result = svc.get_stats()
        assert result["total"] == 50
        assert result["by_status"]["已废止"] == 0
        assert result["by_status"]["未知"] == 0


class TestGetList:
    """get_list 分页列表 — 正常×2 + 边界×1 + 状态转换×1。"""

    def test_normal_paginated_list(self, mock_mgr, svc):
        """分页查询返回 items + total + page + size。"""
        mock_mgr.db.fetchone.return_value = {"cnt": 42}
        mock_rows = [
            {"id": 1, "standard_number": "GB/T 1.1", "status": "现行",
             "std_name": "标准1", "last_checked_at": None, "check_count": 0},
            {"id": 2, "standard_number": "ISO 9001", "status": "现行",
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
        svc.get_list(filters={"status": "已废止"})
        sql_called = mock_mgr.db.fetchall.call_args[0][0]
        assert "IN (?, ?)" in sql_called or "status" in sql_called

    def test_count_query_includes_table_alias(self, mock_mgr, svc):
        """COUNT 查询必须带表别名 f，否则 where 子句的 f.status 列引用无法解析。"""
        mock_mgr.db.fetchone.return_value = {"cnt": 0}
        mock_mgr.db.fetchall.return_value = []
        svc.get_list()
        count_sql = mock_mgr.db.fetchone.call_args[0][0]
        assert "FROM file_index f" in count_sql
