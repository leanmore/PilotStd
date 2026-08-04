# 容器//脚本—数据导出接口
import csv
import io
import json as _json

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

router = APIRouter(tags=["export"])


@router.get("/api/export/standards")
def export_standards(format: str = Query("json", description="csv 或 json"), mgr=Depends(get_manager_dep)):
    """导出标准列表。"""
    try:
        stats = mgr.get_status_stats()
        data = mgr.export_service.get_standards_data()
        items = [{"standard_number": r["standard_number"], "status": r["status"]} for r in data["items"]]

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["standard_number", "status"])
            for item in items:
                writer.writerow([item["standard_number"], item["status"]])
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=standards.csv"},
            )
        else:
            result = _json.dumps({"items": items, "stats": stats}, ensure_ascii=False, indent=2)
            return StreamingResponse(
                iter([result]),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=standards.json"},
            )
    except Exception as e:
        return {"ok": False, "error": str(e)}
