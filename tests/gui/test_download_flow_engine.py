# tests/gui/test_download_flow_engine.py
"""DownloadFlowEngine 单元测试 — 纯 Python，不启动 QApplication。

覆盖 4 个静态方法的：
- 正常路径
- 边界值（空列表、空字符串、零阈值、未来日期）
- 异常容错（无效 CSV、损坏日期、非法路径）
"""

from __future__ import annotations

import datetime

import pytest

from pilotstd.ui.core.handlers.download_flow_engine import (
    DEFAULT_THRESHOLD_DAYS,
    DownloadFlowEngine,
)

# ═══════════════════════════════════════════════════════════════════
# 测试辅助：模拟 ParsedStdInfo
# ═══════════════════════════════════════════════════════════════════


class _FakeStd:
    """模拟 ParsedStdInfo，仅包含测试需要的属性。"""

    def __init__(self, found_publish_date: str = "", found_number: str = ""):
        self.found_publish_date = found_publish_date
        self.found_number = found_number

    def get_full_number(self) -> str:
        return self.found_number or "N/A"


@pytest.fixture
def engine() -> DownloadFlowEngine:
    return DownloadFlowEngine()


# ═══════════════════════════════════════════════════════════════════
# filter_too_new_standards
# ═══════════════════════════════════════════════════════════════════


