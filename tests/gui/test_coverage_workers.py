"""GUI Workers 覆盖率测试 — 覆盖 pilotstd/ui/workers/ 下所有子模块。

覆盖文件：
  - workers.py            → 重导出验证
  - _common.py            → _pct, RowUpdate dataclass 默认值
  - announce.py           → AnnounceWorker 创建、信号、stop
  - archive.py            → ArchiveWorker 创建、信号、stop、target_path
  - auto.py               → AutoWorker 创建、信号、stop、_emit_scan_batch
  - download.py           → DownloadWorker 创建、信号、stop
  - normalize.py          → NormalizeWorker 创建、信号、stop
  - query.py              → QueryWorker 创建、信号、stop
  - scan.py               → ScanWorker 创建、信号、stop
  - update_download.py    → UpdateDownloadWorker 创建、信号、run
"""

import sys
from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

root_dir = __import__("os").path.dirname(
    __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


# ============================================================================
# 辅助 fixture：各 Worker 共用的 mock manager
# ============================================================================


@pytest.fixture
def mock_mgr():
    """返回可复用的 mock StandardManager。"""
    return MagicMock()


# ============================================================================
# 测试 1：workers.py — 重导出验证（9 行）
# ============================================================================


class TestWorkersModule:
    """验证 workers.py 和 workers/__init__.py 的导出完整性。"""

    EXPECTED_ALL = [
        "AnnounceWorker",
        "ArchiveWorker",
        "AutoWorker",
        "DownloadWorker",
        "LogHandler",
        "NormalizeWorker",
        "QueryWorker",
        "RowUpdate",
        "ScanWorker",
        "_pct",
    ]

    def test_workers_py_all_exports(self):
        """workers.py 的 __all__ 包含所有预期导出。"""
        from pilotstd.ui import workers as wm

        assert hasattr(wm, "__all__"), "workers.py 缺少 __all__"
        for name in self.EXPECTED_ALL:
            assert name in wm.__all__, f"workers.py __all__ 缺少 {name}"
            assert hasattr(wm, name), f"workers.py 缺少属性 {name}"

    def test_workers_package_all_exports(self):
        """workers/__init__.py 的 __all__ 包含所有预期导出。"""
        from pilotstd.ui.workers import __all__ as pkg_all

        for name in self.EXPECTED_ALL:
            assert name in pkg_all, f"workers/__init__.py __all__ 缺少 {name}"

    def test_workers_py_re_exports_match_package(self):
        """workers.py 和 workers/__init__.py 的 __all__ 一致。"""
        from pilotstd.ui import workers as wm
        from pilotstd.ui.workers import __all__ as pkg_all

        assert set(wm.__all__) == set(pkg_all), (
            f"workers.py 和 workers/__init__.py 的 __all__ 不一致:\n"
            f"  只在前者: {set(wm.__all__) - set(pkg_all)}\n"
            f"  只在后者: {set(pkg_all) - set(wm.__all__)}"
        )


# ============================================================================
# 测试 2：_common.py — _pct 和 RowUpdate dataclass（13 行未覆盖）
# ============================================================================


class TestPctFunction:
    """覆盖 _pct() 函数的所有分支。"""

    def test_pct_normal(self):
        """正常百分比计算：50/100 = 50%。"""
        from pilotstd.ui.workers._common import _pct

        assert _pct(50, 100) == 50
        assert _pct(1, 3) == 33  # 整数除法取整

    def test_pct_zero_total(self):
        """total 为 0 时返回 0（避免除零）。"""
        from pilotstd.ui.workers._common import _pct

        assert _pct(0, 0) == 0
        assert _pct(5, 0) == 0

    def test_pct_full(self):
        """cur == total 时返回 100%。"""
        from pilotstd.ui.workers._common import _pct

        assert _pct(100, 100) == 100

    def test_pct_zero_current(self):
        """cur 为 0 时返回 0%。"""
        from pilotstd.ui.workers._common import _pct

        assert _pct(0, 50) == 0


class TestShouldLogProgress:
    """覆盖 _should_log_progress 函数。"""

    def test_should_log_true(self):
        """距上次日志超过间隔时返回 True。"""
        from pilotstd.ui.workers._common import _should_log_progress

        result = _should_log_progress(0.0, interval=0.0)
        assert result is True

    def test_should_log_false(self):
        """距上次日志未超过间隔时返回 False。"""
        import time

        from pilotstd.ui.workers._common import _should_log_progress

        now = time.monotonic()
        result = _should_log_progress(now, interval=999999.0)
        assert result is False


class TestLogProgress:
    """覆盖 _log_progress 函数。"""

    def test_log_progress_calls_info(self):
        """_log_progress 正确调用 logger.info，传入格式化参数。"""
        import time

        from pilotstd.ui.workers._common import _log_progress

        mock_logger = MagicMock()
        t_start = time.monotonic()
        _log_progress(mock_logger, "测试", 50, 100, t_start)
        mock_logger.info.assert_called_once()
        # logging 使用 % 格式化，参数按位置传递
        args = mock_logger.info.call_args[0]
        assert args[1] == "测试"  # label
        assert args[2] == 50  # current
        assert args[3] == 100  # total

    def test_log_progress_zero_total(self):
        """total 为 0 时 pct_val 计算结果为 0。"""
        import time

        from pilotstd.ui.workers._common import _log_progress

        mock_logger = MagicMock()
        _log_progress(mock_logger, "测试", 0, 0, time.monotonic())
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        # pct_val = 0 / 0 * 100 → 0（除零保护）
        assert args[4] == 0  # pct_val
        assert args[2] == 0  # current
        assert args[3] == 0  # total


class TestRowUpdateDefaults:
    """覆盖 RowUpdate dataclass 的所有默认值字段。"""

    def test_row_update_all_defaults(self):
        """RowUpdate 创建时所有默认值字段生效。"""
        from pilotstd.models import ParsedStdInfo
        from pilotstd.ui.workers._common import RowUpdate

        parsed = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB/T", number=1, year=2024)
        row = RowUpdate(seq=1, parsed=parsed)

        # 验证所有默认值字段
        assert row.seq == 1
        assert row.parsed is parsed
        assert row.work_status == ""  # 默认空字符串
        assert row.effect_status == ""  # 默认空字符串
        assert row.implement_date == ""  # 默认空字符串
        assert row.std_name_override == ""  # 默认空字符串
        assert row.responsible_dept == ""  # 默认空字符串
        assert row.publish_date == ""  # 默认空字符串
        assert row.is_adopted is False  # 默认 False
        assert row.total == 0  # 默认 0

    def test_row_update_explicit_values(self):
        """RowUpdate 显式传入字段值覆盖默认值。"""
        from pilotstd.models import ParsedStdInfo
        from pilotstd.ui.workers._common import RowUpdate

        parsed = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB/T", number=1, year=2024)
        row = RowUpdate(
            seq=5,
            parsed=parsed,
            work_status="已下载",
            effect_status="现行",
            implement_date="2024-06-01",
            std_name_override="自定义名称",
            responsible_dept="归口单位",
            publish_date="2024-01-01",
            is_adopted=True,
            total=10,
        )

        assert row.seq == 5
        assert row.work_status == "已下载"
        assert row.effect_status == "现行"
        assert row.implement_date == "2024-06-01"
        assert row.std_name_override == "自定义名称"
        assert row.responsible_dept == "归口单位"
        assert row.publish_date == "2024-01-01"
        assert row.is_adopted is True
        assert row.total == 10

    def test_row_update_fields_count(self):
        """RowUpdate 有 10 个字段（seq + parsed + 8 个可选字段）。"""
        from pilotstd.ui.workers._common import RowUpdate

        field_names = {f.name for f in fields(RowUpdate)}
        expected = {
            "seq",
            "parsed",
            "work_status",
            "effect_status",
            "implement_date",
            "std_name_override",
            "responsible_dept",
            "publish_date",
            "is_adopted",
            "total",
        }
        assert field_names == expected


# ============================================================================
# 测试 3：announce.py — AnnounceWorker（8 行未覆盖）
# ============================================================================


class TestAnnounceWorker:
    """覆盖 AnnounceWorker 的创建、信号、stop 方法。"""

    def test_create(self, mock_mgr):
        """创建 AnnounceWorker 不崩溃。"""
        from pilotstd.ui.workers.announce import AnnounceWorker

        worker = AnnounceWorker(mgr=mock_mgr)
        assert worker is not None
        assert worker._mgr is mock_mgr
        assert worker._stopped is False

    def test_signals_exist(self, mock_mgr):
        """AnnounceWorker 包含所有预期的 Qt 信号。"""
        from pilotstd.ui.workers.announce import AnnounceWorker

        worker = AnnounceWorker(mgr=mock_mgr)
        assert hasattr(worker, "progress")
        assert hasattr(worker, "finished_signal")
        assert hasattr(worker, "error")

    def test_stop_sets_flag(self, mock_mgr):
        """stop() 设置 _stopped = True。"""
        from pilotstd.ui.workers.announce import AnnounceWorker

        worker = AnnounceWorker(mgr=mock_mgr)
        assert worker._stopped is False
        worker.stop()
        assert worker._stopped is True

    def test_init_with_optional_params(self, mock_mgr):
        """创建 AnnounceWorker 时传入可选参数。"""
        from pilotstd.ui.workers.announce import AnnounceWorker

        pause_event = MagicMock()
        worker = AnnounceWorker(mgr=mock_mgr, since_date="2024-01-01", pause_event=pause_event)
        assert worker._since_date == "2024-01-01"
        assert worker._pause_event is pause_event

    def test_init_with_empty_since_date_defaults_to_none(self, mock_mgr):
        """since_date 不传时默认为 None。"""
        from pilotstd.ui.workers.announce import AnnounceWorker

        worker = AnnounceWorker(mgr=mock_mgr)
        assert worker._since_date is None


# ============================================================================
# 测试 4：archive.py — ArchiveWorker（15 行未覆盖）
# ============================================================================


class TestArchiveWorker:
    """覆盖 ArchiveWorker 的创建、信号、stop 方法和 target_path。"""

    def test_create(self, mock_mgr):
        """创建 ArchiveWorker 不崩溃。"""
        from pilotstd.ui.workers.archive import ArchiveWorker

        worker = ArchiveWorker(mgr=mock_mgr, parsed_list=[], library_root="/tmp/lib")
        assert worker is not None
        assert worker._mgr is mock_mgr
        assert worker.parsed_list == []
        assert worker.library_root == "/tmp/lib"
        assert worker._stopped is False
        assert worker._overwrite is False

    def test_signals_exist(self, mock_mgr):
        """ArchiveWorker 包含所有预期的 Qt 信号。"""
        from pilotstd.ui.workers.archive import ArchiveWorker

        worker = ArchiveWorker(mgr=mock_mgr, parsed_list=[], library_root="/tmp/lib")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "batch_ready")
        assert hasattr(worker, "finished_signal")
        assert hasattr(worker, "error")

    def test_stop_sets_flag(self, mock_mgr):
        """stop() 设置 _stopped = True。"""
        from pilotstd.ui.workers.archive import ArchiveWorker

        worker = ArchiveWorker(mgr=mock_mgr, parsed_list=[], library_root="/tmp/lib")
        worker.stop()
        assert worker._stopped is True

    def test_init_with_optional_params(self, mock_mgr):
        """创建 ArchiveWorker 时传入所有可选参数。"""
        from pilotstd.ui.workers.archive import ArchiveWorker

        pause_event = MagicMock()
        config = MagicMock()
        worker = ArchiveWorker(
            mgr=mock_mgr,
            parsed_list=[1, 2, 3],
            library_root="/tmp/lib",
            config=config,
            overwrite=True,
            pause_event=pause_event,
        )
        assert worker.parsed_list == [1, 2, 3]
        assert worker._config is config
        assert worker._overwrite is True
        assert worker._pause_event is pause_event

    def test_target_path_returns_str(self, mock_mgr):
        """target_path 静态方法返回有效路径字符串。"""
        from pilotstd.models import ParsedStdInfo
        from pilotstd.ui.workers.archive import ArchiveWorker

        parsed = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB/T",
            number=12345,
            year=2024,
            std_name="测试标准",
        )
        result = ArchiveWorker.target_path(parsed, "/tmp/lib")
        assert isinstance(result, str)
        assert result.startswith("/tmp/lib")
        assert "12345" in result
        assert result.endswith(".pdf")

    def test_target_path_with_effect_status_expired(self, mock_mgr):
        """废止标准的 target_path 包含'过期作废'子目录。"""
        from pilotstd.models import ParsedStdInfo
        from pilotstd.ui.workers.archive import ArchiveWorker

        parsed = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB/T",
            number=12345,
            year=2024,
            std_name="已废止标准",
            effect_status="废止",
        )
        result = ArchiveWorker.target_path(parsed, "/tmp/lib")
        assert "过期作废" in result


