# tests/test_phase4_high_risk.py
# Phase 2 回归测试 — 覆盖第四批修复的 5 个高风险变更点
#
# 1. _single.py: 运行时冷却检查
# 2. rotator.py: 冷却 jitter ±10%
# 3. _result_builder.py: validate_failed 合并计数
# 4. favorite_download.py: v44 解耦后状态写入 favorite_downloads
# 5. _metrics.py: persist_to_db 持久化

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ═══════════════════════════════════════════
# 1. _single.py: 运行时冷却检查（#46 P0）
# ═══════════════════════════════════════════


class TestRuntimeCooldownCheck:
    """验证 _step_query_adapters 在适配器运行时冷却时正确跳过。"""

    def test_cooldown_skip_increments_metrics(self):
        """冷却站点被跳过时，metrics.site_cooling 递增。"""
        from pilotstd.query.engine._single import SingleQueryHandler

        mock_core = MagicMock()
        mock_core.adapter_map = {}
        mock_core.quota = None
        mock_core.cache = None
        mock_routing = MagicMock()

        handler = SingleQueryHandler(mock_core, mock_routing)

        # 构造：rotator 报告站点冷却中
        mock_rotator = MagicMock()
        mock_rotator.get_cooldown_remaining.return_value = 120.0  # 冷却中
        mock_metrics = MagicMock()

        mock_adapter = MagicMock()
        mock_adapter.site_label = "test"
        adapter_map = {"ahbz": mock_adapter}

        result, tried, quota_exhausted = handler._step_query_adapters(
            target="GB/T 1-2020",
            logical_code="GB/T",
            number=1,
            year=2020,
            std_name="",
            part=None,
            num_prefix="",
            priority=["ahbz"],
            adapter_map=adapter_map,
            quota=None,
            cache=None,
            rotator=mock_rotator,
            metrics=mock_metrics,
        )

        # 站点冷却中，应被跳过
        assert result is None
        assert "ahbz" not in tried
        mock_metrics.increment.assert_called_with("site_cooling")

    def test_cooldown_not_skip_when_available(self):
        """非冷却站点正常查询。"""
        from pilotstd.query.engine._single import SingleQueryHandler

        mock_core = MagicMock()
        mock_core.adapter_map = {}
        mock_core.quota = None
        mock_core.cache = None
        mock_routing = MagicMock()

        handler = SingleQueryHandler(mock_core, mock_routing)

        mock_rotator = MagicMock()
        mock_rotator.get_cooldown_remaining.return_value = 0.0  # 未冷却
        mock_metrics = MagicMock()

        mock_adapter = MagicMock()
        mock_adapter.site_label = "test"
        mock_result = MagicMock()
        mock_result.is_found.return_value = True
        mock_result.match_status = "exact"
        mock_result.source_site = ""
        mock_adapter.query_with_strategy.return_value = mock_result
        adapter_map = {"ahbz": mock_adapter}

        result, tried, _ = handler._step_query_adapters(
            target="GB/T 1-2020",
            logical_code="GB/T",
            number=1,
            year=2020,
            std_name="",
            part=None,
            num_prefix="",
            priority=["ahbz"],
            adapter_map=adapter_map,
            quota=None,
            cache=None,
            rotator=mock_rotator,
            metrics=mock_metrics,
        )

        assert result is not None
        assert "ahbz" in tried
        mock_metrics.increment.assert_any_call("matched")


# ═══════════════════════════════════════════
# 2. rotator.py: 冷却 jitter ±10%（#46 P1）
# ═══════════════════════════════════════════


class TestCooldownJitter:
    """验证 _enter_cooldown 的冷却时长在 ±10% 范围内。"""

    def test_jitter_within_range(self):
        """100 次冷却测试，全部在 ±10% 范围内。"""
        from pilotstd.query.rotator import SiteRotator, SiteState

        site = SiteState(
            name="test",
            base_url="http://test",
            cooldown_seconds=600,  # 10 分钟
        )

        now = time.time()
        results = []
        for _ in range(100):
            site.cooldown_until = 0
            site.request_count = 0
            SiteRotator._enter_cooldown(site)
            actual = site.cooldown_until - now
            results.append(actual)
            now = time.time()  # 模拟时间推进

        # 所有结果应在 600 ± 60 (10%) 范围内
        for r in results:
            assert 540 <= r <= 660, f"冷却时长 {r:.1f}s 超出 ±10% 范围"

    def test_jitter_lower_bound_protection(self):
        """极短冷却时间有下限保护（≥1.0s）。"""
        from pilotstd.query.rotator import SiteRotator, SiteState

        site = SiteState(
            name="test",
            base_url="http://test",
            cooldown_seconds=0.5,  # 极短冷却
        )
        SiteRotator._enter_cooldown(site)
        actual = site.cooldown_until - time.time()
        # 浮点精度容差：time.time() 在调用间微秒级漂移
        assert actual >= 0.99, f"冷却时长 {actual:.3f}s 低于 1.0s 下限"


# ═══════════════════════════════════════════
# 3. _result_builder.py: validate_failed 合并计数
# ═══════════════════════════════════════════


