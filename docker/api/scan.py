# docker/api/scan.py — 标准文件扫描 API（含路径遍历防护）
import os
from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse
from pilotstd.core.path_guard import validate_path_in_root
from ..manager import get_manager_dep

router = APIRouter(tags=["scan"])

# 允许扫描的根目录：inbox（监控目录）+ 标准库根目录
_ALLOWED_ROOTS: list[str] = []


def _get_allowed_roots(mgr=None) -> list[str]:
    """延迟获取允许扫描的根目录，避免模块加载时触发配置读取。"""
    if not _ALLOWED_ROOTS:
        root = mgr.cfg.get("storage.root_dir", "") if mgr else ""
        if root:
            _ALLOWED_ROOTS.append(root)
        std_root = os.environ.get("STANDARD_ROOT", "/standards")
        if std_root not in _ALLOWED_ROOTS:
            _ALLOWED_ROOTS.append(std_root)
        if "/inbox" not in _ALLOWED_ROOTS:
            _ALLOWED_ROOTS.append("/inbox")
    return _ALLOWED_ROOTS


def _validate_path(user_path: str, mgr=None) -> str:
    """校验路径：必须在允许的根目录范围内。委托 path_guard 统一实现。"""
    for root in _get_allowed_roots(mgr):
        try:
            return validate_path_in_root(user_path, root)
        except ValueError:
            continue
    raise ValueError("路径不在允许的目录范围内")


@router.post("/api/scan")
def scan_directory(path: str = "/inbox", recursive: bool = True,
                   mgr=Depends(get_manager_dep)):
    """扫描目录中的标准文件，返回文件列表及统计。走 facade 去重+解析。"""
    try:
        safe_path = _validate_path(path, mgr)
    except ValueError:
        return JSONResponse({"error": "路径不在允许的目录范围内"}, status_code=400)

    # 走 facade.scan_directory() —— 含标准号去重 + 解析
    parsed_list = mgr.scan_directory(safe_path)
    files = []
    for p in parsed_list:
        src = getattr(p, 'source_path', '')
        files.append({
            "name": os.path.basename(src),
            "full_path": src,
            "size": 0, "status": "parsed",
            "standard_number": p.get_full_number(),
            "logical_code": p.logical_code,
            "number": p.number,
            "year": p.year,
            "part": p.part,
            "num_prefix": p.num_prefix,
            "num_suffix": p.num_suffix,
            "ext": p.ext or ".pdf",
            "language": p.language,
            "std_name": p.std_name,
        })
    return {
        "total": len(files),
        "pdf_count": sum(1 for f in files if f["name"].lower().endswith(".pdf")),
        "word_count": sum(1 for f in files if f["name"].lower().endswith((".doc", ".docx"))),
        "dup_skipped": 0,
        "skipped_dirs": len(getattr(mgr, '_last_skipped_dirs', [])),
        "files": files,
    }
