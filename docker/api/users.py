# 容器//脚本—用户管理接口
# 权限：用户管理接口需 admin 角色（@require_role）
from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd import SUPERUSER_USERNAME

from ..auth import get_current_user_id, require_role
from ..manager import get_manager_dep
from ..users import add_user, change_password, delete_user, get_user_by_id, list_users

router = APIRouter(tags=["users"])


class AddUserRequest(BaseModel):
    """添加用户请求体：用户名、密码和角色（默认 user）。"""

    username: str
    password: str
    role: str = "user"


# 修改密码请求体（独立于，避免权限混淆）
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@require_role("admin")
@router.get("/api/users")
def api_list_users():
    """列出所有用户（仅管理员）。"""
    return {"users": list_users()}


@require_role("admin")
@router.post("/api/users")
def api_add_user(body: AddUserRequest):
    """添加用户（仅管理员）。"""
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


@require_role("admin")
@router.delete("/api/users/{user_id}")
def api_delete_user(user_id: int, mgr=Depends(get_manager_dep)):
    """删除用户（仅管理员，admin 用户不可删除）。"""
    user = mgr.user_service.get_user_by_id(user_id)
    if user and user["username"] == SUPERUSER_USERNAME:
        raise HTTPException(403, "admin 用户不可删除")
    if not delete_user(user_id):
        raise HTTPException(400, "无法删除（不存在或是最后的管理员）")
    return {"ok": True}


@require_role("admin")
@router.put("/api/users/password")
def api_change_password(body: ChangePasswordRequest, request: Request):
    """修改当前登录用户的密码。"""
    user_id = get_current_user_id(request)
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(400, "用户不存在")
    if not body.new_password or len(body.new_password) < 4:
        raise HTTPException(400, "新密码至少4个字符")
    if not change_password(user["username"], body.old_password, body.new_password):
        raise HTTPException(400, "旧密码不正确")
    return {"ok": True}
