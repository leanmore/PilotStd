# pilotstd/ui/core/handlers/query_flow_engine.py
"""QueryFlowEngine — 查询相关的纯逻辑层（无 Qt 依赖）。

所有方法输入/输出均为 Python 原生类型或项目 dataclass，
不依赖任何 Qt 控件、对话框或信号。
"""

from __future__ import annotations

import csv
import logging
import re
from typing import Any, Callable

from ....i18n import _ as tr
from ....models import ParsedStdInfo

logger = logging.getLogger(__name__)

# ── 状态 → hex 颜色映射常量 ──────────────────────────────────
_STATUS_COLOR_MAP: dict[str, str] = {
    "现行": "#008000",
    "即将实施": "#0000ff",
    "废止": "#ff0000",
    "已废止": "#ff0000",
    "作废": "#ff0000",
    "待确认": "#808000",
}
_FALLBACK_COLOR = "#808000"  # darkYellow（不可下载覆盖）
_EXCLUDED_FROM_OVERRIDE = frozenset({"废止", "已废止", "作废", "待确认"})
_WEBSITE_NO_CATEGORY = "网站无此分类"


class QueryFlowEngine:
    """查询相关的纯逻辑层。

    所有方法均为纯函数风格，不持有 Qt 状态。
    """

    def __init__(self, config: Any) -> None:
        self._config = config

    # ═══════════════════════════════════════════════════════════
    # 数据校验
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def validate_standard(standard: str) -> bool:
        """校验标准号格式是否合法（非空 + 含数字）。"""
        return bool(standard and standard.strip() and re.search(r"\d", standard))

    # ═══════════════════════════════════════════════════════════
    # 状态映射
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def determine_status_color(status: str, is_downloadable: bool) -> str:
        """根据生效状态和可下载性返回 hex 颜色代码。

        规则：
          - 现行 → #008000 (darkGreen)
          - 即将实施 → #0000ff (blue)
          - 废止/已废止/作废 → #ff0000 (red)
          - 待确认 → #808000 (darkYellow)
          - 不可下载且非废止/待确认 → #808000 (darkYellow 覆盖)
          - 其他 → "" (无特殊着色)
        """
        color = _STATUS_COLOR_MAP.get(status, "")
        if not is_downloadable and status not in _EXCLUDED_FROM_OVERRIDE:
            color = _FALLBACK_COLOR
        return color

    # ═══════════════════════════════════════════════════════════
    # 数据转换
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def build_result_cells(
        result: Any,
        parsed: ParsedStdInfo,
        source_label: str,
    ) -> list[tuple[int, str]]:
        """将 QueryResult + ParsedStdInfo 转换为表格单元格列表 [(col, text), ...]。

        字段映射：
          col1 → 工作状态, col3 → 标准名称, col4 → 生效状态,
          col5 → 替代标准, col6 → 发布日期, col7 → 实施日期,
          col8 → 归口单位, col9 → 采标标记
        """
        return [
            (1, f"已查询({source_label})"),
            (3, result.standard_name or parsed.std_name),
            (4, result.status),
            (5, result.replaces if result.replaces != _WEBSITE_NO_CATEGORY else ""),
            (6, result.publish_date if result.publish_date != _WEBSITE_NO_CATEGORY else ""),
            (7, result.implementation_date if result.implementation_date != _WEBSITE_NO_CATEGORY else ""),
            (8, result.responsible_dept if result.responsible_dept != _WEBSITE_NO_CATEGORY else ""),
            (9, "采标" if result.is_adopted else ""),
        ]

    @staticmethod
    def parse_csv_content(
        csv_path: str,
        parse_fn: Callable[[str], Any],
    ) -> tuple[list[ParsedStdInfo], list[str]]:
        """解析待确认 CSV 文件，返回 (parsed_list, failed_names)。

        CSV 格式要求：
          - UTF-8-BOM 编码
          - 第 1 列：标准编号
          - 第 2 列：标准名称（可选，用于回填 std_name）
          - 第 1 行为表头（自动跳过）
          - 空行自动跳过

        parse_fn: 接收 "标准号.pdf" 字符串，返回 ParsedStdInfo 或 None。
        """
        parsed_list: list[ParsedStdInfo] = []
        failed_names: list[str] = []
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return parsed_list, failed_names
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if not row or not row[0].strip():
                continue
            std_num = row[0].strip()
            try:
                parsed = parse_fn(std_num + ".pdf")
            except Exception as e:
                logger.warning("解析标准号失败: %s — %s", std_num, e)
                failed_names.append(std_num)
                continue
            if parsed:
                parsed.std_name = (
                    row[1].strip() if len(row) > 1 and row[1].strip() else parsed.std_name
                )
                parsed_list.append(parsed)
            else:
                failed_names.append(std_num)
        return parsed_list, failed_names

    # ═══════════════════════════════════════════════════════════
    # 数据过滤
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def filter_empty_standards(standards: list[str]) -> list[str]:
        """过滤空标准号和纯空白字符串。"""
        return [s for s in standards if s and s.strip()]

    # ═══════════════════════════════════════════════════════════
    # 数据格式化
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def extract_year_from_std_number(std_num: str) -> str:
        """从标准号末尾提取四位年份（如 'GB/T 1.1-2020' → '2020'）。"""
        match = re.search(r"[-–](\d{4})$", std_num)
        return match.group(1) if match else ""

    @staticmethod
    def build_pending_csv_row(row: dict[str, Any]) -> list[str]:
        """将待确认 DB 行转换为 CSV 行数据列表。"""
        std_num = row.get("standard_number", "")
        year = QueryFlowEngine.extract_year_from_std_number(std_num)
        return [
            std_num,
            row.get("std_name", ""),
            row.get("found_name", ""),
            year,
            row.get("found_number", ""),
            row.get("effect_status", ""),
            str(row.get("score", "")),
            row.get("source_site", ""),
        ]

    @staticmethod
    def build_pending_csv_headers() -> list[str]:
        """返回待确认 CSV 表头标签列表。"""
        return [
            tr("query_pending_col_std_number"),
            tr("query_pending_col_source_filename"),
            tr("query_pending_col_web_name"),
            tr("query_pending_col_local_year"),
            tr("query_pending_col_web_number"),
            tr("query_pending_col_status"),
            tr("query_pending_col_confidence"),
            tr("query_pending_col_source_site"),
        ]

    # ═══════════════════════════════════════════════════════════
    # 列表操作
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def deduplicate_standards(standards: list[str]) -> list[str]:
        """标准号去重（保持原始顺序）。"""
        seen: set[str] = set()
        result: list[str] = []
        for s in standards:
            if s not in seen:
                seen.add(s)
                result.append(s)
        return result

    # ═══════════════════════════════════════════════════════════
    # 批量处理
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def batch_parse_standards(
        standards: list[str],
        parse_fn: Callable[[str], Any],
    ) -> list[dict[str, Any]]:
        """批量解析标准号，返回结构化数据列表。

        每个元素为 {"standard": str, "parsed": ParsedStdInfo | None, "error": str | None}。
        """
        results: list[dict[str, Any]] = []
        for s in standards:
            try:
                parsed = parse_fn(s + ".pdf")
                results.append({"standard": s, "parsed": parsed, "error": None})
            except Exception as e:
                results.append({"standard": s, "parsed": None, "error": str(e)})
        return results
