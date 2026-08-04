# 模块：项目//运行器脚本
# 质量检查运行器——扫描目录，汇总违规

import os
from typing import Any

from .models import CheckReport
from .rules.stale_references import StaleReferencesRule


class QualityRunner:
    """质量检查运行器：遍历文件/目录，用注册的规则逐文件检查，汇总违规报告。"""

    def __init__(self, rules: Any = None) -> None:
        self._rules = rules or [StaleReferencesRule()]

    def run(self, paths: list[str]) -> CheckReport:
        """对指定路径列表执行质量检查，返回汇总报告。"""
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
