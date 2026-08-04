# 模块：项目//核心/处理器/__引擎脚本
"""AutoFlowEngine — 自动管线汇总统计的纯逻辑层（零 Qt 依赖）。

提取 _build_auto_summary_message 中的数据统计逻辑：
结果分类（未找到/已废止/采标）→ 结构化 stats dict。
i18n 格式化由 Handler 层负责。
"""

from __future__ import annotations

from typing import Any


class AutoFlowEngine:
    """自动管线纯逻辑：结果分类统计、汇总数据构建。"""

    # 已废止状态的特征值集合
    EXPIRED_STATUSES: frozenset[str] = frozenset({"废止", "已废止", "作废"})

    @staticmethod
    def build_summary_stats(results: list[Any]) -> dict[str, Any]:
        """从查询结果列表构建汇总统计数据。

        对每条结果按标准名、效力状态、是否采标分类，
        生成完整统计字典，供处理器层做国际化格式化。

        参数接收查询结果列表，每条须有标准名、效力状态、是否采标、获取完整编号等属性。
        返回包含总数、未找到数、废止数、采标数、已找到数、需人工处理列表的字典。
        """
        if not results:
            return {
                "total": 0,
                "not_found_count": 0,
                "expired_count": 0,
                "adopted_count": 0,
                "found_count": 0,
                "manual_all": [],
            }

        total = len(results)
        not_found = [p for p in results if not p.std_name]
        expired = [p for p in results if p.effect_status in AutoFlowEngine.EXPIRED_STATUSES]
        adopted = [p for p in results if p.is_adopted]

        manual_all: list[dict[str, str]] = []
        for p in not_found:
            manual_all.append({"number": p.get_full_number(), "reason": "not_found"})
        for p in adopted:
            manual_all.append({"number": p.get_full_number(), "reason": "adopted"})

        return {
            "total": total,
            "not_found_count": len(not_found),
            "expired_count": len(expired),
            "adopted_count": len(adopted),
            "found_count": total - len(not_found),
            "manual_all": manual_all,
        }
