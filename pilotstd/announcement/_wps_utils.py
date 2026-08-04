# 模块：pilotstd/announcement/_wps_utils.py
# Phase 2a: WPS 文本清洗 + 条目切分工具函数
# 从 parser.py 拆分以控制文件大小

import re


def _clean_wps_fulltext(text: str) -> str:
    """全文级 WPS 文本清洗：去格式标记、控制字符、压缩空白。"""
    # WPS 页脚标记（含前后 — 和页码，跨行匹配）
    text = re.sub(r"\s*—+\s*PAGE\s*\n?\s*MERGEFORMAT\s*\d*\s*—*\s*", " ", text, flags=re.IGNORECASE)
    # 页码标记：PAGE 1 OF 2
    text = re.sub(r"PAGE\s*\d+\s*OF\s*\d+", " ", text, flags=re.IGNORECASE)
    # ASCII 控制字符（保留换行 \n 和制表 \t）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    # 3 个以上连续空白 → 换行（WPS 表格单元格间常有多空格分隔）
    text = re.sub(r"[ \t]{3,}", "\n", text)
    # 3 个以上连续换行 → 压缩为 2 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _split_wps_entries(text: str, std_pattern: "re.Pattern[str]") -> list[str]:
    """按标准号位置切分 WPS 文本，解决多条目粘连问题。

    WPS 解码后常出现多条标准连在一起无换行分隔，
    利用 STD_CODE_PATTERN 定位每条标准的起始位置进行切分。
    """
    if not text:
        return []

    # 先看是否已按行自然分隔（70% 以上的行包含标准号即认为已分隔）
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) > 1:
        std_lines = sum(1 for ln in lines if std_pattern.search(ln))
        if std_lines >= len(lines) * 0.7:
            return lines

    # 正则扫描标准号位置，在匹配之间切分
    matches = list(std_pattern.finditer(text))
    if len(matches) <= 1:
        return [text.strip()] if text.strip() else []

    entries = []
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[start:end].strip()
        # 过滤过短片段（< 10 字符大概率是噪音）
        if len(segment) >= 10:
            entries.append(segment)

    return entries
