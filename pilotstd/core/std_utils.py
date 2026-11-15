# 项目/核心/_工具脚本—标准代号/编号通用工具函数
"""标准体系通用工具：GB 代号判断、标准号解析等。"""

import re
from typing import Any

GB_CODES: frozenset[Any] = frozenset({"GB", "GB/T", "GB/Z"})
GB_T_CODES: frozenset[Any] = frozenset({"GB/T", "GBT"})
GB_Z_CODES: frozenset[Any] = frozenset({"GB/Z", "GBZ"})
SAMPLE_CODES: frozenset[Any] = frozenset({"GSB"})

# 规范键形态：`CODE number[.part]-year`（可选年份）；用于阻断“空代号 + 前导空格”的畸形键
CANONICAL_KEY_RE = re.compile(r"^\S+ \d+(?:\.\d+)?(?:-\d{4})?$")


def is_canonical_standard_number(key: str) -> bool:
    """是否规范标准号（无前导空格、CODE number[.part]-year 形态）。"""
    return bool(key) and key == key.strip() and bool(CANONICAL_KEY_RE.match(key))


# 合订本残片（OCR/转录）："47008-1947 010-2010" → 起始编号 + 真实年份
_COMBINED_RANGE_RE = re.compile(
    r"(\d{2,5})[-－]((?:19|20)\d{2})\s+(\d{2,5})[-－]((?:19|20)\d{2})"
)
# TSG 字母前缀编号：TSG Z8002-2022（Z 是规则分类前缀，不是代号的一部分）
_TSG_PREFIX_RE = re.compile(r"^TSG\s*([A-Z])?\s*(\d{3,5})\s*[-－]\s*((?:19|20)\d{2})")


def _as_int(value: Any) -> int:
    """宽松转 int：空/非数字返回 0（不用 try/except，避免被 G-050 记为静默吞错）。"""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    return int(text) if text.isdigit() else 0


def build_standard_number(
    logical_code: str, number: Any, part: Any = None, year: Any = None, num_prefix: str = ""
) -> str:
    """拼规范标准号；代号为空/编号非法时返回空串（调用方不得写入 DB）。

    背景（2026-11-15 P2-11 根因）：`_organize` 曾直接 `f"{p.logical_code} {p.number}"`，
    代号为空时写出 `" 11-2020"` 这类畸形键，standard_validity 里累计 7 条且每轮复检都命中。
    """
    code = str(logical_code or "").strip()
    num = _as_int(number)
    if not code or num <= 0:
        return ""
    part_val = _as_int(part)
    suffix = f".{part_val}" if part_val > 0 else ""
    prefix = str(num_prefix or "").strip()
    key = f"{code} {prefix}{num}{suffix}"
    year_val = _as_int(year)
    if year_val > 0:
        key += f"-{year_val}"
    return key


def is_gb_code(code: str) -> bool:
    """判断是否属于 openstd 可检索的 GB 家族（含 GB/T、GB/Z）。"""
    return code in GB_CODES


def is_guiding_technical_document(code: str) -> bool:
    """GB/Z：国家标准化指导性技术文件，不是国家标准。"""
    return code.upper().replace(" ", "") in GB_Z_CODES


def classify_document_type(logical_code: str) -> str:
    """细粒度文档类型：gb / gb_t / gb_z / sample / industry / db / ...。

    与 `classify_std_code` 的区别：后者返回检索/路由用的粗粒度族（GB 家族统一为 gb），
    保留给适配器路由；统计、公告、展示需要区分 GB 与 GB/T、GB/Z 时用本函数。
    """
    code = logical_code.upper().replace(" ", "")
    if is_sample_code(code):
        return "sample"
    if code == "GB":
        return "gb"
    if code in GB_T_CODES:
        return "gb_t"
    if code in GB_Z_CODES:
        return "gb_z"
    return classify_std_code(logical_code)


def is_sample_code(code: str) -> bool:
    """判断是否为国家标准样品编号（GSB 或 NN-NNNN-FNN 形式）。"""
    compact = code.upper().replace(" ", "")
    if compact in SAMPLE_CODES or compact.startswith("GSB"):
        return True
    return bool(re.match(r"^\d{2}-\d{3,5}-[A-Z]\d{1,3}$", compact))


def classify_std_code(logical_code: str) -> str:
    """按标准代号返回分类标签。
    返回值: 'gb' | 'industry' | 'db' | 'iso_iec' | 'foreign' | 'group' | 'enterprise' | ''
    """
    from ..organizer.industry_lookup import build_code_mapping
    from ..scan.parser import FOREIGN_CODE_SET, ISO_IEC_SET

    if not logical_code:
        return ""

    code = logical_code.upper().replace(" ", "")

    # 国家标准样品（GSB / NN-NNNN-FNN）不是 GB/GB/T 标准
    if is_sample_code(code):
        return "sample"

    # 类
    if code in GB_CODES:
        return "gb"

    # 国外标准（必须在/之前检查，避免被误匹配）
    for fc in FOREIGN_CODE_SET:
        fc_norm = fc.upper().replace(" ", "")
        if code.startswith(fc_norm):
            return "foreign"

    # 说明：/
    for iso in ISO_IEC_SET:
        if code.startswith(iso.upper().replace(" ", "")):
            return "iso_iec"

    # 地方标准（数据库+数字）
    if re.match(r"^DB\d{2,4}(?:/T)?$", code):
        return "db"

    # 企业标准
    if code == "SG":
        return "enterprise"

    # 行业标准：≤4字符且在_中（含去斜杠形式）
    # 必须在团体标准检查之前，避免类型脚本等开头行业标准被误判为团体标准
    mapping = build_code_mapping()
    code_no_slash = code.replace("/", "")
    if logical_code in mapping or code in mapping or code_no_slash in mapping:
        return "industry"

    # 团体标准（/或其无斜杠形式）
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

    # 检测多词前缀（如、），避免被正则拆分为+_
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


