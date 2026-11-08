"""tests/query/adapters/test_adapter_log_levels.py — 适配器失败日志级别契约（U34-B）。

本文件锁的是**日志级别契约**，不是解析结果正确性。当前覆盖「替代标准字段」与
「上游已告警」两类保持 `debug` 的设计：字段缺失不阻断主查询，但日志必须能区分
网络失败与解析失败；上游已告警的位置不得再打第二条 warning。
"""

import logging

import requests

from pilotstd.query.adapters.csres import CsresAdapter
from pilotstd.query.adapters.hbba import HbbaAdapter
from pilotstd.query.adapters.njbz365 import Njbz365Adapter
from pilotstd.query.adapters.ttbz import TTBZAdapter

# ── 测试替身 ─────────────────────────────────────────────────────────────


class _Headers(dict):
    """requests.Session.headers 的最小替身（支持 update 与下标赋值）。"""


class _FakeResp:
    """httpx/requests 响应的最小替身。"""

    def __init__(self, status_code: int = 200, text: str = "", payload=None, json_error=None) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self._json_error = json_error
        self.headers = {}
        self.encoding = "utf-8"
        self.url = "http://fake.local/"

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _FakeClient:
    """httpx.Client 替身：get/post 返回固定响应或直接抛异常。"""

    def __init__(self, *, get=None, post=None) -> None:  # noqa: ANN001
        self._get = get
        self._post = post
        self.headers = _Headers()

    def get(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if isinstance(self._get, BaseException):
            raise self._get
        return self._get

    def post(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if isinstance(self._post, BaseException):
            raise self._post
        return self._post


class _FakeSession(_FakeClient):
    """requests.Session 替身（构造期会调用 headers.update）。"""


def _records(caplog, level: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def _has(caplog, level: int, needle: str) -> bool:
    return any(needle in msg for msg in _records(caplog, level))


# ── 替代标准字段：保持 DEBUG，但区分网络/解析 ────────────────────────────


def test_csres_replaces_keeps_debug_and_distinguishes_network(caplog, monkeypatch) -> None:
    """csres 替代标准：网络失败必须 DEBUG 且文案含「网络请求失败」。"""
    from pilotstd.query.adapters import csres as csres_mod

    def _raise(*_a, **_k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(csres_mod, "safe_get", _raise)
    adapter = CsresAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_detail_replaces("http://x/detail")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "csres 替代标准网络请求失败")
    assert not _has(caplog, logging.WARNING, "csres 替代标准")


def test_csres_replaces_distinguishes_parse_error(caplog, monkeypatch) -> None:
    """csres 替代标准：非网络异常必须 DEBUG 且文案含「解析失败」。"""
    from pilotstd.query.adapters import csres as csres_mod

    class _BadText(_FakeResp):
        @property
        def text(self):  # noqa: ANN201
            raise ValueError("decode failed")

    monkeypatch.setattr(csres_mod, "safe_get", lambda *_a, **_k: _BadText())
    adapter = CsresAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_detail_replaces("http://x/detail")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "csres 替代标准解析失败")
    assert not _has(caplog, logging.WARNING, "csres 替代标准")


def test_njbz365_replaces_wording_covers_network(caplog, monkeypatch) -> None:
    """njbz365 的 try 同时包了 safe_get：网络异常不得再被记成「解析失败」。"""
    from pilotstd.query.adapters import njbz365 as njbz_mod

    def _raise(*_a, **_k):
        raise requests.Timeout("slow")

    monkeypatch.setattr(njbz_mod, "safe_get", _raise)
    adapter = Njbz365Adapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_replaces("1", "GB 50001")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "njbz365 替代标准网络请求失败")
    assert not _has(caplog, logging.DEBUG, "njbz365 替代标准解析失败")


def test_hbba_replaces_keeps_debug(caplog, monkeypatch) -> None:
    """hbba 替代标准：保持 DEBUG（不阻断主查询），且区分网络失败。"""
    from pilotstd.query.adapters import hbba as hbba_mod

    def _raise(*_a, **_k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(hbba_mod, "safe_get", _raise)
    adapter = HbbaAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_detail_replaces("pk-1")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "hbba 替代标准网络请求失败")
    assert not _has(caplog, logging.WARNING, "hbba 替代标准")


# ── 上游已告警：保持 DEBUG，不重复 WARNING ───────────────────────────────


def test_ttbz_unexpected_exception_stays_debug(caplog, monkeypatch) -> None:
    """ttbz 意外异常：safe_post 已负责告警，此处只能 DEBUG，不得再 WARNING。"""
    from pilotstd.query.adapters import ttbz as ttbz_mod

    def _raise(*_a, **_k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ttbz_mod, "safe_post", _raise)
    adapter = TTBZAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")

    assert _has(caplog, logging.DEBUG, "ttbz 网络请求异常")
    assert not _has(caplog, logging.WARNING, "ttbz 网络请求异常")
