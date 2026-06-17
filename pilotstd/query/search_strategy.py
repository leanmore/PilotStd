# pilotstd/query/search_strategy.py
# 渐进式搜索策略 + 查询结果比对

import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def build_search_terms(logical_code: str, number: int, year: int,
                       std_name: str = "", part: int = None,
                       num_prefix: str = "", num_suffix: str = "") -> List[str]:
    """根据标准信息生成逐级搜索词列表。代号保留 /（如 GB/T）用于网站查询。

    优先级（从窄到宽）：
    1. {代号} {num_prefix}{顺序号}{num_suffix}[.{部分号}] {年份}        — 最精确
    2. {代号} {num_prefix}{顺序号}{num_suffix}[.{部分号}]               — 去掉年份
    3. {代号} {num_prefix}{顺序号}{num_suffix} {年份}                   — 去掉部分号
    4. {num_prefix}{顺序号}{num_suffix}                                 — 纯编号兜底
    5. {代号} {num_prefix}{顺序号}{num_suffix}[.{部分号}] {年份} {名称关键词} — 最后用名称
    """
    terms = []
    code = logical_code
    # num_prefix 前置到顺序号前（如 ASME B16.5, API RP14）
    # 罗马数字卷号（ASME IX/VIII）例外：num_prefix 本身就是编号，不与 number 拼接
    if num_prefix and re.match(r'^[IVXLCDM]+$', num_prefix):
        num_str = num_prefix
    else:
        num_str = f"{num_prefix}{number}" if num_prefix else str(number)
    num_str = f"{num_str}{num_suffix}"
    part_str = f".{part}" if part else ""

    # ① 代号 + 编号[.部分号] + 年份（最精确）
    terms.append(f"{code} {num_str}{part_str} {year}")

    # ② 去年份
    terms.append(f"{code} {num_str}{part_str}")

    # ③ 去部分号（保留年份）——仅在 part 或 num_prefix/non-empty 时生成
    if part or num_prefix:
        terms.append(f"{code} {num_str} {year}")

    # ④ 去年份 + 去部分号
    if part or num_prefix:
        terms.append(f"{code} {num_str}")

    # ⑤ 纯编号兜底（含 num_prefix/num_suffix）
    terms.append(num_str)

    # ⑥ 加上名称关键词（最后手段）
    if std_name:
        keywords = _extract_keywords(std_name)
        if keywords:
            kw_str = " ".join(keywords[:3])
            terms.append(f"{code} {number}{part_str} {year} {kw_str}")

    # 去重保持顺序
    seen = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def build_code_variants(logical_code: str, number: int, year: int,
                        num_prefix: str = "") -> List[str]:
    """按标准类型生成搜索词变体，补充公共回退中缺失的分类标记。
    所有适配器共享，不绑定特定站点。"""
    variants = []
    upper = logical_code.upper().replace('/', '')

    # ASME + 罗马数字前缀 → 追加 BPVC 分类标记
    if upper == "ASME" and num_prefix and re.match(r'^[IVXLCDM]+$', num_prefix):
        variants.append(f"ASME BPVC {num_prefix}.{number}-{year}")
        variants.append(f"ASME BPVC {num_prefix}.{number}")
        variants.append(f"ASME BPVC {num_prefix}-{year}")

    # API → 追加 Std / Spec 出版类型前缀
    if upper == "API":
        variants.append(f"API Std {number}-{year}")
        variants.append(f"API Spec {number}-{year}")

    # DIN（非 EN 前缀）→ 追加 DIN EN 变体
    if upper == "DIN" and "EN" not in logical_code.upper():
        variants.append(f"DIN EN {number}-{year}")

    return variants


def _extract_keywords(name: str) -> List[str]:
    """从标准名称中提取关键搜索词。"""
    stop_words = {"标准", "规范", "技术", "通用", "方法", "试验", "测试",
                  "要求", "规程", "规则", "条件", "安全", "管理", "体系",
                  "第", "部分", "的", "及", "与", "和", "及其", "之一"}
    words = re.findall(r"[一-鿿\w]+", name)
    return [w for w in words if w not in stop_words and len(w) >= 2][:5]


