# 模块：项目//核心/处理器/__引擎脚本
"""AnnounceFlowEngine — 公告数据处理的纯逻辑层（零 Qt、零 I/O、零事件总线）。

提取公告解析、状态过滤、日期排序等纯数据变换逻辑。
"""

from __future__ import annotations

from typing import Any


class AnnounceFlowEngine:
    """公告相关纯逻辑：字段标准化、状态过滤、日期排序。"""

    # ── 字段映射（原始字段 → 标准化字段）────────────────────────
    _FIELD_MAP: dict[str, str] = {
        "TITLE": "title",
        "C_TITLE": "title",
        "NOTICE_DATE": "publish_date",
        "PUBLISH_DATE": "publish_date",
        "CODE": "code",
        "PID": "pid",
        "STANDARD_COUNT": "standard_count",
        "STD_COUNT": "standard_count",
    }

    _DEFAULT_DATE = "0000-00-00"

    # ──_（解析公告数据）──────────────────────────────

    @staticmethod
    def parse_announcement(raw: dict[str, Any] | None) -> dict[str, Any]:
        """将原始公告数据标准化为统一格式。

        处理：字段名映射（兼容多数据源）、类型转换、缺失字段补默认值。
        不执行任何输入输出操作。

        参数：
            raw: 原始公告字典（可能来自不同适配器，字段名各异）

        返回值字典包含：标题、编号、唯一标识、发布日期、含标准数量、是否有效公告。
        """
        if not raw or not isinstance(raw, dict):
            return {
                "title": "",
                "code": "",
                "pid": "",
                "publish_date": AnnounceFlowEngine._DEFAULT_DATE,
                "standard_count": 0,
                "is_valid": False,
            }

        # 字段映射 + 回退
        def _get(*keys: str) -> Any:
            """从 raw dict 中按优先级取第一个非空值。"""
            for k in keys:
                v = raw.get(k)
                if v is not None and v != "":
                    return v
            return None

        title = str(_get("title", "TITLE", "C_TITLE") or "")
        code = str(_get("code", "CODE") or "")
        pid = str(_get("pid", "PID") or "")
        publish_date = str(_get("publish_date", "NOTICE_DATE", "notice_date") or AnnounceFlowEngine._DEFAULT_DATE)
        raw_count = _get("standard_count", "STD_COUNT", "std_count")

        try:
            standard_count = int(raw_count) if raw_count is not None else 0
        except (ValueError, TypeError):
            standard_count = 0

        return {
            "title": title,
            "code": code,
            "pid": pid,
            "publish_date": publish_date,
            "standard_count": standard_count,
            "is_valid": bool(title or code),
        }

    # ──__（按状态过滤公告列表）────────────────────────────

    @staticmethod
    def filter_by_status(items: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
        """按状态过滤公告列表。

        Args:
            items: 公告列表（每项含 "status" 或 "effect_status" 键）
            status: 目标状态值（如 "现行"、"废止"、"即将实施"）

        Returns:
            匹配状态的公告列表
        """
        if not items or not status:
            return list(items) if items else []

        def _matches(item: dict[str, Any]) -> bool:
            item_status = item.get("status") or item.get("effect_status") or ""
            return str(item_status) == status

        return [item for item in items if _matches(item)]

    # ──__（按发布日期排序公告）──────────────────────────────

    @staticmethod
    def sort_by_date(items: list[dict[str, Any]], descending: bool = True) -> list[dict[str, Any]]:
        """按发布日期排序公告列表。

        Args:
            items: 公告列表（每项含 "publish_date" 或 "notice_date" 键）
            descending: True 降序（最新在前），False 升序

        Returns:
            排序后的新列表（不修改原列表）
        """
        if not items:
            return []

        def _date_key(item: dict[str, Any]) -> str:
            d = item.get("publish_date") or item.get("notice_date") or AnnounceFlowEngine._DEFAULT_DATE
            return str(d)

        return sorted(items, key=_date_key, reverse=descending)
