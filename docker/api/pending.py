# 容器//脚本—待确认标准重新查询接口
from fastapi import Body, Depends
from fastapi.routing import APIRouter

from pilotstd.core.db.database import Database
from pilotstd.core.name_resolution import fetch_resolved_names, resolve_name
from pilotstd.core.status import status_key

from ..manager import get_manager_dep

# 复用收藏模块已定义的"请求级 Database 依赖"（请求结束自动关闭连接），避免在多个路由模块
# 里各自实现连接口径（双口径易产生连接泄漏与事务差异）。
from .favorites import get_db

router = APIRouter(tags=["pending"])


@router.get("/api/pending")
def get_pending(db: Database = Depends(get_db), mgr=Depends(get_manager_dep)):
    """获取所有待确认项（来自 pending_lookup 表；名称统一为「最高可得阶段名」）。

    为什么在接口层取回退链：本表行内只有 ①`std_name`（解析名）与 ②`found_name`（查询名）；
    ③决策名的**权威落点是 `announcement_record.final_name`**（迁移 v66 引入，批次二写入点负责落库）。
    自 **v67-a** 起本接口**不再读取本表的 `final_name`**（该列已解耦，仅历史兼容保留），
    改为经 `fetch_resolved_names()` **一次批量**取「③→②→①」（B3-a：固定两条数据查询，严禁 N+1）。

    为什么还要保留行内回退：批量映射只覆盖"公告表中查得到"的标准号；查不到的号必须沿用
    行内 ②/① ⇒ 展示名**绝不返回 None/空串**（前端名称列不空白的最后防线）。
    """
    items = mgr.get_pending_items()
    numbers = [str(item.get("standard_number") or "") for item in items]
    resolved = fetch_resolved_names(db, numbers)  # 一次批量（内部已降级，不抛）
    for item in items:
        number = str(item.get("standard_number") or "")
        # 权威源命中 ⇒ 用回退链结果；否则回退行内 ②查询名 → ①解析名
        item["standard_name"] = resolved.get(number) or resolve_name(
            item.get("found_name"), item.get("std_name")
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
