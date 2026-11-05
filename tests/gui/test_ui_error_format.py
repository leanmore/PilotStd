"""桌面端错误格式化：PermissionError/WinError 32 → 中文可读提示。"""

import errno

from pilotstd.ui.errors import format_ui_error


def test_file_in_use_returns_chinese_hint():
    exc = PermissionError(13, "The process cannot access the file", r"C:\lib\GBT 1-2020.pdf")
    msg = format_ui_error(exc)
    assert "占用" in msg
    assert "PDF" in msg


def test_winerror_32_string_is_recognized():
    msg = format_ui_error(
        "[WinError 32] The process cannot access the file because it is being used by another process"
    )
    assert "占用" in msg


def test_disk_full_returns_chinese_hint():
    exc = OSError(errno.ENOSPC, "No space left on device")
    assert "空间" in format_ui_error(exc)


def test_plain_error_is_passthrough():
    assert format_ui_error(ValueError("boom")) == "boom"
