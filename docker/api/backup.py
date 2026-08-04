# 容器//脚本—备份管理接口
import logging
import os
from datetime import datetime

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["backup"])


def _get_backup_dir(mgr) -> str:
    db_path = mgr.db.path
    return os.path.join(os.path.dirname(db_path), "backups")


@router.get("/api/backup/list")
def list_backups(mgr=Depends(get_manager_dep)):
    """获取所有备份列表。"""
    backup_dir = _get_backup_dir(mgr)
    backups = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".bak") or f.endswith(".db"):
                path = os.path.join(backup_dir, f)
                stat = os.stat(path)
                backups.append(
                    {
                        "id": f,
                        "name": f,
                        "size": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
    return {"items": backups, "count": len(backups)}


@router.post("/api/backup/create")
def create_backup(mgr=Depends(get_manager_dep)):
    """手动创建数据库备份。"""
    try:
        result = mgr.db.backup(
            os.path.join(_get_backup_dir(mgr), f"pilotstd_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        )
        if result:
            return {"ok": True, "message": "备份创建成功"}
        return JSONResponse({"ok": False, "message": "备份创建失败"}, status_code=500)
    except Exception as e:
        logger.exception("手动备份失败")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
