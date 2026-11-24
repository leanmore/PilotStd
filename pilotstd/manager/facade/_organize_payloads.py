# 模块：项目/管理器/门面/_归类载荷脚本
"""归档/规范化失败事件的载荷助手（P1 批 B-4「补对象」）。

拆出原因（守 G-010 警告档棘轮）：`_organize.py` 已在其存量有效行上**不允许增长**，
故把「标准号格式化 + 失败明细构造」放这里，原文件只留导入与一行调用。
"""

from __future__ import annotations

from typing import Any


def _fmt_std_number(p: Any) -> str:
    """把 `ParsedStdInfo` 拼成**可读的标准完整编号**（如 `GB/T 1234-2020`），供失败明细展示。

    为什么不用 `p.number` 而优先 `raw_number`：`number` 是 int（丢前导零），
    `raw_number` 保留原始数字串（见 `pilotstd/models.py:16-18`）；两者都空时退回 `"-"`。
    年度缺失（如 `GB/T 1`）时不追加 `-年份`；样例见
    `tests/download/adapters/test_openstd_download.py:600`。
    """
    code = (getattr(p, "logical_code", "") or "").strip()
    num = (getattr(p, "raw_number", "") or "").strip() or str(getattr(p, "number", "") or "").strip()
    year = getattr(p, "year", 0) or 0
    if not code and not num:
        return "-"
    base = f"{code} {num}".strip()
    return f"{base}-{year}" if year else base


def build_failed_item(parsed: Any, error_message: str) -> dict[str, str] | None:
    """构造一条 `failed_items` 明细（4 列口径，供失败明细块渲染）；无当前条目时返回 None。

    口径与 `_builders_batch.build_failed_items_block` 一致：
    standard_number / standard_name / error_type / error_message。
    """
    if parsed is None:
        return None
    return {
        "standard_number": _fmt_std_number(parsed),
        "standard_name": getattr(parsed, "std_name", "") or "-",
        "error_type": "unknown",
        "error_message": error_message[:120],
    }