# ============================================================================
# 测试 5：auto.py — AutoWorker（9 行未覆盖）
# ============================================================================


class TestAutoWorker:
    """覆盖 AutoWorker 的创建、信号、stop 方法和 _emit_scan_batch。"""

    def test_create(self, mock_mgr):
        """创建 AutoWorker 不崩溃。"""
        from pilotstd.ui.workers.auto import AutoWorker

        worker = AutoWorker(mgr=mock_mgr, root_path="/tmp/scan")
        assert worker is not None
        assert worker._mgr is mock_mgr
        assert worker._root_path == "/tmp/scan"
        assert worker._stopped is False

    def test_all_signals_exist(self, mock_mgr):
        """AutoWorker 包含全部 10 个 Qt 信号。"""
        from pilotstd.ui.workers.auto import AutoWorker

        worker = AutoWorker(mgr=mock_mgr, root_path="/tmp/scan")
        expected_signals = [
            "scan_batch",
            "scan_progress",
            "query_progress",
            "query_result",
            "download_progress",
            "download_result",
            "archive_result",
            "stage_changed",
            "finished_signal",
            "error",
        ]
        for sig_name in expected_signals:
            assert hasattr(worker, sig_name), f"AutoWorker 缺少信号 {sig_name}"

    def test_stop_sets_flag(self, mock_mgr):
        """stop() 设置 _stopped = True。"""
        from pilotstd.ui.workers.auto import AutoWorker

        worker = AutoWorker(mgr=mock_mgr, root_path="/tmp/scan")
        worker.stop()
        assert worker._stopped is True

    def test_emit_scan_batch_when_not_stopped(self, mock_mgr, qtbot):
        """_emit_scan_batch 在未停止时发射 scan_batch 信号。"""
        from pilotstd.ui.workers.auto import AutoWorker

        worker = AutoWorker(mgr=mock_mgr, root_path="/tmp/scan")
        received = []

        worker.scan_batch.connect(lambda rows: received.append(rows))

        batch_data = [{"file": "a.pdf"}, {"file": "b.pdf"}]
        worker._emit_scan_batch(batch_data)
        assert len(received) == 1
        assert received[0] == batch_data

    def test_emit_scan_batch_when_stopped(self, mock_mgr, qtbot):
        """_emit_scan_batch 在停止后不发射信号。"""
        from pilotstd.ui.workers.auto import AutoWorker

        worker = AutoWorker(mgr=mock_mgr, root_path="/tmp/scan")
        worker.stop()
        received = []

        worker.scan_batch.connect(lambda rows: received.append(rows))

        worker._emit_scan_batch([{"file": "a.pdf"}])
        assert len(received) == 0