def _parse_result_number(num_str: str) -> dict:
    """从标准编号字符串中提取 代号、顺序号、部分号、年份。
    支持格式: 'GB/T 22101.1-2026', 'ISO 9001:2015', 'GB 1234-2020',
             'DB35/T 1234-2020', 'IEC 61000-4-2:2008' 等。"""
    if not num_str:
        return {}
    text = num_str.strip()

    # 地方标准：DB + 2~4位行政区划代码 + 可选 /T /Z
    m = re.match(
        r'(DB\d{2,4}(?:/[A-Z])?)\s*(\d+)(?:\.(\d+))?\s*?[—\-:\s]\s*(\d{4})',
        text, re.IGNORECASE)
    if m:
        raw = m.group(1).upper()
        return {
            'raw_code': raw, 'code': raw.replace('/', ''),
            'number': int(m.group(2)),
            'part': int(m.group(3)) if m.group(3) else None,
            'year': int(m.group(4)),
        }

    # 通用格式：纯字母代号 + 序号 + 可选 .部分号 + 分隔符 + 4位年份
    m = re.match(
        r'([A-Z]+(?:/[A-Z]+)?)\s*(\d+)(?:\.(\d+))?\s*?[—\-:\s]\s*(\d{4})',
        text, re.IGNORECASE)
    if m:
        raw = m.group(1).upper()
        return {
            'raw_code': raw, 'code': raw.replace('/', ''),
            'number': int(m.group(2)),
            'part': int(m.group(3)) if m.group(3) else None,
            'year': int(m.group(4)),
        }

    # 罗马数字编号（ASME VIII.1-2021 等）：代号 + 空格 + 罗马数字 + 可选 .数字 + 年份
    m = re.match(
        r'([A-Z]+)\s+([IVXLCDM]+)(?:\.(\d+))?\s*[—\-:\s]\s*(\d{4})',
        text, re.IGNORECASE)
    if m:
        from ..scan.parser import _ROMAN_MAP
        raw = m.group(1).upper()
        roman_str = m.group(2).upper()
        number = _ROMAN_MAP.get(roman_str)
        if number is None:
            number = 0
        part = int(m.group(3)) if m.group(3) else None
        return {
            'raw_code': raw, 'code': raw.replace('/', ''),
            'number': number,
            'part': part,
            'year': int(m.group(4)),
        }

    # 多连字符格式（IEC 61000-4-2:2008 等）：代号 + 首段数字 + 最后的4位年份
    m = re.match(
        r'([A-Z]+)\s*(\d+).*?[—\-:\s](\d{4})$',
        text, re.IGNORECASE)
    if m:
        raw = m.group(1).upper().replace(' ', '')
        return {
            'raw_code': raw, 'code': raw.replace('/', ''),
            'number': int(m.group(2)),
            'part': None,
            'year': int(m.group(3)),
        }

    # 兜底：代号 + 数字（无年份）
    m = re.match(r'([A-Z]+(?:/[A-Z]+)?)\s*(\d+)', text, re.IGNORECASE)
    if m:
        raw = m.group(1).upper()
        return {
            'raw_code': raw, 'code': raw.replace('/', ''),
            'number': int(m.group(2)),
            'part': None, 'year': 0,
        }
    return {}


def _is_code_variant(code1: str, code2: str) -> bool:
    """两个代号是否为变体关系（如 GB ↔ GB/T）。

    仅当两者共享同一基础代号、一个有斜杠后缀一个没有时返回 True。
    例如: GB↔GB/T、GA↔GA/T、SH↔SH/T。
    国外标准无此概念（如 ISO ↔ ISO/T 不存在），不会误匹配。
    """
    if code1 == code2:
        return False
    def _split(c: str):
        c = c.upper()
        if '/' in c:
            base, suffix = c.split('/', 1)
            return base, suffix
        return c, ''
    b1, s1 = _split(code1)
    b2, s2 = _split(code2)
    return b1 == b2 and bool(s1) != bool(s2)


# ── 前缀变体 ────────────────────────────────────────────────

# 存在推荐性/强制性变体关系的代号对（2017年1077项 GB→GB/T 转换公告）
_VARIANT_PAIRS = [
    ("GB", "GB/T"),
    ("GA", "GA/T"),
    ("SH", "SH/T"),
]


def build_code_variant(search_term: str) -> str:
    """生成代号变体搜索词。GB/T→GB、GA/T→GA、SH/T→SH，反之亦然。

    对国外标准（ISO/IEC/BS/DIN 等无 /T 变体体系）返回空字符串。
    用于查询和下载阶段的前缀回退——openstd 对转换标准收录代号不一致。
    """
    term = search_term.strip()
    # 提取搜索词开头的代号部分（如 "GB/T 3836.14 2014" → "GB/T"）
    m = re.match(r'([A-Z]+(?:/[A-Z]+)?)\s', term)
    if not m:
        return ""
    code = m.group(1).upper()
    for a, b in _VARIANT_PAIRS:
        if code == a:
            return term.replace(a, b, 1)
        if code == b:
            return term.replace(b, a, 1)
    return ""




