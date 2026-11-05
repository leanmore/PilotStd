"""测试用管理员身份：给隔离 FastAPI app 的 TestClient / 直接调用路由函数提供 admin cookie。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt
from starlette.requests import Request

from docker.auth import COOKIE_NAME, SECRET


def admin_token() -> str:
    payload = {
        "sub": "1",
        "role": "admin",
        "username": "test_admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def admin_cookies() -> dict[str, str]:
    return {COOKIE_NAME: admin_token()}


def admin_request(method: str = "PUT", path: str = "/api/test") -> Request:
    """构造带 admin cookie 的 Request，供直接调用被 @require_role 包装的路由函数。"""
    token = admin_token()
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [(b"cookie", f"{COOKIE_NAME}={token}".encode())],
        }
    )


def user_cookies() -> dict[str, str]:
    """普通用户（role=user）cookie，用于验证 admin-only 端点拒绝。"""
    payload = {
        "sub": "2",
        "role": "user",
        "username": "test_user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return {COOKIE_NAME: jwt.encode(payload, SECRET, algorithm="HS256")}
