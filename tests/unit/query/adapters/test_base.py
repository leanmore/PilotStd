"""base.py 覆盖率补齐 — 目标: 84% → 95%+"""

import pytest
from unittest.mock import MagicMock, patch

from pilotstd.query.adapters.base import BaseAdapter
from pilotstd.query.models import QueryResult


class ConcreteAdapter(BaseAdapter):
    """最小实现，用于测试抽象基类"""

    supports_replaces_detail = False

    def init(self):
        self._session = MagicMock()
        self.API_URL = "https://test.api/search"

    @property
    def site_name(self) -> str:
        return "test_site"

    @property
    def site_label(self) -> str:
        return "Test Site"

    def _search(self, search_term: str):
        return None

    def _parse_result(self, record, search_term):
        return QueryResult(
            standard_number="GB/T 1234-2020",
            standard_name="Test Standard",
            source_site=self.site_name,
        )


@pytest.fixture
def adapter():
    a = ConcreteAdapter()
    a.init()
    return a


# ─── T1: _search_candidates 默认实现 ───


class TestSearchCandidates:
    def test_returns_empty_when_search_returns_none(self, adapter):
        """_search 返回 None → 返回空列表"""
        adapter._search = MagicMock(return_value=None)
        result = adapter._search_candidates("GB/T 1234-2020")
        assert result == []

    def test_returns_single_result_when_found(self, adapter):
        """_search 返回有效结果 → 返回包含该结果的列表"""
        mock_result = QueryResult(
            standard_number="GB/T 1234-2020",
            standard_name="Test Standard",
        )
        adapter._search = MagicMock(return_value=mock_result)
        result = adapter._search_candidates("GB/T 1234-2020")
        assert len(result) == 1
        assert result[0].standard_number == "GB/T 1234-2020"


# ─── T2: _try_exact_search different 状态 ───


class TestTryExactSearch:
    @patch("pilotstd.query.adapters.base.match_result")
    def test_accepts_different_status_when_specified(self, mock_match, adapter):
        """accepted_statuses 包含 'different' → 返回结果并设置 match_status"""
        mock_match.return_value = (None, "different")
        mock_result = QueryResult(
            standard_number="GB/T 1234-2020",
            standard_name="Test Standard",
            source_site="test_site",
        )
        mock_result.is_found = MagicMock(return_value=True)

        with patch.object(adapter, "_search", return_value=mock_result):
            result = adapter._try_exact_search(
                "GB/T 1234-2020",
                "GB/T",
                1234,
                2020,
                None,
                accepted_statuses={"exact", "different"},
            )
            assert result is not None
            assert result.match_status == "different"

    @patch("pilotstd.query.adapters.base.match_result")
    def test_rejects_status_not_in_accepted(self, mock_match, adapter):
        """匹配状态不在 accepted_statuses 中 → 返回 None"""
        mock_match.return_value = (None, "different")
        mock_result = QueryResult(
            standard_number="GB/T 1234-2020",
            standard_name="Test Standard",
            source_site="test_site",
        )
        mock_result.is_found = MagicMock(return_value=True)

        with patch.object(adapter, "_search", return_value=mock_result):
            result = adapter._try_exact_search(
                "GB/T 1234-2020",
                "GB/T",
                1234,
                2020,
                None,
                accepted_statuses={"exact"},
            )
            assert result is None


# ─── T3-T5: _search_progressive 回退路径 ───


