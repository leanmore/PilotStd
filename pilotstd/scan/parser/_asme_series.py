# 模块：项目/扫描/解析器/_ASME 系列脚本
"""ASME 分类字母/系列词扫描解析（批次10 / P1-7.1 B-8、B-9、B-5 补充）。

放在 BPVC 通道之后、通用 exact 通道之前，专门处理通用的 `_PFX + _NUM` 拆不全的形态：

- 分类字母系列：`ASME B16.5[-年份]` / `ASME Y14.5` / `ASME C1`
  （`B`/`Y`/`C` 是分类字母 → `num_prefix`，16 是序号、5 是部分号）；
- 三级编号 + 联合标准：`ASME A112.18.1/CSA B125.1`
  （联合段只取主标准，第三级 `.1` → `num_suffix`，与 A 通道同一口径）；
- 系列词：`ASME PTC 4[-年份]` / `ASME CSD-1[-年份]` → `num_prefix`。

修复前：无年份被 `validate_result` 硬拒；`PTC`/`CSD` 无 handler 导致 `num_prefix` 空；
`A112.18.1` 被通用通道截断。
"""

import re
from typing import TYPE_CHECKING, Optional

from ...models import ParsedStdInfo

if TYPE_CHECKING:
    from . import StandardParser

# 已知 ASME 系列词（非分类字母）：只在白名单内解析，避免把 `ASME Section ...` 误当系列词。
ASME_SERIES_WORDS = frozenset({"PTC", "CSD", "NQA", "QME"})

_ASME_HEAD_RE = re.compile(r"^ASME\b\s*", re.IGNORECASE)

# 分类字母系列：单字母紧贴序号，可选 `.部分`、`.第三级`、`/联合标准`、`-年份`，允许尾部名称。
_ASME_LETTER_RE = re.compile(
    r"^(?P<series>[A-Z])(?P<number>\d{1,4})"
    r"(?:\.(?P<part>\d{1,3}))?"
    r"(?:\.(?P<level3>\d{1,3}))?"
    r"(?:\s*/\s*[A-Z][A-Z0-9.]*(?:\s+[A-Z][A-Z0-9.]*)*)?"
    r"(?:\s*[-:]\s*(?P<year>(?:19|20)\d{2}))?"
    r"(?:\s+.*)?$",
    re.IGNORECASE,
)

# 系列词形态：`PTC 4`（空格）与 `CSD-1`（连字符）两种官方写法。
_ASME_WORD_RE = re.compile(
    r"^(?P<series>[A-Z]{2,4})\s*(?:[-\s]\s*)(?P<number>\d{1,5})"
    r"(?:\s*[-:]\s*(?P<year>(?:19|20)\d{2}))?"
    r"(?:\s+.*)?$",
    re.IGNORECASE,
)


def match_asme_series(parser: "StandardParser", text: str) -> Optional[ParsedStdInfo]:
    """解析 ASME 分类字母/系列词文件名；非 ASME 或未命中返回 None。"""
    head = _ASME_HEAD_RE.match(text or "")
    if not head:
        return None
    body = text[head.end() :]

    letter = _ASME_LETTER_RE.match(body)
    if letter:
        level3 = letter.group("level3")
        return parser._build_result(
            text,
            head.end() + letter.end(),
            "ASME",
            int(letter.group("number")),
            int(letter.group("part")) if letter.group("part") else None,
            int(letter.group("year")) if letter.group("year") else 0,
            num_prefix=letter.group("series"),
            num_suffix=f".{level3}" if level3 else "",
        )

    word = _ASME_WORD_RE.match(body)
    if word and word.group("series").upper() in ASME_SERIES_WORDS:
        return parser._build_result(
            text,
            head.end() + word.end(),
            "ASME",
            int(word.group("number")),
            None,
            int(word.group("year")) if word.group("year") else 0,
            num_prefix=word.group("series"),
        )
    return None
