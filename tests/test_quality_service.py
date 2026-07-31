"""pilotstd/manager/quality_service.py 补测。"""
from unittest.mock import MagicMock, patch

from pilotstd.manager.quality_service import QualityService


class TestQualityService:
    def test_run_check_with_violations(self):
        svc = QualityService(MagicMock())
        mock_report = MagicMock()
        mock_violation = MagicMock()
        mock_violation.rule = "G-010"
        mock_violation.severity.value = "error"
        mock_violation.file = "test.py"
        mock_violation.line = 42
        mock_violation.message = "too long"
        mock_report.violations = [mock_violation]
        mock_report.files_checked = 10
        with patch("pilotstd.quality.QualityRunner") as MockRunner:
            MockRunner.return_value.run.return_value = mock_report
            result = svc.run_check()
            assert result["ok"] is True
            assert result["summary"]["total"] == 1
            assert result["summary"]["files_checked"] == 10

    def test_run_check_no_violations(self):
        svc = QualityService(MagicMock())
        mock_report = MagicMock()
        mock_report.violations = []
        mock_report.files_checked = 5
        with patch("pilotstd.quality.QualityRunner") as MockRunner:
            MockRunner.return_value.run.return_value = mock_report
            result = svc.run_check()
            assert result["ok"] is True
            assert result["summary"]["total"] == 0
            assert result["summary"]["passed"] is True
            assert result["summary"]["failed"] == 0

    def test_run_check_with_error_violations(self):
        svc = QualityService(MagicMock())
        mock_v = MagicMock()
        mock_v.rule = "G-015"
        mock_v.severity.value = "error"
        mock_v.file = "x.py"
        mock_v.line = 1
        mock_v.message = "bad import"
        mock_report = MagicMock()
        mock_report.violations = [mock_v]
        mock_report.files_checked = 3
        with patch("pilotstd.quality.QualityRunner") as MockRunner:
            MockRunner.return_value.run.return_value = mock_report
            result = svc.run_check()
            assert result["results"][0]["rule"] == "G-015"
            assert result["results"][0]["severity"] == "error"
