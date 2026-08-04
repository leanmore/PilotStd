# pilotstd/core/std_utils.py — 标准代号/编号通用工具函数
"""标准体系通用工具：GB 代号判断、标准号解析等。"""

import re
from typing import Any

GB_CODES: frozenset[Any] = frozenset({"GB", "GB/T", "GB/Z", "GSB"})


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

    # 国外标准（必须在 ISO/IEC 之前检查，避免 IEEE 被 IEC startswith 误匹配）
    for fc in FOREIGN_CODE_SET:
        fc_norm = fc.upper().replace(" ", "")
        if code.startswith(fc_norm):
            return "foreign"

    # 说明：ISO/IEC
    for iso in ISO_IEC_SET:
        if code.startswith(iso.upper().replace(" ", "")):
            return "iso_iec"

    # 地方标准（DB + 数字）
    if re.match(r"^DB\d{2,4}(?:/T)?$", code):
        return "db"

    # 企业标准
    if code == "SG":
        return "enterprise"

    # 行业标准：≤4 字符且在 code_mapping 中（含去斜杠形式）
    # 必须在团体标准检查之前，避免 TSG 等 T 开头行业标准被误判为团体标准
    mapping = build_code_mapping()
    code_no_slash = code.replace("/", "")
    if logical_code in mapping or code in mapping or code_no_slash in mapping:
        return "industry"

    # 团体标准（T/xxx 或其无斜杠形式）
    if code.startswith("T/") or re.match(r"^T[A-Z]{2,}", code):
        return "group"

    return ""


# ── 标准编号字符串解析（唯一公用入口）────────────────────────────


def _try_parse_db_standard(text: str) -> dict[str, Any] | None:
    """尝试按地方标准格式解析: DB + 2~4位行政区划代码 + 可选 /T /Z。"""
    m = re.match(
        r"(DB\d{2,4}(?:/[A-Z])?)\s*(\d+)(?:\.(\d+))?\s*?[—\-:\s]\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    raw = m.group(1).upper()
    return {
        "raw_code": raw,
        "code": raw.replace("/", ""),
        "number": int(m.group(2)),
        "part": int(m.group(3)) if m.group(3) else None,
        "year": int(m.group(4)),
    }


def _try_parse_general_format(text: str) -> dict[str, Any] | None:
    """尝试按通用格式解析: 纯字母代号 + 序号 + 可选 .数字/.P数字 + 分隔符 + 4位年份。"""
    from ..scan.parser._constants import PRESERVED_MULTI_WORD

    # 检测多词前缀（如 DIN EN、BS EN ISO），避免被正则拆分为 code + num_prefix
    text_upper = text.upper()
    multi_word_code = ""
    for mw in sorted(PRESERVED_MULTI_WORD, key=len, reverse=True):
        if text_upper.startswith(mw + " ") or text_upper.startswith(mw + ".") or text_upper.startswith(mw + "-"):
            multi_word_code = mw
            break

    if multi_word_code:
        remainder = text[len(multi_word_code) :].strip()
        m = re.match(
            r"(\d+)(?:\.(\d+))?(?:[Pp](\d+))?\s*[—\-:\s]\s*(\d{4})",
            remainder,
            re.IGNORECASE,
        )
        if not m:
            return None
        raw = multi_word_code.upper()
        return {
            "raw_code": raw,
            "code": raw.replace("/", "").replace(" ", ""),
            "number": int(m.group(1)),
            "part": int(m.group(2)) if m.group(2) else (int(m.group(3)) if m.group(3) else None),
            "year": int(m.group(4)),
            "num_prefix": "",
        }

    m = re.match(
        r"([A-Z]+(?:/[A-Z]+)?)\s*(?:([A-Z]+)\s+)?(\d+)(?:\.(\d+))?(?:[Pp](\d+))?\s*[—\-:\s]\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    raw = m.group(1).upper()
    prefix = m.group(2)
    number = int(m.group(3))
    part = int(m.group(4)) if m.group(4) else (int(m.group(5)) if m.group(5) else None)
    year = int(m.group(6))
    return {
        "raw_code": raw,
        "code": raw.replace("/", ""),
        "number": number,
        "part": part,
        "year": year,
        "num_prefix": prefix if prefix else "",
    }


def _try_parse_roman(text: str) -> dict[str, Any] | None:
    """尝试按罗马数字编号格式解析: 代号 + 罗马数字（≥2字符） + 可选 .数字 + 年份。"""
    m = re.match(
        r"([A-Z]+)\s+([IVXLCDM]{2,})(?:\.(\d+))?\s*[—\-:\s]\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
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


def _try_parse_dot_prefix(text: str) -> dict[str, Any] | None:
    """尝试按点号前缀格式解析: ANSI C.81-2003（CODE PREFIX.NUMBER-YEAR）。"""
    m = re.match(r"([A-Z]+)\s+([A-Z]+)\.(\d+)\s*[—\-:\s]\s*(\d{4})", text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).upper()
    return {
        "raw_code": raw,
        "code": raw.replace("/", ""),
        "number": int(m.group(3)),
        "year": int(m.group(4)),
        "num_prefix": m.group(2),
    }


def _try_parse_multi_hyphen(text: str) -> dict[str, Any] | None:
    """尝试按多连字符格式解析: 代号 + 首段数字 + ... + 最后的4位年份。"""
    m = re.match(r"([A-Z]+)\s*(\d+).*?[—\-:\s](\d{4})$", text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).upper().replace(" ", "")
    return {
        "raw_code": raw,
        "code": raw.replace("/", ""),
        "number": int(m.group(2)),
        "part": None,
        "year": int(m.group(3)),
    }


def _try_parse_fallback(text: str) -> dict[str, Any] | None:
    """兜底解析: 代号 + 数字（无年份）。"""
    m = re.match(r"([A-Z]+(?:/[A-Z]+)?)\s*(\d+)", text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).upper()
    return {
        "raw_code": raw,
        "code": raw.replace("/", ""),
        "number": int(m.group(2)),
        "part": None,
        "year": 0,
    }


def parse_std_number(text: str) -> dict[str, Any] | None:
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

    # 按优先级依次尝试各解析器
    for parser in (
        _try_parse_db_standard,
        _try_parse_general_format,
        _try_parse_roman,
        _try_parse_dot_prefix,
        _try_parse_multi_hyphen,
        _try_parse_fallback,
    ):
        result = parser(text)
        if result is not None:
            return result

    return None
