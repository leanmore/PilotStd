# 容器//_脚本—用户偏好存取接口（重构版）
# 分隔
# ⚠️破坏性变更()：
# 旧端点（//-?=&=/?=）已删除。
# 替代方案：
# 读取全部偏好：//
# 增量更新：//
# 重置为默认值：删除//

from typing import Any, Dict

from fastapi import Depends, HTTPException
from fastapi.routing import APIRouter
from pydantic import BaseModel

from docker.auth import get_current_user_id
from docker.users import get_user_by_id
from pilotstd.manager.settings_manager import UserPreferenceManager

router = APIRouter()


class PreferencesUpdate(BaseModel):
    updates: Dict[str, Any]


@router.get("/api/user-preference")
async def get_preferences(username: str = Depends(get_current_user_id)):
    """获取当前用户全部偏好（JSON 聚合格式，含默认值合并）。"""
    user = get_user_by_id(int(username))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = UserPreferenceManager.get_preferences(user["id"])
    return {"status": "success", "data": prefs}


@router.patch("/api/user-preference")
async def update_preferences(
    data: PreferencesUpdate,
    username: str = Depends(get_current_user_id),
):
    """增量更新用户偏好（只传需要修改的字段）。"""
    user = get_user_by_id(int(username))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_prefs = UserPreferenceManager.update_preferences(user["id"], data.updates)
    return {"status": "success", "data": new_prefs}


@router.delete("/api/user-preference")
async def reset_preferences(username: str = Depends(get_current_user_id)):
    """重置用户偏好到默认值。"""
    user = get_user_by_id(int(username))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    default_prefs = UserPreferenceManager.reset_preferences(user["id"])
    return {"status": "success", "data": default_prefs, "message": "已恢复默认设置"}
