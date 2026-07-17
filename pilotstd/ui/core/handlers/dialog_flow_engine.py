# pilotstd/ui/core/handlers/dialog_flow_engine.py
"""DialogFlowEngine — 对话框/任务注册的纯逻辑层（零 Qt 依赖）。

提取 register_task 中的 label→TaskType 映射、参数校验、错误消息格式化。
"""

from __future__ import annotations

from typing import Any


class DialogFlowEngine:
    """对话框相关纯逻辑：任务类型映射、参数校验、错误格式化。"""

    # ═══════════════════════════════════════════════════════════════
    # 类常量
    # ═══════════════════════════════════════════════════════════════

    LABEL_TO_TASK_TYPE: dict[str, str] = {
        "扫描": "SCAN",
        "查询": "QUERY",
        "下载": "DOWNLOAD",
        "规范化": "ORGANIZE",
    }
    """任务标签 → TaskType 枚举名映射。"""

    DEFAULT_TASK_TYPE = "SCAN"
    """未匹配标签时的默认 TaskType。"""

    # ═══════════════════════════════════════════════════════════════
    # 任务类型查询
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def get_task_type_name(label: str) -> str:
        """返回标签对应的 TaskType 枚举名，未知标签返回 DEFAULT_TASK_TYPE。

        Args:
            label: 中文任务标签（"扫描"/"查询"/"下载"/"规范化"）

        Returns:
            TaskType 枚举名（"SCAN"/"QUERY"/"DOWNLOAD"/"ORGANIZE"）。
        """
        if not isinstance(label, str):
            return DialogFlowEngine.DEFAULT_TASK_TYPE
        return DialogFlowEngine.LABEL_TO_TASK_TYPE.get(label, DialogFlowEngine.DEFAULT_TASK_TYPE)

    # ═══════════════════════════════════════════════════════════════
    # 参数校验
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def validate_task_params(label: str, total: int, completed: int, failed: int = 0) -> dict[str, Any]:
        """校验任务注册参数并返回标准化结果。

        Args:
            label: 任务标签
            total: 总条数
            completed: 已完成数
            failed: 失败数

        Returns:
            {
                "label": str,         # 原始标签
                "total": int,         # 标准化 total（≥0）
                "completed": int,     # 标准化 completed（≥0）
                "failed": int,        # 标准化 failed（≥0）
                "type_name": str,     # TaskType 枚举名
                "is_valid": bool,     # 参数是否合法
                "errors": list[str],  # 错误信息列表
            }
        """
        errors: list[str] = []

        if not isinstance(label, str) or not label.strip():
            errors.append("任务标签不能为空")
        if not isinstance(total, int) or total < 0:
            errors.append(f"total 无效: {total}")
        if not isinstance(completed, int) or completed < 0:
            errors.append(f"completed 无效: {completed}")
        if not isinstance(failed, int) or failed < 0:
            errors.append(f"failed 无效: {failed}")

        type_name = (
            DialogFlowEngine.get_task_type_name(label) if isinstance(label, str) else DialogFlowEngine.DEFAULT_TASK_TYPE
        )

        return {
            "label": label if isinstance(label, str) else str(label),
            "total": max(0, total) if isinstance(total, int) else 0,
            "completed": max(0, completed) if isinstance(completed, int) else 0,
            "failed": max(0, failed) if isinstance(failed, int) else 0,
            "type_name": type_name,
            "is_valid": len(errors) == 0,
            "errors": errors,
        }

    # ═══════════════════════════════════════════════════════════════
    # 错误格式化
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def format_task_error(message: str) -> str:
        """格式化任务操作错误消息。

        Args:
            message: 原始错误信息

        Returns:
            格式化后的完整错误消息。
        """
        return f"任务记录失败: {message}"
