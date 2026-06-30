# pilotstd/scan/parser/_utils.py
# 标准解析器工具函数混入模块
"""文本清洗、语言检测、字段提取、结果构建等工具方法。"""

import logging
import re
from typing import Optional

from ...core.file_utils import normalize_std_filename
from ...models import ParsedStdInfo
from ..lang_detect import detect_language
from ._constants import PRESERVED_MULTI_WORD

logger = logging.getLogger(__name__)


class UtilsMixin:
    """工具方法混入类 — 文本清洗、字段提取、结果构建。"""

    # ── 文本清洗 ────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        # 先走公共清洗：斜杠归一化、缺斜杠还原、符号清理、垃圾后缀截断、空格压缩
        text = normalize_std_filename(text)
        # 解析器特有：+ _ → 空格，No. 去掉，: → -，合订本范围截断
        text = text.replace("+", " ")
        text = text.replace("_", " ")
        text = re.sub(r"\bNo\.\s*", "", text)
        text = text.replace(":", "-")
        text = re.sub(r"\s*[～~]\s*\d+", "", text)
        return text.strip()

    @staticmethod
    def _detect_language(basename: str) -> str:
        """从原始 basename 识别语言版本标记（委托 lang_detect 模块）。"""
        return detect_language(basename)

    @staticmethod
    def _detect_file_kind(basename: str) -> str:
        """从文件名识别文件属性标签：扫描版/扫描件/水印版/文本版。"""
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

    # ── 公共辅助 ────────────────────────────────────────────

    @staticmethod
    def _normalize_year(year_str: str) -> int:
        year = int(year_str)
        if year < 100:
            return 1900 + year
        return year

    def _trim_prefix(self, prefix: str, text: str) -> str:
        """用已知代号表截断贪婪匹配的前缀。逐词验证，每个词必须在 code_mapping 中。
        'ANSI API Standard' → 'ANSI API'（Standard 不在表中，截断）。"""
        if " " not in prefix:
            return prefix
        words = prefix.split()
        for i in range(len(words), 0, -1):
            candidate = " ".join(words[:i])
            # 整体匹配（如 BS EN、BS EN ISO）
            if candidate in self.code_mapping or candidate in PRESERVED_MULTI_WORD:
                return candidate
            # 逐词验证：每个词是否都是已知代号（如 ANSI + API）
            if all(w in self.code_mapping for w in words[:i]):
                return candidate
        return words[0]  # 没匹配到至少保留第一个词

    @staticmethod
    def _extract_number(number_str: str) -> tuple[Optional[int], str]:
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
    def _extract_num_prefix(number_str: str) -> str:
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
    def _extract_part(part_str: Optional[str]) -> Optional[int]:
        """从部分号字符串提取整数，支持字母后缀（810G→810）。"""
        if not part_str:
            return None
        if part_str[0].isalpha():
            part_str = part_str[1:]
        try:
            return int(part_str)
        except ValueError:
            return None

    @staticmethod
    def _clean_std_name(name: str) -> str:
        """剥离 std_name 中残留的语种/版次标记，避免归档时重复叠加。"""
        # 括号语种
        name = re.sub(r"\s*[（(]中文[）)]", "", name)
        name = re.sub(r"\s*[（(]中文版[）)]", "", name)
        name = re.sub(r"\s*[（(]中[）)]", "", name)
        name = re.sub(r"\s*[（(]英文[）)]", "", name)
        name = re.sub(r"\s*[（(]英文版[）)]", "", name)
        name = re.sub(r"\s*[（(]English[）)]", "", name)
        # 单词/连字符语种
        name = re.sub(r"\s*中文版\s*", " ", name)
        name = re.sub(r"\s*英文版\s*", " ", name)
        name = re.sub(r"\s*[-–—]+\s*中文翻译\s*", " ", name)
        name = re.sub(r"\s*English\s+version\s*", " ", name, flags=re.IGNORECASE)
        # 语言代码
        name = re.sub(r"\s*[_\s\-]CN\s*", " ", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*[_\s\-\d]EN\s*", " ", name, flags=re.IGNORECASE)
        # 附加描述（parser 已将 + 替换为空格，匹配空格分隔版本）
        name = re.sub(r"\s*中英对照(?:\s+\d+万字注解)?(?:\s+\d+张附图)?", "", name)
        name = re.sub(r"\s*\d+万字注解(?:\s+\d+张附图)?", "", name)
        name = re.sub(r"\s*\d+张附图", "", name)
        # 版次标记（前后空格一并移除）
        name = re.sub(r"\s*\d+版\s*", " ", name)
        name = re.sub(r"\s*第\s*\d+\s*版\s*", " ", name)
        name = re.sub(r"\s*\d{1,2}\s*(?:st|nd|rd|th)\s*", " ", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*[A-Za-z]+\s+Edition\s*", " ", name, flags=re.IGNORECASE)
        # 嵌入版次-语种残留（-5th-中文版 的残留碎片）+ 孤儿版字
        name = re.sub(r"^\s*版\s*", " ", name)  # 孤儿版字（如 "版 石油..."）
        name = re.sub(r"^[-–—_\s]+", "", name)  # 开头残留分隔符
        name = re.sub(r"[-–—_\s]+$", "", name)  # 末尾残留分隔符
        name = re.sub(r"\s{2,}", " ", name)  # 多余空格
        # 清除剥离版次/语种后残留的空括号（如 "(5th中文版)" → "( )" → ""）
        name = re.sub(r"[（(]\s*[）)]", "", name)
        return name.strip()

    @staticmethod
    def _validate_result(year: int, number: int, logical_code: str, require_year: bool = True) -> bool:
        """校验解析结果是否构成合法的标准编号。

        规则:
          - year 必须大于 0（当 require_year=True 时）：0 表示"无年份"。
          - year 在 1-99（两位年份，如 "98"）或 1900-2099（四位年份）范围内。
          - require_year=False 时跳过年份校验，仅校验 logical_code 和 number。
            用于支持字母修订版标准（如 MIL-STD-810G），此类标准无年份。
          - number 必须为正整数（> 0）。
          - logical_code 必须为非空字符串。
        """
        if not logical_code or not isinstance(logical_code, str):
            return False
        if not isinstance(number, int) or number <= 0:
            return False
        if require_year:
            if not isinstance(year, int) or year <= 0:
                return False
            # 两位年份（1-99）或四位年份（1900-2099）
            if year > 99 and (year < 1900 or year > 2099):
                return False
        return True

    def _build_result(
        self,
        text: str,
        match_end: int,
        logical_code: str,
        number: int,
        part: Optional[int],
        year: int,
        num_prefix: str = "",
        num_suffix: str = "",
        file_kind: str | None = None,
        require_year: bool = True,
    ) -> Optional[ParsedStdInfo]:
        if file_kind is None:
            file_kind = getattr(self, "_current_file_kind", "")
        """构建 ParsedStdInfo，处理名称尾部清理。"""
        remaining = text[match_end:].strip()
        name = re.sub(r"^[-–—\s]+", "", remaining)
        if re.match(r"^\d{1,3}$", name):
            name = ""
        name = self._clean_std_name(name)  # 剥离语种/版次标记，避免归档时重复

        # 自查校验：require_year=False 时跳过年份校验（字母修订版如 MIL-STD-810G）
        if not self._validate_result(year, number, logical_code, require_year):
            return None

        # [TRACE] 指令A-2: 输出ParsedStdInfo完整字段
        logger.debug(
            "[TRACE-A] 解析信息: 代号=%s 编号=%d 年份=%d 部分号=%s "
            "标准名称=%r 源名称=%r 编号前缀=%r 编号后缀=%r 扩展名=%r",
            logical_code,
            number,
            year,
            part,
            name,
            name,
            num_prefix,
            num_suffix,
            getattr(self, "_current_file_kind", ""),
        )

        return ParsedStdInfo(
            raw_filename=text,
            logical_code=logical_code,
            number=number,
            num_prefix=num_prefix,
            num_suffix=num_suffix,
            part=part,
            year=year,
            std_name=name,
            source_name=name,  # 原始名称，不被后处理覆盖
            file_kind=file_kind,
        )