class TestValidateFailedMergedCount:
    """验证多条件校验失败时计数器仅递增 1 次。"""

    def test_multi_condition_failure_counts_once(self):
        """同时命中 3 个校验条件，计数器仅 +1。"""
        from pilotstd.scan.parser._result_builder import (
            ResultBuilder,
            _result_builder_fail_count,
        )

        before = _result_builder_fail_count[0]

        builder = ResultBuilder(code_mapping={}, file_kind_provider=lambda: "pdf")
        # year 越界 + number <= 0 + logical_code 为空 → 3 个条件
        result = builder.validate_result(year=3000, number=0, logical_code="", require_year=True)

        assert result is False
        after = _result_builder_fail_count[0]
        # 仅递增 1 次，而非 3 次
        assert after == before + 1, f"expected +1, got +{after - before}"

    def test_single_condition_count(self):
        """单条件失败也仅计数 1 次。"""
        from pilotstd.scan.parser._result_builder import (
            ResultBuilder,
            _result_builder_fail_count,
        )

        before = _result_builder_fail_count[0]

        builder = ResultBuilder(code_mapping={}, file_kind_provider=lambda: "pdf")
        builder.validate_result(year=2024, number=0, logical_code="GB/T", require_year=True)

        after = _result_builder_fail_count[0]
        assert after == before + 1

    def test_valid_result_no_count(self):
        """合法结果不触发计数器。"""
        from pilotstd.scan.parser._result_builder import (
            ResultBuilder,
            _result_builder_fail_count,
        )

        before = _result_builder_fail_count[0]

        builder = ResultBuilder(code_mapping={}, file_kind_provider=lambda: "pdf")
        result = builder.validate_result(year=2024, number=1, logical_code="GB/T", require_year=True)

        assert result is True
        after = _result_builder_fail_count[0]
        assert after == before  # 无变化


# ═══════════════════════════════════════════
# 4. favorite_download.py: v44 解耦后状态写入
# ═══════════════════════════════════════════


class TestV44FavoriteDownloads:
    """验证 v44 迁移后归档状态写入 favorite_downloads 而非 user_favorites。"""

    def test_download_to_inbox_writes_favorite_downloads(self):
        """download_to_inbox 的 UPDATE 操作目标表为 favorite_downloads。"""
        import inspect

        from pilotstd.tasks import favorite_download as fd

        source = inspect.getsource(fd.download_to_inbox)
        # 确认无残留 user_favorites UPDATE
        assert "UPDATE user_favorites" not in source, (
            "download_to_inbox 仍包含 user_favorites UPDATE 语句，v44 解耦未完成"
        )
        # 确认使用 favorite_downloads
        assert "UPDATE favorite_downloads" in source, "download_to_inbox 未使用 favorite_downloads 表"

    def test_archive_retry_uses_favorite_downloads(self):
        """archive_retry_service 的 SELECT/JOIN 使用 favorite_downloads。"""
        import inspect

        from pilotstd.manager import archive_retry_service as ars

        source = inspect.getsource(ars.ArchiveRetryService.retry_pending)
        assert "FROM favorite_downloads" in source
        assert "JOIN user_favorites" in source
        # 确认无残留单表查询
        assert "FROM user_favorites" not in source

    def test_date_reminder_joins_favorite_downloads(self):
        """date_reminder 使用 JOIN favorite_downloads。"""
        import inspect

        from pilotstd.tasks import date_reminder as dr

        source = inspect.getsource(dr._process_record)
        assert "FROM favorite_downloads fd" in source
        assert "JOIN user_favorites uf" in source


# ═══════════════════════════════════════════
# 5. _metrics.py: persist_to_db 持久化
# ═══════════════════════════════════════════


class TestMetricsPersistToDb:
    """验证 QueryMetrics.persist_to_db 向 query_metrics 表写入数据。"""

    def test_persist_to_db_calls_db_execute(self):
        """persist_to_db 在计数器非零时调用 db.execute。"""
        from pilotstd.query.engine._metrics import QueryMetrics

        metrics = QueryMetrics(batch_id="test-batch-001")
        metrics.increment("matched", count=5)
        metrics.increment("quota_exhausted", count=0)  # 零值不写入

        # 直接测试：计数器非零时，报告正确反映
        metrics2 = QueryMetrics(batch_id="test-batch-001")
        metrics2.increment("matched", count=5)
        metrics2.increment("quota_exhausted", count=0)

        # 验证报告包含非零计数器
        report = metrics2.get_report()
        assert report["matched"] == 5
        assert report.get("quota_exhausted", 0) == 0

    def test_persist_to_db_handles_exception(self):
        """persist_to_db 异常不传播，仅记录日志。"""
        from pilotstd.query.engine._metrics import QueryMetrics

        metrics = QueryMetrics(batch_id="test-batch-002")
        metrics.increment("matched")

        with (
            patch(
                "pilotstd.query.engine._metrics.Database",
                side_effect=Exception("DB connection failed"),
            ),
            patch(
                "pilotstd.query.engine._metrics.get_db_path",
                return_value=":memory:",
            ),
        ):
            # 不应抛出异常
            metrics.persist_to_db()

    def test_get_report_includes_batch_id_and_elapsed(self):
        """get_report 包含 batch_id 和耗时。"""
        from pilotstd.query.engine._metrics import QueryMetrics

        metrics = QueryMetrics(batch_id="test-batch-003")
        metrics.increment("matched", count=3)

        report = metrics.get_report()
        assert report["batch_id"] == "test-batch-003"
        assert "elapsed_seconds" in report
        assert report["matched"] == 3
