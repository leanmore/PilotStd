"""CloakBrowser 内核预检：binary_info 判定未安装/不可执行时返回明确原因。"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from pilotstd.wechat_ip.browser import browser_kernel_status


def test_kernel_ready_when_binary_executable(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "cloakbrowser",
        SimpleNamespace(binary_info=lambda: {"installed": True, "binary_path": sys.executable}),
    )
    available, reason = browser_kernel_status()
    assert available is True
    assert reason == ""


def test_kernel_missing_when_not_installed(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "cloakbrowser",
        SimpleNamespace(binary_info=lambda: {"installed": False, "binary_path": ""}),
    )
    available, reason = browser_kernel_status()
    assert available is False
    assert "not installed" in reason


def test_kernel_missing_when_binary_not_executable(monkeypatch, tmp_path):
    fake = tmp_path / "chrome"
    fake.write_text("")
    monkeypatch.setitem(
        sys.modules,
        "cloakbrowser",
        SimpleNamespace(binary_info=lambda: {"installed": True, "binary_path": str(fake)}),
    )
    # Windows 的 os.access(X_OK) 对普通文件也返回 True，测试里显式模拟不可执行。
    monkeypatch.setattr("pilotstd.wechat_ip.browser.os.access", lambda *args: False)
    available, reason = browser_kernel_status()
    assert available is False
    assert "not executable" in reason
