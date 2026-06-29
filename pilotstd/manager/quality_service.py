# pilotstd/manager/quality_service.py
# 数据质量检查服务 — 供 API 层使用

from typing import Any


class QualityService:
    """数据质量检查服务（API 层迁移目标）。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    def run_check(self) -> dict[str, Any]:
        """运行数据质量检查，返回 violations 列表和摘要。"""
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
