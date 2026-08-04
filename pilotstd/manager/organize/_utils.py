# 模块：pilotstd/manager/organize/_utils.py
# 静态工具函数 — 从 organizer_service.py 拆分

import os

from ...organizer.industry_lookup import (
    FOREIGN_CODES,
    INDUSTRY_MAP,
    NATIONAL_CODES,
    get_folder_name,
    is_db_code,
)


def _is_word_or_template(src_path: str) -> bool:
    """通过扩展名判断是否为 Word/模板文件"""
    return src_path.lower().endswith((".doc", ".docx"))


def _resolve_industry_in_path(rel_path: str) -> str:
    """解析相对路径第一段中的行业代号为完整目录名。"""
    if not rel_path:
        return rel_path
    parts = rel_path.split(os.sep, 1)
    first = parts[0]
    if first in INDUSTRY_MAP or first in NATIONAL_CODES or first in FOREIGN_CODES or is_db_code(first):
        resolved = get_folder_name(first)
        if resolved != first:
            return os.path.join(resolved, parts[1]) if len(parts) > 1 else resolved
    return rel_path
