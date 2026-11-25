# 模块：项目/核心/_工具脚本/标准号表示
"""标准号规范化表示（唯一实现，批次10 / P1-7.1 B-11）。

`build_standard_number`（归档 / `standard_validity` 登记键）与
`models.ParsedStdInfo.get_full_number`（展示 / 下载文件名 / 本地索引名）共用本模块，避免两处
各自拼接导致（2026-11-25 实跑证据，见 `docs/plans/2026-11-25-p1-api-refresh.md` §3.2 R2）：

- 双前缀 `ASME BB16.5-2020` / 双后缀 `API SPEC 6DD-2021`
  —— B 通道 `raw_number` 已含前缀/后缀，旧实现又拼了一次；
- BPVC 丢卷册 `ASME 8.1-2025` —— 罗马卷号必须渲染成 `BPVC.VIII.1`；
- 类型词与序号粘连 `API STD610` / `ASME VIII8.1` —— `validity_checker` 判畸形键拒绝登记。
"""

import re
from typing import Any

_ROMAN_RE = re.compile(r"^[IVXLCDM]+$")
# ASME 系列词与序号之间的官方分隔符：`PTC 4` 用空格，`CSD-1` / `NQA-1` 用连字符。
_ASME_HYPHEN_SERIES = frozenset({"CSD", "NQA", "QME"})
# API 技术报告（TR）的字母修订版官方写法是连字符：`API TR 938-C`（后缀字段本身不含连字符，
# 由原始串解析时被 `str.strip("-")` 去掉；此处按出版类型补回，避免归档键/搜索词丢连字符）。
_API_HYPHEN_SUFFIX_SERIES = frozenset({"TR"})


def _as_int(value: Any) -> int:
    """宽松转 int：空/非数字返回 0（不用 try/except，避免被 G-050 记为静默吞错）。"""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    return int(text) if text.isdigit() else 0


def _plain_number(raw: str, prefix: str, suffix: str) -> str:
    """从 B 通道 `raw_number` 去掉已含的前缀/后缀，返回纯数字串（保留前导零）。"""
    text = raw
    if prefix and text.upper().startswith(prefix.upper()):
        text = text[len(prefix) :]
    if suffix and text.upper().endswith(suffix.upper()):
        text = text[: -len(suffix)]
    return text


def format_standard_number(
    logical_code: Any,
    number: Any,
    part: Any = None,
    year: Any = None,
    *,
    num_prefix: str = "",
    num_suffix: str = "",
    raw_number: str = "",
) -> str:
    """拼规范标准号；代号为空 / 编号非法时返回空串（调用方不得写入 DB）。"""
    code = str(logical_code or "").strip()
    if not code:
        return ""
    prefix = str(num_prefix or "").strip()
    suffix = str(num_suffix or "").strip()
    part_val = _as_int(part)
    year_val = _as_int(year)
    part_str = f".{part_val}" if part_val > 0 else ""
    prefix_upper = prefix.upper()

    number_val = _as_int(number)
    if number_val <= 0:
        # 非整数编号（历史调用方会传字符串编号，如 "1.1"）：保留原文，不丢件
        raw_text = str(number or "").strip()
        if not re.fullmatch(r"\d+(?:\.\d+)?", raw_text):
            return ""
        number_text = raw_text
    else:
        raw = str(raw_number or "").strip()
        number_text = _plain_number(raw, prefix, suffix) if raw else ""
        number_text = number_text if number_text.isdigit() else str(number_val)

    if prefix and code.upper() == "ASME" and _ROMAN_RE.match(prefix_upper):
        # BPVC 卷/册/篇：罗马卷号必须带 BPVC 前缀，册篇字母按点号分段
        body = f"BPVC.{prefix_upper}"
        if part_val > 0:
            body += f".{part_val}"
        if suffix:
            body += f".{suffix.upper()}"
    elif prefix and len(prefix) == 1 and prefix.isalpha():
        # 分类字母（ASME B/Y/C、ASTM A/B…）：单字母紧贴序号
        body = f"{prefix_upper}{number_text}{part_str}{suffix}"
    elif prefix and prefix_upper in _ASME_HYPHEN_SERIES:
        body = f"{prefix_upper}-{number_text}{part_str}{suffix}"
    elif prefix and code.upper() == "API" and prefix_upper in _API_HYPHEN_SUFFIX_SERIES and suffix:
        body = f"{prefix} {number_text}{part_str}-{suffix}"
    elif prefix and _ROMAN_RE.match(prefix_upper):
        body = f"{prefix_upper}{number_text}{suffix}{part_str}"
    elif prefix:
        # 类型词/系列词（API STD/SPEC/RP/PTC、ASME PTC…）与序号之间保留空格
        body = f"{prefix} {number_text}{suffix}{part_str}"
    elif code.upper() == "API" and part_val > 0:
        # API 无类型词的分册号用连字符（官方写法 `API 579-1`），不用点号
        body = f"{number_text}-{part_val}{suffix}"
    else:
        body = f"{number_text}{part_str}{suffix}"

    key = f"{code} {body}"
    if year_val > 0:
        key += f"-{year_val}"
    return key
