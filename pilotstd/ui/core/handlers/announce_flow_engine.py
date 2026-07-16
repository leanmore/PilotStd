# pilotstd/ui/core/handlers/announce_flow_engine.py
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

    # ── parse_announcement ──────────────────────────────────────

    @staticmethod
    def parse_announcement(raw: dict[str, Any] | None) -> dict[str, Any]:
        """将原始公告数据标准化为统一格式。

        处理：字段名映射（兼容多数据源）、类型转换、缺失字段补默认值。
        不执行任何 I/O。

        Args:
            raw: 原始公告 dict（可能来自不同适配器，字段名各异）

        Returns:
            {
                "title": str,           # 公告标题
                "code": str,            # 公告编号
                "pid": str,             # 公告唯一标识
                "publish_date": str,    # 发布日期（YYYY-MM-DD）
                "standard_count": int,  # 含标准数量
                "is_valid": bool,       # 是否为有效公告（至少有 title 或 code）
            }
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

    # ── filter_by_status ────────────────────────────────────────

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

    # ── sort_by_date ────────────────────────────────────────────

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