class TestSearchProgressive:
    def test_space_format_fallback(self, adapter):
        """完整号搜索失败 → 空格格式回退"""
        calls = []

        def search_side_effect(term):
            calls.append(term)
            if term == "GB/T 1234 2020":
                return QueryResult(
                    standard_number=term,
                    standard_name="Test Standard",
                )
            return None

        adapter._search = MagicMock(side_effect=search_side_effect)

        result = adapter._search_progressive(
            logical_code="GB/T",
            number=1234,
            year=2020,
            part=None,
            num_prefix="",
            num_suffix="",
            target="GB/T 1234-2020",
        )

        assert result is not None
        assert any(c == "GB/T 1234 2020" for c in calls)

    def test_no_prefix_fallback(self, adapter):
        """空格格式也失败 → 去前缀回退"""
        calls = []

        def search_side_effect(term):
            calls.append(term)
            if term == "ANSI 78.81-2020":
                return QueryResult(
                    standard_number=term,
                    standard_name="Test Standard",
                )
            return None

        adapter._search = MagicMock(side_effect=search_side_effect)

        result = adapter._search_progressive(
            logical_code="ANSI",
            number=78,
            year=2020,
            part=None,
            num_prefix="C",
            num_suffix=".81",
            target="ANSI C78.81-2020",
        )

        assert result is not None
        assert any(c == "ANSI 78.81-2020" for c in calls)

    def test_no_year_fallback(self, adapter):
        """去前缀也失败 → 去年份回退（接受 newer/older）"""
        calls = []

        def search_side_effect(term):
            calls.append(term)
            if term == "GB/T 1234":
                return QueryResult(
                    standard_number="GB/T 1234",
                    standard_name="Test Standard",
                )
            return None

        adapter._search = MagicMock(side_effect=search_side_effect)

        with patch("pilotstd.query.adapters.base.match_result") as mock_match:
            mock_match.return_value = (None, "newer")
            result = adapter._search_progressive(
                logical_code="GB/T",
                number=1234,
                year=2020,
                part=None,
                num_prefix="",
                num_suffix="",
                target="GB/T 1234-2020",
            )

        assert result is not None
        assert any(c == "GB/T 1234" for c in calls)


# ─── T6: _post_search_candidates 错误路径 ───


