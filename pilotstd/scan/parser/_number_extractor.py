# pilotstd/scan/parser/_number_extractor.py
# 数字提取 Handler
"""提供标准号中年份/编号/分册号提取功能。"""

from typing import Optional


class NumberExtractor:
    """年份归一化、编号提取、编号前缀提取、分册号提取。"""

    @staticmethod
    def normalize_year(year_str: str) -> int:
        year = int(year_str)
        if year < 100:
            return 1900 + year
        return year

    @staticmethod
    def extract_number(number_str: str) -> tuple[Optional[int], str]:
        """从编号字符串提取整数和后缀字母。如 '6D'→(6,'D'), 'B16'→(16,''), '500'→(500,'')。"""
        if not number_str:
            return None, ""
        clean = number_str
        # 去掉前导字母（如 ASME 的 B16, ASTM 的 D4236）
        while clean and clean[0].isalpha():
            clean = clean[1:]
        # 去掉后缀字母（如 API 的 6D, 6A）
        suffix = ""
        while clean and clean[-1].isalpha():
            suffix = clean[-1] + suffix
            clean = clean[:-1]
        try:
            return (int(clean), suffix) if clean else (None, "")
        except ValueError:
            return None, ""

    @staticmethod
    def extract_num_prefix(number_str: str) -> str:
        """提取编号中的字母前缀。如 'B16'→'B', '500'→''。"""
        if not number_str:
            return ""
        prefix = ""
        for c in number_str:
            if c.isalpha():
                prefix += c
            else:
                break
        return prefix

    @staticmethod
    def extract_part(part_str: Optional[str]) -> Optional[int]:
        """从部分号字符串提取整数，支持字母后缀（810G→810）。"""
        if not part_str:
            return None
        if part_str[0].isalpha():
            part_str = part_str[1:]
        try:
            return int(part_str)
        except ValueError:
            return None
