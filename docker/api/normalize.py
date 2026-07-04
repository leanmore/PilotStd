# docker/api/normalize.py — 文件规范化 API（通过 StandardManager 统一入口）
from fastapi import Body, Depends
from fastapi.routing import APIRouter

from pilotstd.models import ParsedStdInfo

from ..manager import get_manager_dep

router = APIRouter(tags=["normalize"])


def _dict_to_parsed(item: dict) -> ParsedStdInfo:
    """JSON dict → ParsedStdInfo，供 normalize_files_stream 使用。"""
    return ParsedStdInfo(
        raw_filename=item.get("name", item.get("full_path", "")),
        logical_code=item.get("logical_code", ""),
        number=item.get("number", 0),
        year=item.get("year", 0),
        std_name=item.get("standard_name", item.get("std_name", "")),
        part=item.get("part"),
        num_prefix=item.get("num_prefix", ""),
        num_suffix=item.get("num_suffix", ""),
        language=item.get("language", ""),
        ext=item.get("ext", ".pdf"),
        source_path=item.get("source_path", item.get("full_path", "")),
    )


@router.post("/api/normalize")
def normalize_files(
    items: list[dict] = Body(..., embed=True),
    run_id: str = Body(..., embed=True),
    mgr=Depends(get_manager_dep),
):
    """计算规范文件名。通过 StandardManager 统一入口。"""
    # 更新管道：进入规范化阶段
    try:
        mgr.pipeline_store.update_step(
            run_id,
            "normalize",
            "running",
            60,
            step_results={"count": len(items)},
        )
    except Exception:
        pass

    try:
        parsed_list = [_dict_to_parsed(it) for it in items]
        norm_results = mgr.normalize_files_stream(parsed_list)
        results = [{"source_path": r["source"], "new_filename": r["normalized"]} for r in norm_results]
        mgr.pipeline_store.update_step(
            run_id,
            "normalize",
            "completed",
            80,
            step_results={"count": len(results)},
        )
    except Exception as exc:
        mgr.pipeline_store.update_step(
            run_id,
            "normalize",
            "failed",
            60,
            error=str(exc),
        )
        raise

    return {"results": results}