# ============================================================================
# 测试 5a：AutoWorker.run() — 补覆盖 L40-61
# ============================================================================


class TestAutoWorkerRun:
    """AutoWorker.run() 方法补测试 — 覆盖 L40-61 全部路径"""

    @pytest.fixture
    def auto_worker(self):
        """创建带 mock manager 的 AutoWorker 实例"""
        from pilotstd.ui.workers.auto import AutoWorker

        mgr = MagicMock()
        worker = AutoWorker(mgr=mgr, root_path="/fake/root")
        return worker, mgr

    def test_run_normal_completion_emits_finished_and_stage_signals(self, qtbot, auto_worker):
        """正常路径：auto_run_stream 返回 report → finished_signal 收到完整 dict"""
        worker, mgr = auto_worker
        expected_report = {"scanned": 4, "queried": 4, "downloaded": 4, "archived": 4}
        mgr.auto_run_stream.return_value = expected_report

        with qtbot.waitSignal(worker.finished_signal, timeout=3000) as blocker:
            worker.run()

        assert blocker.args == [expected_report]
        assert mgr.auto_run_stream.call_count == 1

    def test_run_exception_emits_error_and_empty_finished(self, qtbot, auto_worker):
        """异常路径：auto_run_stream 抛异常 → error 信号 + finally 仍发空 report"""
        worker, mgr = auto_worker
        mgr.auto_run_stream.side_effect = RuntimeError("boom")

        with qtbot.waitSignals([worker.error, worker.finished_signal], timeout=3000) as blocker:
            worker.run()

        events = blocker.all_signals_and_args
        assert len(events) == 2
        assert events[0].args == ("boom",)
        assert events[1].args == ({},)

    def test_run_callbacks_emit_corresponding_signals(self, qtbot, auto_worker):
        """回调路径：验证 on_* 回调正确转发为 Qt Signal"""
        worker, mgr = auto_worker

        def fake_stream(*args, **kwargs):
            on_scan_batch = kwargs.get("on_scan_batch")
            if on_scan_batch:
                on_scan_batch([{"id": 1}])

            on_query_progress = kwargs.get("on_query_progress")
            if on_query_progress:
                on_query_progress(5, 10)

            on_download_result = kwargs.get("on_download_result")
            if on_download_result:
                on_download_result(0, "ok")

            on_stage_change = kwargs.get("on_stage_change")
            if on_stage_change:
                on_stage_change("download", 1, 4)

            return {"scanned": 2}

        mgr.auto_run_stream.side_effect = fake_stream

        with qtbot.waitSignals(
            [worker.scan_batch, worker.query_progress, worker.download_result, worker.stage_changed],
            timeout=3000
        ) as blocker:
            worker.run()

        args_list = [e.args for e in blocker.all_signals_and_args]
        assert len(args_list) == 4
        assert args_list[0] == ([{"id": 1}],)
        assert args_list[1] == (5, 10)
        assert args_list[2] == (0, "ok")
        assert args_list[3] == ("download", 1, 4)


