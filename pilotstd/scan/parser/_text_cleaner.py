# 模块：项目/扫描/解析器/__清理器脚本
# 文本清洗
"""提供标准文件名文本清洗功能。"""

import re

from ...core.file_utils import normalize_std_filename


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
        text = re.sub(r"\s*[～~]\s*\d+", "", text)
        return text.strip()
