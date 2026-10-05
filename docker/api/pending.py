# 容器//脚本—待确认标准重新查询接口
from fastapi import Body, Depends
from fastapi.routing import APIRouter

from pilotstd.core.name_resolution import resolve_name
from pilotstd.core.status import status_key

from ..manager import get_manager_dep

router = APIRouter(tags=["pending"])


@router.get("/api/pending")
def get_pending(mgr=Depends(get_manager_dep)):
    """获取所有待确认项（来自 pending_lookup 表；名称统一为「最高可得阶段名」）。

    为什么在接口层再算一次：`pending_lookup` 行内同时存着 ①`std_name`（解析名）、
    ②`found_name`（查询名）、③`final_name`（决策名）。前端各页面只应关心"这个标准现在
    该叫什么" ⇒ 在此按 **③→②→①** 算出**唯一**对外名 `standard_name`。

    为什么零成本：三个字段**就在本行内**，无需任何 DB 往返，也不存在 N+1。

    为什么保留 ③/② 等原键：待确认页要**并列展示**"解析名 vs 查询名"供人工判断，
    它们是**不同语义的字段**，不是同一名称的重复键；而 `std_name` 作为对外展示名属阶段①化石
    ⇒ 按 D8 覆盖为 `standard_name` 后 `pop` 掉旧键。
    """
    items = mgr.get_pending_items()
    for item in items:
        # 回退链：③ 决策名 > ② 查询名 > ① 解析名（取第一个非空；全空则为空串）
        item["standard_name"] = resolve_name(
            item.get("final_name"), item.get("found_name"), item.get("std_name")
        )
        item.pop("std_name", None)  # D8：对外不再暴露旧键
    return {"items": items}


@router.post("/api/pending/requery")
def requery_pending(numbers: list[str] = Body(), site: str = "", mgr=Depends(get_manager_dep)):
    """对待确认标准进行重新查询。指定 site 时置顶该站点，否则引擎自动路由。"""
    results, _ = mgr.query_by_numbers(numbers, preferred_site=site)

    # 31:查询成功的条目从待确认列表移除
    confirmed: list[str] = []
    for r in results:
        if r.standard_name:
            confirmed.append(r.standard_number)
    if confirmed:
        mgr.resolve_pending_by_numbers(confirmed, "confirmed")

    return {
        "results": [
            {
                "standard_number": r.standard_number,
                "standard_name": r.standard_name,
                "status": r.status,
                "status_key": status_key(r.status),
                "source_site": r.source_site,
                "match_status": getattr(r, "match_status", ""),
            }
            for r in results
        ]
    }
