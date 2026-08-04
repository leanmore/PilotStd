# 模块：pilotstd/scan/parser/_result_builder.py
# 结果构建 Handler
"""提供标准解析结果构建和名称清理功能。"""

import logging
import re
from typing import Callable, Optional

from ...models import ParsedStdInfo
from ._constants import PRESERVED_MULTI_WORD

logger = logging.getLogger(__name__)

# ✅ #46 P1: 模块级校验失败计数器
_result_builder_fail_count = [0]


def get_validate_fail_count() -> int:
    """获取 validate_result 累计失败次数。"""
    return _result_builder_fail_count[0]


logger = logging.getLogger(__name__)


class ResultBuilder:
    """标准解析结果构建 — 前缀截断、名称清理、校验、结果组装。

    需要注入 code_mapping（代号映射表）和 file_kind_provider（运行时 file_kind 获取回调）。
    """

    def __init__(
        self,
        code_mapping: dict,
        file_kind_provider: Callable[[], str],
    ) -> None:
        self._code_mapping = code_mapping
        self._file_kind_provider = file_kind_provider

    # ── 前缀截断 ────────────────────────────────────────────

    def trim_prefix(self, prefix: str, text: str) -> str:
        """用已知代号表截断贪婪匹配的前缀。逐词验证，每个词必须在 code_mapping 中。

        'ANSI API Standard' → 'ANSI API'（Standard 不在表中，截断）。
        """
        if " " not in prefix:
            return prefix
        words = prefix.split()
        for i in range(len(words), 0, -1):
            candidate = " ".join(words[:i])
            # 整体匹配（如 BS EN、BS EN ISO）
            if candidate in self._code_mapping or candidate in PRESERVED_MULTI_WORD:
                return candidate
            # 逐词验证：每个词是否都是已知代号（如 ANSI + API）
            if all(w in self._code_mapping for w in words[:i]):
                return candidate
        return words[0]  # 没匹配到至少保留第一个词

    # ── 标准名称清理 ─────────────────────────────────────────

    @staticmethod
    def clean_std_name(name: str) -> str:
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

    # ── 结果校验 ────────────────────────────────────────────

    @staticmethod
    def validate_result(
        year: int,
        number: int,
        logical_code: str,
        require_year: bool = True,
    ) -> bool:
        """校验解析结果是否构成合法的标准编号。

        规则:
          - year 必须大于 0（当 require_year=True 时）：0 表示"无年份"。
          - year 在 1-99（两位年份，如 "98"）或 1900-2099（四位年份）范围内。
          - require_year=False 时跳过年份校验，仅校验 logical_code 和 number。
            用于支持字母修订版标准（如 MIL-STD-810G），此类标准无年份。
          - number 必须为正整数（> 0）。
          - logical_code 必须为非空字符串。
        """
        failures = []
        if not logical_code or not isinstance(logical_code, str):
            failures.append("missing_logical_code")
        if not isinstance(number, int) or number <= 0:
            failures.append(f"invalid_number({number})")
        if require_year:
            if not isinstance(year, int) or year <= 0:
                failures.append(f"year_non_positive({year})")
            # 两位年份（1-99）或四位年份（1900-2099）
            if year > 99 and (year < 1900 or year > 2099):
                failures.append(f"year_out_of_range({year})")
        if failures:
            logger.warning(
                "[VALIDATE_FAILED] code=%r number=%d year=%d reasons=%s",
                logical_code,
                number,
                year,
                failures,
            )
            # ✅ #46 P1: 合并计数，无论几个条件，只计 1 次
            _result_builder_fail_count[0] += 1
            return False
        return True

    # ── 结果构建 ────────────────────────────────────────────

    def build_result(
        self,
        text: str,
        match_end: int,
        logical_code: str,
        number: int,
        part: Optional[int],
        year: int,
        num_prefix: str = "",
        num_suffix: str = "",
        raw_number: str = "",
        file_kind: str | None = None,
        require_year: bool = True,
    ) -> Optional[ParsedStdInfo]:
        """构建 ParsedStdInfo，处理名称尾部清理。"""
        if file_kind is None:
            file_kind = self._file_kind_provider()

        remaining = text[match_end:].strip()
        name = re.sub(r"^[-–—\s]+", "", remaining)
        if re.match(r"^\d{1,3}$", name):
            name = ""
        name = self.clean_std_name(name)  # 剥离语种/版次标记，避免归档时重复

        # 自查校验：require_year=False 时跳过年份校验（字母修订版如 MIL-STD-810G）
        if not self.validate_result(year, number, logical_code, require_year):
            return None

        # [TRACE] 指令A-2: 输出ParsedStdInfo完整字段
        # 说明：NOTE: debug format string has 10 placeholders — keep args in sync
        logger.debug(
            "[TRACE-A] 解析信息: 代号=%s 编号=%d 年份=%d 部分号=%s "
            "标准名称=%r 源名称=%r 编号前缀=%r 编号后缀=%r 扩展名=%r 原始编号=%r",
            logical_code,
            number,
            year,
            part,
            name,
            name,
            num_prefix,
            num_suffix,
            file_kind,
            raw_number,
        )

        return ParsedStdInfo(
            raw_filename=text,
            logical_code=logical_code,
            number=number,
            raw_number=raw_number,
            num_prefix=num_prefix,
            num_suffix=num_suffix,
            part=part,
            year=year,
            std_name=name,
            source_name=name,  # 原始名称，不被后处理覆盖
            file_kind=file_kind,
        )
