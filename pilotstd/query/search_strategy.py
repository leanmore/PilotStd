# pilotstd/query/search_strategy.py
# 搜索策略 + 查询结果比对

import logging
import re
from typing import Any, List, Tuple

logger = logging.getLogger(__name__)


def build_code_variants(logical_code: str, number: int, year: int, num_prefix: str = "") -> List[str]:
    """按标准类型生成搜索词变体，补充公共回退中缺失的分类标记。
    所有适配器共享，不绑定特定站点。"""
    variants = []
    upper = logical_code.upper().replace("/", "")

    # ASME + 罗马数字前缀 → 追加 BPVC 分类标记
    if upper == "ASME" and num_prefix and re.match(r"^[IVXLCDM]+$", num_prefix):
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


def _parse_result_number(num_str: str) -> dict[str, Any]:
    """从标准编号字符串中提取 代号、顺序号、部分号、年份。
    委托 core.std_utils.parse_std_number()。"""
    from ..core.std_utils import parse_std_number

    r = parse_std_number(num_str)
    return r if r else {}


def _is_code_variant(code1: str, code2: str) -> bool:
    """两个代号是否为变体关系（如 GB ↔ GB/T）。

    仅当两者共享同一基础代号、一个有斜杠后缀一个没有时返回 True。
    例如: GB↔GB/T、GA↔GA/T、SH↔SH/T。
    国外标准无此概念（如 ISO ↔ ISO/T 不存在），不会误匹配。
    """
    if code1 == code2:
        return False

    def _split(c: str) -> tuple[str, str]:
        """拆分代号为 (基础代号, 后缀)，如 'GB/T' → ('GB', 'T')，'GB' → ('GB', '')。"""
        c = c.upper()
        if "/" in c:
            base, suffix = c.split("/", 1)
            return base, suffix
        return c, ""

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


def _exact_parse_match(
    result_number_str: str,
    local_code_clean: str,
    local_code: str,
    local_number: int,
    local_year: int,
    local_part: int | None,
) -> Tuple[bool, str] | None:
    """精确解析路径：解析标准编号后逐字段比对代号、顺序号、年份、部分号。
    返回匹配结果；解析失败时返回 None 以触发模糊回退。"""
    parsed = _parse_result_number(result_number_str)
    if not parsed:
        return None
    code_match = parsed.get("code", "") == local_code_clean
    num_exact = parsed.get("number") == local_number
    result_part = parsed.get("part")
    if local_part is not None and result_part is not None:
        part_match = result_part == local_part
    else:
        part_match = True
    result_year = parsed.get("year")
    if not num_exact:
        return False, "mismatch"
    if not part_match:
        return False, "mismatch"
    code_variant = False
    if not code_match:
        result_raw = parsed.get("raw_code", "")
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


def _fuzzy_text_match(
    result_name: str, result_number_str: str, local_code_clean: str, local_number: int, local_year: int
) -> Tuple[bool, str]:
    """模糊回退：文本中匹配代号、顺序号、年份，数字用词边界避免子串误匹配。"""
    combined = f"{result_name} {result_number_str}".upper()
    code_match = local_code_clean in combined
    num_str = str(local_number)
    num_match = bool(re.search(rf"(?<!\d){re.escape(num_str)}(?!\d)", combined))
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
        return True, "code_only"
    return False, "mismatch"


def match_result(
    local_code: str,
    local_number: int,
    local_year: int,
    result_name: str = "",
    result_number_str: str = "",
    local_part: int | None = None,
) -> Tuple[bool, str]:
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

    exact = _exact_parse_match(result_number_str, local_code_clean, local_code, local_number, local_year, local_part)
    if exact is not None:
        return exact

    return _fuzzy_text_match(result_name, result_number_str, local_code_clean, local_number, local_year)


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
    ("现行", "现行"),
    ("即将实施", "即将实施"),
    ("废止", "废止"),
    ("作废", "废止"),
    ("已废止", "废止"),
    ("未实施", "未实施"),
    ("被代替", "被代替"),
    # 国外标准英文状态映射（njbz365 返回英文，csres 返回中文；两者都覆盖）
    ("Active", "现行"),
    ("active", "现行"),
    ("Withdrawn", "废止"),
    ("withdrawn", "废止"),
    ("Superseded", "被代替"),
    ("superseded", "被代替"),
    ("Obsolete", "废止"),
    ("obsolete", "废止"),
    ("Replaced", "被代替"),
    ("replaced", "被代替"),
    ("Cancelled", "废止"),
    ("cancelled", "废止"),
]