# ============================================================================
# 测试 6：download.py — DownloadWorker（18 行未覆盖）
# ============================================================================


class TestDownloadWorker:
    """覆盖 DownloadWorker 的创建、信号、stop 方法。"""

    def test_create(self, mock_mgr):
        """创建 DownloadWorker 不崩溃。"""
        from pilotstd.ui.workers.download import DownloadWorker

        worker = DownloadWorker(mgr=mock_mgr, parsed_list=[])
        assert worker is not None
        assert worker._mgr is mock_mgr
        assert worker.parsed_list == []
        assert worker._stopped is False

    def test_signals_exist(self, mock_mgr):
        """DownloadWorker 包含所有预期的 Qt 信号。"""
        from pilotstd.ui.workers.download import DownloadWorker

        worker = DownloadWorker(mgr=mock_mgr, parsed_list=[])
        assert hasattr(worker, "progress")
        assert hasattr(worker, "batch_ready")
        assert hasattr(worker, "finished_signal")
        assert hasattr(worker, "error")

    def test_stop_sets_flag(self, mock_mgr):
        """stop() 设置 _stopped = True。"""
        from pilotstd.ui.workers.download import DownloadWorker

        worker = DownloadWorker(mgr=mock_mgr, parsed_list=[])
        worker.stop()
        assert worker._stopped is True

    def test_init_with_pause_event(self, mock_mgr):
        """创建 DownloadWorker 时传入 pause_event。"""
        from pilotstd.ui.workers.download import DownloadWorker

        pause_event = MagicMock()
        worker = DownloadWorker(mgr=mock_mgr, parsed_list=[1, 2], pause_event=pause_event)
        assert worker._pause_event is pause_event
        assert worker.parsed_list == [1, 2]


