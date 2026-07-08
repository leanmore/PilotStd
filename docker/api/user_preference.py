# docker/api/user_preference.py — 用户偏好存取 API
from fastapi import Depends
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["user_preference"])


@router.post("/api/user-preference")
def save_user_preference(key: str, value: str, mgr=Depends(get_manager_dep)):
    """保存用户偏好（如公告起始日期）。"""
    mgr.announce_service.save_user_preference(key, value)
    return {"ok": True}


@router.get("/api/user-preference")
def get_user_preference(key: str, mgr=Depends(get_manager_dep)):
    """读取用户偏好。"""
    value = mgr.announce_service._get_user_since_date()
    return {"key": key, "value": value}
