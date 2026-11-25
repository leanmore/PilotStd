# 模块：项目/管理/门面/_归档键辅助
"""归档条目的规范编号键构造（批次10 / P1-7.1 B-11）。

从 `_organize.py`（G-010 警告档文件）拆出：`build_standard_number` 的调用参数较长，
在 `_register_moved_standards` / `_resolve_archived_pending` 两处重复；集中到本模块，
同时保证 `num_suffix`（`API 6D` 的 `D`、BPVC 册篇字母）进键，避免去重/登记丢后缀。
"""

from typing import Any

from ...core.std_utils import build_standard_number


def standard_number_for_item(item: Any, *, include_prefix: bool = True) -> str:
    """归档条目 → 规范编号键（`include_prefix=False` 用于“不带类型词”的 pending 变体键）。"""
    return build_standard_number(
        str(getattr(item, "logical_code", "") or ""),
        getattr(item, "number", 0),
        getattr(item, "part", None),
        getattr(item, "year", 0),
        (getattr(item, "num_prefix", "") or "") if include_prefix else "",
        getattr(item, "num_suffix", "") or "",
    )


def standard_number_from_parsed(parsed: dict[str, Any]) -> str:
    """A 通道解析结果（`parse_std_number`）→ 规范编号键。"""
    return build_standard_number(
        str(parsed.get("code") or ""),
        parsed.get("number"),
        parsed.get("part"),
        parsed.get("year"),
        parsed.get("num_prefix", "") or "",
        parsed.get("num_suffix", "") or "",
    )
