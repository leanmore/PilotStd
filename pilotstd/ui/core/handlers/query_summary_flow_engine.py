# pilotstd/ui/core/handlers/query_summary_flow_engine.py
"""QuerySummaryFlowEngine — 查询汇总的纯逻辑层（零 Qt 依赖）。

数据分组、状态描述映射、安全字符串转换、统计消息构建。
"""

from __future__ import annotations

from typing import Any


class QuerySummaryFlowEngine:
    """查询汇总的纯逻辑处理：分桶、原因映射、安全字符串、统计。"""

    # ═══════════════════════════════════════════════════════════════
    # 类常量
    # ═══════════════════════════════════════════════════════════════

    STATUS_LABEL_MAP: dict[str, str] = {
        "chain_exhausted": "所有适配器已尝试",
        "match_not_exact": "匹配不精确",
        "name_conflict": "名称冲突",
        "source_path_empty": "源路径为空",
        "replacement_manual": "需手动替换",
        "user_retained": "用户保留",
        "version_mismatch": "版本不匹配",
    }
    """stage_status / match_status → 中文描述。"""

    ACTION_TO_BUCKET: dict[str, str] = {
        "archive": "organize",
        "normalize": "normalize",
        "expire": "expire",
        "download": "download",
        "manual_download": "manual_download",
        "pending": "pending",
        "not_found": "not_found",
    }
    """next_action → 桶名映射。"""

    BUCKET_NAMES: tuple[str, ...] = (
        "organize",
        "normalize",
        "expire",
        "download",
        "manual_download",
        "pending",
        "not_found",
    )
    """所有桶名，按逻辑顺序排列。"""

    # ═══════════════════════════════════════════════════════════════
    # 分桶
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def build_buckets(standards: list[Any]) -> dict[str, list[Any]]:
        """将 ParsedStdInfo 列表按 next_action 分组到对应桶中。

        Args:
            standards: ParsedStdInfo 列表

        Returns:
            {桶名: [条目列表]}，所有 BUCKET_NAMES 中的桶都会出现（即使为空列表）。
        """
        buckets: dict[str, list[Any]] = {k: [] for k in QuerySummaryFlowEngine.BUCKET_NAMES}
        if not isinstance(standards, list):
            return buckets
        for p in standards:
            action = getattr(p, "next_action", "") or ""
            key = QuerySummaryFlowEngine.ACTION_TO_BUCKET.get(action)
            if key is not None:
                buckets[key].append(p)
        return buckets

    # ═══════════════════════════════════════════════════════════════
    # 待确认原因
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_pending_reason(status: str) -> str:
        """返回状态码对应的中文描述。

        Args:
            status: stage_status 或 match_status 值

        Returns:
            中文描述字符串；未知状态码返回空字符串。
        """
        if not isinstance(status, str):
            return ""
        return QuerySummaryFlowEngine.STATUS_LABEL_MAP.get(status, "")

    # ═══════════════════════════════════════════════════════════════
    # 安全字符串转换
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def safe_str(value: Any) -> str:
        """空值安全的字符串转换。

        - bool 值返回空字符串（避免 False → "False"）
        - None / 0 / 空字符串返回 ""
        - 其他值调用 str()
        """
        if isinstance(value, bool):
            return ""
        return str(value) if value else ""

    # ═══════════════════════════════════════════════════════════════
    # 统计消息
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def build_summary_message(buckets: dict[str, list[Any]] | None, total: int) -> str:
        """从分桶结果构建统计摘要文本。

        Args:
            buckets: build_buckets 的输出
            total: 总条目数

        Returns:
            可读的统计摘要字符串。
        """
        if not isinstance(buckets, dict):
            buckets = {}
        archive = len(buckets.get("organize", []))
        pending = len(buckets.get("pending", []))
        expire = len(buckets.get("expire", []))
        return f"总计 {total} 条，归档 {archive} 条，待确认 {pending} 条，过期 {expire} 条"
