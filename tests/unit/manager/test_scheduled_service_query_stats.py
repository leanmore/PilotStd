"""ScheduledService.query_by_numbers 的统计口径与参数透传。

现场实测（2026-10-16，部署实例 v0.138.3 / `7c521a7b`）：
`POST /api/query` 对 `GB 2894-2025`、`GB 2894-2008` 两条结果都返回
`is_downloadable=true`，而 `stats.downloadable` 恒为 **0**——因为
`query_by_numbers` 只填了 `total/found`，与逐条字段自相矛盾（使用方据此判断会误判）。
同一处还把 `force_refresh` 静默丢弃（`query_standards` 支持该参数），
这正是缺陷报告"连查 3 次含 force_refresh 都不变"的原因：该参数从未生效。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pilotstd.manager.scheduled_service import ScheduledService
from pilotstd.query.models import QueryResult


def _service(results: list[QueryResult]) -> tuple[ScheduledService, MagicMock]:
    """构造注入了假查询引擎的 ScheduledService（其余依赖与本测试无关）。"""
    engine = MagicMock()
    engine.query_standards.return_value = results
    return (
        ScheduledService(
            cfg=MagicMock(),
            scanner=MagicMock(),
            parser=MagicMock(),
            query_engine=engine,
            file_index=MagicMock(),
            quota_tracker=MagicMock(),
            download_engine=MagicMock(),
        ),
        engine,
    )


class TestQueryByNumbersStats:
    """统计必须反映逐条结果，而不是只填 total/found。"""

    def test_counts_reflect_each_result(self):
        """downloadable/adopted_restricted/exact/not_found 都要真算出来。"""
        results = [
            QueryResult(
                standard_number="GB 2894-2025",
                standard_name="安全色和安全标志",
                match_status="exact",
                is_downloadable=True,
                is_adopted=False,
                source_site="cssn",
            ),
            QueryResult(
                standard_number="GB/T 7584.1-2026",
                standard_name="声学 护听器",
                match_status="exact",
                is_downloadable=False,
                is_adopted=True,
                source_site="cssn",
            ),
            QueryResult(
                standard_number="AQ/T 9007-2019",
                standard_name="",
                error_message="所有来源均未找到该标准",
            ),
        ]
        svc, _engine = _service(results)

        returned, stats = svc.query_by_numbers(["GB 2894-2025", "GB/T 7584.1-2026", "AQ/T 9007-2019"])

        assert returned is results
        assert stats.total == 3
        assert stats.found == 2
        # 与 _finalize_query 同口径：按 is_downloadable 计，未命中项默认 True 也计入
        assert stats.downloadable == 2
        assert stats.adopted_restricted == 1
        assert stats.exact == 2
        assert stats.not_found == 1

    def test_all_downloadable_results_are_counted(self):
        """两条可下载结果 ⇒ downloadable=2（现场实测该值曾恒为 0）。"""
        results = [
            QueryResult(standard_number="GB 2894-2025", standard_name="甲", is_downloadable=True),
            QueryResult(standard_number="GB 2894-2008", standard_name="乙", is_downloadable=True),
        ]
        svc, _engine = _service(results)

        _returned, stats = svc.query_by_numbers(["GB 2894-2025", "GB 2894-2008"])

        assert stats.downloadable == 2
        assert stats.not_found == 0


class TestQueryByNumbersParameterForwarding:
    """force_refresh 与 preferred_site 必须透传到查询引擎。"""

    def test_force_refresh_is_forwarded(self):
        svc, engine = _service([])

        svc.query_by_numbers(["GB 2894-2025"], force_refresh=True, preferred_site="std_gov")

        _args, kwargs = engine.query_standards.call_args
        assert kwargs["force_refresh"] is True, "force_refresh 被丢弃 ⇒ /api/query?force_refresh=true 无效"
        assert kwargs["preferred_site"] == "std_gov"
        assert kwargs["use_parallel"] is True

    def test_force_refresh_defaults_to_false(self):
        svc, engine = _service([])

        svc.query_by_numbers(["GB 2894-2025"])

        _args, kwargs = engine.query_standards.call_args
        assert kwargs["force_refresh"] is False
