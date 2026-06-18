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
    from ..organizer.industry_lookup import build_code_mapping
    from ..scan.parser import FOREIGN_CODE_SET, ISO_IEC_SET

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
    if re.match(r"^DB\d{2,4}(?:/T)?$", code):
        return "db"

    # 企业标准
    if code == "SG":
        return "enterprise"

    # 团体标准（T/xxx 或其无斜杠形式）
    if code.startswith("T/") or re.match(r"^T[A-Z]{2,}", code):
        return "group"

    # 行业标准：≤4 字符且在 code_mapping 中（含去斜杠形式）
    mapping = build_code_mapping()
    code_no_slash = code.replace("/", "")
    if logical_code in mapping or code in mapping or code_no_slash in mapping:
        return "industry"

    return ""


# ── 标准编号字符串解析（唯一公用入口）────────────────────────────


def parse_std_number(text: str) -> dict | None:
    """从标准编号字符串提取结构化字段。所有场景的编号解析统一入口。

    支持格式:
      'GB/T 22101.1-2026', 'ISO 9001:2015', 'GB 1234-2020',
      'DB35/T 1234-2020', 'IEC 61000-4-2:2008',
      'ASME VIII.1-2021'（罗马数字）, 'API 685-2000',
      'UL 982-2019', 'MSS SP 55-2006'

    Returns:
      {raw_code, code, number, year, part, num_prefix, num_suffix}
      或 None（无法解析）。
    """
    if not text:
        return None
    text = text.strip()

    # 地方标准: DB + 2~4位行政区划代码 + 可选 /T /Z
    m = re.match(
        r"(DB\d{2,4}(?:/[A-Z])?)\s*(\d+)(?:\.(\d+))?\s*?[—\-:\s]\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if m:
        raw = m.group(1).upper()
        return {
            "raw_code": raw,
            "code": raw.replace("/", ""),
            "number": int(m.group(2)),
            "part": int(m.group(3)) if m.group(3) else None,
            "year": int(m.group(4)),
        }

    # 通用格式: 纯字母代号 [+空格+字母前缀] + 序号 + 可选 .p数字/.P数字/.-数字 + 分隔符 + 4位年份
    m = re.match(
        r"([A-Z]+(?:/[A-Z]+)?)\s*(?:([A-Z]+)\s+)?(\d+)(?:\.(\d+))?(?:[Pp](\d+))?\s*[—\-:\s]\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if m:
        raw = m.group(1).upper()
        prefix = m.group(2)
        number = int(m.group(3))
        part = (
            int(m.group(4)) if m.group(4) else (int(m.group(5)) if m.group(5) else None)
        )
        year = int(m.group(6))
        return {
            "raw_code": raw,
            "code": raw.replace("/", ""),
            "number": number,
            "part": part,
            "year": year,
            "num_prefix": prefix if prefix else "",
        }

    # 罗马数字编号: 代号 + 罗马数字（≥2字符，排除单字母前缀误判）+ 可选 .数字 + 年份
    m = re.match(
        r"([A-Z]+)\s+([IVXLCDM]{2,})(?:\.(\d+))?\s*[—\-:\s]\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if m:
        from ..scan.parser import _ROMAN_MAP

        raw = m.group(1).upper()
        roman_str = m.group(2).upper()
        number = _ROMAN_MAP.get(roman_str, 0)
        return {
            "raw_code": raw,
            "code": raw.replace("/", ""),
            "number": number,
            "part": int(m.group(3)) if m.group(3) else None,
            "year": int(m.group(4)),
        }

    # 点号前缀: "ANSI C.81-2003"（CODE PREFIX.NUMBER-YEAR）
    m = re.match(
        r"([A-Z]+)\s+([A-Z]+)\.(\d+)\s*[—\-:\s]\s*(\d{4})", text, re.IGNORECASE
    )
    if m:
        raw = m.group(1).upper()
        return {
            "raw_code": raw,
            "code": raw.replace("/", ""),
            "number": int(m.group(3)),
            "year": int(m.group(4)),
            "num_prefix": m.group(2),
        }

    # 多连字符格式: 代号 + 首段数字 + ... + 最后的4位年份
    m = re.match(r"([A-Z]+)\s*(\d+).*?[—\-:\s](\d{4})$", text, re.IGNORECASE)
    if m:
        raw = m.group(1).upper().replace(" ", "")
        return {
            "raw_code": raw,
            "code": raw.replace("/", ""),
            "number": int(m.group(2)),
            "part": None,
            "year": int(m.group(3)),
        }

    # 兜底: 代号 + 数字（无年份）
    m = re.match(r"([A-Z]+(?:/[A-Z]+)?)\s*(\d+)", text, re.IGNORECASE)
    if m:
        raw = m.group(1).upper()
        return {
            "raw_code": raw,
            "code": raw.replace("/", ""),
            "number": int(m.group(2)),
            "part": None,
            "year": 0,
        }

    return None
