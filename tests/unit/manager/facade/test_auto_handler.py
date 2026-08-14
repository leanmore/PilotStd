"""_auto.py (AutoPipeline) 覆盖率补齐 — 目标: 0% → 95%+"""

from unittest.mock import MagicMock

import pytest

from pilotstd.manager.facade._auto import AutoPipeline
from pilotstd.manager.facade._download import DownloadHandler
from pilotstd.manager.facade._organize import OrganizeHandler
from pilotstd.manager.facade._query import QueryHandler
from pilotstd.manager.facade._scan import ScanHandler

# ── Fixtures ──


@pytest.fixture
def mock_core():
    core = MagicMock()
    core.cfg = MagicMock()
    core.cfg.get.return_value = True
    core.download_list = []
    core.last_skipped_dirs = []
    return core


@pytest.fixture
def mock_scan():
    sh = MagicMock(spec=ScanHandler)
    sh.scan_directory.return_value = []
    sh.scan_directory_stream.return_value = []
    return sh


@pytest.fixture
def mock_query():
    qh = MagicMock(spec=QueryHandler)
    qh.query.return_value = ([], MagicMock(found=0))
    return qh


@pytest.fixture
def mock_download():
    dh = MagicMock(spec=DownloadHandler)
    dh.download.return_value = ([], MagicMock(success=0))
    dh.download_stream.return_value = ([], MagicMock(success=0))
    return dh


@pytest.fixture
def mock_organize():
    oh = MagicMock(spec=OrganizeHandler)
    oh.archive_standards.return_value = {"moved": 0}
    oh.organize_skipped_dirs.return_value = {"moved": 0}
    oh.organize_fallback.return_value = {"moved": 0}
    return oh


@pytest.fixture
def pipeline(mock_core, mock_scan, mock_query, mock_download, mock_organize):
    return AutoPipeline(mock_core, mock_scan, mock_query, mock_download, mock_organize)


# ════════════════════════════════════════════════════════════
# T1: auto_run 主入口
# ════════════════════════════════════════════════════════════


class TestAutoRun:
    def test_happy_path_all_stages(self, pipeline, mock_scan, mock_query, mock_download, mock_organize):
        """完整 4 阶段流程 → 所有计数正确。"""
        mock_scan.scan_directory.return_value = [MagicMock()] * 5
        q_stats = MagicMock(found=3)
        mock_query.query.return_value = ([], q_stats)
        dl_stats = MagicMock(success=2)
        mock_download.download.return_value = ([], dl_stats)
        mock_organize.archive_standards.return_value = {"moved": 4}

        report = pipeline.auto_run("/fake/root")

        assert report["scan"] == 5
        assert report["query_found"] == 3
        assert report["download_success"] == 2
        assert report["organize_moved"] == 4

    def test_mirror_skipped_dirs_enabled_with_dirs(
        self, pipeline, mock_core, mock_scan, mock_organize
    ):
        """mirror_skipped_dirs=True + 有跳过目录 → mirror_skipped 被计入。"""
        mock_core.cfg.get.return_value = True
        mock_core.last_skipped_dirs = ["/skip1", "/skip2"]
        mock_organize.organize_skipped_dirs.return_value = {"moved": 2}

        report = pipeline.auto_run("/root")
        assert report["mirror_skipped"] == 2

    def test_mirror_skipped_dirs_empty_noop(self, pipeline, mock_core, mock_scan):
        """mirror_skipped_dirs=True 但无跳过目录 → 不调用 organize_skipped_dirs。"""
        mock_core.cfg.get.side_effect = lambda k, d=None: {
            "storage.mirror_skipped_dirs": True,
            "storage.mirror_fallback": False,
        }.get(k, d)
        mock_core.last_skipped_dirs = []

        report = pipeline.auto_run("/root")
        assert report["mirror_skipped"] == 0

    def test_mirror_skipped_dirs_disabled(self, pipeline, mock_core, mock_scan):
        """mirror_skipped_dirs=False → 跳过镜像步骤。"""
        mock_core.cfg.get.side_effect = lambda k, d=None: {
            "storage.mirror_skipped_dirs": False,
            "storage.mirror_fallback": False,
        }.get(k, d)

        report = pipeline.auto_run("/root")
        assert report["mirror_skipped"] == 0

    def test_mirror_fallback_enabled(self, pipeline, mock_core, mock_scan, mock_organize):
        """mirror_fallback=True → organize_fallback 被调用。"""
        mock_core.cfg.get.side_effect = lambda k, d=None: {
            "storage.mirror_skipped_dirs": False,
            "storage.mirror_fallback": True,
        }.get(k, d)
        mock_organize.organize_fallback.return_value = {"moved": 3}

        report = pipeline.auto_run("/root")
        assert report["fallback_mirrored"] == 3

    def test_mirror_fallback_disabled(self, pipeline, mock_core, mock_scan):
        """mirror_fallback=False → 不调用 organize_fallback。"""
        mock_core.cfg.get.return_value = False

        report = pipeline.auto_run("/root")
        assert report["fallback_mirrored"] == 0