# ============================================================================
# 测试 7：normalize.py — NormalizeWorker（4 行未覆盖）
# ============================================================================


class TestNormalizeWorker:
    """覆盖 NormalizeWorker 的创建、信号、stop 方法。"""

    def test_create(self, mock_mgr):
        """创建 NormalizeWorker 不崩溃。"""
        from pilotstd.ui.workers.normalize import NormalizeWorker

        worker = NormalizeWorker(mgr=mock_mgr, parsed_list=[])
        assert worker is not None
        assert worker._mgr is mock_mgr
        assert worker.parsed_list == []
        assert worker._stopped is False

    def test_signals_exist(self, mock_mgr):
        """NormalizeWorker 包含所有预期的 Qt 信号。"""
        from pilotstd.ui.workers.normalize import NormalizeWorker

        worker = NormalizeWorker(mgr=mock_mgr, parsed_list=[])
        assert hasattr(worker, "progress")
        assert hasattr(worker, "batch_ready")
        assert hasattr(worker, "finished_signal")
        assert hasattr(worker, "error")

    def test_stop_sets_flag(self, mock_mgr):
        """stop() 设置 _stopped = True。"""
        from pilotstd.ui.workers.normalize import NormalizeWorker

        worker = NormalizeWorker(mgr=mock_mgr, parsed_list=[])
        worker.stop()
        assert worker._stopped is True

    def test_init_with_pause_event(self, mock_mgr):
        """创建 NormalizeWorker 时传入 pause_event。"""
        from pilotstd.ui.workers.normalize import NormalizeWorker

        pause_event = MagicMock()
        worker = NormalizeWorker(mgr=mock_mgr, parsed_list=[], pause_event=pause_event)
        assert worker._pause_event is pause_event


