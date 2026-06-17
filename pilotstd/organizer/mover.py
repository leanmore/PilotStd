# pilotstd/organizer/mover.py
# 文件移动与规范化：将标准文件归入对应代号目录

import os
import logging
from typing import Optional

from ..core.file_utils import (
    safe_move,
    make_standard_filename,
    truncate_path,
)
from ..models import ParsedStdInfo
from .dir_builder import DirBuilder
from .industry_lookup import get_folder_name

logger = logging.getLogger(__name__)


class FileMover:
    """将标准文件移动到归类的目录结构中。"""

    def __init__(self, dir_builder: DirBuilder):
        self._dirs = dir_builder
        self._library_root = os.path.abspath(dir_builder.root)  # 库根目录绝对路径，用于路径越界校验

    # ── 路径安全校验 ──

    def _is_safe_path(self, target: str) -> bool:
        """校验目标路径在库根目录内，防止路径遍历越界"""
        return os.path.abspath(target).startswith(os.path.abspath(self._library_root) + os.sep)

    # ── 独立步骤：规范化生成路径 ──

    def normalize_filename(self, parsed: ParsedStdInfo) -> str:
        """仅生成规范文件名和目标路径，不移动文件。返回完整目标路径。"""
        folder = get_folder_name(parsed.logical_code)
        filename = make_standard_filename(
            logical_code=parsed.logical_code,
            number=parsed.number,
            year=parsed.year,
            std_name=parsed.std_name,
            part=parsed.part,
            ext=parsed.ext,
            num_suffix=parsed.num_suffix,
            num_prefix=parsed.num_prefix,
            language=parsed.language,
            file_kind=parsed.file_kind,
        )
        return truncate_path(self._dirs.root, folder, filename)

    # ── 独立步骤：仅移动 ──

    def archive(self, src_path: str, dst_path: str) -> Optional[str]:
        """仅执行移动操作，不做重命名。成功返回新路径，失败返回 None。"""
        if safe_move(src_path, dst_path):
            return dst_path
        return None

    # ── 合并步骤（旧接口，保持兼容）──

    def move_to_code_dir(self, src_path: str, parsed: ParsedStdInfo) -> Optional[str]:
        """将文件移动到对应代号目录下，按规范生成文件名。成功返回新路径，失败返回 None。"""
        logger.debug("移动: %s → 代号=%s 号=%s 年=%s",
                     os.path.basename(src_path), parsed.logical_code,
                     parsed.number, parsed.year)
        dst = self.normalize_filename(parsed)
        if not self._is_safe_path(dst):
            logger.error("路径越界被拒绝: %s", dst)
            return None
        return self.archive(src_path, dst)

    def move_to_expire(self, src_path: str, parsed: ParsedStdInfo) -> Optional[str]:
        """将过期文件移动到过期作废子目录。"""
        folder = get_folder_name(parsed.logical_code)
        expire_dir = self._dirs.get_expire_dir(parsed.logical_code)
        basename = os.path.basename(src_path)
        dst = os.path.join(expire_dir, basename)

        if not self._is_safe_path(dst):
            logger.error("路径越界被拒绝: %s", dst)
            return None
        if safe_move(src_path, dst):
            return dst
        return None
