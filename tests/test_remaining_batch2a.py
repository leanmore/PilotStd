# tests/test_remaining_batch2a.py — U-3/U-4 批 2a：health unknown + 通知开关默认开
"""锁定老板拍板的两条语义：

- `docker/api/health._is_private_ip`：非法 IP → **None（unknown）** + WARNING，调用方不当作公网；
- `NotificationManager._read_user_enabled`：读配置失败 → **默认开（True）** + WARNING。
"""

import logging
import os
from unittest.mock import patch

import docker.api.health as health_mod
from pilotstd.core.notification.manager import NotificationManager


def test_invalid_ip_returns_unknown_and_warns(caplog) -> None:
    """非法 IP → None（第三态）+ WARNING。"""
    with caplog.at_level(logging.WARNING, logger="docker.api.health"):
        assert health_mod._is_private_ip("not-an-ip") is None

    assert any("unknown" in r.message for r in caplog.records)


def test_unknown_ip_is_denied_403(monkeypatch, caplog) -> None:
    """health_check 对 unknown 必须 fail-safe 拒绝（403），不得放行。"""
    from fastapi.testclient import TestClient

    from docker.app import app

    client = TestClient(app)
    with (
        patch.dict(os.environ, {"ENV": "production"}),
        patch.object(health_mod, "_is_private_ip", return_value=None),
        caplog.at_level(logging.WARNING, logger="docker.api.health"),
    ):
        resp = client.get("/api/health")

    assert resp.status_code == 403
    assert any("按非内部 IP 处理" in r.message for r in caplog.records)


def test_private_ip_still_bool() -> None:
    """正常 IP 仍返回布尔：内网 True / 公网 False。"""
    assert health_mod._is_private_ip("127.0.0.1") is True
    assert health_mod._is_private_ip("10.1.2.3") is True
    assert health_mod._is_private_ip("8.8.8.8") is False


def test_user_enabled_db_error_defaults_true(monkeypatch, caplog) -> None:
    """DB 查询异常 → True（默认开）+ WARNING。"""

    class _BadDB:
        def fetchone(self, *a, **k):  # noqa: ANN002, ANN003
            raise RuntimeError("db down")

    mgr = object.__new__(NotificationManager)
    mgr._db = _BadDB()

    with caplog.at_level(logging.WARNING, logger="pilotstd.core.notification.manager"):
        assert mgr._read_user_enabled(1) is True

    assert any("按默认开处理" in r.message for r in caplog.records)


def test_user_enabled_missing_column_defaults_true(caplog) -> None:
    """行缺列（KeyError/TypeError）→ True + WARNING。"""

    class _WeirdRow:
        def __getitem__(self, key):  # noqa: ANN001
            raise KeyError(key)

    class _DB:
        def fetchone(self, *a, **k):  # noqa: ANN002, ANN003
            return _WeirdRow()

    mgr = object.__new__(NotificationManager)
    mgr._db = _DB()

    with caplog.at_level(logging.WARNING, logger="pilotstd.core.notification.manager"):
        assert mgr._read_user_enabled(1) is True

    assert any("列缺失" in r.message for r in caplog.records)
