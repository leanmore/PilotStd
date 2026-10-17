#!/usr/bin/env python3
"""覆盖率阈值唯一来源（G-034 门禁与覆盖率报告生成器共用）。

阈值取自 `pyproject.toml` 的 `[tool.coverage.report] fail_under`。项目里曾同时存在
**四套口径**（pyproject 51 / CI test-backend 45 / CI GUI 58 / 旧 gates.md 80，体检 B-1），
任何按 gates.md 判断"达标线"的人都会得出错误结论，故把唯一权威钉在 pyproject。

读不到 `fail_under` 时退回 45：与 CI `test-backend` 的实际阻断值一致，宁可保守。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

FALLBACK_THRESHOLD = 45.0


def resolve_threshold(pyproject: Path = PYPROJECT) -> float:
    """从 `pyproject.toml` 的 `[tool.coverage.report] fail_under` 取唯一权威阈值。"""
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return FALLBACK_THRESHOLD
    match = re.search(r"^\s*fail_under\s*=\s*([\d.]+)", text, re.MULTILINE)
    if not match:
        return FALLBACK_THRESHOLD
    try:
        return float(match.group(1))
    except ValueError:
        return FALLBACK_THRESHOLD
