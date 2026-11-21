"""G-013 规则 0 的判定实现（2026-11-21 从主脚本拆出，守 G-010 500 行上限）。

规则 0：提交信息命中 `\\b(fix|bugfix|hotfix|bug)\\b` 时必须带 `tests/` 变更；
**纯文档提交豁免**：改动非空且全部位于 `docs/` 或 `*.md` 时放行。
"""

from __future__ import annotations

import re
from typing import List

BUGFIX_PATTERN = re.compile(r"\b(fix|bugfix|hotfix|bug)\b", re.IGNORECASE)


def is_test_file(path: str) -> bool:
    """规则 0 的“带测试”判据：`tests/` 或前端 `web/src/**/*.test.ts(x)`。

    不用 `'test' in path`：`scripts/check_g_013_test_coverage.py` 这类**文件名含 test 的生产脚本**
    会被误当成测试变更，规则 0 被架空（2026-10-17 实测）。
    """
    normalized = path.replace("\\", "/").lower()
    if normalized.startswith("tests/") or "/tests/" in normalized:
        return True
    return bool(re.search(r"(^|/)web/src/.*\.test\.(ts|tsx|js|jsx)$", normalized))


def is_docs_only(changed_files: List[str]) -> bool:
    """改动是否**全部**位于 `docs/` 或 `*.md`（纯文档提交）。

    空列表返回 False：没有改动信息时不做豁免，避免"拿不到范围"被当成纯文档。
    """
    if not changed_files:
        return False
    for f in changed_files:
        path = f.replace("\\", "/")
        if path.startswith("docs/") or path.lower().endswith(".md"):
            continue
        return False
    return True


def _check_bugfix_rule(changed_files: List[str], commit_msg: str) -> tuple[bool, List[str]]:
    """规则 0：`fix`/`bugfix`/`hotfix` 提交必须带 `tests/` 下的变更。

    返回 ``(is_bugfix, errors)``。单独成函数是为了让 `run_check()` 守住 G-010 的
    80 有效行上限（2026-10-17 接线 commit-msg 后实测 84 行被拦）。
    """
    is_bugfix = bool(BUGFIX_PATTERN.search(commit_msg))
    if is_bugfix and is_docs_only(changed_files):
        # 纯文档提交豁免（2026-11-21）：提交信息里的 fix/bug 常是“修文档错误/修债号”，
        # 强制配测试只会产出无意义用例；豁免严格限定“全部改动都在文档目录或 Markdown 文件”。
        return is_bugfix, []
    has_test_change = any(is_test_file(f) for f in changed_files)
    if is_bugfix and not has_test_change:
        return is_bugfix, [
            "[TEST-BLOCK] Bug 修复必须伴随测试用例的新增或修改 "
            "(commit message 包含 fix/bugfix/hotfix，但未检测到测试文件变更；"
            "纯文档提交需全部改动位于 docs/ 或 *.md 才豁免)"
        ]
    return is_bugfix, []
