# 模块：pilotstd/scan/parser/_constants.py
# 标准解析器常量 — 正则模式 + 查询表
"""正则原子构件、代号集合、分组路由表。"""

import re

from ..edition_detect import edition_skip_pattern
from ..lang_detect import detect_language

# 需保留的多段前缀（不拆分首段）
PRESERVED_MULTI_WORD = frozenset(
    {
        "BS EN",
        "BS EN ISO",
        "DIN EN",
        "DIN EN ISO",
        "NF EN",
        # IEC 类型前缀（不可被 _normalize_prefix 拆分）
        "IEC TR",
        "IEC TS",
        "IEC PAS",
        # 国外标准代号+分类字母（不可拆分）
        "ASTM A",
        "ASTM B",
        "ASTM C",
        "ASTM D",
        "ASTM E",
        "ASTM F",
        "ASTM G",
        "JIS A",
        "JIS B",
        "JIS C",
        "JIS D",
        "JIS E",
        "JIS F",
        "JIS G",
        "JIS H",
        "JIS K",
        "JIS L",
        "JIS M",
        "JIS P",
        "JIS Q",
        "JIS R",
        "JIS S",
        "JIS T",
        "JIS W",
        "JIS X",
        "JIS Z",
        "CSA C",
        "CSA Z",
        "NF C",
        "NF L",
        "NF Z",
        "AWWA B",
        "AWWA C",
        "AWWA D",
        "AWWA E",
        "AWWA F",
        "AWWA G",
    }
)
# ── 国外代号集合 ────────────────────────────────────────────
FOREIGN_CODE_SET = frozenset(
    {
        "API",
        "ANSI",
        "AS",
        "ASME",
        "ASTM",
        "AWWA",
        "BS",
        "CAC",
        "CSA",
        "DIN",
        "EN",
        "GOST",
        "IEEE",
        "ITU",
        "JIS",
        "KS",
        "MIL",
        "MSS",
        "NF",
        "NFPA",
        "SAE",
        "SANS",
        "UL",
        "UNE",
    }
)
# ISO/IEC 单独处理（冒号年份+类型前缀）
ISO_IEC_SET = frozenset({"ISO", "IEC"})
# ITU 系列代码（ITU-T 等）
ITU_CODES = frozenset({"ITU-T", "ITU-R", "ITU-D"})
# CAC 多前缀
CAC_PREFIXES = frozenset({"Codex Stan", "CXS", "CXA", "CXP", "CXG", "CAC"})
# API 类型前缀（含 Bull/Publ/TR 等文档类型）
API_TYPES = frozenset({"Spec", "Std", "RP", "MPMS", "Bull", "Publ", "TR", "TDB"})
# IEC 类型前缀
IEC_TYPES = frozenset({"TR", "TS", "PAS"})
# MIL 类型
MIL_TYPES = frozenset({"STD", "DTL", "HDBK", "PRF"})
# SAE 技术前缀
SAE_PREFIXES = frozenset({"J", "ARP", "AMS"})
# ASME BPVC 罗马数字卷号映射（不转换，仅用于 number 排序值）
_ROMAN_MAP = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
}
_ASME_BPVC_RE = re.compile(
    r"^ASME\s+(?:BPVC[\.\-\s]*)?"  # BPVC 可选（兼容 ASME IX-2021）
    r"([IVXLCDM]+)"  # 卷号（罗马数字）
    r"(?:[\.\-](\d{1,2})(?=[\-]\d{4}))?"  # 子分册（仅当后面还有-年份时匹配）
    r"(?:[\-](\d{4}))?",  # 年份（4位数字）
    re.IGNORECASE,
)

# ── 正则原子构件 ────────────────────────────────────────────
_PFX = r"(?P<prefix>(?:ITU-[TRD])|[A-Z]{2,}(?:[\-\s]+[A-Z]{2,})*(?:/[A-Z]+)?)"  # 标准代号段（如 "BS EN", "ITU-T", "ANSI/UL"）  # noqa: E501
_NUM = r"(?P<number>[A-Z]?\d{1,6}[A-Z]?)"  # 编号（支持字母后缀如 API 6D）
_PART_SHORT = r"(?:[\.\-](?P<part>\d{1,2}))?"  # 短分册号（1-2位纯数字）
_PART_LONG = r"(?:[\.\-](?P<part>[A-Z]?\d{1,3}))?"  # 长分册号（可含前导字母，如 B16）
_YEAR4 = r"(?P<year>(?:19|20)\d{2})"  # 四位年份
_YEAR_LOOSE = r"(?P<year>(?:19|20)\d{2}|\d{2})"  # 宽年份（兼容两位年份）
_YEAR_DB = r"(?:[\-]?(?P<year>(?:19|20)\d{2}))"  # 地方标准年份（必需）
_SEP = r"[\s\.\-\+]{0,10}"  # 分隔符（限制最大10字符防回溯爆炸）
_SEP_LAZY = r"[\s\.\-\+]*?"  # 懒惰分隔符
# 版次跳过：N版 / 第N版 / Nth Edition / TENTH EDITION（来自 edition_detect 模块）
_EDITION_SKIP = edition_skip_pattern()
# endorser + type 前缀（regex_typed 系列共用）
_ENDORSER = r"(?:/(?P<endorser>[A-Z]{2,}))?"  # 背书者（如 ANSI/UL）
_TYPE = r"(?:(?P<type>[A-Z]{2,})(?:\s+|\-))?"  # 类型前缀（如 API Spec）


def _compile(*parts: str) -> re.Pattern[str]:
    """组装正则原子构件为编译后的 Pattern。"""
    return re.compile("".join(parts), re.IGNORECASE)


# 语言版本标记识别 — 委托 lang_detect 模块（parser + 归档规则共用）
_LANG_DETECTOR = detect_language  # 函数引用，保持向后兼容

# 国外代号→分组路由（6组）
_FOREIGN_GROUP_MAP = {
    # 组1: 纯序号型 — 无需后处理，正则可正确提取全部字段
    "UL": "pure_numeric",
    "AS": "pure_numeric",
    "KS": "pure_numeric",
    "SANS": "pure_numeric",
    "UNE": "pure_numeric",
    "IEEE": "pure_numeric",
    "NFPA": "pure_numeric",
    # 组2: 字母分类型 — 从 raw 提取分类字母 → num_prefix
    "ASTM": "letter_class",
    "JIS": "letter_class",
    "CSA": "letter_class",
    "AWWA": "letter_class",
    "NF": "letter_class",
    # 组3: 类型前缀型 — 从 raw 提取类型标识 → num_prefix
    "API": "type_prefix",
    "MIL": "type_prefix",
    "SAE": "type_prefix",
    "MSS": "type_prefix",
    "IEC": "type_prefix",
    # 组4: 多段前缀型 — PRESERVED_MULTI_WORD 已保留，无需后处理
    "BS": "multi_prefix",
    "DIN": "multi_prefix",
    "EN": "multi_prefix",
    # 组5: 特殊分隔符型 — GOST(点号) + ASME(BPVC罗马数字)
    "GOST": "special_sep",
    "ASME": "special_sep",
    # 组6: 独特体系 — 各一个 mini-handler
    "ANSI": "unique",
    "CAC": "unique",
    "ITU": "unique",
}
