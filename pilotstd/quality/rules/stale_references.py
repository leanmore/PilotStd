# pilotstd/quality/rules/stale_references.py
# 陈旧引用检测——导入了已删除函数/方法的文件

import ast
from typing import Any, Set

from ..models import Severity, Violation


class StaleReferencesRule:
    """检测导入了已删除函数/类的陈旧引用。"""

    name = "stale-references"

    # 已知已删除的符号
    DELETED_SYMBOLS: Set[str] = {
        "build_search_terms",
        "build_code_variant",
        "query_single",  # 适配器层已删除
        "query_batch",  # 适配器层已删除
    }

    # 已删除符号来源模块（可选，精确匹配）
    DELETED_IMPORTS: Set[tuple[str, str]] = {
        ("pilotstd.query.search_strategy", "build_search_terms"),
        ("pilotstd.query.adapters.base", "query_single"),
        ("pilotstd.query.adapters.base", "query_batch"),
    }

    def check_file(self, filepath: str) -> list[Any]:
        """解析单个 Python 文件，检测是否导入了已知已删除的符号。"""
        violations: list[Any] = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, UnicodeDecodeError):
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        key = (node.module, alias.name)
                        if key in self.DELETED_IMPORTS:
                            violations.append(
                                Violation(
                                    rule=self.name,
                                    severity=Severity.ERROR,
                                    file=filepath,
                                    line=node.lineno,
                                    message=f"导入了已删除的符号 '{alias.name}' from '{node.module}'",
                                )
                            )
            elif isinstance(node, ast.Attribute):
                if isinstance(node.attr, str) and node.attr in self.DELETED_SYMBOLS:
                    violations.append(
                        Violation(
                            rule=self.name,
                            severity=Severity.ERROR,
                            file=filepath,
                            line=node.lineno,
                            message=f"调用了已删除的方法 '{node.attr}'",
                        )
                    )

        return violations
