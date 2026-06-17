# pilotstd/core/std_utils.py — 标准代号/编号通用工具函数
"""标准体系通用工具：GB 代号判断、标准号解析等。"""

import re

GB_CODES: frozenset = frozenset({"GB", "GB/T", "GB/Z", "GSB"})


def is_gb_code(code: str) -> bool:
    """判断标准代号是否为 GB 类（openstd 可下载）。"""
    return code in GB_CODES


def classify_std_code(logical_code: str) -> str:
    """按标准代号返回分类标签。
    返回值: 'gb' | 'industry' | 'db' | 'iso_iec' | 'foreign' | 'group' | 'enterprise' | ''
    """
    from ..scan.parser import FOREIGN_CODE_SET, ISO_IEC_SET
    from ..organizer.industry_lookup import build_code_mapping

    if not logical_code:
        return ""

    code = logical_code.upper().replace(" ", "")

    # GB 类
    if code in GB_CODES:
        return "gb"

    # ISO/IEC
    for iso in ISO_IEC_SET:
        if code.startswith(iso.upper().replace(" ", "")):
            return "iso_iec"

    # 国外标准
    for fc in FOREIGN_CODE_SET:
        fc_norm = fc.upper().replace(" ", "")
        if code.startswith(fc_norm):
            return "foreign"

    # 地方标准（DB + 数字）
    if re.match(r'^DB\d{2,4}(?:/T)?$', code):
        return "db"

    # 企业标准
    if code == "SG":
        return "enterprise"

    # 团体标准（T/xxx 或其无斜杠形式）
    if code.startswith("T/") or re.match(r'^T[A-Z]{2,}', code):
        return "group"

    # 行业标准：≤4 字符且在 code_mapping 中（含去斜杠形式）
    mapping = build_code_mapping()
    code_no_slash = code.replace("/", "")
    if logical_code in mapping or code in mapping or code_no_slash in mapping:
        return "industry"

    return ""
