# 容器//归档脚本—文件归档接口（移动到标准库目录结构）
import logging

from fastapi import Body, Depends, HTTPException
from fastapi.routing import APIRouter

from pilotstd.core.path_guard import get_allowed_roots, validate_path_in_root
from pilotstd.models import ParsedStdInfo

from ..manager import get_manager_dep
from ._pipeline import safe_update_step

logger = logging.getLogger(__name__)

router = APIRouter(tags=["archive"])


def _config_root(mgr) -> str:
    """取配置的库根目录；测试替身可能返回非字符串，一律按空处理。"""
    # 测试替身返回的可能是任意对象：只接受字符串，其余一律按未配置处理
    try:
        root = mgr.cfg.get("storage.root_dir", "")
    except Exception as e:
        logger.warning("read storage.root_dir failed: %s", e)
        return ""
    return root if isinstance(root, str) else ""


def _validate_source_path(path: str, config_root: str) -> None:
    """D-22：source_path 必须落在允许的根目录内，否则拒绝归档。

    允许根与 /api/scan-and-index 同源（配置根 + STANDARD_ROOT + Docker 挂载点），
    防止客户端指定任意服务器路径（如 /etc/passwd）后被移入 library 外泄。
    """
    # get_allowed_roots 已做 realpath 规范化与去重；逐个根试配，全部越界才拒绝
    for root in get_allowed_roots(config_root):
        try:
            validate_path_in_root(path, root)
            return
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"source_path outside allowed roots: {path}")


@router.post("/api/archive")
def archive_files(
    items: list[dict] = Body(..., embed=True),
    run_id: str = Body(..., embed=True),
    word_source_root: str = Body("", embed=True),
    mgr=Depends(get_manager_dep),
):
    """将已处理的文件移动到分类目录。"""
    # 更新管道：进入归档阶段（失败只记日志，不阻断归档）
    safe_update_step(
        mgr.pipeline_store, run_id, "archive", "running", 80, step_results={"count": len(items)}
    )

    try:
        config_root = _config_root(mgr)
        parsed_list = []
        for item in items:
            source_path = item.get("source_path", "")
            if source_path:
                _validate_source_path(source_path, config_root)
            if not item.get("logical_code"):
                raw_name = source_path.split("/")[-1].split("\\")[-1]
                logger.warning("归档校验失败: logical_code 为空, 文件=%s", raw_name)
                raise ValueError(f"logical_code 缺失: {raw_name}")
            parsed = ParsedStdInfo(
                raw_filename=source_path.split("/")[-1].split("\\")[-1],
                source_path=source_path,
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
