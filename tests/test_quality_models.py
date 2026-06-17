# tests/test_quality_models.py
# 质量检查数据模型单元测试

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.quality.models import Violation, RuleResult, CheckReport, Severity


def test_violation_creation():
    v = Violation(
        rule="dup_impl",
        severity=Severity.WARNING,
        file="pilotstd/pipeline/router.py",
        line=32,
        message="函数 _is_gb_code 重复定义",
        suggestion="改为 from ..core.std_utils import is_gb_code"
    )
    assert v.rule == "dup_impl"
    assert v.severity == Severity.WARNING
    assert v.line == 32


def test_check_report_totals():
    report = CheckReport(rules=[
        RuleResult(rule_name="test1", description="",
                   violations=[
                       Violation(rule="test1", severity=Severity.ERROR,
                                 file="a.py", line=1, message="err"),
                       Violation(rule="test1", severity=Severity.WARNING,
                                 file="b.py", line=2, message="warn"),
                   ]),
        RuleResult(rule_name="test2", description="", violations=[]),
    ])
    assert report.total_violations == 2
    assert report.error_count == 1
    assert report.warning_count == 1


def test_severity_values():
    assert Severity.ERROR.value == "error"
    assert Severity.WARNING.value == "warning"
    assert Severity.INFO.value == "info"
