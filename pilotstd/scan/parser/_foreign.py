# 模块：项目/扫描/解析器/_脚本
# 标准解析器国外标准后处理模块—原，现为模块级纯函数
"""国外标准定向后处理 — 按分组路由到对应 handler。"""

import re

from ...models import ParsedStdInfo
from ._constants import (
    _FOREIGN_GROUP_MAP,
    API_TYPES,
    CAC_PREFIXES,
    IEC_TYPES,
    MIL_TYPES,
    SAE_PREFIXES,
)


def _post_process_foreign(info: ParsedStdInfo) -> None:
    """国外标准定向后处理，按分组路由到对应 handler。原 Mixin 方法，现为模块级纯函数。"""
    raw = info.raw_filename
    base_code = info.logical_code.split()[0].upper()  # 取首段（如 "ASME BPVC"→"ASME"）
    group = _FOREIGN_GROUP_MAP.get(base_code)
    if group is None:
        return
    _dispatch_foreign_handler(info, raw, group)


def _dispatch_foreign_handler(info: ParsedStdInfo, raw: str, group: str) -> None:
    """按组路由到对应 handler，组1/组4 无需处理直接返回。原 Mixin 方法，现为模块级纯函数。"""
    if group == "letter_class":
        _handle_letter_class(info, raw)
    elif group == "type_prefix":
        _handle_type_prefix(info, raw)
    elif group == "special_sep":
        _handle_special_sep(info, raw)
    elif group == "unique":
        _handle_unique(info, raw)
    # _/_：无需后处理


def _handle_letter_class(info: ParsedStdInfo, raw: str) -> None:
    """组2: 字母分类型 — 从原始文件名提取分类字母 → num_prefix。原 Mixin 方法，现为模块级纯函数。"""
    code = info.logical_code.upper()

    if code.startswith("ASTM"):
        m = re.search(r"\bASTM\s+([A-G])\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1).upper()

    elif code.startswith("JIS"):
        m = re.search(r"\bJIS\s+([A-Z])\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1).upper()

    elif code.startswith("CSA"):
        m = re.search(r"\bCSA\s+([A-Z])\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1).upper()

    elif code.startswith("AWWA"):
        m = re.search(r"\bAWWA\s+([A-G])\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1).upper()

    elif code.startswith("NF"):
        m = re.search(r"\bNF\s+([A-Z])\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1).upper()


def _handle_type_prefix(info: ParsedStdInfo, raw: str) -> None:
    """组3: 类型前缀型 — 从原始文件名提取类型标识 → num_prefix。原 Mixin 方法，现为模块级纯函数。"""
    code = info.logical_code.upper()

    if code.startswith("API"):
        m = re.search(rf"(?<=\bAPI\s)({'|'.join(API_TYPES)})\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1)

    elif code.startswith("MSS"):
        if re.search(r"\bMSS\s+SP\b", raw, re.IGNORECASE):
            info.num_prefix = "SP"

    elif code.startswith("MIL"):
        m = re.search(rf"\bMIL[-\s]({'|'.join(MIL_TYPES)})\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1)

    elif code.startswith("SAE"):
        m = re.search(rf"\bSAE\s+({'|'.join(SAE_PREFIXES)})\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1)

    elif code.startswith("IEC"):
        m = re.search(rf"\bIEC\s+({'|'.join(IEC_TYPES)})\b", raw, re.IGNORECASE)
        if m:
            info.num_prefix = m.group(1)
            info.logical_code = "IEC"  # 从 "IEC TR" 修正为 "IEC"


def _handle_special_sep(info: ParsedStdInfo, raw: str) -> None:
    """组5: 特殊分隔符型 — GOST(点号数字) + ASME(BPVC罗马数字卷号)。原 Mixin 方法，现为模块级纯函数。"""
    code = info.logical_code.upper()

    if code.startswith("GOST"):
        m = re.search(r"\bGOST\s*(?:R\s+)?(?:ISO\s+)?(\d+(?:\.\d+)+)", raw, re.IGNORECASE)
        if m:
            parts = m.group(1).split(".")
            if len(parts) >= 3:
                info.num_prefix = parts[0]
                info.number = int(parts[1])
                info.raw_number = parts[1]
                info.part = int(parts[2])
            else:
                info.number = int(parts[0])
                info.raw_number = parts[0]
                info.part = int(parts[1])
        # 年份：紧跟点号数字后的 -年份
        ym = re.search(r"[\-]\s*((?:19|20)\d{2})\b", raw)
        if ym:
            info.year = int(ym.group(1))

    elif code.startswith("ASME"):
        # 罗马数字卷号由___在_进程之前处理
        # 此处仅处理非的标准，当前无需额外后处理
        pass


def _handle_unique(info: ParsedStdInfo, raw: str) -> None:
    """组6: 独特体系 — ANSI(双重署名) + CAC(文本前缀) + ITU(补全年份)。原 Mixin 方法，现为模块级纯函数。"""
    code = info.logical_code.upper()

    if code.startswith("ANSI"):
        # 双重署名由_的捕获组处理，无需后处理
        return

    if code.startswith("CAC"):
        # 尝试匹配特殊前缀（/////）
        for cac_pfx in CAC_PREFIXES:
            if cac_pfx.upper() in raw.upper():
                info.logical_code = cac_pfx
                break

    elif code.startswith("ITU"):
        # //部门后缀已在_中保留
        # 尝试从补全年份（若无）
        if info.year == 0:
            ym = re.search(r"[\-]\s*((?:19|20)\d{2})\b", raw)
            if ym:
                info.year = int(ym.group(1))
