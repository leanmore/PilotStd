# 模块：pilotstd/ui/core/handlers/project_flow_engine.py
"""ProjectFlowEngine — 项目状态的纯逻辑层（零 Qt 依赖）。

提取项目状态序列化/反序列化、路径校验的纯计算逻辑。
"""

from __future__ import annotations

from typing import Any


class ProjectFlowEngine:
    """项目状态纯逻辑：序列化、反序列化、路径校验。"""

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 类常量
    # ═══════════════════════════════════════════════════════════════ 分隔

    PROJECT_STATE_KEYS = ("work_table_rows", "current_path", "unrecognized_files")
    """项目状态 dict 的必需键。"""

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 序列化
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def serialize_project_state(session_data: dict[str, Any]) -> dict[str, Any]:
        """标准化 session 数据为可存储的项目状态。

        Args:
            session_data: 从工作区收集的原始 session 数据

        Returns:
            标准化后的 dict，确保所有必需键存在。
        """
        if not isinstance(session_data, dict):
            session_data = {}
        return {
            "work_table_rows": session_data.get("work_table_rows", []),
            "current_path": session_data.get("current_path", ""),
            "unrecognized_files": session_data.get("unrecognized_files", []),
        }

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 反序列化
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def deserialize_project_state(config_data: dict[str, Any]) -> dict[str, Any]:
        """从配置数据还原 session 状态，缺失键以默认值回填。

        Args:
            config_data: 从项目文件加载的原始 dict

        Returns:
            标准化后的 dict，确保所有必需键存在。
        """
        return ProjectFlowEngine.serialize_project_state(config_data)

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 路径校验
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def validate_project_path(path: str, base: str | None = None) -> bool:
        """字符串级别校验项目路径合法性。

        Args:
            path: 待校验的项目文件路径
            base: 可选的基础目录（用于路径遍历检测）

        Returns:
            True 表示路径通过基本安全检查。
        """
        if not isinstance(path, str) or not path.strip():
            return False
        # 空字节注入
        if "\x00" in path:
            return False
        # 路径遍历检测
        segments = path.replace("\\", "/").split("/")
        if any(seg == ".." for seg in segments):
            return False
        # 超长路径
        if len(path) > 4096:
            return False
        return True
