# pilotstd/ui/core/handlers/table_helper_flow_engine.py
"""TableHelperFlowEngine — 工作表辅助的纯逻辑层（零 Qt 依赖）。

提取 enforce_min_column_width / find_row_by_seq 的纯计算逻辑。
"""

from __future__ import annotations

from typing import Any


class TableHelperFlowEngine:
    """工作表辅助纯逻辑：列宽约束、行查找。"""

    # ═══════════════════════════════════════════════════════════════
    # 列宽约束
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def enforce_min_column_width(width: int, min_width: int) -> int:
        """确保列宽不小于最小值。

        Args:
            width: 当前列宽
            min_width: 最小允许列宽

        Returns:
            max(width, min_width)
        """
        return max(int(width), int(min_width))

    # ═══════════════════════════════════════════════════════════════
    # 按序号查找行
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def find_row_by_seq(rows: list[dict[str, Any]], seq: int) -> int:
        """在行数据列表中按序号查找行索引。

        Args:
            rows: 行数据列表，每行 dict 至少包含 "seq" 或 "#" 键
            seq: 要查找的序号

        Returns:
            匹配行的索引（0-based），未找到返回 -1。
        """
        if not isinstance(rows, list):
            return -1
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            val = row.get("seq") or row.get("#")
            try:
                if val is not None and int(str(val)) == seq:
                    return i
            except (ValueError, TypeError):
                continue
        return -1