# ============================================================================
# 测试 8：query.py — QueryWorker（6 行未覆盖）
# ============================================================================


class TestQueryWorker:
    """覆盖 QueryWorker 的创建、信号、stop 方法。"""

    def test_create(self, mock_mgr):
        """创建 QueryWorker 不崩溃。"""
        from pilotstd.ui.workers.query import QueryWorker

        worker = QueryWorker(manager=mock_mgr, parsed_list=[])
        assert worker is not None
        assert worker._mgr is mock_mgr
        assert worker.parsed_list == []
        assert worker._stopped is False
        assert worker._site is None
        assert worker._force_refresh is False

    def test_signals_exist(self, mock_mgr):
        """QueryWorker 包含所有预期的 Qt 信号。"""
        from pilotstd.ui.workers.query import QueryWorker

        worker = QueryWorker(manager=mock_mgr, parsed_list=[])
        assert hasattr(worker, "progress")
        assert hasattr(worker, "result_ready")
        assert hasattr(worker, "batch_ready")
        assert hasattr(worker, "finished_signal")
        assert hasattr(worker, "error")

    def test_stop_sets_flag(self, mock_mgr):
        """stop() 设置 _stopped = True。"""
        from pilotstd.ui.workers.query import QueryWorker

        worker = QueryWorker(manager=mock_mgr, parsed_list=[])
        worker.stop()
        assert worker._stopped is True

    def test_init_with_all_optional_params(self, mock_mgr):
        """创建 QueryWorker 时传入全部可选参数。"""
        from pilotstd.ui.workers.query import QueryWorker

        pause_event = MagicMock()
        worker = QueryWorker(
            manager=mock_mgr,
            parsed_list=[1, 2, 3],
            pause_event=pause_event,
            site="njbz365",
            force_refresh=True,
        )
        assert worker._pause_event is pause_event
        assert worker._site == "njbz365"
        assert worker._force_refresh is True


class TestQueryWorkerPauseEvent:
    """QueryWorker set_pause_event 补测试 — 覆盖 L89-90"""

    def test_run_calls_set_pause_event_when_provided(self, qtbot):
        """构造时传入 pause_event → run() 中调用 mgr.set_pause_event"""
        import threading

        from pilotstd.ui.workers.query import QueryWorker

        mgr = MagicMock()
        pause_event = threading.Event()
        worker = QueryWorker(
            manager=mgr,
            parsed_list=[],
            pause_event=pause_event,
        )

        mgr.query_stream.return_value = ([], MagicMock())

        with qtbot.waitSignal(worker.finished_signal, timeout=3000):
            worker.run()

        mgr.set_pause_event.assert_called_once_with(pause_event)


