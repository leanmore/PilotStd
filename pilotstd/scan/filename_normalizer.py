# pilotstd/scan/filename_normalizer.py
# 归档文件名规范化器 — 剥离原始语种/版次标记，重新组装为统一格式
#
# 流水线: 源文件名 → ①识语种 → ②识版次 → ③剥离标记 → ④清理 → ⑤重组
# 输出: [标准号] [标题] [版次](语种).pdf
#
# 剥离策略：仅剥离语种/版次标记，保护标准代号段（如 BS EN 中的 EN 不是语种）

import re
import os
from .lang_detect import detect_language
from .edition_detect import extract_edition

# ── 剥离用正则 ────────────────────────────────────────────────

# 中文语种标记（可安全在全文中剥离）
_ZH_MARK = re.compile(
    r'\s*[（(](?:中文版?|中)[）)]'         # （中文）/ (中文版) / （中）
    r'|\s*[-\-\s]+中文翻译'               # --中文翻译
    r'|\s+中文版(?=\s|$|-)'              # " 中文版" 后跟空白/结尾/-
    r'|[_\s\-]CN(?=[_\s\-\d]|$)'         # _CN / -CN / 2000CN（不在标准代号段中）
    r'|(?<=[一-鿿])CN$',          # 中文字符后的 CN（末尾）
)

# 英文语种标记
_EN_MARK = re.compile(
    r'\s*[（(](?:英文|English)[）)]'       # （英文）/ (English)
    r'|\s+英文版(?=\s|$|-)'              # " 英文版"
    r'|\s+English\s+version'             # English version
    r'|(?<=[一-鿿])en$'          # 中文字符后的裸 en（末尾）
    r'|(?<=[一-鿿])EN$',         # 中文字符后的裸 EN（末尾）
    re.IGNORECASE,
)

# EN/CN 语言代码（需保护 BS EN / DIN EN 等标准代号段）
_EN_CN_CODE = re.compile(
    # 中文字符/数字/下划线后跟 EN/CN（固定宽度后顾 1 字符）
    r'(?<=[一-鿿\d_])(?:EN|en|CN)(?=[\s\-._]|$)'
    # _2000CN 模式（固定宽度后顾 5 字符）
    r'|(?<=[_\s\-]\d{4})(?:EN|en|CN)(?=[\s\-._]|$)',
    re.IGNORECASE,
)

# 版次标记（可安全在全文中剥离）
_EDITION_ALL = re.compile(
    r'\s*(?:第\s*)?\d{1,2}\s*版'           # 10版 / 第10版
    r'|\s*\d{1,2}\s*(?:st|nd|rd|th)'      # 10th / 5th
    r'|\s*[A-Za-z]+\s+Edition'            # Tenth Edition
    r'|\s*[（(]\d{1,2}(?:st|nd|rd|th)'     # (5th...) — 版次+语种混合
    r'\s*(?:中文版|中文|英文版|英文)?'       # 括号内可选语种
    r'\s*[）)]',                            # 闭合括号
    re.IGNORECASE,
)

# 版次嵌入型（-5th-中文版 等）
_EDITION_HYBRID = re.compile(
    r'[_-]\d{1,2}(?:st|nd|rd|th)'          # _5th / -5th
    r'(?:[_-](?:中文版|英文版|CN|EN))?'     # 紧跟的语种
    r'[_-]?'                                 # 尾部分隔符
    r'(?=[一-鿿a-zA-Z])',            # 后面是标题文本
    re.IGNORECASE,
)

# 附加描述（+中英对照...+3万字注解...+160张附图）
_EXTRA_DESC = re.compile(
    r'\s*\+中英对照(\+[^+]*)*'             # +中英对照 及后续
    r'|\s*\+\d+万字注解(\+[^+]*)*'         # +3万字注解 及后续
    r'|\s*\+\d+张附图',                   # +160张附图
)


def normalize_archive_name(filename: str) -> str:
    """将源文件名规范化为归档标准格式。

    Args:
        filename: 源文件完整文件名

    Returns:
        规范化后的文件名。无语言标记的文件原样返回。
    """
    base, ext = os.path.splitext(filename)
    ext = ext or ".pdf"

    # ① 识语种
    lang = detect_language(base)

    # ② 识版次
    edition = extract_edition(base, lang)

    # ③ 剥离标记（顺序重要：先剥离嵌入版次，再剥离语种，最后是纯版次）
    cleaned = base

    # 嵌入版次（_4th_EN / -5th-中文版 等，先剥离避免残留分隔符）
    cleaned = _EDITION_HYBRID.sub(' ', cleaned)

    # 混合版次括号（(5th中文版)）
    cleaned = _EDITION_ALL.sub('', cleaned)

    # 附加描述
    cleaned = _EXTRA_DESC.sub('', cleaned)

    # 中文/英文语种标记
    cleaned = _ZH_MARK.sub('', cleaned)
    cleaned = _EN_MARK.sub('', cleaned)

    # EN/CN 代码（受保护的标准代号段内的不会被误删）
    cleaned = _EN_CN_CODE.sub('', cleaned)

    # ④ 清理多余分隔符
    cleaned = re.sub(r'_{2,}', '_', cleaned)             # 多余下划线 → 一个
    cleaned = re.sub(r'-{2,}', '-', cleaned)             # 多余连字符 → 一个
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)            # 多余空格 → 一个
    cleaned = re.sub(r'\s*[-_]\s+(?=[一-鿿a-zA-Z])', ' ', cleaned)  # 剥离后残留的 -_ 接文本
    cleaned = re.sub(r'\s*[-_]\s*$', '', cleaned)        # 末尾残留 -_
    cleaned = re.sub(r'^\s*[-_]\s*', '', cleaned)        # 开头残留 -_
    cleaned = cleaned.strip()

    # ⑤ 重组 — 语种标签紧贴，版次与标题间用空格
    result = cleaned
    if edition:
        result = f"{result} {edition}"
    if lang:
        result = f"{result}({lang})"

    return result + ext
