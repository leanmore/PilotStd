# 容器//脚本—待确认标准重新查询接口
from typing import Any

from fastapi import Body, Depends, Query, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel

from pilotstd.core.db.database import Database
from pilotstd.core.name_resolution import fetch_resolved_names, resolve_name
from pilotstd.core.status import status_key

from ..auth import require_role
from ..manager import get_manager_dep

# 复用收藏模块已定义的"请求级 Database 依赖"（请求结束自动关闭连接），避免在多个路由模块
# 里各自实现连接口径（双口径易产生连接泄漏与事务差异）。
from .favorites import get_db

router = APIRouter(tags=["pending"])

# ════════════════════════════════════════════════════════════════ 分隔
# 响应模型：与各路由成功返回的字典键一一对应
# ════════════════════════════════════════════════════════════════ 分隔


class PendingMarkMissingResponse(BaseModel):
    """缺失标记结果：检查数 / 缺失数 / 更新数 / 是否因挂载异常跳过 / 是否强制绕过保护。"""

    checked: int
    missing: int
    updated: int
    skipped: bool
    # 是否以 protect=false 强制执行（跳过挂载保护）。便于运维事后审计「谁强制跑过」。
    forced: bool = False


class PendingRequeryItem(BaseModel):
    """重新查询结果条目：标准号、名称、状态、状态键、来源与匹配状态。"""

    standard_number: str
    standard_name: str
    status: str
    status_key: str
    source_site: str
    match_status: Any = ""  # 真实值为字符串；保留任意类型以兼容外部占位值


class PendingRequeryResponse(BaseModel):
    """待确认标准重新查询响应：逐条查询结果。"""

    results: list[PendingRequeryItem]


class PendingListResponse(BaseModel):
    """待确认列表响应：数据表原始行原样透传（列集随迁移演进）。"""

    items: list[dict[str, Any]]


@router.get("/api/pending", response_model=PendingListResponse)
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


@router.post("/api/pending/requery", response_model=PendingRequeryResponse)
@require_role("admin")
def requery_pending(request: Request, numbers: list[str] = Body(), site: str = "", mgr=Depends(get_manager_dep)):
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

@router.post("/api/pending/mark-missing", response_model=PendingMarkMissingResponse)
@require_role("admin")
def mark_pending_missing(
    request: Request,
    protect: bool = Query(
        True,
        description=(
            "Enable mount/collapse guard (default true). "
            "Pass false to force the run after confirming files are genuinely missing."
        ),
    ),
    db=Depends(get_db),
) -> PendingMarkMissingResponse:
    """把“有路径但文件已不存在”的待确认行标成 `file_missing`（幂等，不删行、不移文件）。

    挂载保护：缺失行数 ≥50 且占比 ≥90% 视为 `/standards` 未挂载，整轮跳过并返回 `skipped=true`，
    避免一次根目录异常把整表 pending 误标成文件缺失（与 `file_index.validate_paths` 同一判据）。

    ── 为什么加 `protect` 参数（2026-11-24，生产实测驱动）──
    实测该保护会**误报**：挂载确实正常、路径也在配置扫描根下，但数据真的大面积缺失
    （外推 61/61），于是整轮跳过 —— 管理员**在 API 上没有任何办法推进**，
    只能手工跑脚本。现暴露 `protect=false` 供管理员在**确认数据真缺失**后强制执行，
    并在响应里回 `forced=true` 以便审计。
    """
    from pilotstd.manager.pending_service import mark_missing_files

    stats = mark_missing_files(db, protect=protect)
    return PendingMarkMissingResponse(
        checked=int(stats.get("checked", 0)),
        missing=int(stats.get("missing", 0)),
        updated=int(stats.get("updated", 0)),
        skipped=bool(stats.get("skipped")),
        forced=not protect,
    )
