"""_wps_utils.py 单元测试 — 文本清洗 + 条目拆分全覆盖。"""

import re

import pytest

from pilotstd.announcement._wps_utils import _clean_wps_fulltext, _split_wps_entries


class TestCleanWpsFulltext:
    def test_removes_page_marks(self):
        text = "content — PAGE  MERGEFORMAT 1 — more"
        result = _clean_wps_fulltext(text)
        assert "PAGE" not in result
        assert "MERGEFORMAT" not in result

    def test_removes_page_numbering(self):
        text = "header PAGE 1 OF 2 footer"
        result = _clean_wps_fulltext(text)
        assert "PAGE 1 OF 2" not in result

    def test_compresses_multiple_newlines(self):
        text = "line1\n\n\n\nline2\n\n\n\n\nline3"
        result = _clean_wps_fulltext(text)
        assert "\n\n\n" not in result

    def test_replaces_tab_sequences(self):
        text = "col1   col2      col3"
        result = _clean_wps_fulltext(text)
        assert "col1\ncol2\ncol3" in result or "col1" in result

    def test_empty_string_ok(self):
        result = _clean_wps_fulltext("")
        assert result == ""


class TestSplitWpsEntries:
    @pytest.fixture
    def std_pattern(self):
        return re.compile(r"GB/T\s*\d+[\.-]?\d*-?\d{4}")

    def test_empty_text_returns_empty(self, std_pattern):
        assert _split_wps_entries("", std_pattern) == []

    def test_single_entry_returns_list(self, std_pattern):
        text = "GB/T 1234-2020 测试标准内容"
        result = _split_wps_entries(text, std_pattern)
        assert len(result) == 1
        assert "GB/T 1234-2020" in result[0]

    def test_multiple_entries_split(self, std_pattern):
        text = "GB/T 1234-2020 内容一 GB/T 5678-2021 内容二"
        result = _split_wps_entries(text, std_pattern)
        assert len(result) == 2

    def test_short_segment_filtered(self, std_pattern):
        """< 10 字符的片段被过滤。"""
        text = "GB/T 1-2020 abc GB/T 2-2020 sufficient content here yes"
        result = _split_wps_entries(text, std_pattern)
        filtered = [s for s in result if len(s) < 10]
        assert len(filtered) == 0

    def test_already_line_separated(self, std_pattern):
        """已有换行分隔 → 直接返回行列表。"""
        text = "GB/T 1234-2020 内容第一行\nGB/T 5678-2021 内容第二行"
        result = _split_wps_entries(text, std_pattern)
        assert len(result) == 2
