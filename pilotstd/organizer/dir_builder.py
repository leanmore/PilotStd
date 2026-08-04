# 模块：pilotstd/organizer/dir_builder.py
# 目录结构生成：{root}/{基础代号} {行业名称}/{过期作废}/

import logging
import os

from ..core.file_utils import ensure_dir
from .industry_lookup import get_folder_name

logger = logging.getLogger(__name__)


class DirBuilder:
    """按标准代号生成归类目录结构。"""

    def __init__(self, root_dir: str, expire_dir_name: str = "过期作废"):
        self._root = ensure_dir(root_dir)
        self._expire_name = expire_dir_name

    def ensure_code_dir(self, logical_code: str) -> str:
        """确保某文件代号对应的第二层目录存在，返回其路径。"""
        folder = get_folder_name(logical_code)
        return ensure_dir(os.path.join(self._root, folder))

    def ensure_expire_dir(self, logical_code: str) -> str:
        """确保某文件代号的过期作废子目录存在。"""
        code_dir = self.ensure_code_dir(logical_code)
        return ensure_dir(os.path.join(code_dir, self._expire_name))

    def get_expire_dir(self, logical_code: str) -> str:
        """返回指定代号的过期作废子目录路径（不保证目录存在）。"""
        code_dir = self.ensure_code_dir(logical_code)
        return os.path.join(code_dir, self._expire_name)

    @property
    def root(self) -> str:
        return self._root