# ============================================================================
# 测试 9：scan.py — ScanWorker（6 行未覆盖）
# ============================================================================


class TestScanWorker:
    """覆盖 ScanWorker 的创建、信号、stop 方法。"""

    def test_create(self, mock_mgr):
        """创建 ScanWorker 不崩溃。"""
        from pilotstd.ui.workers.scan import ScanWorker

        worker = ScanWorker(mgr=mock_mgr, root_path="/tmp/scan")
        assert worker is not None
        assert worker._mgr is mock_mgr
        assert worker._root_path == "/tmp/scan"
        assert worker._stopped is False
        assert worker.unrecognized == []

    def test_signals_exist(self, mock_mgr):
        """ScanWorker 包含所有预期的 Qt 信号。"""
        from pilotstd.ui.workers.scan import ScanWorker

        worker = ScanWorker(mgr=mock_mgr, root_path="/tmp/scan")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "batch_ready")
        assert hasattr(worker, "finished_signal")
        assert hasattr(worker, "error")

    def test_stop_sets_flag(self, mock_mgr):
        """stop() 设置 _stopped = True。"""
        from pilotstd.ui.workers.scan import ScanWorker

        worker = ScanWorker(mgr=mock_mgr, root_path="/tmp/scan")
        worker.stop()
        assert worker._stopped is True

    def test_init_with_pause_event(self, mock_mgr):
        """创建 ScanWorker 时传入 pause_event。"""
        from pilotstd.ui.workers.scan import ScanWorker

        pause_event = MagicMock()
        worker = ScanWorker(mgr=mock_mgr, root_path="/tmp/scan", pause_event=pause_event)
        assert worker._pause_event is pause_event


# ============================================================================
# 测试 10：update_download.py — UpdateDownloadWorker（22 行未覆盖）
# ============================================================================


