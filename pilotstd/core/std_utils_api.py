# 模块：项目/核心/_工具脚本/API 类型词解析
"""API 类型词/系列词编号解析（P1-7.1 B-6；批次10 B-8 扩展后缀与联合标准）。

从 `std_utils.py` 拆出（G-010 代码规模门禁：std_utils.py 需 ≤400 有效行）。
`parse_std_number` 的解析链在 ASME 系列分支之后调用 `_try_parse_api_typed`，
统一处理 API 的「类型词 + 序号 + 字母后缀 + 分册 + 年份」：

- 类型词（STD/SPEC/RP/MPMS/BULL/PUBL/TR/TDB/Q）不属于代号 → `num_prefix`；
- 字母后缀可多段：`6D` / `5CT` / `2A-WSD` / `938-C`（修复前只允许 1 个尾字母且不认连字符）；
- 分册：`579-1` / `MPMS 11.1`；
- 联合标准只取主标准：`API 579-1/ASME FFS-1` → `part=1`；
- 版次（`11th` / `11th Edition`）不是年份 → `year=0`。
"""

import re
from typing import Any

# 类型词全表（与 `pilotstd/scan/parser/_constants.py:API_TYPES` 同一集合口径 + 质量体系 `Q`）。
_API_TYPE_WORDS = frozenset({"STD", "SPEC", "RP", "MPMS", "BULL", "PUBL", "TR", "TDB", "Q"})

_API_HEAD_RE = re.compile(r"^API\s+", re.IGNORECASE)
_API_BODY_RE = re.compile(
    r"^(?:(?P<type>[A-Za-z]{1,4})\s*)?(?P<number>\d{1,6})(?P<tail>.*)$"
)
_EDITION_TAIL_RE = re.compile(r"-?\s*\d{1,2}\s*(?:st|nd|rd|th)\s*(?:Edition)?", re.IGNORECASE)
_YEAR_TAIL_RE = re.compile(r"^-((?:19|20)\d{2})$")
_PART_DOT_TAIL_RE = re.compile(r"^\.(\d{1,3})$")
_SUFFIX_YEAR_TAIL_RE = re.compile(r"^([A-Z]{1,4}(?:-[A-Z]{1,4})*)(?:-((?:19|20)\d{2}))?$")
_SUFFIX_TAIL_RE = re.compile(r"^-([A-Z]{1,4}(?:-[A-Z]{1,4})*)$")
_PART_HYPHEN_TAIL_RE = re.compile(r"^-(\d{1,3})$")


def _triple(tail: str) -> tuple[str, int | None, int] | None:
    """拆 `tail`（序号之后的部分）为 (后缀, 分册号, 年份)；无法归类返回 None。"""
    if _EDITION_TAIL_RE.fullmatch(tail):
        return "", None, 0
    m = _YEAR_TAIL_RE.fullmatch(tail)
    if m:
        return "", None, int(m.group(1))
    m = _PART_DOT_TAIL_RE.fullmatch(tail)
    if m:
        return "", int(m.group(1)), 0
    m = _SUFFIX_YEAR_TAIL_RE.fullmatch(tail)
    if m:
        return m.group(1), None, int(m.group(2)) if m.group(2) else 0
    m = _SUFFIX_TAIL_RE.fullmatch(tail)
    if m:
        return m.group(1), None, 0
    m = _PART_HYPHEN_TAIL_RE.fullmatch(tail)
    if m:
        return "", int(m.group(1)), 0
    return None


def _try_parse_api_typed(text: str) -> dict[str, Any] | None:
    """解析 `API [类型词] <序号><字母后缀/分册>[-年份]`；非 API 或不合法返回 None。"""
    from .std_utils import normalize_std_code_text

    s = re.sub(r"\s+", " ", normalize_std_code_text(text)).strip()
    head = _API_HEAD_RE.match(s)
    if not head:
        return None
    body = s[head.end() :].strip()
    m = _API_BODY_RE.match(body)
    if not m:
        return None

    type_word = (m.group("type") or "").strip()
    if type_word and type_word.upper() not in _API_TYPE_WORDS:
        return None

    # 联合标准段（`/ASME FFS-1` 等）不改变主标准身份，只保留 `/` 之前部分。
    tail = re.split(r"\s*/", m.group("tail").strip(), maxsplit=1)[0].strip()
    parts = _triple(tail) if tail else ("", None, 0)
    if parts is None:
        return None
    num_suffix, part, year = parts
    return {
        "raw_code": "API",
        "code": "API",
        "number": int(m.group("number")),
        "part": part,
        "year": year,
        "num_prefix": type_word,
        "num_suffix": num_suffix,
    }
