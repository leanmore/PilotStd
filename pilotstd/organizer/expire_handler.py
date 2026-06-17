# pilotstd/organizer/expire_handler.py
# 过期标准处理：批量扫描并移动过期文件

import os
import logging
from typing import List, Tuple

from ..models import ParsedStdInfo
from .mover import FileMover

logger = logging.getLogger(__name__)


class ExpireHandler:
    """处理过期标准文件的批量移动。"""

    def __init__(self, mover: FileMover):
        self._mover = mover

    def process_expired(self, items: List[Tuple[str, ParsedStdInfo]]) -> dict:
        """批量移动过期文件到 过期作废/ 目录。

        Args:
            items: [(文件完整路径, ParsedStdInfo), ...]

        Returns:
            {"moved": int, "failed": int, "details": [str]}
        """
        result = {"moved": 0, "failed": 0, "details": []}
        for src_path, parsed in items:
            if not os.path.exists(src_path):
                result["failed"] += 1
                result["details"].append(f"文件不存在: {src_path}")
                continue
            dst = self._mover.move_to_expire(src_path, parsed)
            if dst:
                result["moved"] += 1
                result["details"].append(f"{os.path.basename(src_path)} → 过期作废/")
            else:
                result["failed"] += 1
                result["details"].append(f"移动失败: {src_path}")
        return result
