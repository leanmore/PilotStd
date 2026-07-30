# pilotstd/ui/core/handlers/toolbar_flow_engine.py
"""ToolbarFlowEngine — 工具栏状态机纯逻辑引擎（零 Qt 依赖）。

按钮使能/可见性决策、批量状态合并、动作组解析。
不依赖 QAction / QToolBar / QWidget 等 GUI 对象。
"""

from __future__ import annotations

from typing import Any


class ToolbarFlowEngine:
    """工具栏状态决策纯静态方法集合。

    仅抽取状态机转换规则，按钮绑定和信号槽操作保留在原 Handler。
    """

    @staticmethod
    def compute_button_state(
        selection_count: int,
        is_running: bool,
        rule: dict[str, Any],
    ) -> dict[str, bool]:
        """根据当前上下文计算单个按钮的 enabled / visible 状态。

        rule 格式:
            {"min_selection": 1, "max_selection": None, "hide_when_running": True}

        Args:
            selection_count: 当前选中项数量
            is_running: 是否有后台任务正在执行
            rule: 按钮状态规则字典

        Returns:
            {"enabled": bool, "visible": bool}
        """
        min_sel = rule.get("min_selection", 0) or 0
        max_sel = rule.get("max_selection")
        hide_running = rule.get("hide_when_running", False)

        # 选中数量在 [min, max] 范围内则启用
        enabled = selection_count >= min_sel
        if max_sel is not None:
            enabled = enabled and selection_count <= max_sel

        # 运行中隐藏：后台任务执行时不显示该按钮
        visible = True
        if hide_running and is_running:
            visible = False

        return {"enabled": enabled, "visible": visible}

    @staticmethod
    def merge_toolbar_states(
        button_states: list[dict[str, bool]],
    ) -> dict[str, bool]:
        """合并多个按钮状态，得出工具栏整体使能/可见性。

        toolbar_enabled: 至少一个按钮 enabled
        toolbar_visible: 至少一个按钮 visible
        空列表返回全部 False（安全降级）。
        """
        if not button_states:
            return {"toolbar_enabled": False, "toolbar_visible": False}
        any_enabled = any(s.get("enabled", False) for s in button_states)
        any_visible = any(s.get("visible", False) for s in button_states)
        return {"toolbar_enabled": any_enabled, "toolbar_visible": any_visible}

    @staticmethod
    def resolve_action_group(
        current_mode: str,
        mode_actions: dict[str, list[str]],
    ) -> list[str]:
        """根据当前模式返回应激活的 action ID 列表。

        未知模式返回空列表（安全降级），不抛异常。
        """
        return list(mode_actions.get(current_mode, []))
