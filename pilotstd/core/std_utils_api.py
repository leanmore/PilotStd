# 模块：项目/核心/_工具脚本/API 类型词解析
"""API 类型词/系列词编号解析（P1-7.1 B-6）。

从 `std_utils.py` 拆出（G-010 代码规模门禁：std_utils.py 需 ≤400 有效行）。
`parse_std_number` 的解析链在 variant 分支之前调用 `_try_parse_api_typed`。
"""

import re
from typing import Any

# API 的 STD/RP/Spec/Bull/MPMS/TR/TDB/Publ 是出版类型、Q 是质量体系系列，均不属于代号。
# 修复前全大写类型词被 `_try_parse_variant_prefix` 的 token 正则吞进代号（`APISTD`/`APIRP`/`APIQ`）。
_API_TYPED_RE = re.compile(
    r"^(API)\s+([A-Z]{1,4})\s*(\d{1,6})(?:\.(\d+))?(?:([A-Z]{1,2}))?"
    r"(?:\s*[-:]\s*((?:19|20)\d{2}))?$",
    re.IGNORECASE,
)


def _try_parse_api_typed(text: str) -> dict[str, Any] | None:
    """解析 `API <类型词> <序号>[字母后缀][.分册][-年份]`（B-6）。

    类型词统一落到 `num_prefix`（`API STD 610-2004`→`num_prefix=STD`、`API Q1-2023`→`Q`）；
    年份可缺省（year=0，与 `_try_parse_fallback` 一致）。`API 610-2004` 这类无类型词的编号不匹配。
    """
    from .std_utils import normalize_std_code_text

    s = re.sub(r"\s+", " ", normalize_std_code_text(text)).strip()
    m = _API_TYPED_RE.match(s)
    if not m:
        return None
    from ..scan.parser._constants import API_TYPES

    type_word = m.group(2)
    if type_word.upper() not in {t.upper() for t in API_TYPES} and type_word.upper() != "Q":
        return None
    return {
        "raw_code": "API",
        "code": "API",
        "number": int(m.group(3)),
        "part": int(m.group(4)) if m.group(4) else None,
        "year": int(m.group(6)) if m.group(6) else 0,
        "num_prefix": type_word,
        "num_suffix": m.group(5).upper() if m.group(5) else "",
    }
