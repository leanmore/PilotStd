"""D-13 补测：/api/health 与 /api/cache/* 端点（此前函数级零覆盖）。

健康检查无需鉴权；缓存端点为 admin（require_role 读 Request cookie），
故直接构造 starlette Request 并注入 admin JWT，避免依赖完整 AuthMiddleware。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt
from starlette.requests import Request

from docker.auth import ADMIN_ROLE, COOKIE_NAME, SECRET


def _request(path: str, client: str = "127.0.0.1", admin: bool = True) -> Request:
    headers = []
    if admin:
        token = jwt.encode({"sub": "1", "role": ADMIN_ROLE}, SECRET, algorithm="HS256")
        headers.append((b"cookie", f"{COOKIE_NAME}={token}".encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "client": (client, 1234),
            "scheme": "http",
        }
    )


def test_health_ok(monkeypatch) -> None:
    from docker import manager as manager_module
    from docker.api.health import health_check

    mgr = MagicMock()
    mgr.db.fetchone.return_value = {"ok": 1}
    mgr.monitor_service = object()
    mgr.parser = object()
    monkeypatch.setattr(manager_module, "get_manager", lambda: mgr)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("APP_VERSION", "v-test")

    response = health_check(_request("/api/health"))
    data = json.loads(response.body)

    assert data["status"] == "ok"
    assert data["version"] == "v-test"
    assert data["services"] == {"database": True, "monitor_service": True, "parser": True}


def test_health_degraded_when_db_unavailable(monkeypatch) -> None:
    from docker import manager as manager_module
    from docker.api.health import health_check

    mgr = MagicMock()
    mgr.db.fetchone.side_effect = RuntimeError("db down")
    mgr.monitor_service = object()
    mgr.parser = None
    monkeypatch.setattr(manager_module, "get_manager", lambda: mgr)
    monkeypatch.delenv("ENV", raising=False)

    data = json.loads(health_check(_request("/api/health")).body)
    assert data["status"] == "degraded"
    assert data["services"]["database"] is False
    assert data["services"]["parser"] is False


def test_health_production_rejects_public_ip(monkeypatch) -> None:
    from docker.api.health import health_check

    monkeypatch.setenv("ENV", "production")
    with pytest.raises(HTTPException) as exc:
        health_check(_request("/api/health", client="8.8.8.8"))
    assert exc.value.status_code == 403


def test_cache_get_and_put_config(monkeypatch) -> None:
    from docker.api import cache as cache_api

    fake = MagicMock()
    monkeypatch.setattr(cache_api, "CacheManager", lambda db: fake)

    assert cache_api.get_config(_request("/api/cache/config"), mgr=MagicMock()) is fake.get_config.return_value

    body = {"max_size_mb": 64, "ignored": "x"}
    assert cache_api.put_config(_request("/api/cache/config"), body, mgr=MagicMock()) == {"ok": True}
    fake.set_config.assert_called_once_with("max_size_mb", 64)


def test_cache_cleanup_writes_audit(monkeypatch) -> None:
    from docker.api import cache as cache_api

    fake = MagicMock()
    fake.get_stats.return_value = {"size_mb": 1.5}
    monkeypatch.setattr(cache_api, "CacheManager", lambda db: fake)
    audit = MagicMock()
    monkeypatch.setattr(cache_api, "write_audit", audit)

    result = cache_api.trigger_cleanup(_request("/api/cache/cleanup"), mgr=MagicMock())

    assert result == {"ok": True, "stats": {"size_mb": 1.5}}
    fake.cleanup.assert_called_once_with(force=True)
    audit.assert_called_once()
    assert audit.call_args.kwargs["action"] == "CACHE_CLEANUP"
