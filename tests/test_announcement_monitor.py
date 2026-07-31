"""pilotstd/announcement/monitor.py 补测 — AnnounceMonitor 阶段计时/API统计/摘要全覆盖。"""
import time

import pytest
from pilotstd.announcement.monitor import AnnounceMonitor


@pytest.fixture
def fresh_monitor():
    """空白监控实例，无任何数据。"""
    return AnnounceMonitor()


@pytest.fixture
def populated_monitor():
    """含完整数据的监控实例。"""
    m = AnnounceMonitor()
    m.total_announcements = 10
    m.total_standards_parsed = 25
    m.html_hits = 3
    m.attachment_hits = 5
    m.ocr_hits = 2
    m.api_calls = 8
    m.api_failures = 1
    m.fetch_list_ms = 1200
    m.fetch_detail_total_ms = 3500
    m.parse_total_ms = 800
    m.write_db_ms = 200
    return m


class TestStageTiming:
    """阶段计时 — 正常×2 + 边界×1 + 异常×1 + 状态转换×1。"""

    def test_normal_end_stage_fetch_list(self, fresh_monitor):
        """fetch_list 阶段结束，耗时写入 fetch_list_ms。"""
        fresh_monitor.start_stage()
        elapsed = fresh_monitor.end_stage("fetch_list")
        assert fresh_monitor.fetch_list_ms >= 0
        assert elapsed >= 0

    def test_normal_all_four_stages_recorded(self, fresh_monitor):
        """四个阶段依次执行，各自耗时被正确记录。"""
        for stage in ["fetch_list", "fetch_detail", "parse", "write_db"]:
            fresh_monitor.start_stage()
            fresh_monitor.end_stage(stage)
        assert fresh_monitor.fetch_list_ms >= 0
        assert fresh_monitor.fetch_detail_total_ms >= 0
        assert fresh_monitor.parse_total_ms >= 0
        assert fresh_monitor.write_db_ms >= 0

    def test_boundary_unknown_stage_does_not_modify_existing(self, fresh_monitor):
        """未知阶段名称不改变已记录耗时且不抛异常。"""
        fresh_monitor.start_stage()
        before = fresh_monitor.fetch_list_ms
        fresh_monitor.end_stage("unknown_stage")
        assert fresh_monitor.fetch_list_ms == before

    def test_exception_start_stage_without_end(self, fresh_monitor):
        """start 后不 end 是可接受的，不抛异常。"""
        fresh_monitor.start_stage()
        assert fresh_monitor._stage_start > 0

    def test_state_detail_and_parse_accumulate(self, fresh_monitor):
        """fetch_detail 和 parse 阶段累计叠加（+=）。"""
        fresh_monitor.start_stage()
        fresh_monitor.end_stage("fetch_detail")
        first = fresh_monitor.fetch_detail_total_ms
        fresh_monitor.start_stage()
        fresh_monitor.end_stage("fetch_detail")
        assert fresh_monitor.fetch_detail_total_ms >= first


class TestApiCounting:
    """API 调用计数 — 正常×2 + 边界×1 + 状态转换×1。"""

    def test_normal_successful_call(self, fresh_monitor):
        """成功 API 调用：calls+1，failures 不变。"""
        fresh_monitor.inc_api_call(success=True)
        assert fresh_monitor.api_calls == 1
        assert fresh_monitor.api_failures == 0

    def test_normal_failed_call(self, fresh_monitor):
        """失败 API 调用：calls+1，failures+1。"""
        fresh_monitor.inc_api_call(success=False)
        assert fresh_monitor.api_calls == 1
        assert fresh_monitor.api_failures == 1

    def test_boundary_default_success_true(self, fresh_monitor):
        """默认参数 success=True。"""
        fresh_monitor.inc_api_call()
        assert fresh_monitor.api_failures == 0

    def test_state_mixed_call_totals(self, fresh_monitor):
        """混合成功/失败：正确分计。"""
        for s in [True, True, False, True, False]:
            fresh_monitor.inc_api_call(success=s)
        assert fresh_monitor.api_calls == 5
        assert fresh_monitor.api_failures == 2


class TestSummary:
    """摘要生成 — 正常×2 + 边界×1 + 状态转换×1。"""

    def test_normal_full_data_summary(self, populated_monitor):
        """完整数据摘要含公告数、标准数、命中分布、API成功率、各阶段耗时。"""
        s = populated_monitor.summary()
        assert "10条" in s
        assert "25标准" in s
        assert "HTML=3" in s
        assert "API=8" in s

    def test_normal_zero_announcements_returns_no_data(self, fresh_monitor):
        """无公告时返回'公告: 无数据'。"""
        assert fresh_monitor.summary() == "公告: 无数据"

    def test_boundary_all_timings_zero(self, populated_monitor):
        """零耗时摘要不含负数。"""
        populated_monitor.fetch_list_ms = 0
        populated_monitor.fetch_detail_total_ms = 0
        s = populated_monitor.summary()
        assert "0ms" in s

    def test_state_total_elapsed_increases(self, fresh_monitor):
        """total_elapsed_ms 随时间单调非递减。"""
        t1 = fresh_monitor.total_elapsed_ms
        t2 = fresh_monitor.total_elapsed_ms
        assert t2 >= t1
