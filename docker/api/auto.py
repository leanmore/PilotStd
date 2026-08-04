# 容器//脚本—一键处理接口
from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["auto"])


@router.post("/api/auto")
def auto_run(mgr=Depends(get_manager_dep)):
    """一键处理：扫描 → 查询 → 下载 → 归档。"""
    try:
        results = mgr.auto_run()
        return {"ok": True, "results": results, "message": "一键处理完成"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
