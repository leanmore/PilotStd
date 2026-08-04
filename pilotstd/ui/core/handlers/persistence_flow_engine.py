# 模块：项目//核心/处理器/持久化__引擎脚本
"""PersistenceFlowEngine — 持久化数据序列化/反序列化纯逻辑层（零 Qt 依赖）。

所有方法输入/输出均为 Python 原生类型（dict、list、int、str、bytes），
不依赖任何 Qt 控件、对话框或信号。
"""

from __future__ import annotations

import base64
import logging
from typing import Any

logger = logging.getLogger(__name__)


class PersistenceFlowEngine:
    """持久化相关数据的序列化与反序列化纯逻辑。"""

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 窗口几何
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_window_geometry(x: int, y: int, width: int, height: int) -> dict[str, int]:
        """将窗口坐标和尺寸序列化为 dict。"""
        return {"x": x, "y": y, "width": width, "height": height}

    @staticmethod
    def deserialize_window_geometry(data: Any, default: dict[str, int]) -> dict[str, int]:
        """从 dict 反序列化窗口几何；数据无效时返回 default。"""
        if not isinstance(data, dict):
            return default
        required = ("x", "y", "width", "height")
        if not all(k in data for k in required):
            return default
        try:
            return {k: int(data[k]) for k in required}
        except (ValueError, TypeError):
            return default

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 分栏尺寸
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_splitter_sizes(sizes: list[int]) -> list[int]:
        """序列化分栏尺寸列表。"""
        return list(sizes)

    @staticmethod
    def deserialize_splitter_sizes(data: Any, default: list[int]) -> list[int]:
        """反序列化分栏尺寸；数据无效时返回 default。"""
        if isinstance(data, list) and all(isinstance(v, int) for v in data):
            return list(data)
        return list(default)

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 列宽
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_column_widths(widths: list[int]) -> list[int]:
        """序列化列宽列表。"""
        return list(widths)

    @staticmethod
    def deserialize_column_widths(data: Any, col_count: int, default: int) -> list[int]:
        """反序列化列宽；数据无效或长度不匹配时返回 [default] * col_count。"""
        if isinstance(data, list) and all(isinstance(v, int) for v in data) and len(data) == col_count:
            return list(data)
        return [default] * col_count

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 表头状态
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_header_state(state: bytes) -> str:
        """将表头状态 bytes 编码为 Base64 字符串。"""
        return base64.b64encode(state).decode("ascii")

    @staticmethod
    def deserialize_header_state(data: Any) -> bytes:
        """从 Base64 字符串解码表头状态；解码失败返回 b""。"""
        if not isinstance(data, str):
            return b""
        try:
            return base64.b64decode(data, validate=True)
        except Exception:
            logger.debug("表头状态 Base64 解码失败，返回空 bytes", exc_info=True)
            return b""
