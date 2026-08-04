# 容器//归类脚本—文件组织/归类接口（含路径遍历防护）
import logging
import os

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.path_guard import get_allowed_roots, validate_path_in_root

from ..manager import get_manager_dep
from .models import ListFilesResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["organize"])


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
            items.append(
                {
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "path": os.path.join(safe_path, entry.name),
                    "size": entry.stat().st_size if not entry.is_dir() else 0,
                }
            )
    except (PermissionError, OSError) as e:
        logger.warning("目录扫描失败: %s — %s", safe_path, e)
    return {
        "path": safe_path,
        "files": sorted(items, key=lambda x: (x["type"], x["name"])),
    }


@router.post("/api/clean-empty")
def clean_empty_dirs(path: str = "/standards", mgr=Depends(get_manager_dep)):
    """清除指定目录下的所有空文件夹。"""
    try:
        safe_path = _validate_path(path, mgr.cfg)
    except ValueError:
        return JSONResponse({"error": "路径不在允许的目录范围内"}, status_code=400)

    removed = 0
    # 自底向上遍历（=），确保子目录先被清空
    for root, dirs, _files in os.walk(safe_path, topdown=False):
        for d in dirs:
            dpath = os.path.join(root, d)
            try:
                # 仅删除空目录，非空目录跳过
                if not os.listdir(dpath):
                    os.rmdir(dpath)
                    removed += 1
            except OSError:
                pass
    return {"cleaned": removed}
