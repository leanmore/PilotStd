# 模块：项目/下载/_文件名片段
"""下载任务标准号 → 文件名构造参数（批次10 / P1-7.1 B-11）。

`make_standard_filename` 除 `logical_code` 外还需要 `num_prefix`/`num_suffix`，否则 BPVC 卷册与
API 字母后缀会丢（下载件名 `ASME 8.1-2025.pdf` / `API 6-2021.pdf`）。此处集中从
`task.standard_number` 提取字段，避免在 `engine._resolve_target_path`（G-010 警告档文件）里堆代码。
"""

from typing import Any


def build_filename_fields(standard_number: str) -> dict[str, Any]:
    """解析标准号并返回 `make_standard_filename` 需要的字段字典。"""
    from ..query.search_strategy import _parse_result_number

    parsed = _parse_result_number(standard_number or "") or {}
    if parsed:
        logical_code = str(parsed.get("code") or "")
    else:
        logical_code = standard_number.split()[0] if " " in standard_number else standard_number
    return {
        "logical_code": logical_code,
        "number": parsed.get("number", 0) or 0,
        "year": parsed.get("year", 0) or 0,
        "part": parsed.get("part"),
        "num_prefix": parsed.get("num_prefix", "") or "",
        "num_suffix": parsed.get("num_suffix", "") or "",
    }