CODE_WIDTH_TRANS = str.maketrans(
    {
        "\uff0d": "-",
        "\u2014": "-",
        "\u2013": "-",
        "\u2212": "-",
        "\uff0f": "/",
        "\uff1f": "/",
        "\u4e00": "-",  # i18n-allow: 字符归一化表，不是用户文案
        "\u04bb": "-",
        "\u3000": " ",
        # 软连字符与零宽字符：从 PDF/网页复制时常见，肉眼不可见但会让同一标准号不等。
        # 这里映射为空格而**不是删除**，保证 translate 前后长度不变（parser 用
        # normalize_std_code_text 的匹配下标去切原文，长度一变就会截断标准号）。
        "\u00ad": " ",
        "\u200b": " ",
        "\u200c": " ",
        "\u200d": " ",
        "\ufeff": " ",
    }
)

# 标准号 token 的**唯一语法定义**：公告行提取、语义解析、matcher 共用。
STD_CODE_TOKEN_PATTERN = re.compile(
    r"([A-Z][A-Z0-9]*(?:\s+[A-Z][A-Z0-9]*)*(?:/[A-Z0-9]+)*)\s*/?\s*-?\s*(\d+(?:\.\d+)*)\s*[—\-－–−һ﹣‑]\s*(\d{4})"
)


def normalize_std_code_text(text: str) -> str:
    """**长度保持**的字符级归一化（全角/各种破折号/零宽字符 → 半角）。

    专供「先用正则匹配、再用匹配下标回切原文」的解析路径使用：任何删除/压缩空白的
    操作都会让下标错位并截断标准号。比较/入库请用 `normalize_std_code`。
    """
    return str(text).translate(CODE_WIDTH_TRANS)


def normalize_std_code(text: str) -> str:
    """标准号**比较/入库**的唯一归一化实现。

    在长度保持版基础上再消除连接符两侧空格、折叠空白；网页解析、附件解析、合并、
    去重、入库唯一键五处共用。展示层仍保留源站原始写法。
    """
    s = normalize_std_code_text(text)
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def _try_parse_sample_code(text: str) -> dict[str, Any] | None:
    """国家标准样品编号：04-2809-F01-2025 / GSB 03-4369-2025。

    这类编号不是“标准号 + 年份”，通用正则会把 04-2809- 前缀丢掉，只剩 F01-2025。
    """
    s = re.sub(r"\s+", " ", text.strip())
    m = re.match(
        r"^(?:(?P<gsb>GSB)\s+(?P<gcat>\d{2})-(?P<gserial>\d{3,5})"
        r"|(?P<cat>\d{2})-(?P<serial>\d{3,5})-(?P<suffix>[A-Z]\d{1,3}))-\s*(?P<year>\d{4})$",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None
    if m.group("gsb"):
        code = f"GSB {m.group('gcat')}-{m.group('gserial')}"
        return {
            "raw_code": code,
            "code": code,
            "number": int(m.group("gserial")),
            "part": None,
            "year": int(m.group("year")),
            "num_prefix": "",
            "num_suffix": "",
        }
    code = f"{m.group('cat')}-{m.group('serial')}-{m.group('suffix')}"
    return {
        "raw_code": code,
        "code": code,
        "number": int(m.group("serial")),
        "part": None,
        "year": int(m.group("year")),
        "num_prefix": "",
        "num_suffix": m.group("suffix"),
    }


def _try_parse_variant_prefix(text: str) -> dict[str, Any] | None:
    """解析新版公告里常见的变形前缀：DB52T、DB11/、NB/SH/T、SJ/T-、HG/T … 一 …、QB T。"""
    s = re.sub(r"\s+", " ", normalize_std_code_text(text)).strip()
    # DB11/ 2567：尾部斜杠是行政区分隔符，不是“/T”代号段
    s = re.sub(r"^(DB\d{2,4})/\s*(?=\d)", r"\1 ", s)
    # QB T 1750 -> QB/T 1750；只处理“单字母+空格+单字母”的代号段
    s = re.sub(r"([A-Z])\s+([A-Z])(?=[\s/])", r"\1/\2", s)
    s = re.sub(r"\s*/\s*", "/", s)
    m = STD_CODE_TOKEN_PATTERN.match(s)
    if not m:
        return None
    parts = [int(x) for x in m.group(2).split(".")]
    prefix = m.group(1)
    return {
        "raw_code": prefix,
        "code": re.sub(r"\s+", "", prefix).replace("/", ""),
        "number": parts[0],
        "part": parts[1] if len(parts) > 1 else None,
        "year": int(m.group(3)),
        "num_prefix": "",
        "num_suffix": "",
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
    # 合订本残片先归一到"起始编号-真实年份"，避免把 1947 之类残片年份当年份
    text = _COMBINED_RANGE_RE.sub(r"\1-\4 合订本", text)  # i18n-allow: 合订本标识
    tsg = _TSG_PREFIX_RE.match(text)
    if tsg:
        return {
            "raw_code": "TSG",
            "code": "TSG",
            "number": int(tsg.group(2)),
            "year": int(tsg.group(3)),
            "part": None,
            "num_prefix": tsg.group(1) or "",
            "num_suffix": "",
        }

    # 按优先级依次尝试各解析器
    for parser in (
        _try_parse_sample_code,
        _try_parse_variant_prefix,
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
