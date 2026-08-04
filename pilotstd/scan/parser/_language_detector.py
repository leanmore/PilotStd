# 模块：项目/扫描/解析器/__检测器脚本
# 语言检测
"""提供文件名语言版本检测功能。"""

from ..lang_detect import detect_language


class LanguageDetector:
    """从原始 basename 识别语言版本标记。"""

    @staticmethod
    def detect(basename: str) -> str:
        """委托 lang_detect 模块检测语言版本标记。"""
        return detect_language(basename)
