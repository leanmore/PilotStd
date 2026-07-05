# docker/api/scan.py — 标准文件扫描 API（含路径遍历防护 + 管道运行追踪）
import os
import uuid

from fastapi import Body, Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.path_guard import get_allowed_roots, validate_path_in_root

from ..manager import get_manager_dep

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


@router.post("/api/scan")
def scan_directory(
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


@router.post("/api/scan-and-index")
def scan_and_index(
    path: str | None = None,
    mgr=Depends(get_manager_dep),
):
    """扫描目录 → 解析标准号 → 写入 file_index 表（使首页统计生效）。
    不传 path 时使用配置的 library_root。
    """
    try:
        count = mgr.scan_and_index(path)
        return {"ok": True, "indexed": count, "path": path or "(library root)"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
