"""A-21 第二步：日志接口的用户隔离与 admin all=true。"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import docker.api.notification_logs as logs_api


def _call(monkeypatch, role="admin", all=False, user_id=None, current=1):
    monkeypatch.setattr(logs_api, "get_current_role", lambda request: role)
    nmgr = MagicMock()
    nmgr.ops.get_logs.return_value = {"items": [], "total": 0, "page": 1, "size": 20}
    logs_api.get_logs(
        request=MagicMock(),
        page=1,
        page_size=20,
        channel=None,
        status=None,
        start_date=None,
        end_date=None,
        is_read=None,
        all=all,
        user_id=user_id,
        nmgr=nmgr,
        current_user=current,
    )
    return nmgr.ops.get_logs.call_args.kwargs["user_id"]


def test_all_and_user_id_mutually_exclusive(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _call(monkeypatch, all=True, user_id=2)
    assert exc.value.status_code == 400


def test_non_admin_all_forbidden(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _call(monkeypatch, role="user", all=True)
    assert exc.value.status_code == 403


def test_non_admin_user_id_forced_to_self(monkeypatch):
    assert _call(monkeypatch, role="user", user_id=2, current=1) == 1


def test_admin_can_filter_other_user(monkeypatch):
    assert _call(monkeypatch, role="admin", user_id=2, current=1) == 2


def test_admin_without_user_id_sees_self(monkeypatch):
    assert _call(monkeypatch, role="admin", current=7) == 7


def test_admin_all_means_no_user_filter(monkeypatch):
    assert _call(monkeypatch, role="admin", all=True, current=1) is None


def test_get_current_role_without_token_is_user():
    from docker.auth import get_current_role

    class Req:
        cookies: dict = {}

    assert get_current_role(Req()) == "user"


def test_get_current_role_invalid_token_is_user():
    from docker.auth import COOKIE_NAME, get_current_role

    class Req:
        cookies = {COOKIE_NAME: "not-a-jwt"}

    assert get_current_role(Req()) == "user"
