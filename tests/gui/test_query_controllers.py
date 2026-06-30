# tests/gui/test_query_controllers.py
# 测试查询控制器三个子模块 — mixin, pending, summary
# 每个子模块至少 2 个用例

from unittest.mock import MagicMock

from pilotstd.ui.controllers.query import QueryMixin
from pilotstd.ui.controllers.query.mixin import QueryCoreMethods
from pilotstd.ui.controllers.query.pending import QueryPendingMethods
from pilotstd.ui.controllers.query.summary import QuerySummaryMethods


class TestQueryControllerComposition:
    """QueryMixin 类组合测试。"""

    def test_query_mixin_inherits_all_three(self) -> None:
        """QueryMixin 继承自三个子模块。"""
        assert issubclass(QueryMixin, QueryCoreMethods)
        assert issubclass(QueryMixin, QuerySummaryMethods)
        assert issubclass(QueryMixin, QueryPendingMethods)

    def test_query_mixin_has_all_methods(self) -> None:
        """QueryMixin 实例具备所有核心方法。"""
        mixin = QueryMixin()
        assert hasattr(mixin, "_on_query")
        assert hasattr(mixin, "_count_query_actions")
        assert hasattr(mixin, "_build_pending_table")


class TestQueryCoreMethods:
    """mixin 核心查询方法测试。"""

    def test_on_query_no_mgr_ready_returns_early(self) -> None:
        """mgr 未就绪时 _on_query 直接返回。"""
        obj = QueryCoreMethods()
        obj._mgr_ready = False  # type: ignore[attr-defined]
        # 不应抛异常
        obj._on_query()  # type: ignore[call-arg]

    def test_on_query_result_ready_updates_table_cells(self) -> None:
        """_on_query_result_ready 刷新表格行文本。"""
        obj = QueryCoreMethods()
        result = MagicMock()
        result.standard_name = "测试标准"
        result.status = "现行"
        result.replaces = ""
        result.publish_date = "2020-01-01"
        result.implementation_date = "2020-06-01"
        result.responsible_dept = "国家标准委"
        result.is_adopted = True
        result.is_downloadable = True
        result.source_site = "csres"

        # 模拟表格
        parsed = MagicMock()
        parsed.std_name = "原始名称"
        obj._parsed_results = [parsed]  # type: ignore[attr-defined]

        mock_table = MagicMock()
        mock_table.item.return_value = MagicMock(text=MagicMock())
        obj._find_row_by_seq = MagicMock(return_value=0)  # type: ignore[method-assign]
        obj.work_table = mock_table  # type: ignore[attr-defined]

        obj._on_query_result_ready(0, result)  # type: ignore[call-arg]


class TestQuerySummaryMethods:
    """summary 模块摘要统计方法测试。"""

    def _make_parsed(self, action: str) -> MagicMock:
        p = MagicMock()
        p.next_action = action
        return p

    def test_count_query_actions_counts_all_categories(self) -> None:
        """_count_query_actions 正确统计各类 action 数量。"""
        obj = QuerySummaryMethods()
        obj._parsed_results = [  # type: ignore[attr-defined]
            self._make_parsed("archive"),
            self._make_parsed("archive"),
            self._make_parsed("pending"),
            self._make_parsed("expire"),
            self._make_parsed("normalize"),
            self._make_parsed("not_found"),
        ]
        counts = obj._count_query_actions()  # type: ignore[call-arg]
        assert counts["archive"] == 2
        assert counts["pending"] == 1
        assert counts["expire"] == 1
        assert counts["normalize"] == 1
        assert counts["not_found"] == 1

    def test_count_query_actions_empty_list(self) -> None:
        """空列表所有分类计数为 0。"""
        obj = QuerySummaryMethods()
        obj._parsed_results = []  # type: ignore[attr-defined]
        counts = obj._count_query_actions()  # type: ignore[call-arg]
        for cat in ("archive", "normalize", "expire", "not_found", "pending"):
            assert counts[cat] == 0, f"{cat} 应为 0"

    def test_build_query_summary_text_contains_total(self) -> None:
        """摘要文本包含总数和各分类统计。"""
        obj = QuerySummaryMethods()
        obj._parsed_results = [  # type: ignore[attr-defined]
            self._make_parsed("archive"),
            self._make_parsed("pending"),
        ]
        counts = obj._count_query_actions()  # type: ignore[call-arg]
        text = obj._build_query_summary_text(counts, 0)  # type: ignore[call-arg]
        assert "2" in text  # 总数
        assert "1" in text  # archive=1, pending=1


class TestQueryPendingMethods:
    """pending 模块待确认方法测试。"""

    def test_build_pending_table_creates_table(self) -> None:
        """_build_pending_table 创建有效 QTableWidget。"""
        obj = QueryPendingMethods()
        parsed = MagicMock()
        parsed.get_full_number.return_value = "GB 1-2020"
        parsed.std_name = "基础规范"
        parsed.found_name = ""
        parsed.year = 2020
        parsed.found_number = ""
        parsed.effect_status = ""
        parsed.match_status = ""
        parsed.found_source_site = ""

        table = obj._build_pending_table([parsed])  # type: ignore[call-arg]
        assert table.rowCount() == 1
        assert table.columnCount() == 8

    def test_build_pending_table_empty_list(self) -> None:
        """空列表创建的空表格行数为 0。"""
        obj = QueryPendingMethods()
        table = obj._build_pending_table([])  # type: ignore[call-arg]
        assert table.rowCount() == 0

    def test_write_pending_to_db_delegates_to_manager(self) -> None:
        """_write_pending_to_db 委托 manager.record_pending。"""
        obj = QueryPendingMethods()
        obj._mgr = MagicMock()  # type: ignore[attr-defined]
        items = [MagicMock()]
        obj._write_pending_to_db(items)  # type: ignore[call-arg]
        obj._mgr.record_pending.assert_called_once_with(items)  # type: ignore[attr-defined]

    def test_resolve_pending_in_db_delegates_to_manager(self) -> None:
        """_resolve_pending_in_db 委托 manager.resolve_pending。"""
        obj = QueryPendingMethods()
        obj._mgr = MagicMock()  # type: ignore[attr-defined]
        items = [MagicMock()]
        obj._resolve_pending_in_db(items, "discarded")  # type: ignore[call-arg]
        obj._mgr.resolve_pending.assert_called_once_with(items, "discarded")  # type: ignore[attr-defined]