class TestUpdateDownloadWorker:
    """覆盖 UpdateDownloadWorker 的创建、信号和 run 方法基本逻辑。"""

    @pytest.fixture
    def mock_release(self):
        """模拟 GitHub Release 数据结构。"""
        return {
            "download_url": "https://example.com/release/v1.0.zip",
            "filename": "PilotStd_v1.0.zip",
            "body": "## Release Notes\nSHA256: abc123def456\n",
        }

    def test_create(self, mock_release):
        """创建 UpdateDownloadWorker 不崩溃。"""
        from pilotstd.ui.workers.update_download import UpdateDownloadWorker

        worker = UpdateDownloadWorker(release=mock_release)
        assert worker is not None
        assert worker._release is mock_release

    def test_signals_exist(self, mock_release):
        """UpdateDownloadWorker 包含所有预期的 Qt 信号。"""
        from pilotstd.ui.workers.update_download import UpdateDownloadWorker

        worker = UpdateDownloadWorker(release=mock_release)
        assert hasattr(worker, "progress_msg")
        assert hasattr(worker, "download_ready")
        assert hasattr(worker, "download_failed")

    def test_run_emits_progress_msg(self, mock_release, qtbot):
        """run() 启动后发射 progress_msg 信号。"""
        from pilotstd.ui.workers.update_download import UpdateDownloadWorker

        worker = UpdateDownloadWorker(release=mock_release)
        messages = []

        worker.progress_msg.connect(lambda msg: messages.append(msg))

        # Mock 内部依赖以阻止真实网络和文件操作
        with (
            patch("pilotstd.platform.updater.download_update", return_value=True),
            patch("pilotstd.platform.updater.extract_sha256_from_body", return_value="abc123"),
            patch("pilotstd.platform.updater.generate_update_script", return_value="/tmp/update.bat"),
        ):
            worker.run()

            # 第一个进度消息应该是"正在下载 ..."
            assert len(messages) >= 1
            assert "正在下载" in messages[0] or "下载" in messages[0]

    def test_run_download_failed(self, mock_release, qtbot):
        """下载失败时发射 download_failed 信号。"""
        from pilotstd.ui.workers.update_download import UpdateDownloadWorker

        worker = UpdateDownloadWorker(release=mock_release)
        failures = []

        worker.download_failed.connect(lambda msg: failures.append(msg))

        with (
            patch("pilotstd.platform.updater.download_update", return_value=False),
            patch("pilotstd.platform.updater.extract_sha256_from_body", return_value="abc123"),
        ):
            worker.run()
            assert len(failures) == 1
            assert "下载或校验失败" in failures[0]

    def test_run_exception_emits_failed(self, mock_release, qtbot):
        """下载过程抛异常时发射 download_failed 信号。"""
        from pilotstd.ui.workers.update_download import UpdateDownloadWorker

        worker = UpdateDownloadWorker(release=mock_release)
        failures = []

        worker.download_failed.connect(lambda msg: failures.append(msg))

        with (
            patch("pilotstd.platform.updater.download_update", side_effect=Exception("网络错误")),
            patch("pilotstd.platform.updater.extract_sha256_from_body", return_value="abc123"),
        ):
            worker.run()
            assert len(failures) == 1
            assert "网络错误" in failures[0]

    def test_run_success_emits_download_ready(self, mock_release, qtbot, tmp_path):
        """下载成功时发射 download_ready 信号。"""
        from pilotstd.ui.workers.update_download import UpdateDownloadWorker

        worker = UpdateDownloadWorker(release=mock_release)
        ready_paths = []

        worker.download_ready.connect(lambda path: ready_paths.append(path))

        with (
            patch("pilotstd.platform.updater.download_update", return_value=True),
            patch("pilotstd.platform.updater.extract_sha256_from_body", return_value="abc123"),
            patch("pilotstd.platform.updater.generate_update_script", return_value=str(tmp_path / "update.bat")),
            patch("os.access", return_value=True),
        ):
            worker.run()
            assert len(ready_paths) == 1

    def test_run_write_permission_denied(self, mock_release, qtbot):
        """无法写入 exe 目录时发射 download_failed。"""
        from pilotstd.ui.workers.update_download import UpdateDownloadWorker

        worker = UpdateDownloadWorker(release=mock_release)
        failures = []

        worker.download_failed.connect(lambda msg: failures.append(msg))

        with (
            patch("pilotstd.platform.updater.download_update", return_value=True),
            patch("pilotstd.platform.updater.extract_sha256_from_body", return_value="abc123"),
            patch("builtins.open", side_effect=PermissionError("mocked")),
        ):
            worker.run()
            assert len(failures) == 1
            assert "无法写入" in failures[0] or "管理员" in failures[0]


# ============================================================================
# 集成测试：通过 workers.py 的兼容导入路径验证所有 Worker
# ============================================================================


class TestWorkersViaCompatImport:
    """通过 workers.py 的兼容导入路径验证所有 Worker 类可正常实例化。"""

    def test_import_all_workers_from_compat_module(self, mock_mgr):
        """从 pilotstd.ui.workers 导入所有 Worker 类均可正常实例化。"""
        from pilotstd.ui.workers import (
            AnnounceWorker,
            ArchiveWorker,
            AutoWorker,
            DownloadWorker,
            NormalizeWorker,
            QueryWorker,
            ScanWorker,
        )

        # 所有 Worker 均可创建，不抛异常
        w1 = AnnounceWorker(mgr=mock_mgr)
        w2 = ArchiveWorker(mgr=mock_mgr, parsed_list=[], library_root="/tmp")
        w3 = AutoWorker(mgr=mock_mgr, root_path="/tmp")
        w4 = DownloadWorker(mgr=mock_mgr, parsed_list=[])
        w5 = NormalizeWorker(mgr=mock_mgr, parsed_list=[])
        w6 = QueryWorker(manager=mock_mgr, parsed_list=[])
        w7 = ScanWorker(mgr=mock_mgr, root_path="/tmp")

        assert all([w1, w2, w3, w4, w5, w6, w7])

    def test_import_common_items_from_compat_module(self):
        """从 pilotstd.ui.workers 导入 _common 的工具项。"""
        from pilotstd.ui.workers import LogHandler, RowUpdate, _pct

        assert callable(_pct)
        assert RowUpdate is not None
        assert LogHandler is not None
