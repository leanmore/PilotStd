# 模块：项目/核心/_工具脚本/ASME 系列解析
"""ASME 分类字母/系列词编号解析（批次10 / P1-7.1 B-8、B-9）。

从 `std_utils.py` 拆出（G-010：`std_utils.py` 已处 400~500 行警告档，不允许增长）。
`parse_std_number` 的解析链在 BPVC 分支之后调用 `_try_parse_asme_series`，覆盖：

- 分类字母系列：`ASME B16.5-2020` / `ASME B31.3` / `ASME Y14.5` / `ASME C1`
  （`B`/`Y`/`C` 是分类字母 → `num_prefix`，16 是序号、5 是部分号）；
- 系列词：`ASME PTC 4-2013` / `ASME CSD-1-2024`（`PTC`/`CSD` 是出版系列 → `num_prefix`，
  修复前被 `STD_CODE_TOKEN_PATTERN` 吞成代号 `ASMEPTC`/`ASMECSD`）；
- 三级编号 + 联合标准：`ASME A112.18.1/CSA B125.1`（联合段只取主标准，第三级 `.1` → `num_suffix`）。
"""

import re
from typing import Any

# ASME 系列词（非分类字母）：出版类型/规范系列，与序号之间可用空格或连字符分隔。
# 仅登记已知系列，避免把 `ASME Section ...` 之类的文字写法误当系列词。
_ASME_SERIES_WORDS = frozenset({"PTC", "CSD", "NQA", "QME"})

_ASME_HEAD_RE = re.compile(r"^ASME\b\s*", re.IGNORECASE)

# 分类字母系列：单字母紧贴序号，可选 `.部分`、`.第三级`、`/联合标准`、`-年份`。
# 允许尾部 ` 名称`（扫描文件名常见），名称前必须有空白，避免把后续字母吞进编号。
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


def _result(
    series: str, number: int, part: int | None, year: int, num_suffix: str
) -> dict[str, Any]:
    """按统一字段口径组装解析结果（代号固定 `ASME`，系列词进 `num_prefix`）。"""
    return {
        "raw_code": "ASME",
        "code": "ASME",
        "number": number,
        "part": part,
        "year": year,
        "num_prefix": series.upper(),
        "num_suffix": num_suffix,
    }


def _try_parse_asme_series(text: str) -> dict[str, Any] | None:
    """解析 ASME 分类字母/系列词编号；非 ASME 或未命中返回 None。"""
    from .std_utils import normalize_std_code_text

    s = re.sub(r"\s+", " ", normalize_std_code_text(text)).strip()
    head = _ASME_HEAD_RE.match(s)
    if not head:
        return None
    body = s[head.end() :]

    letter = _ASME_LETTER_RE.match(body)
    if letter:
        level3 = letter.group("level3")
        return _result(
            series=letter.group("series"),
            number=int(letter.group("number")),
            part=int(letter.group("part")) if letter.group("part") else None,
            year=int(letter.group("year")) if letter.group("year") else 0,
            # 第三级编号无法单独成字段（models 无对应槽位）：按报告 §5 口径保留为 `.N` 后缀
            num_suffix=f".{level3}" if level3 else "",
        )

    word = _ASME_WORD_RE.match(body)
    if word and word.group("series").upper() in _ASME_SERIES_WORDS:
        return _result(
            series=word.group("series"),
            number=int(word.group("number")),
            part=None,
            year=int(word.group("year")) if word.group("year") else 0,
            num_suffix="",
        )
    return None
