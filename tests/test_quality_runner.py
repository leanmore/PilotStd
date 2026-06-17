# tests/test_quality_runner.py
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.quality.runner import _format_terminal, _format_json, _format_markdown
from scripts.quality.models import CheckReport, RuleResult, Violation, Severity


def make_sample_report():
    return CheckReport(rules=[
        RuleResult(rule_name="dup_impl", description="重复实现检查",
                   violations=[
                       Violation(rule="dup_impl", severity=Severity.WARNING,
                                 file="pilotstd/pipeline/router.py", line=32,
                                 message="函数 _is_gb_code 重复定义",
                                 suggestion="改为 import"),
                   ]),
        RuleResult(rule_name="raw_logger", description="日志入口检查",
                   violations=[]),
    ])


def test_terminal_output_contains_rule_names():
    out = _format_terminal(make_sample_report())
    assert "dup_impl" in out
    assert "raw_logger" in out
    assert "router.py" in out


def test_json_output_is_valid():
    data = json.loads(_format_json(make_sample_report()))
    assert data["summary"]["total"] == 1
    assert len(data["violations"]) == 1


def test_markdown_output_contains_table():
    out = _format_markdown(make_sample_report())
    assert "|" in out
    assert "dup_impl" in out


def test_empty_report():
    out = _format_terminal(CheckReport())
    assert "全部通过" in out
