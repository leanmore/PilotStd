# 容器//归类脚本—文件组织/归类接口（含路径遍历防护）
import logging
import os

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.audit import get_current_user_id, write_audit
from pilotstd.core.path_guard import get_allowed_roots, validate_path_in_root

from ..auth import require_role
from ..manager import get_manager_dep
from .models import ListFilesResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["organize"])


class CleanEmptyResponse(BaseModel):
    """清理空目录响应：本次删除的空目录数量。"""

    cleaned: int


def _validate_path(user_path: str, cfg) -> str:
    """校验路径：必须在允许的根目录范围内（支持多根目录，与 scan 模块对齐）。"""
    config_root = _get_config_root(cfg)
    for root in get_allowed_roots(config_root):
        try:
            return validate_path_in_root(user_path, root)
        except ValueError:
            continue
    raise ValueError("路径不在允许的目录范围内")


def _get_config_root(cfg) -> str:
    """获取用户配置的库根目录路径（与 get_library_root 一致但不自动创建目录）。"""
    import os as _os

    return _os.path.abspath(
        _os.path.normpath(
            _os.environ.get("STANDARD_ROOT") or cfg.get("storage.root_dir", _os.path.expanduser("~/标准"))
        )
    )


@router.get("/api/files", response_model=ListFilesResponse)
def list_files(path: str = "/standards", mgr=Depends(get_manager_dep)):
    """列出指定目录下的文件和子目录。"""
    try:
        safe_path = _validate_path(path, mgr.cfg)
    except ValueError:
        return JSONResponse({"error": "路径不在允许的目录范围内"}, status_code=400)

    if not os.path.exists(safe_path):
        return JSONResponse({"error": "路径不存在"}, status_code=404)
    items = []
    try:
        # 遍历目录，跳过系统目录@
        for entry in os.scandir(safe_path):
            if entry.name.startswith("@eaDir"):
                continue
            is_dir = entry.is_dir()
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "type": "dir" if is_dir else "file",
                    "path": os.path.join(safe_path, entry.name),
                    "size": 0 if is_dir else stat.st_size,
                    "mtime": 0.0 if is_dir else stat.st_mtime,
                }
            )
    except (PermissionError, OSError) as e:
        logger.warning("目录扫描失败: %s — %s", safe_path, e)
    return {
        "path": safe_path,
        "files": sorted(items, key=lambda x: (x["type"], x["name"])),
    }


@router.post("/api/clean-empty", response_model=CleanEmptyResponse)
@require_role("admin")
def clean_empty_dirs(request: Request, path: str = "/standards", mgr=Depends(get_manager_dep)):
    """清除指定目录下的所有空文件夹。"""
    try:
        safe_path = _validate_path(path, mgr.cfg)
    except ValueError:
        return JSONResponse({"error": "路径不在允许的目录范围内"}, status_code=400)

    removed = 0
    # 自底向上遍历：子目录先处理，父目录再判断（此时子目录已被删）
    # 2026-11-20：改用 remove_dir_if_empty —— 只含 Thumbs.db/desktop.ini/~$ 锁文件的目录
    # 以前被判“非空”永远清不掉；现在与监控模块的空目录清理同口径。安全路径函数自身不删。
    from pilotstd.core.file_utils import remove_dir_if_empty

    for root, dirs, _files in os.walk(safe_path, topdown=False):
        for d in dirs:
            if remove_dir_if_empty(os.path.join(root, d)):
                removed += 1
    write_audit(
        action="CLEAN_EMPTY_DIRS",
        resource="POST /api/clean-empty",
        detail={"path": safe_path, "cleaned": removed},
        user_id=get_current_user_id(),
    )
    return {"cleaned": removed}
