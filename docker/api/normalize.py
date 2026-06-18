# docker/api/normalize.py — 文件规范化 API（通过 StandardManager 统一入口）
from fastapi import Depends
from fastapi import Request as FastAPIRequest
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
async def normalize_files(request: FastAPIRequest, mgr=Depends(get_manager_dep)):
    """计算规范文件名。通过 StandardManager 统一入口。"""
    body = await request.json()
    items = body if isinstance(body, list) else body.get("items", [])
    parsed_list = [_dict_to_parsed(it) for it in items]
    norm_results = mgr.normalize_files_stream(parsed_list)
    results = [{"source_path": r["source"], "new_filename": r["normalized"]}
               for r in norm_results]
    return {"results": results}
