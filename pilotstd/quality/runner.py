# pilotstd/quality/runner.py
# 质量检查运行器——扫描目录，汇总违规

import os

from .models import CheckReport
from .rules.stale_references import StaleReferencesRule


class QualityRunner:
    def __init__(self, rules=None):
        self._rules = rules or [StaleReferencesRule()]

    def run(self, paths: list) -> CheckReport:
        report = CheckReport()
        for path in paths:
            if os.path.isfile(path) and path.endswith(".py"):
                report.files_checked += 1
                for rule in self._rules:
                    report.violations.extend(rule.check_file(path))
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        if f.endswith(".py"):
                            report.files_checked += 1
                            filepath = os.path.join(root, f)
                            for rule in self._rules:
                                report.violations.extend(rule.check_file(filepath))
        return report