# ════════════════════════════════════════════════════════════
# T2: _auto_stage_query
# ════════════════════════════════════════════════════════════


class TestAutoStageQuery:
    def test_without_progress_callback(self, pipeline, mock_query):
        """on_query_progress=None → 不创建包装回调。"""
        q_stats = MagicMock(found=5)
        mock_query.query.return_value = ([], q_stats)

        report, t = pipeline._auto_stage_query([MagicMock()], None, None, {"query_found": 0}, 0)

        assert report["query_found"] == 5

    def test_with_progress_callback(self, pipeline, mock_query):
        """on_query_progress 非空 → 创建 _wrapped 回调 + 最终发送 100%。"""
        q_stats = MagicMock(found=3)
        mock_query.query.return_value = ([], q_stats)
        on_progress = MagicMock()

        pipeline._auto_stage_query(
            [MagicMock()] * 10, on_progress, None, {"query_found": 0}, 0
        )

        # 最终 should call on_query_progress(100, 100)
        on_progress.assert_any_call(100, 100)
        # query 被调用时传入了 progress_callback
        call_kwargs = mock_query.query.call_args[1]
        assert "progress_callback" in call_kwargs
        assert callable(call_kwargs["progress_callback"])

    def test_wrapped_callback_scales_correctly(self, pipeline, mock_query):
        """_wrapped 回调正确缩放 cur/total → scaled/100。"""
        captured_cb = None

        def capture_query(parsed, **kwargs):
            nonlocal captured_cb
            captured_cb = kwargs.get("progress_callback")

        mock_query.query.side_effect = lambda parsed, **kw: (
            capture_query(parsed, **kw) or ([], MagicMock(found=0))
        )

        on_progress = MagicMock()

        pipeline._auto_stage_query(
            [MagicMock()] * 20, on_progress, None, {"query_found": 0}, 0
        )

        # 模拟回调被内部调用 cur=10, total=20 → scaled=50
        captured_cb(10, 20)
        on_progress.assert_any_call(50, 100)

    def test_wrapped_callback_total_zero_guard(self, pipeline, mock_query):
        """total=0 → scaled=0，不除零（L110-111）。"""
        captured_cb = None

        def capture_query(parsed, **kwargs):
            nonlocal captured_cb
            captured_cb = kwargs.get("progress_callback")

        mock_query.query.side_effect = lambda parsed, **kw: (
            capture_query(parsed, **kw) or ([], MagicMock(found=0))
        )

        on_progress = MagicMock()

        pipeline._auto_stage_query(
            [], on_progress, None, {"query_found": 0}, 0
        )

        # total=0 → scaled=0
        captured_cb(5, 0)
        on_progress.assert_any_call(0, 100)

    def test_with_result_callback(self, pipeline, mock_query):
        """on_query_result → 传给 query 的 result_callback。"""
        q_stats = MagicMock(found=2)
        mock_query.query.return_value = ([], q_stats)
        on_result = MagicMock()

        pipeline._auto_stage_query(
            [MagicMock()], None, on_result, {"query_found": 0}, 0
        )

        call_kwargs = mock_query.query.call_args[1]
        assert call_kwargs["result_callback"] is on_result


# ════════════════════════════════════════════════════════════
# T3: _auto_stage_archive_and_fallback
# ════════════════════════════════════════════════════════════


