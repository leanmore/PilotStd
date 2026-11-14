"""多用户 P1：`resolve_user_id` 的归属解析（contextvar 优先、cookie 兜底、绝不返回 0）。"""

import pytest
from fastapi import HTTPException

from docker.api._identity import resolve_user_id
from pilotstd.core.context import set_current_user_id
from tests._auth_helpers import admin_request


@pytest.fixture(autouse=True)
def _clear_ctx():
    from pilotstd.core.context import _current_user_id

    token = _current_user_id.set(None)
    yield
    _current_user_id.reset(token)


def test_contextvar_wins():
    token = set_current_user_id(7)
    try:
        assert resolve_user_id(admin_request()) == 7
    finally:
        from pilotstd.core.context import _current_user_id

        _current_user_id.reset(token)


def test_falls_back_to_cookie_subject():
    # 未设置 contextvar（如直接调用路由函数）→ 从 admin cookie 的 sub 取到 1
    assert resolve_user_id(admin_request()) == 1


def test_no_identity_raises_401_not_zero():
    with pytest.raises(HTTPException) as exc:
        resolve_user_id(admin_request.__globals__["Request"](
            {"type": "http", "method": "POST", "path": "/api/auto", "headers": []}
        ))
    assert exc.value.status_code == 401
