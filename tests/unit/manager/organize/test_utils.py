"""_utils.py 单元测试 — 目标: 100%"""

import os
import pytest

from pilotstd.manager.organize._utils import (
    _is_word_or_template,
    _resolve_industry_in_path,
)


class TestIsWordOrTemplate:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("report.doc", True),
            ("report.docx", True),
            ("REPORT.DOC", True),
            ("REPORT.DOCX", True),
            ("path/to/file.Doc", True),
            ("path/to/file.DocX", True),
        ],
    )
    def test_returns_true_for_word_extensions(self, path, expected):
        assert _is_word_or_template(path) is expected

    @pytest.mark.parametrize(
        "path",
        [
            "standard.pdf",
            "readme.txt",
            "",
            "file.docm",
            "file.docx~",
            "file.xls",
            "file.ppt",
            "file.docc",
        ],
    )
    def test_returns_false_for_non_word_files(self, path):
        assert _is_word_or_template(path) is False


class TestResolveIndustryInPath:
    def test_empty_string_returns_empty(self):
        assert _resolve_industry_in_path("") == ""

    def test_unknown_code_returns_as_is(self):
        assert _resolve_industry_in_path("UNKNOWN_DIR/file.pdf") == "UNKNOWN_DIR/file.pdf"

    def test_no_sep_returns_as_is(self):
        assert _resolve_industry_in_path("just_a_file.pdf") == "just_a_file.pdf"

    def test_known_national_code_resolves(self):
        """GB 是 NATIONAL_CODES 成员 → 解析为 'GB 国家标准'"""
        result = _resolve_industry_in_path("GB" + os.sep + "file.pdf")
        assert "国家标准" in result
        assert result != "GB" + os.sep + "file.pdf"

    def test_known_industry_code_resolves(self):
        """AQ（安全生产）在 INDUSTRY_MAP 中 → 解析"""
        result = _resolve_industry_in_path("AQ" + os.sep + "sub" + os.sep + "file.pdf")
        assert "安全生产" in result
        assert result.startswith("AQ")

    def test_known_foreign_code_resolves(self):
        """ISO 在 FOREIGN_CODES 中 → 解析"""
        result = _resolve_industry_in_path("ISO" + os.sep + "file.pdf")
        assert "ISO" in result
        assert result != "ISO" + os.sep + "file.pdf"

    def test_single_segment_resolved(self):
        """只有一段路径，解析后仅返回解析名（不追加 parts[1]）"""
        result = _resolve_industry_in_path("GB")
        assert "国家标准" in result
        assert os.sep not in result

    def test_resolved_same_as_first_returns_unchanged(self):
        """解析结果与原名相同 → 返回原路径"""
        result = _resolve_industry_in_path("SomeCode")
        assert result == "SomeCode"