class TestAutoStageArchiveAndFallback:
    def test_filters_pending_items(self, pipeline, mock_organize):
        """next_action='pending' 的条目被过滤，不进入归档。"""
        pending = MagicMock()
        pending.next_action = "pending"
        normal = MagicMock()
        normal.next_action = ""
        parsed = [pending, normal]

        pipeline._auto_stage_archive_and_fallback(
            parsed, "/root", None, None, {"organize_moved": 0}, 0
        )

        # archive_standards 只收到非 pending 的条目
        archive_call = mock_organize.archive_standards.call_args[0][0]
        assert len(archive_call) == 1
        assert archive_call[0] is normal

    def test_on_stage_change_called_for_all_stages(self, pipeline, mock_organize):
        """on_stage_change → archive / mirror / fallback / done 各阶段都被调用。"""
        on_stage = MagicMock()

        pipeline._auto_stage_archive_and_fallback(
            [], "/root", None, on_stage, {"organize_moved": 0}, 0
        )

        stages = [c.args[0] for c in on_stage.call_args_list]
        assert "archive" in stages
        assert "done" in stages

    def test_with_mirror_skipped_dirs(self, pipeline, mock_core, mock_organize):
        """有跳过目录 + on_stage_change → mirror_skipped 阶段触发。"""
        mock_core.last_skipped_dirs = ["/skip"]
        mock_organize.organize_skipped_dirs.return_value = {"moved": 1}
        on_stage = MagicMock()

        report = pipeline._auto_stage_archive_and_fallback(
            [], "/root", None, on_stage, {"organize_moved": 0, "mirror_skipped": 0, "fallback_mirrored": 0}, 0
        )

        stages = [c.args[0] for c in on_stage.call_args_list]
        assert "mirror_skipped" in stages
        assert report["mirror_skipped"] == 1

    def test_with_mirror_fallback(self, pipeline, mock_core, mock_organize):
        """mirror_fallback=True + on_stage_change → fallback 阶段触发。"""
        mock_core.cfg.get.return_value = True
        mock_organize.organize_fallback.return_value = {"moved": 2}
        on_stage = MagicMock()

        report = pipeline._auto_stage_archive_and_fallback(
            [], "/root", None, on_stage, {"organize_moved": 0, "mirror_skipped": 0, "fallback_mirrored": 0}, 0
        )

        stages = [c.args[0] for c in on_stage.call_args_list]
        assert "fallback" in stages
        assert report["fallback_mirrored"] == 2

    def test_no_mirror_when_disabled(self, pipeline, mock_core):
        """两个 mirror 都禁用 → 直接到 done。"""
        mock_core.cfg.get.return_value = False
        on_stage = MagicMock()

        pipeline._auto_stage_archive_and_fallback(
            [], "/root", None, on_stage, {"organize_moved": 0, "mirror_skipped": 0, "fallback_mirrored": 0}, 0
        )

        stages = [c.args[0] for c in on_stage.call_args_list]
        assert "mirror_skipped" not in stages
        assert "fallback" not in stages

    def test_with_archive_result_callback(self, pipeline, mock_organize):
        """on_archive_result → 传给 archive_standards。"""
        on_result = MagicMock()

        pipeline._auto_stage_archive_and_fallback(
            [], "/root", on_result, None, {"organize_moved": 0}, 0
        )

        call_kwargs = mock_organize.archive_standards.call_args[1]
        assert call_kwargs["on_result"] is on_result

    def test_skipped_dirs_empty_no_mirror_stage(self, pipeline, mock_core, mock_organize):
        """mirror enabled 但 last_skipped_dirs 为空 → 不触发 mirror_skipped 阶段。"""
        mock_core.cfg.get.return_value = True
        mock_core.last_skipped_dirs = []
        on_stage = MagicMock()

        pipeline._auto_stage_archive_and_fallback(
            [], "/root", None, on_stage, {"organize_moved": 0, "mirror_skipped": 0, "fallback_mirrored": 0}, 0
        )

        stages = [c.args[0] for c in on_stage.call_args_list]
        assert "mirror_skipped" not in stages


# ════════════════════════════════════════════════════════════
# T4: auto_run_stream 流式管线
# ════════════════════════════════════════════════════════════


class TestAutoRunStream:
    def test_happy_path_all_stages(self, pipeline, mock_scan, mock_query, mock_download, mock_organize, mock_core):
        """流式 4 阶段全部执行。"""
        mock_scan.scan_directory_stream.return_value = [MagicMock()] * 3
        mock_core.download_list = [MagicMock()]
        dl_stats = MagicMock(success=1)
        mock_download.download_stream.return_value = ([], dl_stats)

        report = pipeline.auto_run_stream("/root")

        assert report["scan"] == 3
        assert report["download_success"] == 1

    def test_empty_scan_returns_early(self, pipeline, mock_scan, mock_query):
        """扫描结果为空 → 提前返回，不执行后续阶段。"""
        mock_scan.scan_directory_stream.return_value = []
        on_stage = MagicMock()

        report = pipeline.auto_run_stream("/root", on_stage_change=on_stage)

        assert report["scan"] == 0
        mock_query.query.assert_not_called()
        on_stage.assert_any_call("done", 0, 0)

    def test_no_download_list_skips_download(self, pipeline, mock_core, mock_scan, mock_download):
        """download_list 为空 → 跳过下载阶段。"""
        mock_scan.scan_directory_stream.return_value = [MagicMock()]
        mock_core.download_list = []

        report = pipeline.auto_run_stream("/root")
        assert report["download_success"] == 0
        mock_download.download_stream.assert_not_called()

    def test_on_stage_change_called_for_all_stages(self, pipeline, mock_scan, mock_core):
        """on_stage_change → scan / query / download / archive / done 各阶段。"""
        mock_scan.scan_directory_stream.return_value = [MagicMock()]
        mock_core.download_list = [MagicMock()]
        on_stage = MagicMock()

        pipeline.auto_run_stream("/root", on_stage_change=on_stage)

        stages = [c.args[0] for c in on_stage.call_args_list]
        assert "scan" in stages
        assert "query" in stages
        assert "download" in stages

    def test_all_callbacks_passed_through(self, pipeline, mock_scan, mock_query, mock_core):
        """所有回调 → 正确透传到下游。"""
        mock_scan.scan_directory_stream.return_value = [MagicMock()]
        cb_scan_progress = MagicMock()
        cb_scan_batch = MagicMock()

        pipeline.auto_run_stream(
            "/root",
            on_scan_progress=cb_scan_progress,
            on_scan_batch=cb_scan_batch,
        )

        scan_call = mock_scan.scan_directory_stream.call_args
        assert scan_call[1]["on_progress"] is cb_scan_progress
        assert scan_call[1]["on_batch"] is cb_scan_batch
