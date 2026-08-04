# 模块：项目/扫描/解析器/__提取器脚本
# 数字提取
"""提供标准号中年份/编号/分册号提取功能。"""

from typing import Optional


class NumberExtractor:
    """年份归一化、编号提取、编号前缀提取、分册号提取。"""

    @staticmethod
    def normalize_year(year_str: str) -> int:
        """年份归一化：两位年份（<100）补 1900 前缀，四位年份直接返回。"""
        year = int(year_str)
        if year < 100:
            return 1900 + year
        return year

    @staticmethod
    def extract_number(number_str: str) -> tuple[Optional[int], str, str]:
        """从编号字符串提取整数、后缀字母和原始字符串。如 '6D'→(6,'D','6D'), '001'→(1,'','001')。
        返回三元组 (int_val, suffix, raw_str)，raw_str 保留前导零等原始信息。"""
        if not number_str:
            return None, "", ""
        clean = number_str
        while clean and clean[0].isalpha():
            clean = clean[1:]
        suffix = ""
        while clean and clean[-1].isalpha():
            suffix = clean[-1] + suffix
            clean = clean[:-1]
        try:
            return (int(clean), suffix, number_str) if clean else (None, "", "")
        except ValueError:
            return None, "", ""

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
