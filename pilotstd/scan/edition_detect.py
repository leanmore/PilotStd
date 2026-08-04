# 模块：pilotstd/scan/edition_detect.py
# 统一版次识别 — parser 跳过版次、归档规则翻译版次，共用同一套模式

import re

# ── 版次正则 ────────────────────────────────────────────────
# 捕获组: cn=中文版次数字, en_num=英文序数数字, en_word=英文全称版次
_EDITION_RE = re.compile(
    r"(?:第\s*)?(?P<cn>\d{1,2})\s*版"  # 中文: 10版 / 第10版
    r"|(?P<en_num>\d{1,2})\s*(?:st|nd|rd|th)"  # 英文序数: 10th / 5th
    r"|(?P<en_word>[A-Za-z]+)\s+Edition",  # 英文全称: Tenth Edition
    re.IGNORECASE,
)

# 英文序数 → 数字映射
_ORDINAL_MAP = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
}


def extract_edition(text: str, language: str) -> str:
    """从文件名提取版次，按语种翻译。

    zh → '第N版'（如 '第10版'）
    en → 保留原文（如 '10th' / 'Tenth Edition'）

    未识别到版次返回空字符串。
    """
    m = _EDITION_RE.search(text)
    if not m:
        return ""

    if m.group("cn"):
        n = int(m.group("cn"))
        return f"第{n}版"

    if m.group("en_num"):
        n = int(m.group("en_num"))
        if language == "中文版":
            return f"第{n}版"
        return f"{n}th"

    if m.group("en_word"):
        word = m.group("en_word")
        full = m.group(0)  # 完整匹配（如 "Tenth Edition"）
        n = _ORDINAL_MAP.get(word.lower(), 0)
        if n is not None and language == "中文版":
            return f"第{n}版"
        return full  # 保留完整原文（如 "Tenth Edition"）

    return ""


def edition_skip_pattern() -> str:
    """返回版次跳过用的正则片段（供 parser.py 正则组装）。

    兼容: 10版 / 第10版 / 10th Edition / TENTH EDITION
    """
    return r"(?:\s*\d+版\s*|\s*[A-Za-z]+\s+Edition\s*)?"
