# 模块：pilotstd/core/project.py
# 项目管理：工作状态保存/恢复（.pilotstd JSON 格式）

import json
import logging
import os
from dataclasses import asdict
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PROJECT_VERSION = "1.0"


class ProjectManager:
    """项目文件管理，用于保存和恢复软件工作状态。"""

    def __init__(self) -> None:
        self._current_path: Optional[str] = None
        self._dirty = False

    @property
    def current_path(self) -> Optional[str]:
        """当前打开的项目文件路径，未保存时为 None。"""
        return self._current_path

    def save(self, filepath: str, state: Dict[str, Any]) -> bool:
        """保存项目状态到 .pilotstd 文件（JSON）。"""
        try:
            payload = {
                "version": PROJECT_VERSION,
                "app": "PilotStd",
                "state": self._serialize_state(state),
            }
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._current_path = filepath
            self._dirty = False
            logger.info(f"项目已保存: {filepath}")
            return True
        except OSError as e:
            logger.error(f"保存项目失败: {e}")
            return False

    def load(self, filepath: str) -> Optional[Dict[str, Any]]:
        """从 .pilotstd 文件恢复项目状态。"""
        try:
            if not os.path.exists(filepath):
                return None
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            version = data.get("version", "0")
            if version != PROJECT_VERSION:
                logger.warning(f"项目文件版本不匹配: {version}")
            self._current_path = filepath
            self._dirty = False
            state = data.get("state", {})
            logger.info(f"项目已加载: {filepath}")
            return self._deserialize_state(state)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"加载项目失败: {e}")
            return None

    def mark_dirty(self) -> None:
        self._dirty = True

    # ---- 内部 ----

    @staticmethod
    def _serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
        """将包含 dataclass/普通对象的字典序列化为纯 dict。"""
        result = {}
        for key, value in state.items():
            if hasattr(value, "__dict__"):
                result[key] = asdict(value) if hasattr(value, "__dataclass_fields__") else value.__dict__
            elif isinstance(value, list):
                result[key] = [
                    asdict(v) if hasattr(v, "__dataclass_fields__") else v.__dict__ if hasattr(v, "__dict__") else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    @staticmethod
    def _deserialize_state(data: Dict[str, Any]) -> Dict[str, Any]:
        """反序列化项目状态（当前直接透传，预留未来 dataclass 重建逻辑）。"""
        return data
