# pilotstd/ui/core/handlers/actions_flow_engine.py
"""ActionsFlowEngine — 动作处理相关的纯逻辑层（无 Qt 依赖）。"""

from __future__ import annotations

import time as _time

# ── 常量 ──────────────────────────────────────────────────
_TOOLBAR_BUTTON_KEYS = (
    "btn_select",
    "btn_query",
    "btn_download",
    "btn_normalize",
    "btn_save",
    "btn_auto",
    "btn_announce",
    "btn_pause",
)

_THROTTLE_SECONDS = 86400  # 24 小时


class ActionsFlowEngine:
    """动作处理相关的纯逻辑层。"""

    # ═══════════════════════════════════════════════════════════
    # 常量
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def get_toolbar_button_keys() -> tuple[str, ...]:
        """返回工具栏所有操作按钮的键名列表。"""
        return _TOOLBAR_BUTTON_KEYS

    # ═══════════════════════════════════════════════════════════
    # 版本/更新
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def is_update_throttled(last_check_ts: float | int) -> bool:
        """检查是否在 24h 节流窗口内。返回 True 表示应跳过检查。"""
        if not isinstance(last_check_ts, (int, float)):
            return False
        return _time.time() - last_check_ts < _THROTTLE_SECONDS

    @staticmethod
    def is_frozen() -> bool:
        """判断当前是否为 PyInstaller 打包后的 exe 运行模式。"""
        import sys

        return bool(getattr(sys, "frozen", False))