class TestPostSearchCandidates:
    @patch("pilotstd.query.network.safe_post")
    def test_safe_post_failure_returns_empty(self, mock_safe_post, adapter):
        """safe_post 返回 None → 空列表"""
        mock_safe_post.return_value = None
        result = adapter._post_search_candidates("GB/T 1234-2020")
        assert result == []

    @patch("pilotstd.query.network.safe_post")
    def test_non_200_status_returns_empty(self, mock_safe_post, adapter):
        """safe_post 返回非200状态码 → 空列表"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_safe_post.return_value = mock_resp
        result = adapter._post_search_candidates("GB/T 1234-2020")
        assert result == []

    @patch("pilotstd.query.network.safe_post")
    def test_json_parse_error_returns_empty(self, mock_safe_post, adapter):
        """JSON 解析失败 → 空列表"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_safe_post.return_value = mock_resp
        result = adapter._post_search_candidates("GB/T 1234-2020")
        assert result == []

    @patch("pilotstd.query.network.safe_post")
    def test_empty_records_returns_empty(self, mock_safe_post, adapter):
        """records 为空 → 空列表"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"records": []}
        mock_safe_post.return_value = mock_resp
        result = adapter._post_search_candidates("GB/T 1234-2020")
        assert result == []


# ─── T7-T8: query_with_strategy variants 分支 ───


class TestQueryWithStrategyVariants:
    def test_variants_fallback_when_progressive_fails(self, adapter):
        """前四步全部失败 → 变体搜索命中"""
        adapter._search = MagicMock(return_value=None)

        def candidates_side_effect(term):
            if term == "GB 1234-2020":
                return [
                    QueryResult(
                        standard_number="GB 1234-2020",
                        standard_name="Test Standard",
                        source_site="test_site",
                    )
                ]
            return []

        adapter._search_candidates = MagicMock(side_effect=candidates_side_effect)

        with (
            patch("pilotstd.query.adapters.base.build_code_variants") as mock_variants,
            patch("pilotstd.query.adapters.base.match_result") as mock_match,
        ):
            mock_variants.return_value = ["GB 1234-2020"]
            mock_match.return_value = (None, "exact")
            result = adapter.query_with_strategy(
                logical_code="GB/T",
                number=1234,
                year=2020,
            )
            assert result is not None
            assert result.standard_number == "GB 1234-2020"
            assert result.match_status == "exact"

    def test_variants_early_break_on_confirmed(self, adapter):
        """variants 中第二个候选达到 CONFIRMED → 提前退出外层循环"""
        adapter._search = MagicMock(return_value=None)

        low_result = QueryResult(
            standard_number="GB 1234-2020/Draft",
            standard_name="Draft Standard",
            source_site="test_site",
        )
        high_result = QueryResult(
            standard_number="GB 1234-2020",
            standard_name="Confirmed Standard",
            source_site="test_site",
        )

        def candidates_side_effect(term):
            if term == "variant_a":
                return [low_result]
            if term == "variant_b":
                return [high_result]
            return []

        adapter._search_candidates = MagicMock(side_effect=candidates_side_effect)

        with (
            patch("pilotstd.query.adapters.base.build_code_variants") as mock_variants,
            patch("pilotstd.query.adapters.base.match_result") as mock_match,
            patch("pilotstd.query.adapters.base.MATCH_SCORE_CONFIRMED", 80),
            patch("pilotstd.query.adapters.base.MATCH_SCORE_HIGH_CONFIDENCE", 80),
            patch("pilotstd.query.adapters.base.MATCH_SCORE", {"low": 10, "confirmed": 80}),
        ):
            mock_variants.return_value = ["variant_a", "variant_b", "variant_c"]
            mock_match.side_effect = [(None, "low"), (None, "confirmed")]
            result = adapter.query_with_strategy(
                logical_code="GB/T", number=1234, year=2020
            )

        assert result is not None
        assert result.standard_number == "GB 1234-2020"
        searched_terms = [
            call.args[0] for call in adapter._search_candidates.call_args_list
        ]
        assert "variant_c" not in searched_terms

    def test_variants_returns_not_found_when_all_fail(self, adapter):
        """所有搜索方式都失败 → 返回未找到结果"""
        adapter._search = MagicMock(return_value=None)
        adapter._search_candidates = MagicMock(return_value=[])

        with patch("pilotstd.query.adapters.base.build_code_variants") as mock_variants:
            mock_variants.return_value = ["GB 1234-2020", "GB/T 1234-2020"]
            result = adapter.query_with_strategy(
                logical_code="GB/T",
                number=1234,
                year=2020,
            )
            assert result is not None
            assert result.error_message == "未找到匹配结果"


# ─── T9: _detect_split_parts ───


class TestDetectSplitParts:
    def test_returns_empty_when_less_than_two_candidates(self, adapter):
        """少于2个候选 → 空字符串"""
        candidates = [(QueryResult(standard_number="GB/T 1234-2020"), 1)]
        result = adapter._detect_split_parts(candidates, 1234)
        assert result == ""

    def test_detects_split_parts(self, adapter):
        """2个及以上不同部分 → 返回逗号分隔列表"""
        candidates = [
            (QueryResult(standard_number="GB/T 1234.1-2020"), 1),
            (QueryResult(standard_number="GB/T 1234.2-2020"), 1),
        ]
        result = adapter._detect_split_parts(candidates, 1234)
        assert "GB/T 1234.1-2020" in result
        assert "GB/T 1234.2-2020" in result

    def test_ignores_candidates_without_part(self, adapter):
        """part 为 None 的候选被跳过 → 不足2个有效 part → 空字符串"""
        candidates = [
            (QueryResult(standard_number="GB/T 1234-2020"), 1),
            (QueryResult(standard_number="GB/T 1234.1-2020"), 1),
        ]
        result = adapter._detect_split_parts(candidates, 1234)
        assert result == ""

    def test_ignores_candidates_with_different_number(self, adapter):
        """number 不匹配的候选被过滤 → 不足2个同 number → 空字符串"""
        candidates = [
            (QueryResult(standard_number="GB/T 1234.1-2020"), 1),
            (QueryResult(standard_number="GB/T 5678.2-2020"), 1),
        ]
        result = adapter._detect_split_parts(candidates, 1234)
        assert result == ""

    def test_skips_unparseable_standard_number(self, adapter):
        """解析失败的 standard_number → continue 跳过"""
        candidates = [
            (QueryResult(standard_number="not-a-standard"), 1),
            (QueryResult(standard_number="GB/T 1234.1-2020"), 1),
        ]
        result = adapter._detect_split_parts(candidates, 1234)
        assert result == ""


# ─── T10: _search 默认实现 ───


class NoOverrideAdapter(BaseAdapter):
    """不重写 _search，使用基类默认实现"""

    supports_replaces_detail = False

    def init(self):
        self._session = MagicMock()
        self.API_URL = "https://test.api/search"

    @property
    def site_name(self) -> str:
        return "test_site"

    @property
    def site_label(self) -> str:
        return "Test Site"

    def _parse_result(self, record, search_term):
        return QueryResult(
            standard_number=record.get("num", ""),
            standard_name=record.get("name", "Test"),
            publish_date=record.get("date", ""),
            source_site=self.site_name,
        )


@pytest.fixture
def no_override_adapter():
    a = NoOverrideAdapter()
    a.init()
    return a


class TestSearchDefaultImpl:
    def test_returns_none_when_candidates_empty(self, no_override_adapter):
        """_search_candidates 返回空 → _search 返回 None"""
        no_override_adapter._search_candidates = MagicMock(return_value=[])
        result = no_override_adapter._search("GB/T 1234-2020")
        assert result is None

    def test_returns_exact_standard_number_match(self, no_override_adapter):
        """candidates 中存在 standard_number 完全匹配 → 直接返回"""
        c1 = QueryResult(standard_number="GB/T 1234-2015", standard_name="Old")
        c2 = QueryResult(standard_number="GB/T 1234-2020", standard_name="Exact")
        no_override_adapter._search_candidates = MagicMock(return_value=[c1, c2])
        result = no_override_adapter._search("GB/T 1234-2020")
        assert result is not None
        assert result.standard_number == "GB/T 1234-2020"

    def test_returns_latest_when_no_exact_match(self, no_override_adapter):
        """无完全匹配 → 返回 publish_date 最新的"""
        c1 = QueryResult(
            standard_number="GB/T 1234-2015",
            standard_name="Old",
            publish_date="2015-01-01",
        )
        c2 = QueryResult(
            standard_number="GB/T 1234-2020",
            standard_name="New",
            publish_date="2020-01-01",
        )
        no_override_adapter._search_candidates = MagicMock(return_value=[c1, c2])
        result = no_override_adapter._search("GB/T 1234")
        assert result is not None
        assert result.standard_number == "GB/T 1234-2020"


# ─── T11: query_with_strategy progressive 成功路径 ───


class TestQueryWithStrategyProgressiveSuccess:
    def test_progressive_success_returns_early(self, adapter):
        """_search_progressive 第一步就成功 → 不进入 variants 循环"""
        mock_result = QueryResult(
            standard_number="GB/T 1234-2020",
            standard_name="Test Standard",
            source_site="test_site",
        )

        def search_side_effect(term):
            if term == "GB/T 1234-2020":
                return mock_result
            return None

        adapter._search = MagicMock(side_effect=search_side_effect)

        result = adapter.query_with_strategy(
            logical_code="GB/T",
            number=1234,
            year=2020,
        )
        assert result is not None
        assert result.standard_number == "GB/T 1234-2020"


# ─── T12: query_with_strategy None 候选 ───


class TestQueryWithStrategyNoneCandidate:
    def test_none_candidate_skipped(self, adapter):
        """variants 循环中 candidate 为 None → continue 跳过"""
        adapter._search = MagicMock(return_value=None)

        adapter._search_candidates = MagicMock(return_value=[None])

        with (
            patch("pilotstd.query.adapters.base.build_code_variants") as mock_variants,
        ):
            mock_variants.return_value = ["GB 1234-2020"]
            result = adapter.query_with_strategy(
                logical_code="GB/T",
                number=1234,
                year=2020,
            )
            assert result is not None
            assert result.error_message == "未找到匹配结果"


# ─── T13: _post_search_candidates 成功路径 ───


class TestPostSearchCandidatesSuccess:
    @patch("pilotstd.query.network.safe_post")
    def test_valid_records_returns_parsed_results(self, mock_safe_post, adapter):
        """有效 JSON 且有 records → 调用 _parse_result 并返回结果列表"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "records": [
                {"num": "GB/T 1", "name": "Std 1"},
                {"num": "GB/T 2", "name": "Std 2"},
            ]
        }
        mock_safe_post.return_value = mock_resp

        def parse_side_effect(rec, term):
            return QueryResult(
                standard_number=rec["num"],
                standard_name=rec["name"],
                source_site="test_site",
            )

        with patch.object(adapter, "_parse_result", side_effect=parse_side_effect):
            results = adapter._post_search_candidates("GB/T")
            assert len(results) == 2
            assert results[0].standard_number == "GB/T 1"
            assert results[1].standard_number == "GB/T 2"
