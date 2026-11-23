"""tests/test_resource_leaks.py — 资源泄漏修复的回归守护（方向 C 批次 8）。

覆盖：
  NEW-37  `announcement/base.py` 的 `_fetch_list` 自己创建的 Session 必须关闭，
          外部注入的 `self._http` **不得**被关闭
  NEW-38  `query/network.py` 的 `safe_raw_get` / `safe_raw_post` 必须用 with 关闭 Session，
          且返回的 resp.content 仍可读（关闭前已缓存）
  NEW-40  `LogHandler.close()` 必须停掉批量刷新定时器

用源码级断言 + 行为级断言混合：
  - Session 关闭行为可 mock 验证（行为级，更可信）
  - 定时器停止可从源码结构验证（Qt 对象生命周期难以在无 GUI 环境稳定测）
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── NEW-38：safe_raw_get / safe_raw_post 的 Session 关闭 ──


class _FakeResp:
    """最小 Response 替身：content 是惰性属性，模拟 requests 的行为。"""

    def __init__(self, status_code=200, body=b"hello"):
        self.status_code = status_code
        self._body = body
        self.content_read_count = 0

    @property
    def content(self):
        self.content_read_count += 1
        return self._body


def test_safe_raw_get_closes_own_session():
    """safe_raw_get 必须关闭它自己创建的 Session。"""
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=False)

    resp = _FakeResp()
    with patch("pilotstd.query.network.requests.Session", return_value=fake_session), patch(
        "pilotstd.query.network.safe_request", return_value=resp
    ):
        from pilotstd.query.network import safe_raw_get

        got = safe_raw_get("http://x", "site")

    assert got is resp
    # with 语句退出 → Session 被关闭（__exit__ 被调用）
    fake_session.__exit__.assert_called_once()
    # 响应体在关闭前已被读取一次（保证关闭后调用方仍能读缓存）
    assert resp.content_read_count >= 1


def test_safe_raw_post_closes_own_session():
    """safe_raw_post 同理。"""
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=False)

    resp = _FakeResp()
    with patch("pilotstd.query.network.requests.Session", return_value=fake_session), patch(
        "pilotstd.query.network.safe_request", return_value=resp
    ):
        from pilotstd.query.network import safe_raw_post

        got = safe_raw_post("http://x", "site")

    assert got is resp
    fake_session.__exit__.assert_called_once()


# ── NEW-37：_fetch_list 的 owns_session 语义 ──


def test_fetch_list_source_has_owns_session_guard():
    """源码必须体现「只关自己创建的 Session」语义。"""
    src = (ROOT / "pilotstd" / "announcement" / "base.py").read_text(encoding="utf-8")
    assert "owns_session" in src, "缺少 owns_session 标志（无法区分自建/注入的 Session）"
    assert "finally:" in src
    assert "session.close()" in src
    # 必须在 finally 里带条件，不能无条件关闭注入的实例
    assert "if owns_session:" in src


def test_fetch_list_closes_own_session_but_not_injected():
    """行为级：自建 Session 关闭，注入 Session 不关闭。"""
    from pilotstd.announcement import base as base_mod

    # 构造一个最小子类实例（绕开抽象方法）
    class _Probe(base_mod.BaseAnnounceCrawler):
        standard_type = "probe"
        site_name = "probe-site"
        _list_url = "http://example.invalid/list"
        _detail_url = "http://example.invalid/detail"

        def __init__(self, http):
            self._http = http

    # 场景 A：注入 session → 不得关闭
    injected = MagicMock()
    injected.headers = {}
    with patch.object(base_mod, "safe_request", return_value=None):
        probe = _Probe(injected)
        probe._fetch_list("", 10)
    injected.close.assert_not_called()

    # 场景 B：未注入 → 自建 session 必须关闭
    own = MagicMock()
    own.headers = {}
    with patch.object(base_mod.requests, "Session", return_value=own), patch.object(
        base_mod, "safe_request", return_value=None
    ):
        probe2 = _Probe(None)
        probe2._fetch_list("", 10)
    own.close.assert_called_once()


# ── NEW-40：LogHandler.close 停定时器 ──


def test_log_handler_close_stops_timer_source():
    """源码必须体现 close() 停定时器（Qt 对象生命周期难以无 GUI 稳定测）。"""
    src = (ROOT / "pilotstd" / "ui" / "workers" / "_common.py").read_text(encoding="utf-8")
    close_start = src.find("def close(self)")
    assert close_start > 0
    # 取 close 方法体（到下一个 def 之前）
    nxt = src.find("\n    def ", close_start + 10)
    body = src[close_start:nxt] if nxt > 0 else src[close_start:]
    assert "_buf_timer.stop()" in body, "close() 必须 stop 批量刷新定时器（NEW-40）"
    assert "timeout.disconnect" in body, "close() 应断开定时器信号，避免迟到回调"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
