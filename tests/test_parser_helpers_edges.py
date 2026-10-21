"""D-13 P1：ResultBuilder / NumberExtractor / FileKindDetector / 兼容层的边界覆盖。"""

from __future__ import annotations

from pilotstd.scan.parser._file_kind_detector import FileKindDetector
from pilotstd.scan.parser._number_extractor import NumberExtractor
from pilotstd.scan.parser._result_builder import ResultBuilder, get_validate_fail_count
from pilotstd.scan.parser._utils import UtilsMixin


def _builder() -> ResultBuilder:
    return ResultBuilder({"ANSI": "ANSI", "API": "API"}, lambda: "std")


def test_trim_prefix_variants() -> None:
    b = _builder()
    assert b.trim_prefix("ANSI API Standard", "") == "ANSI API"
    assert b.trim_prefix("XYZ", "") == "XYZ"
    assert b.trim_prefix("XYZ Other", "") == "XYZ"


def test_validate_result_failure_reasons_and_count() -> None:
    before = get_validate_fail_count()
    assert ResultBuilder.validate_result(2020, 1, "GB") is True
    assert ResultBuilder.validate_result(2020, 1, "") is False
    assert ResultBuilder.validate_result(2020, 0, "GB") is False
    assert ResultBuilder.validate_result(0, 1, "GB") is False
    assert ResultBuilder.validate_result(1800, 1, "GB") is False
    assert ResultBuilder.validate_result(0, 1, "GB", require_year=False) is True
    assert get_validate_fail_count() == before + 4


def test_clean_std_name_removes_language_and_edition() -> None:
    b = _builder()
    assert "中文" not in b.clean_std_name("标题（中文版）第2版")
    assert b.clean_std_name("标题") == "标题"


def test_number_extractor_edge_inputs() -> None:
    assert NumberExtractor.extract_number("") == (None, "", "")
    assert NumberExtractor.extract_number("abc") == (None, "", "")
    assert NumberExtractor.extract_part("X") is None
    assert NumberExtractor.extract_num_prefix("") == ""
    assert NumberExtractor.extract_part("G810") == 810


def test_file_kind_detector_all_keywords() -> None:
    for name, label in (
        ("扫描版", "扫描版"),
        ("扫描件", "扫描版"),
        ("水印版", "水印版"),
        ("文本版", "文本版"),
        ("文字版", "文本版"),
        ("可编辑版", "文本版"),
    ):
        assert FileKindDetector.detect(name) == label
    assert FileKindDetector.detect("普通文件") == ""


def test_utils_compat_alias() -> None:
    from pilotstd.scan.parser._core import ParserCore

    assert UtilsMixin is ParserCore


def test_number_extractor_more_edges() -> None:
    assert NumberExtractor.normalize_year("2020") == 2020
    assert NumberExtractor.extract_number("12A3") == (None, "", "")
    assert NumberExtractor.extract_part("") is None
    assert NumberExtractor.extract_number("6D") == (6, "D", "6D")
    assert NumberExtractor.extract_num_prefix("B16") == "B"


def test_build_result_success_and_failure() -> None:
    b = ResultBuilder({"GB": "GB"}, lambda: "扫描版")
    info = b.build_result("GB 1-2020 标题", 10, "GB", 1, None, 2020)
    assert info is not None
    assert info.file_kind == "扫描版"
    assert info.std_name == "标题"
    assert b.build_result("GB 1-2020 标题", 2, "", 1, None, 2020) is None
    assert b.build_result("GB 1-2020 123", 10, "GB", 1, None, 2020).std_name == ""


def test_classify_unknown_code() -> None:
    from pilotstd.scan.parser import StandardParser

    assert StandardParser._classify_code(None, "XYZ") == "unknown"
