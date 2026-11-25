# 模块：项目/核心/_工具脚本/BPVC 解析
"""ASME BPVC 卷/册/篇体系编号解析（P1-7.1 B-5）。

从 `std_utils.py` 拆出（G-010 代码规模门禁：std_utils.py 需 ≤400 有效行）。
`parse_std_number` 的解析链在 BPVC 分支调用 `_try_parse_bpvc`。
"""

import re
from typing import Any

# `ASME BPVC.VIII.1-2021` / `ASME BPVC.IX-2021` / `ASME BPVC.II.D` / `ASME BPVC.II.D.M-2021`：
# 卷号是罗马数字，`BPVC` 后的点号让既有 roman/general/variant 解析器全部失败；
# `Section VIII Div.1` / `Section II Part D` 是同一体系的文字写法（Div→分册、Part→册篇字母）。
# 字段口径（报告 §4 G2）：卷号→number（阿拉伯值）、Div→part、册/篇字母→num_suffix，年份可缺省。
_BPVC_DOT_RE = re.compile(
    r"^(?:ASME\s+)?BPVC\s*[.\-\s]*"
    r"(?P<vol>[IVXLCDM]+)"
    r"(?:(?:[.\-])(?P<div>\d{1,2})|\.(?P<book>[A-Z](?:\.[A-Z])*))?"
    r"(?:\s*[-:]\s*(?P<year>(?:19|20)\d{2}))?$",
    re.IGNORECASE,
)
_BPVC_SECTION_RE = re.compile(
    r"^(?:ASME\s+)?(?:BPVC\s+)?Section\s+(?P<vol>[IVXLCDM]+)"
    r"(?:[,\s]*(?:Div(?:ision)?)[.\s]*(?P<div>\d{1,2}))?"
    r"(?:[,\s]*(?:Part)[.\s]*(?P<book>[A-Z](?:\.[A-Z])*))?"
    r"(?:\s*[-:]\s*(?P<year>(?:19|20)\d{2}))?$",
    re.IGNORECASE,
)


def _try_parse_bpvc(text: str) -> dict[str, Any] | None:
    """解析 ASME BPVC 卷/册/篇（B-5）：点号官方写法 + Section/Div/Part 文字写法。

    覆盖 `ASME BPVC.VIII.1-2021`、`ASME BPVC.II.D`、`ASME BPVC.II.D.M-2021`、
    `ASME BPVC Section VIII Div. 1-2021`、`ASME BPVC Section II Part D`；
    `ASME` / `BPVC` 前缀可省略（`BPVC.IX-2021`、`Section VIII Div.1`）。
    """
    from .std_utils import normalize_std_code_text

    s = re.sub(r"\s+", " ", normalize_std_code_text(text)).strip()
    m = _BPVC_DOT_RE.match(s) or _BPVC_SECTION_RE.match(s)
    if not m:
        return None
    from ..scan.parser import _ROMAN_MAP

    roman = m.group("vol").upper()
    number = _ROMAN_MAP.get(roman)
    if not number:
        return None
    return {
        "raw_code": "ASME",
        "code": "ASME",
        "number": number,
        "part": int(m.group("div")) if m.group("div") else None,
        "year": int(m.group("year")) if m.group("year") else 0,
        "num_prefix": roman,
        "num_suffix": (m.group("book") or "").upper(),
    }