def match_result(local_code: str, local_number: int, local_year: int,
                 result_name: str = "", result_number_str: str = "",
                 local_part: int = None) -> Tuple[bool, str]:
    """将网站返回结果与本地解析信息比对，优先解析标准编号精确对比。

    返回 (是否匹配, 匹配状态):
        "exact"     — 代号、顺序号、年份全部一致（含部分号）
        "newer"     — 代号和顺序号一致，年份更新
        "older"     — 代号和顺序号一致，年份更早
        "code_only" — 仅代号匹配
        "mismatch"  — 都不匹配

    当本地与结果代号为变体关系（如 GB ↔ GB/T）且顺序号一致时，
    视为代号匹配，纳入 exact/newer/older 正常评分。
    """
    if not result_name and not result_number_str:
        return False, "mismatch"

    local_code_clean = local_code.replace("/", "").upper()

    # 优先精确解析标准编号
    parsed = _parse_result_number(result_number_str)
    if parsed:
        code_match = parsed.get('code', '') == local_code_clean
        num_exact = parsed.get('number') == local_number
        result_part = parsed.get('part')
        if local_part is not None and result_part is not None:
            part_match = result_part == local_part
        else:
            part_match = True
        result_year = parsed.get('year')

        if not num_exact:
            return False, "mismatch"
        # 部分号不匹配 → 不同标准（如 GB 30000.3 vs GB 30000.30）
        if not part_match:
            return False, "mismatch"

        # 代号变体检测：同一基础代号，一个有后缀（/T /Z 等）一个没有
        # 如 GB ↔ GB/T、GA ↔ GA/T 等。仅当顺序号一致时才触发（num_exact 已保证）
        code_variant = False
        if not code_match:
            result_raw = parsed.get('raw_code', '')
            local_upper = local_code.upper()
            if result_raw and _is_code_variant(local_upper, result_raw):
                code_variant = True

        if code_match or code_variant:
            if result_year and result_year == local_year:
                return True, "exact"
            if result_year and result_year > local_year:
                return True, "newer"
            if result_year and result_year < local_year:
                return True, "older"
            return True, "exact"
        return (True, "code_only") if code_match else (False, "mismatch")

    # 回退：文本模糊匹配（数字用词边界避免子串误匹配）
    combined = f"{result_name} {result_number_str}".upper()
    code_match = local_code_clean in combined
    num_str = str(local_number)
    num_match = bool(re.search(rf'(?<!\d){re.escape(num_str)}(?!\d)', combined))
    year_str = str(local_year)
    year_match = year_str in combined

    if code_match and num_match and year_match:
        return True, "exact"
    if code_match and num_match:
        years_in_result = re.findall(r"\b(19\d{2}|20\d{2})\b", combined)
        if years_in_result:
            result_year = max(int(y) for y in years_in_result)
            if result_year > local_year:
                return True, "newer"
            elif result_year < local_year:
                return True, "older"
        return True, "exact"
    if code_match:
        return (True, "code_only") if code_match else (False, "mismatch")

    return False, "mismatch"


# ── 共享工具函数 ────────────────────────────────────────────

MATCH_SCORE = {
    "exact": 100,
    "newer": 80,
    "older": 50,
    "code_only": 20,
    "mismatch": 0,
}
# 别名，main_window 两处引用使用不同名称
CONFIDENCE_SCORE = MATCH_SCORE

# 匹配分数阈值：代号+编号确认（等同号或新版号），达到此分数即可停止宽搜
MATCH_SCORE_CONFIRMED = 50
# 低于此分数标记为"待确认"，高于此分数视为高置信度
MATCH_SCORE_HIGH_CONFIDENCE = 80

STATUS_MAP = [
    ("现行", "现行"), ("即将实施", "即将实施"),
    ("废止", "废止"), ("作废", "废止"),
    ("已废止", "废止"), ("未实施", "未实施"),
    ("被代替", "被代替"),
    # 国外标准英文状态映射（njbz365 返回英文，csres 返回中文；两者都覆盖）
    ("Active", "现行"), ("active", "现行"),
    ("Withdrawn", "废止"), ("withdrawn", "废止"),
    ("Superseded", "被代替"), ("superseded", "被代替"),
    ("Obsolete", "废止"), ("obsolete", "废止"),
    ("Replaced", "被代替"), ("replaced", "被代替"),
    ("Cancelled", "废止"), ("cancelled", "废止"),
]


def map_status(text: str) -> str:
    """统一的状态文本映射。"""
    for kw, st in STATUS_MAP:
        if kw in str(text):
            return st
    return str(text) if text else "未知"


def ts_to_date(ts) -> str:
    """毫秒时间戳 → 日期字符串。"""
    from datetime import datetime
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return ""


ADOPTION_KW = ["ISO", "IEC", "IDT", "MOD", "EQV", "采标", "采用"]


def is_adopted(name: str, en_name: str = "") -> bool:
    """统一的采标判定：中文名 + 英文名中匹配采标关键词。"""
    text = f"{name} {en_name}"
    return any(kw in text for kw in ADOPTION_KW)
