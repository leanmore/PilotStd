# pilotstd/ui/core/handlers/table_flow_engine.py
"""TableFlowEngine — 工作表导出/可见性的纯逻辑层（零 Qt 依赖）。

提取 row_get、format_csv_row、format_txt_row、validate_column_visibility
的纯计算逻辑。
"""

from __future__ import annotations

from typing import Any


class TableFlowEngine:
    """工作表纯逻辑：字段获取、行格式化、列可见性校验。"""

    # ═══════════════════════════════════════════════════════════════
    # 安全字段获取
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def row_get(row: Any, key: str, default: str = "") -> str:
        """安全获取字段值 — 兼容 dict 和对象属性。

        Args:
            row: dict 或任意对象
            key: 字段名
            default: 默认值

        Returns:
            字段值的字符串形式。
        """
        if isinstance(row, dict):
            return str(row.get(key, default))
        return str(getattr(row, key, default))

    # ═══════════════════════════════════════════════════════════════
    # CSV 行格式化
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def format_csv_row(row_data: dict[str, Any], headers: list[str]) -> list[str]:
        """将行数据按表头顺序格式化为 CSV 值列表。

        Args:
            row_data: 单行数据 dict
            headers: 列键名列表（决定输出顺序）

        Returns:
            与 headers 等长的字符串列表。
        """
        return [TableFlowEngine.row_get(row_data, h) for h in headers]

    # ═══════════════════════════════════════════════════════════════
    # TXT 行格式化
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def format_txt_row(row_data: dict[str, Any], headers: list[str]) -> str:
        """将行数据按表头顺序格式化为制表符分隔的文本行。

        Args:
            row_data: 单行数据 dict
            headers: 列键名列表

        Returns:
            制表符分隔的字符串。
        """
        return "\t".join(TableFlowEngine.row_get(row_data, h) for h in headers)

    # ═══════════════════════════════════════════════════════════════
    # 列可见性校验
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def validate_column_visibility(
        visible: list[bool] | None, col_count: int, default_vis: list[bool] | None = None
    ) -> list[bool]:
        """校验并补全列可见性配置。

        Args:
            visible: 当前可见性列表（可能为 None 或长度不足）
            col_count: 期望的列数
            default_vis: 默认可见性列表

        Returns:
            长度为 col_count 的可见性列表。
        """
        if default_vis is None:
            default_vis = [True] * col_count
        if not isinstance(visible, list) or not visible:
            return list(default_vis[:col_count])
        result = list(visible[:col_count])
        while len(result) < col_count:
            idx = len(result)
            result.append(default_vis[idx] if idx < len(default_vis) else True)
        return result
