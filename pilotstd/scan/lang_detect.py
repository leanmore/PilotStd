# pilotstd/scan/lang_detect.py
# 统一语种信号识别 — parser 和归档命名规则共用同一套模式

import re

# ── 中文语种信号 ────────────────────────────────────────────
_LANG_ZH = re.compile(
    r"(?:（中文）|\(中文\)|（中文版）|\(中文版\)|（中）)"  # 括号形式
    r"|[\s\-]中文版|(?:\d|th)中文版"  # -中文版 / " 中文版" / 5th中文版
    r"|[\s\-]中文(?=[\s\-_.]|$)"  # 中文（后跟分隔符或结尾）
    r"|[_\s\-\d]CN(?=[_\s\-.\d]|$)|[_\s\-]CN$"  # CN 语言代码（含 2000CN）
    r"|[\-\s]+中文翻译"  # --中文翻译
)

# ── 英文语种信号 ────────────────────────────────────────────
_LANG_EN = re.compile(
    r"(?:（英文）|\(英文\)|\(English\)|（English）)"  # 括号形式
    r"|[\s\-]英文版|[\s\-]英文(?=[\s\-_.]|$)"  # 英文版/英文
    r"|[\s\-]English[\s\-_.]"  # English 单词
    r"|[_\s\-\d]EN(?=[_\s\-.\d]|$)|[_\s\-]en(?=[_\s\-.\d]|$)"  # EN/en 语言代码（含 _EN / 2000EN）
    r"|(?<![a-zA-Z])en$|(?<![a-zA-Z])EN$",  # 末尾裸 en/EN（中文字符后等）
    re.IGNORECASE,
)


def detect_language(basename: str) -> str:
    """从文件名 basename 识别语种标记。返回 '中文版' / '英文版' / ''。

    用于：parser.py 解析阶段 + filename_normalizer.py 归档阶段。
    """
    if _LANG_ZH.search(basename):
        return "中文版"
    if _LANG_EN.search(basename):
        return "英文版"
    return ""
