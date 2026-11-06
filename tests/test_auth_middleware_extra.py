"""鉴权中间件边界：限流、API Key 三通道、跨源拒绝。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from docker import auth_middleware as mw


def _middleware():
    return mw.AuthMiddleware(app=MagicMock())


class _Req:
    def __init__(self, headers=None, cookies=None, query=None, host="127.0.0.1"):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.query_params = query or {}
        self.client = SimpleNamespace(host=host)
        self.state = SimpleNamespace()


def test_rate_limit_blocks_after_threshold(monkeypatch):
    monkeypatch.setattr(mw, "API_RATE_LIMIT", 2)
    monkeypatch.setattr(mw, "API_RATE_WINDOW", 60)
    mw._api_rate_limit.clear()
    m = _middleware()
    req = _Req(host="10.0.0.9")
    assert m._check_rate_limit(req) is None
    assert m._check_rate_limit(req) is None
    resp = m._check_rate_limit(req)
    assert resp is not None and resp.status_code == 429


def test_api_key_header_and_bearer(monkeypatch):
    m = _middleware()
    monkeypatch.setattr(mw, "verify_api_key", lambda token: {"key_id": "k1"} if token == "ok" else None)
    req = _Req(headers={"X-API-KEY": "ok"})
    assert m._authenticate_api_key(req) is True
    assert req.state.api_key_id == "k1"
    assert m._authenticate_api_key(_Req(headers={"Authorization": "Bearer ok"})) is True


def test_invalid_pst_key_raises_401(monkeypatch):
    m = _middleware()
    monkeypatch.setattr(mw, "verify_api_key", lambda token: None)
    with pytest.raises(HTTPException) as exc:
        m._authenticate_api_key(_Req(headers={"X-API-KEY": "pst_bad"}))
    assert exc.value.status_code == 401


def test_cross_origin_session_rejected():
    m = _middleware()
    req = _Req(headers={"Origin": "http://evil.example", "Host": "pilot.local"})
    with pytest.raises(HTTPException) as exc:
        m._authenticate_session(req)
    assert exc.value.status_code == 403


def test_api_key_query_token(monkeypatch):
    m = _middleware()
    monkeypatch.setattr(mw, "verify_api_key", lambda token: {"key_id": "q"} if token == "qt" else None)
    assert m._authenticate_api_key(_Req(query={"token": "qt"})) is True


def test_session_missing_token_401():
    m = _middleware()
    with pytest.raises(HTTPException) as exc:
        m._authenticate_session(_Req())
    assert exc.value.status_code == 401


def test_session_csrf_mismatch_403(monkeypatch):
    m = _middleware()
    monkeypatch.setattr(mw.jwt, "decode", lambda *a, **k: {"sub": "1", "role": "admin"})
    monkeypatch.setattr(mw, "get_session_store", lambda: SimpleNamespace(get=lambda token: {"ok": True}))
    req = _Req(cookies={mw.COOKIE_NAME: "tok", "csrf_token": "a"}, headers={"X-CSRF-Token": "b"})
    req.method = "POST"
    with pytest.raises(HTTPException) as exc:
        m._authenticate_session(req)
    assert exc.value.status_code == 403

