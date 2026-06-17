# docker/api/organize.py — 文件组织/归类 API（含路径遍历防护）
import os
import logging
from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse
from pilotstd.core.config import get_library_root
from pilotstd.core.path_guard import validate_path_in_root
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["organize"])


def _validate_library_path(user_path: str, cfg) -> str:
    """校验路径：必须在库根目录范围内。委托 path_guard 统一实现。"""
    return validate_path_in_root(user_path, get_library_root(cfg))


@router.get("/api/files")
def list_files(path: str = "/standards", mgr=Depends(get_manager_dep)):
    """列出指定目录下的文件和子目录。"""
    try:
        safe_path = _validate_library_path(path, mgr.cfg)
    except ValueError:
        return JSONResponse({"error": "路径不在允许的目录范围内"}, status_code=400)

    if not os.path.exists(safe_path):
        return JSONResponse({"error": "路径不存在"}, status_code=404)
    items = []
    try:
        for entry in os.scandir(safe_path):
            items.append({"name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "path": os.path.join(safe_path, entry.name),
                "size": entry.stat().st_size if not entry.is_dir() else 0})
    except (PermissionError, OSError) as e:
        logger.warning("目录扫描失败: %s — %s", safe_path, e)
    return {"path": safe_path, "files": sorted(items, key=lambda x: (x["type"], x["name"]))}


@router.post("/api/clean-empty")
def clean_empty_dirs(path: str = "/standards", mgr=Depends(get_manager_dep)):
    """清除指定目录下的所有空文件夹。"""
    try:
        safe_path = _validate_library_path(path, mgr.cfg)
    except ValueError:
        return JSONResponse({"error": "路径不在允许的目录范围内"}, status_code=400)

    removed = 0
    for root, dirs, _files in os.walk(safe_path, topdown=False):
        for d in dirs:
            dpath = os.path.join(root, d)
            try:
                if not os.listdir(dpath):
                    os.rmdir(dpath)
                    removed += 1
            except OSError:
                pass
    return {"cleaned": removed}
