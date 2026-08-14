"""pilotstd/core/download_utils.py 补测 — 下载列表导入解析全覆盖。"""
from unittest.mock import patch

from pilotstd.core.download_utils import _looks_like_csv, _parse_csv_content, parse_download_sources


class TestParseDownloadSources:
    """parse_download_sources — 正常×2 + 边界×1 + 异常×1 + 状态转换×1。"""

    def test_normal_txt_each_line_one_number(self):
        """TXT 模式：每行一个标准号。"""
        result = parse_download_sources("GB/T 12345-2020\nISO 9001:2015\nGB/T 1.1-2020")
        assert len(result["valid"]) == 3
        assert result["invalid"] == []
        assert result["duplicates"] == []

    def test_normal_csv_with_standard_number_column(self):
        """CSV 模式：自动识别 standard_number 列并提取。"""
        csv_text = "standard_number,year\nGB/T 12345-2020,2020\nISO 9001:2015,2015"
        result = parse_download_sources(csv_text)
        assert "GB/T 12345-2020" in result["valid"]
        assert "ISO 9001:2015" in result["valid"]

    def test_boundary_empty_and_whitespace_input(self):
        """空输入和纯空白输入返回全空列表。"""
        for inp in [None, "", "   \n  "]:
            result = parse_download_sources(inp)
            assert result == {"valid": [], "invalid": [], "duplicates": []}

    def test_exception_invalid_and_duplicate_numbers(self):
        """无效标准号和重复标准号被正确归类。"""
        text = "GB/T 12345-2020\nnot_a_standard\nGB/T 12345-2020\nxyz"
        result = parse_download_sources(text)
        assert "GB/T 12345-2020" in result["valid"]
        assert "not_a_standard" in result["invalid"]
        assert "xyz" in result["invalid"]
        assert "GB/T 12345-2020" in result["duplicates"]

    def test_state_mixed_valid_invalid_duplicate_counts(self):
        """有效+无效+重复的完整状态分布验证。"""
        text = "\n".join([
            "GB/T 1.1-2020",
            "bad-entry!!!",
            "GB/T 1.1-2020",
            "ISO 9001:2015",
            "",
            "another-bad",
        ])
        result = parse_download_sources(text)
        assert len(result["valid"]) == 2
        assert len(result["invalid"]) == 2
        assert len(result["duplicates"]) == 1


class TestLooksLikeCsv:
    """CSV 启发式检测。"""

    def test_detect_csv_header_with_comma(self):
        """含 standard_number 列名和逗号 → 识别为 CSV。"""
        assert _looks_like_csv("standard_number,year\nGB/T 12345,2020")

    def test_detect_csv_header_with_tab(self):
        """含 standard_number 列名和制表符 → 识别为 TSV。"""
        assert _looks_like_csv("standard_number\tyear\nGB/T 12345\t2020")

    def test_detect_not_csv_plain_text(self):
        """不含 standard_number 列名 → 不识为 CSV。"""
        assert not _looks_like_csv("GB/T 12345-2020\nISO 9001:2015")

    def test_boundary_empty_input(self):
        """空文本不误识别为 CSV。"""
        assert not _looks_like_csv("")

    def test_detect_csv_case_insensitive(self):
        """列名大小写不敏感。"""
        assert _looks_like_csv("Standard_Number,Year\nGB/T 12345,2020")


class TestParseCsvContent:
    """CSV 内容解析。"""

    def test_extract_standard_number_column(self):
        """正确提取 standard_number 列。"""
        csv_text = "standard_number,year,note\nGB/T 1.1,2020,abc\nISO 9001,2015,def"
        result = _parse_csv_content(csv_text)
        assert result == ["GB/T 1.1", "ISO 9001"]

    def test_skip_empty_values_in_csv(self):
        """空白标准号值被跳过。"""
        csv_text = "standard_number\nGB/T 1.1\n\nISO 9001"
        result = _parse_csv_content(csv_text)
        assert len(result) == 2

    def test_exception_malformed_csv_returns_empty(self):
        """畸形 CSV 返回空列表不崩溃。"""
        assert _parse_csv_content("not,a,valid,csv,header") == []

    def test_exception_csv_parse_error_returns_empty(self):
        """CSV 解析异常被捕获，返回空列表。"""
        with patch("pilotstd.core.download_utils.csv.DictReader", side_effect=Exception("bad csv")):
            result = _parse_csv_content("any,text")
            assert result == []