class TestFilterTooNewStandards:
    def test_normal(self, engine):
        today = datetime.date.today()
        old_date = (today - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        recent_date = (today - datetime.timedelta(days=5)).strftime("%Y-%m-%d")

        standards = [
            _FakeStd(found_publish_date=old_date),
            _FakeStd(found_publish_date=recent_date),
            _FakeStd(found_publish_date=""),
        ]
        result = engine.filter_too_new_standards(standards, threshold_days=20)
        assert len(result) == 1
        assert result[0] is standards[1]

    def test_empty_list(self, engine):
        assert engine.filter_too_new_standards([]) == []

    def test_all_old(self, engine):
        today = datetime.date.today()
        old1 = (today - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
        old2 = (today - datetime.timedelta(days=200)).strftime("%Y-%m-%d")
        standards = [_FakeStd(found_publish_date=old1), _FakeStd(found_publish_date=old2)]
        assert engine.filter_too_new_standards(standards, threshold_days=20) == []

    def test_all_too_new(self, engine):
        today = datetime.date.today()
        d1 = (today - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        d2 = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        standards = [_FakeStd(found_publish_date=d1), _FakeStd(found_publish_date=d2)]
        result = engine.filter_too_new_standards(standards, threshold_days=20)
        assert len(result) == 2

    def test_zero_threshold(self, engine):
        """阈值为 0：任何标准都不满 0 天，无过新标准。"""
        today = datetime.date.today()
        today_str = today.strftime("%Y-%m-%d")
        yesterday_str = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        standards = [
            _FakeStd(found_publish_date=today_str),
            _FakeStd(found_publish_date=yesterday_str),
        ]
        result = engine.filter_too_new_standards(standards, threshold_days=0)
        assert len(result) == 0

    def test_explicit_reference_date(self, engine):
        ref = datetime.date(2026, 1, 15)
        pub = "2026-01-10"  # 5 days before ref
        standards = [_FakeStd(found_publish_date=pub)]
        result = engine.filter_too_new_standards(standards, threshold_days=10, reference_date=ref)
        assert len(result) == 1

    def test_exact_boundary(self, engine):
        """恰好 threshold_days 天前不算过新。"""
        ref = datetime.date(2026, 1, 15)
        pub = "2026-01-05"  # exactly 10 days before ref
        standards = [_FakeStd(found_publish_date=pub)]
        result = engine.filter_too_new_standards(standards, threshold_days=10, reference_date=ref)
        assert len(result) == 0

    def test_invalid_date_format(self, engine):
        standards = [_FakeStd(found_publish_date="not-a-date")]
        result = engine.filter_too_new_standards(standards, threshold_days=20)
        assert result == []

    def test_no_publish_date_attr(self, engine):
        """对象没有 found_publish_date 属性 → 跳过。"""

        class NoDate:
            pass

        standards = [NoDate()]  # type: ignore[arg-type]
        result = engine.filter_too_new_standards(standards, threshold_days=20)  # type: ignore[arg-type]
        assert result == []

    def test_future_date(self, engine):
        """发布日期在未来 → 算过新。"""
        today = datetime.date.today()
        future = (today + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        standards = [_FakeStd(found_publish_date=future)]
        result = engine.filter_too_new_standards(standards, threshold_days=20)
        assert len(result) == 1

    def test_returned_references_are_same_objects(self, engine):
        """验证返回列表中的对象与输入是同一引用。"""
        today = datetime.date.today()
        pub = (today - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        s = _FakeStd(found_publish_date=pub)
        result = engine.filter_too_new_standards([s], threshold_days=20)
        assert result[0] is s


# ═══════════════════════════════════════════════════════════════════
# parse_download_csv
# ═══════════════════════════════════════════════════════════════════


class TestParseDownloadCsv:
    def test_normal(self, engine):
        csv_content = "number,title,year\nGB/T 1.1,标准名称,2020\nGB/T 2.0,另一个标准,2021"
        result = engine.parse_download_csv(csv_content)
        assert len(result) == 2
        assert result[0] == {"number": "GB/T 1.1", "title": "标准名称", "year": "2020"}
        assert result[1]["number"] == "GB/T 2.0"

    def test_empty_string(self, engine):
        assert engine.parse_download_csv("") == []

    def test_whitespace_only(self, engine):
        assert engine.parse_download_csv("   \n  \n  ") == []

    def test_none(self, engine):
        assert engine.parse_download_csv(None) == []  # type: ignore[arg-type]

    def test_header_only(self, engine):
        result = engine.parse_download_csv("col1,col2,col3")
        assert result == []

    def test_empty_rows_filtered(self, engine):
        csv_content = "col1,col2\na,b\n   ,   \nc,d\n"
        result = engine.parse_download_csv(csv_content)
        assert len(result) == 2

    def test_malformed_csv(self, engine):
        result = engine.parse_download_csv('"unclosed quote')
        assert result == []  # 容错不崩溃

    def test_bytes_input_returns_empty(self, engine):
        """非 str 类型输入 → 异常被捕获，返回空列表。"""
        result = engine.parse_download_csv(b"col1,col2\na,b")  # type: ignore[arg-type]
        assert result == []

    def test_single_column(self, engine):
        csv_content = "standard_number\nGB/T 1.1\nGB/T 2.0\nISO 9001"
        result = engine.parse_download_csv(csv_content)
        assert len(result) == 3
        assert result[0]["standard_number"] == "GB/T 1.1"

    def test_unicode(self, engine):
        csv_content = "编号,名称\nGB/T 1.1,标准化工作导则\nGB/T 2.0,标准化工作指南"
        result = engine.parse_download_csv(csv_content)
        assert len(result) == 2
        assert result[1]["名称"] == "标准化工作指南"


# ═══════════════════════════════════════════════════════════════════
# validate_download_paths
# ═══════════════════════════════════════════════════════════════════


class TestValidateDownloadPaths:
    def test_normal(self, engine):
        paths = ["GB/T 1.1-2020.pdf", "subdir/ISO 9001.pdf"]
        result = engine.validate_download_paths(paths, "/data/downloads")
        assert result["GB/T 1.1-2020.pdf"] is True
        assert result["subdir/ISO 9001.pdf"] is True

    def test_empty_list(self, engine):
        assert engine.validate_download_paths([], "/root") == {}

    def test_empty_path(self, engine):
        result = engine.validate_download_paths([""], "/root")
        assert result[""] is False

    def test_whitespace_only(self, engine):
        result = engine.validate_download_paths(["   "], "/root")
        assert result["   "] is False

    def test_null_byte_injection(self, engine):
        result = engine.validate_download_paths(["good.pdf\x00evil.exe"], "/root")
        assert result["good.pdf\x00evil.exe"] is False

    def test_path_traversal(self, engine):
        result = engine.validate_download_paths(["../../../etc/passwd"], "/root")
        assert result["../../../etc/passwd"] is False

    def test_path_traversal_encoded(self, engine):
        result = engine.validate_download_paths(["subdir/../../etc/passwd"], "/root")
        assert result["subdir/../../etc/passwd"] is False

    def test_path_too_long(self, engine):
        long_path = "x" * 5000 + ".pdf"
        result = engine.validate_download_paths([long_path], "/root")
        assert result[long_path] is False

    def test_non_string(self, engine):
        result = engine.validate_download_paths([None, 123], "/root")  # type: ignore[list-item]
        assert result["None"] is False
        assert result["123"] is False


# ═══════════════════════════════════════════════════════════════════
# deduplicate_downloads
# ═══════════════════════════════════════════════════════════════════


class TestDeduplicateDownloads:
    def test_normal(self, engine):
        items = [
            {"number": "GB/T 1.1", "name": "A"},
            {"number": "GB/T 2.0", "name": "B"},
            {"number": "GB/T 1.1", "name": "A-dup"},
        ]
        result = engine.deduplicate_downloads(items, "number")
        assert len(result) == 2
        assert result[0]["name"] == "A"  # 保留首次出现
        assert result[1]["name"] == "B"

    def test_empty_list(self, engine):
        assert engine.deduplicate_downloads([], "key") == []

    def test_no_duplicates(self, engine):
        items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        result = engine.deduplicate_downloads(items, "id")
        assert len(result) == 3

    def test_all_duplicates(self, engine):
        items = [{"id": "x"}, {"id": "x"}, {"id": "x"}]
        result = engine.deduplicate_downloads(items, "id")
        assert len(result) == 1

    def test_missing_key(self, engine):
        items = [{"id": "a"}, {"name": "b"}, {"id": "c"}]
        result = engine.deduplicate_downloads(items, "id")
        assert len(result) == 2  # 缺 key 的跳过

    def test_non_dict_items_skipped(self, engine):
        items = [{"id": "a"}, "not_a_dict", {"id": "b"}]  # type: ignore[list-item]
        result = engine.deduplicate_downloads(items, "id")
        assert len(result) == 2
        assert result[0] == {"id": "a"}
        assert result[1] == {"id": "b"}

    def test_none_value_skipped(self, engine):
        items = [{"id": None}, {"id": "a"}]  # type: ignore[list-item]
        result = engine.deduplicate_downloads(items, "id")
        assert len(result) == 1
        assert result[0]["id"] == "a"

    def test_preserves_order(self, engine):
        items = [
            {"n": "c"},
            {"n": "a"},
            {"n": "b"},
            {"n": "a"},  # dup
            {"n": "d"},
        ]
        result = engine.deduplicate_downloads(items, "n")
        assert [r["n"] for r in result] == ["c", "a", "b", "d"]


# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════


def test_default_threshold_days():
    assert DEFAULT_THRESHOLD_DAYS == 28
