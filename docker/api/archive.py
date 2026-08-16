# 容器//归档脚本—文件归档接口（移动到标准库目录结构）
from fastapi import Body, Depends
from fastapi.routing import APIRouter

from pilotstd.models import ParsedStdInfo

from ..manager import get_manager_dep

router = APIRouter(tags=["archive"])


@router.post("/api/archive")
def archive_files(
    items: list[dict] = Body(..., embed=True),
    run_id: str = Body(..., embed=True),
    word_source_root: str = Body("", embed=True),
    mgr=Depends(get_manager_dep),
):
    """将已处理的文件移动到分类目录。"""
    # 更新管道：进入归档阶段
    try:
        mgr.pipeline_store.update_step(
            run_id,
            "archive",
            "running",
            80,
            step_results={"count": len(items)},
        )
    except Exception:
        pass

    try:
        parsed_list = []
        for item in items:
            parsed = ParsedStdInfo(
                raw_filename=item.get("source_path", "").split("/")[-1].split("\\")[-1],
                source_path=item.get("source_path", ""),
                logical_code=item.get("logical_code", ""),
                number=item.get("number", 0),
                year=item.get("year", 0),
                part=item.get("part"),
                std_name=item.get("std_name", ""),
                num_prefix=item.get("num_prefix", ""),
                num_suffix=item.get("num_suffix", ""),
                language=item.get("language", ""),
                ext=item.get("ext", ".pdf"),
            )
            parsed_list.append(parsed)

        result = mgr.archive_standards(parsed_list, word_source_root=word_source_root)
        mgr.pipeline_store.update_step(
            run_id,
            "archive",
            "completed",
            100,
            step_results={"count": len(parsed_list), "results": result},
        )
    except Exception as exc:
        mgr.pipeline_store.update_step(
            run_id,
            "archive",
            "failed",
            80,
            error=str(exc),
        )
        raise

    return result
