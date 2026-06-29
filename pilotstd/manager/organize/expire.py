# pilotstd/manager/organize/expire.py
# 过期处理 — 从 organizer_service.py 拆分

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class OrganizerExpireMixin:
    """过期处理方法（混入 OrganizerService）。"""

    def handle_expired(self: Any, parsed_list: list[Any]) -> dict[str, Any]:
        """将查询结果为「废止」的标准移入 过期作废 目录。"""
        pairs = []
        for p in parsed_list:
            src = getattr(p, "source_path", "")
            if src and os.path.isfile(src):
                pairs.append((src, p))
        return self._expire_handler.process_expired(pairs)

    def merge_expire_from_source(self: Any, root_dir: str, parsed_list: list[Any]) -> int:
        """将源目录中的过期作废文件夹合并到标准库对应目录。返回合并文件数。"""
        from ...core.file_utils import safe_move as _safe_move
        from ...organizer.industry_lookup import get_folder_name as _get_folder_name

        expire_folder = self._cfg.get("storage.expire_folder", "过期作废")
        source_dirs = set()
        for parsed in parsed_list:
            src = getattr(parsed, "source_path", "")
            if src and os.path.exists(src):
                source_dirs.add(os.path.dirname(src))
        merged = 0
        for src_dir in source_dirs:
            src_expire = os.path.join(src_dir, expire_folder)
            if not os.path.isdir(src_expire):
                continue
            for parsed in parsed_list:
                src = getattr(parsed, "source_path", "")
                if not src or not src.startswith(src_dir):
                    continue
                folder_name = _get_folder_name(parsed.logical_code)
                tgt_expire = os.path.join(root_dir, folder_name, expire_folder)
                os.makedirs(tgt_expire, exist_ok=True)
                for item in os.listdir(src_expire):
                    src_item = os.path.join(src_expire, item)
                    tgt_item = os.path.join(tgt_expire, item)
                    if os.path.isfile(src_item) and not os.path.exists(tgt_item):
                        try:
                            _safe_move(src_item, tgt_item, on_exists="skip")
                            merged += 1
                        except OSError:
                            pass
                try:
                    if not os.listdir(src_expire):
                        os.rmdir(src_expire)
                except OSError:
                    pass
        return merged