def map_status(text: str) -> str:
    """统一的状态文本映射。"""
    for kw, st in STATUS_MAP:
        if kw in str(text):
            return st
    return str(text) if text else "未知"


def ts_to_date(ts: Any) -> str:
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


# ── 查询调度：按标准类型映射适配器优先级 ────────────────────
# 键 = 标准代号（小写）或 classify_std_code() 分类标签
# 值 = {"primary": 主适配器, "fallback": 兜底适配器}
# 设计目标：动态评分 + 实时负载感知替代固定优先级路由

ADAPTER_TYPE_MAP: dict[str, dict[str, str | list[str] | list[int]]] = {
    # GB 类 → ahbz:std_gov:njbz365:csres = 30:40:25:5 加权分配
    "gb": {
        "chain": ["ahbz", "std_gov", "njbz365", "csres"],
        "weights": [30, 40, 25, 5],
    },
    # 行标类 → hbba 专业平台，njbz365 二线，csres 兜底
    "industry": {"chain": ["hbba", "njbz365", "csres"]},
    # 地标类 → dbba 专业平台
    "db": {"primary": "dbba", "fallback": "csres"},
    "db11": {"primary": "dbba", "fallback": "csres"},
    "db31": {"primary": "dbba", "fallback": "csres"},
    # 国际标准 → iso_gov
    "iso": {"primary": "iso_gov", "fallback": "csres"},
    "iec": {"primary": "iso_gov", "fallback": "csres"},
    "ieee": {"primary": "iso_gov", "fallback": "csres"},
    "iso_iec": {"primary": "iso_gov", "fallback": "csres"},
    # 国外标准 → 通用路由
    "astm": {"primary": "iso_gov", "fallback": "csres"},
    "asme": {"primary": "iso_gov", "fallback": "csres"},
    "api": {"primary": "iso_gov", "fallback": "csres"},
    "foreign": {"primary": "njbz365", "fallback": "ahbz"},
    # 团体标准 → ahbz 专业平台（type=5），njbz365 兜底
    "group": {"primary": "ttbz", "fallback": "ahbz"},
    # 生态环境标准 → mee 官网优先，std_gov 兜底
    "env": {"primary": "mee", "fallback": "std_gov"},
    # 自然资源标准 → nrsis 官网优先，hbba 兜底
    "natural_resources": {"primary": "nrsis", "fallback": "hbba"},
    # 交通运输标准 → jtst 官网优先，std_gov 兜底
    "transport": {"primary": "jtst", "fallback": "std_gov"},
    # 工程建设标准 → ccsn 官网优先，std_gov 兜底
    "construction": {"primary": "ccsn", "fallback": "std_gov"},
    # 计量技术规范 → jjg 官网优先，std_gov 兜底
    "measurement": {"primary": "jjg", "fallback": "std_gov"},
    # 食品安全国家标准 → sppt 官网优先，std_gov 兜底
    "food_safety": {"primary": "sppt", "fallback": "std_gov"},
}


def is_recently_published(pub_date_str: str, window_days: int = 28) -> bool:
    """判断发布时间是否在指定天数内（不满 window_days 天返回 True）。
    用于决定是否允许下载。
    """
    from datetime import datetime, timedelta

    if not pub_date_str:
        return False
    try:
        pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
        return datetime.now() - pub_date < timedelta(days=window_days)
    except (ValueError, TypeError):
        return False
