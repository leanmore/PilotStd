# 模块：项目/扫描/解析器/__提取器脚本
# 数字提取
"""提供标准号中年份/编号/分册号提取功能。"""

from typing import Optional


class NumberExtractor:
    """年份归一化、编号提取、编号前缀提取、分册号提取。"""

    @staticmethod
    def normalize_year(year_str: str) -> int:
        """年份归一化：两位年份按 70 分界补全（20→2020、86→1986），四位直接返回。

        原实现一律 `1900 + yy`，会把 2000 年代的标准算成 1920（D1-1 审计发现）。
        """
        year = int(year_str)
        if year < 100:
            return 2000 + year if year < 70 else 1900 + year
        return year

    @staticmethod
    def extract_number(number_str: str) -> tuple[Optional[int], str, str]:
        """从编号字符串提取整数、字母后缀和原始字符串。

        批次10（P1-7.1 B-8）：后缀允许「多字母 + 连字符多段」，从尾部整体收集：
        `6D`→(6,'D','6D')、`5CT`→(5,'CT','5CT')、`A-WSD` 段的 `2A-WSD`→(2,'A-WSD',…)、
        `938-C`→(938,'C','938-C')（前导连字符不进入后缀）。前导字母仍剥离（`B16`→16）。
        无法提取纯数字部分（如 `abc` / `12A3`）返回 (None, "", "")。
        """
        if not number_str:
            return None, "", ""
        body = number_str
        while body and body[0].isalpha():
            body = body[1:]
        end = len(body)
        while end > 0 and (body[end - 1].isalpha() or body[end - 1] == "-"):
            end -= 1
        digits = body[:end]
        suffix = body[end:].strip("-")
        if not digits.isdigit():
            return None, "", ""
        return int(digits), suffix, number_str

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
