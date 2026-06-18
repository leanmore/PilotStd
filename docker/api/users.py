# docker/api/users.py — 用户管理 API
from fastapi import HTTPException, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel

from ..users import add_user, change_password, delete_user, list_users

router = APIRouter(tags=["users"])


class AddUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.get("/api/users")
def api_list_users():
    """列出所有用户。"""
    return {"users": list_users()}


@router.post("/api/users")
def api_add_user(body: AddUserRequest):
    """添加用户。"""
    if not body.username or not body.password:
        raise HTTPException(400, "用户名和密码不能为空")
    if len(body.username) < 2:
        raise HTTPException(400, "用户名至少2个字符")
    if len(body.password) < 8:
        raise HTTPException(400, "密码长度不能少于 8 位")
    try:
        if not add_user(body.username, body.password, body.role):
            raise HTTPException(409, "用户名已存在")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.delete("/api/users/{user_id}")
def api_delete_user(user_id: int):
    """删除用户。"""
    if not delete_user(user_id):
        raise HTTPException(400, "无法删除（不存在或是最后的管理员）")
    return {"ok": True}


@router.put("/api/users/password")
def api_change_password(body: ChangePasswordRequest, request: Request):
    """修改当前登录用户的密码。"""
    from ..auth import get_current_username

    username = get_current_username(request)
    if not body.new_password or len(body.new_password) < 4:
        raise HTTPException(400, "新密码至少4个字符")
    if not change_password(username, body.old_password, body.new_password):
        raise HTTPException(400, "旧密码不正确")
    return {"ok": True}
