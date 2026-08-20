# 模块：项目/扫描/解析器/__清理器脚本
# 文本清洗
"""提供标准文件名文本清洗功能。"""

import re

from ...core.file_utils import normalize_std_filename

# 合订本残片模式："47008-1947 010-2010"（起始编号-假年份 空格 残片编号-真实年份）。
# 由 "47008～47010-2010" 这类合订本范围被误转录/误识别产生；取起始编号 + 最后年份，
# 并追加"合订本"标识，避免被后续流程当作普通单标准（年份可能错到 1947 等假值）。
_COMBINED_STD_RE = re.compile(
    r"(\d{2,5})[-－]((?:19|20)\d{2})\s+(\d{2,5})[-－]((?:19|20)\d{2})"
)


class TextCleaner:
    """文本清洗：斜杠归一化、符号清理、合订本范围截断。"""

    @staticmethod
    def clean(text: str) -> str:
        # 先走公共清洗：斜杠归一化、缺斜杠还原、符号清理、垃圾后缀截断、空格压缩
        text = normalize_std_filename(text)
        # 解析器特有：+_→空格，.去掉，:→-，合订本范围截断
        text = text.replace("+", " ")
        text = text.replace("_", " ")
        text = re.sub(r"\bNo\.\s*", "", text)
        text = text.replace(":", "-")
        # 合订本残片归一化：47008-1947 010-2010 → 47008-2010 合订本
        text = _COMBINED_STD_RE.sub(r"\1-\4 合订本", text)
        text = re.sub(r"\s*[～~]\s*\d+", "", text)
        return text.strip()
