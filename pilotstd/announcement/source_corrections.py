# 模块：公告源站标准号纠错
"""按“标准名称反查权威标准号”修正源站已知录入错误。

只对**指定公告 + 精确名称**生效，避免影响其他公告中的同名标准：
- 2014 年第4号：源站把《视频中物品图像检验技术规范》写成 GA/T 1023-2013，
  权威登记为 GA/T 1018-2013；GA/T 1023 属于《视频中人像检验技术规范》。
- 2019 年第8号：源站两行都写成 WS 439-2013；国卫通〔2013〕1号明确
  《裂头蚴病的诊断》为 WS 438-2013，《钩虫病的诊断》为 WS 439-2013。
"""

from __future__ import annotations

import re

# (source_site, announce_no, 标准名称) -> 权威标准号
SOURCE_CODE_CORRECTIONS: dict[tuple[str, str, str], str] = {
    ("announcement_hb", "2014年第4号(总第172号)", "视频中物品图像检验技术规范"): "GA/T 1018-2013",  # i18n-allow
    ("announcement_hb", "2019年第8号(总第236号)", "裂头蚴病的诊断"): "WS 438-2013",  # i18n-allow
}


def _norm_name(name: str) -> str:
    """去掉空白和书名号，避免 PDF/HTML 换行导致匹配失败。"""
    return re.sub(r"[\s《》]+", "", name or "")


_NORMALIZED_CORRECTIONS = {
    (site, anno, _norm_name(name)): code for (site, anno, name), code in SOURCE_CODE_CORRECTIONS.items()
}


def correct_std_code(source_site: str, announce_no: str, std_name: str, std_code: str) -> str:
    """命中已知源站错误时返回权威标准号，否则原样返回。"""
    return _NORMALIZED_CORRECTIONS.get(
        (source_site, announce_no, _norm_name(std_name)),
        std_code,
    )
