"""pilotstd/core/export_utils.py 补测 — 导出文件名生成全覆盖。"""
import datetime
from unittest.mock import patch

import pytest
from pilotstd.core.export_utils import generate_export_batch_timestamp, get_export_filename


def _mock_now(year, month, day, hour, minute, second):
    """构造一个 fake 模块，datetime.datetime.now() 返回固定时间。"""
    fake_dt = datetime.datetime(year, month, day, hour, minute, second)
    FakeDatetime = type("FakeDatetime", (), {"now": classmethod(lambda cls: fake_dt)})
    return type("FakeModule", (), {"datetime": FakeDatetime})()


class TestGenerateExportBatchTimestamp:
    """时间戳生成 — 正常×2 + 边界×1 + 异常×1 + 状态转换×1。"""

    def test_normal_returns_yyyymmdd_hhmmss_format(self):
        """正常返回 YYYYMMDD_HHMMSS 格式，15 字符含下划线。"""
        ts = generate_export_batch_timestamp()
        assert len(ts) == 15
        assert ts[8] == "_"
        # 确保为数字和下划线组成
        assert ts.replace("_", "").isdigit()

    def test_normal_two_calls_in_same_batch_close_in_time(self):
        """同批次两次调用时间戳单调非递减。"""
        ts1 = generate_export_batch_timestamp()
        ts2 = generate_export_batch_timestamp()
        assert ts1 <= ts2

    def test_boundary_fixed_time_known_output(self):
        """固定时间点输出精确可预测。"""
        mock_dt = _mock_now(2026, 1, 15, 9, 5, 30)
        with patch("pilotstd.core.export_utils.datetime", mock_dt):
            assert generate_export_batch_timestamp() == "20260115_090530"

    def test_exception_midnight_rollover_preserves_format(self):
        """跨日边界（00:00:00）时间戳格式仍然正确。"""
        mock_dt = _mock_now(2026, 1, 15, 0, 0, 0)
        with patch("pilotstd.core.export_utils.datetime", mock_dt):
            ts = generate_export_batch_timestamp()
            assert ts == "20260115_000000"

    def test_state_consecutive_batches_unique_timestamps(self):
        """不同批次（模拟 1 秒前进）产生不同时间戳。"""
        ts = generate_export_batch_timestamp()
        mock_dt = _mock_now(2027, 6, 30, 23, 59, 59)
        with patch("pilotstd.core.export_utils.datetime", mock_dt):
            ts2 = generate_export_batch_timestamp()
        assert ts != ts2


class TestGetExportFilename:
    """文件名生成 — 正常×2 + 边界×1 + 异常×1 + 状态转换×1。"""

    def test_normal_csv_filename(self):
        """标准 CSV 文件名：名称_时间戳.csv。"""
        fname = get_export_filename("标准导出", "20260115_090530")
        assert fname == "标准导出_20260115_090530.csv"

    def test_normal_custom_extension(self):
        """自定义扩展名如 .xlsx 正常工作。"""
        fname = get_export_filename("Report", "20260115_090530", ".xlsx")
        assert fname == "Report_20260115_090530.xlsx"

    def test_boundary_spaces_in_name_replaced_with_underscore(self):
        """名称中的空格替换为下划线，跨平台兼容。"""
        fname = get_export_filename("My Export Report", "20260115_090530")
        assert fname == "My_Export_Report_20260115_090530.csv"

    def test_exception_special_fs_characters_preserved(self):
        """冒号、斜杠等特殊字符原样保留（不崩溃，仅替换空格）。"""
        fname = get_export_filename("a:b/c", "20260115_090530")
        assert "a:b/c" in fname
        assert fname.endswith(".csv")

    def test_state_consecutive_spaces_all_replaced(self):
        """连续空格全部替换为下划线，tab 保留。"""
        fname = get_export_filename("a  b\tc", "20260115_090530")
        assert fname == "a__b\tc_20260115_090530.csv"
