# 模块：pilotstd/scan/parser/_file_kind_detector.py
# 文件属性标记 Handler
"""提供文件名文件属性标签检测功能。"""


class FileKindDetector:
    """从文件名识别文件属性标签：扫描版/扫描件/水印版/文本版。"""

    @staticmethod
    def detect(basename: str) -> str:
        """从文件名中检测文件属性标签：扫描版/水印版/文本版，无匹配返回空字符串。"""
        for kw, label in [
            ("扫描版", "扫描版"),
            ("扫描件", "扫描版"),
            ("水印版", "水印版"),
            ("文本版", "文本版"),
            ("文字版", "文本版"),
            ("可编辑版", "文本版"),
        ]:
            if kw in basename:
                return label
        return ""
