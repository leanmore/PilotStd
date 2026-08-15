# 容器//扫描脚本—标准文件扫描接口（含路径遍历防护+管道运行追踪）
# 权限：扫描触发接口需 admin 角色（@require_role）
import os
import uuid

from fastapi import Body, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.path_guard import get_allowed_roots, validate_path_in_root

from ..auth import require_role
from ..manager import get_manager_dep
from .models import ScanIndexResponse

router = APIRouter(tags=["scan"])


def _validate_path(user_path: str, mgr=None) -> str:
    """校验路径：必须在允许的根目录范围内（支持多根目录，与 organize 模块对齐）。"""
    config_root = mgr.cfg.get("storage.root_dir", "") if mgr else ""
    for root in get_allowed_roots(config_root):
        try:
            return validate_path_in_root(user_path, root)
        except ValueError:
            continue
    raise ValueError("路径不在允许的目录范围内")


# 扫描端点：解析路径 → 调用 StandardManager 扫描文件列表
@router.post("/api/scan")
@require_role("admin")
def scan_directory(
    request: Request,
    path: str = "/inbox",
    run_id: str | None = Body(None, embed=True),
    mgr=Depends(get_manager_dep),
):
    """扫描目录中的标准文件，返回文件列表及统计。走 facade 去重+解析。"""
    try:
        safe_path = _validate_path(path, mgr)
    except ValueError:
        return JSONResponse({"error": "路径不在允许的目录范围内"}, status_code=400)

    # 创建管道运行记录（可选：不传则自动生成）
    run_id = run_id or str(uuid.uuid4())
    mgr.pipeline_store.create(run_id)

    try:
        parsed_list = mgr.scan_directory(safe_path)
    except Exception as exc:
        mgr.pipeline_store.update_step(
            run_id,
            "scan",
            "failed",
            0,
            error=str(exc),
        )
        return JSONResponse({"error": str(exc), "run_id": run_id}, status_code=500)

    files = []
    for p in parsed_list:
        src = getattr(p, "source_path", "")
        files.append(
            {
                "name": os.path.basename(src),
                "full_path": src,
                "size": 0,
                "status": "parsed",
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
            }
        )

    # 更新管道：扫描完成
    mgr.pipeline_store.update_step(
        run_id,
        "scan",
        "completed",
        20,
        step_results={"total": len(files)},
    )

    return {
        "run_id": run_id,
        "total": len(files),
        "pdf_count": sum(1 for f in files if f["name"].lower().endswith(".pdf")),
        "word_count": sum(1 for f in files if f["name"].lower().endswith((".doc", ".docx"))),
        "dup_skipped": 0,
        "skipped_dirs": len(getattr(mgr, "_last_skipped_dirs", [])),
        "files": files,
    }


@router.post("/api/scan-and-index", response_model=ScanIndexResponse)
@require_role("admin")
def scan_and_index(
    request: Request,
    path: str | None = None,
    mgr=Depends(get_manager_dep),
):
    """Q6-1: 扫描标准库 → 四要素匹配 → UPDATE standards 表扫描状态。
    path 参数保留向后兼容但不再使用，始终扫描配置的 library_root。

    返回 indexed/skipped/failed 三项计数。
    仅 UPDATE scan_status='pending' 的记录为 'indexed'，不新增 standards 条目。
    """
    try:
        result = mgr.scan_and_index(path)
        return result
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
