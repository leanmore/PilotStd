"""wechat_ip 浏览器关闭：Playwright 引擎必须 stop，防止 driver 进程残留。"""

from __future__ import annotations

from unittest.mock import MagicMock

from pilotstd.wechat_ip.browser import WechatIPUpdater


def test_close_stops_playwright_engine():
    updater = WechatIPUpdater()
    browser = MagicMock()
    pw = MagicMock()
    updater._browser = browser
    updater._pw = pw
    updater.close()
    browser.close.assert_called_once()
    pw.stop.assert_called_once()
    assert updater._browser is None
    assert updater._pw is None


def test_close_still_stops_playwright_when_browser_close_raises():
    updater = WechatIPUpdater()
    updater._browser = MagicMock()
    updater._browser.close.side_effect = RuntimeError("boom")
    pw = MagicMock()
    updater._pw = pw
    updater.close()
    pw.stop.assert_called_once()
