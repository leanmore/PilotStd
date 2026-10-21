"""Windows 文件名安全：GB/T、GB/Z 绝不能以带斜杠形式落盘。"""

from __future__ import annotations

from pilotstd.core.file_utils import make_standard_filename, safe_code_for_filename


def test_gb_t_and_gb_z_codes_have_no_slash_for_windows() -> None:
    for code, expected_prefix in (("GB/T", "GBT"), ("GB/Z", "GBZ")):
        name = make_standard_filename(code, 1, 2020, "测试名称")
        assert "/" not in name
        assert "\\" not in name
        assert name.startswith(expected_prefix + " ")


def test_safe_code_strips_slash() -> None:
    assert safe_code_for_filename("GB/T") == "GBT"
    assert safe_code_for_filename("GB/Z") == "GBZ"
    assert "/" not in safe_code_for_filename("NB/SH/T")


def test_invalid_chars_in_name_are_replaced() -> None:
    name = make_standard_filename("GB/T", 1, 2020, '名称/含:非法*字符?<>|')
    for ch in ("/", "\\", ":", "*", "?", "<", ">", "|"):
        assert ch not in name
