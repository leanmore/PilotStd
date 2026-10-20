"""D-13 P1：ParserCore 的委托方法逐项覆盖（正常路径由 test_parser* 覆盖）。"""

from __future__ import annotations

from pilotstd.scan.parser._core import ParserCore


def _core() -> ParserCore:
    return ParserCore({"GB": "GB"}, lambda: "std")


def test_delegates_text_clean_and_detectors() -> None:
    core = _core()
    assert core.clean("  GB/T 1.1-2020  ") == core.text_cleaner.clean("  GB/T 1.1-2020  ")
    assert core.detect_language("GB_T_1.1-2020.pdf") == core.language_detector.detect("GB_T_1.1-2020.pdf")
    assert core.detect_file_kind("GB_T_1.1-2020.pdf") == core.file_kind_detector.detect("GB_T_1.1-2020.pdf")


def test_delegates_number_extractors() -> None:
    core = _core()
    assert core.normalize_year("99") == core.number_extractor.normalize_year("99")
    assert core.extract_number("6D") == core.number_extractor.extract_number("6D")
    assert core.extract_num_prefix("B16") == core.number_extractor.extract_num_prefix("B16")
    assert core.extract_part("810G") == core.number_extractor.extract_part("810G")


def test_delegates_result_builder_helpers() -> None:
    core = _core()
    assert core.trim_prefix("GB", "GB/T 1.1") == core.result_builder.trim_prefix("GB", "GB/T 1.1")
    assert core.clean_std_name("  test  ") == core.result_builder.clean_std_name("  test  ")
    assert core.validate_result(2020, 1, "GB") == core.result_builder.validate_result(2020, 1, "GB")
