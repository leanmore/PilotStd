# docker/api/quality.py — 数据质量检查 API
import logging

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quality"])


@router.post("/api/quality/run")
def run_quality_check(mgr=Depends(get_manager_dep)):
    """运行数据质量检查。"""
    try:
        from pilotstd.quality import QualityRunner

        runner = QualityRunner()
        report = runner.run(["pilotstd", "docker"])
        violations = [
            {
                "rule": v.rule,
                "severity": v.severity.value,
                "file": v.file,
                "line": v.line,
                "message": v.message,
            }
            for v in report.violations
        ]
        passed = sum(1 for v in report.violations if v.severity.value == "error") == 0
        return {
            "ok": True,
            "results": violations,
            "summary": {
                "total": len(report.violations),
                "files_checked": report.files_checked,
                "passed": passed,
                "failed": len(report.violations) if not passed else 0,
            },
        }
    except ImportError:
        return {"ok": False, "error": "质量检查模块未安装"}
    except Exception as e:
        logger.exception("质量检查运行失败")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
