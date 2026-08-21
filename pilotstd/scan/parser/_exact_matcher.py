# 模块：项目/扫描/解析器/__匹配器脚本
"""ExactMatcher — 精确匹配通道独立类（原 ExactMatchMixin 的 7 个匹配方法）。

通过组合注入 parser 引用，替代 MRO 隐式依赖。
共享引用: regex/regex_db/regex_no_year/regex_typed/regex_typed_v2/code_mapping
回调 parser: _normalize_year, _extract_number, _build_result, _validate_result 等
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Pattern

from ...constants.group_std_orgs import group_std_orgs
from ...models import ParsedStdInfo
from ._constants import _ASME_BPVC_RE, _ROMAN_MAP, _SEP, _YEAR4

logger = logging.getLogger(__name__)


class ExactMatcher:
    """精确匹配通道集合 — 组合注入到 StandardParser。"""

    def __init__(self, parser) -> None:
        # 共享引用：直接复制解析器的属性引用，避免同步维护
        self._parser = parser
        # 共享引用（直接从解析器复制，同一个对象）
        self.regex: Pattern[str] = parser.regex
        self.regex_no_year: Pattern[str] = parser.regex_no_year
        self.regex_typed: Pattern[str] = parser.regex_typed
        self.regex_typed_v2: Pattern[str] = parser.regex_typed_v2
        self.regex_db: Pattern[str] = parser.regex_db
        self.code_mapping: dict = parser.code_mapping

    # ── 7 个匹配通道 ────────────────────────────────────────

    def _exact_match_db(self, text: str) -> Optional[ParsedStdInfo]:
        """地方标准专用匹配：DB + 行政区划代码 + 顺序号 + 年份。

        logical_code 仅含代号部分且**无空格**（DB22/T、DB50），顺序号独立存 number。
        无空格形态保证归档安全文件名（DB22T 2883-2018）可被 normalize_std_filename
        的缺斜杠还原正则（^(DB\\d{2,4})([TZ])）还原，实现扫描→归档→再扫描自洽。
        """
        m = self.regex_db.match(text)
        if not m:
            return None
        # 提取行政区划代码和可选推荐性标识
        code = m.group("code")
        std_type = m.group("type")
        number_str = m.group("number")
        try:
            number = int(number_str)
        except ValueError:
            return None
        logical_code = f"DB{code}/{std_type}" if std_type else f"DB{code}"
        year = self._parser._normalize_year(m.group("year")) if m.group("year") else 0
        remaining = text[m.end() :].strip()
        name = re.sub(r"^[-–—\s]+", "", remaining)
        name = self._parser._clean_std_name(name)
        if not self._parser._validate_result(year, number, logical_code):
            return None
        return ParsedStdInfo(
            raw_filename=text,
            logical_code=logical_code,
            number=number,
            raw_number=number_str,
            year=year,
            std_name=name,
            source_name=name,
        )

    def _exact_match_group(self, text: str) -> Optional[ParsedStdInfo]:
        """团体标准解析通道：T/XXX 001-2019 与无斜杠归档形态 TXXX 001-2019。

        白名单策略：group_std_orgs 为空集合时透传（所有 T/XXX 均解析，不 warning）；
        非空时验证组织代码，不在白名单则 warning 但仍继续解析（不静默丢失）。
        无斜杠分支先排除已知代号（如 TSG 特种设备安全技术规范），避免误归团体标准。
        """
        # 带斜杠形态：T/CIESC 001-2019
        m = re.match(
            r"T/(?P<org>[A-Z]{2,})" + _SEP + r"(?P<number>\d{1,5})" + _SEP + _YEAR4,
            text,
        )
        if m:
            return self._build_group_result(text, m, f"T/{m.group('org')}")

        # 无斜杠形态（归档名）：TCIESC 001-2019；T{org} 为已知代号（如 TSG）时跳过
        m = re.match(
            r"T(?P<org>[A-Z]{2,})" + _SEP + r"(?P<number>\d{1,5})" + _SEP + _YEAR4,
            text,
        )
        if m:
            org = m.group("org")
            if f"T{org}" in self.code_mapping or org in self.code_mapping:
                return None
            return self._build_group_result(text, m, f"T/{org}")
        return None

    def _build_group_result(
        self, text: str, m: re.Match[str], logical_code: str
    ) -> Optional[ParsedStdInfo]:
        """构建团体标准解析结果：白名单验证 + 字段提取。"""
        org = m.group("org")
        if group_std_orgs and org not in group_std_orgs:
            logger.warning("团体标准组织代码未在白名单中: T/%s（仍继续解析）", org)
        number_str = m.group("number")
        try:
            number = int(number_str)
        except ValueError:
            return None
        year = self._parser._normalize_year(m.group("year")) if m.group("year") else 0
        remaining = text[m.end() :].strip()
        name = re.sub(r"^[-–—\s]+", "", remaining)
        name = self._parser._clean_std_name(name)
        if not self._parser._validate_result(year, number, logical_code):
            return None
        return ParsedStdInfo(
            raw_filename=text,
            logical_code=logical_code,
            number=number,
            raw_number=number_str,
            year=year,
            std_name=name,
            source_name=name,
        )

    def _exact_match_bpvc(self, text: str) -> Optional[ParsedStdInfo]:
        """ASME BPVC 罗马数字卷号专用匹配。"""
        m = _ASME_BPVC_RE.match(text)
        if not m:
            return None
        roman_str = m.group(1).upper()
        vol_num = _ROMAN_MAP.get(roman_str)
        if vol_num is None:
            return None
        sub = m.group(2)
        year_str = m.group(3)
        year = int(year_str) if year_str else 0
        remaining = text[m.end() :].strip()
        name = re.sub(r"^[-–—\s]+", "", remaining)
        name = self._parser._clean_std_name(name)
        if not self._parser._validate_result(year, vol_num, "ASME"):
            return None
        return ParsedStdInfo(
            raw_filename=text,
            logical_code="ASME",
            number=vol_num,
            num_prefix=roman_str,
            part=int(sub) if sub else None,
            year=year,
            std_name=name,
            source_name=name,
        )

    def _exact_match_itu(self, text: str) -> Optional[ParsedStdInfo]:
        """ITU 推荐号专用匹配。格式: ITU-T G.992.1-1999, ITU-R M.1457-2019。"""
        m = re.match(
            r"(ITU-[TRD])\s+"
            r"([A-Z])"
            r"\.(\d+(?:\.\d+)*)"
            r"(?:[\-]\s*((?:19|20)\d{2}))?",
            text,
            re.IGNORECASE,
        )
        if not m:
            return None
        code = m.group(1).upper()
        series = m.group(2).upper()
        numbers = m.group(3)
        year = int(m.group(4)) if m.group(4) else 0
        remaining = text[m.end() :].strip()
        name = re.sub(r"^[-–—\s]+", "", remaining)
        name = self._parser._clean_std_name(name)
        parts = numbers.split(".")
        number = int(parts[0])
        if not self._parser._validate_result(year, number, code):
            return None
        return ParsedStdInfo(
            raw_filename=text,
            logical_code=code,
            number=number,
            num_prefix=f"{series}.{numbers}",
            part=int(parts[1]) if len(parts) > 1 else None,
            year=year,
            std_name=name,
            source_name=name,
        )

    def _exact_match(self, text: str) -> Optional[ParsedStdInfo]:
        """精确匹配通道：按 regex 解析代号、编号、部分号、年份并构建结果。"""
        match = self.regex.match(text)
        if not match:
            return None
        # 提取各字段并委托解析器的辅助方法处理
        prefix = self._parser._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix, raw_number_str = self._parser._extract_number(num_str)
        if number is None:
            return None
        num_prefix = self._parser._extract_num_prefix(num_str)
        part = self._parser._extract_part(match.group("part"))
        year = self._parser._normalize_year(match.group("year"))
        logical_code = self.code_mapping.get(prefix, prefix)
        return self._parser._build_result(  # type: ignore[no-any-return]
            text, match.end(), logical_code, number, part, year, num_prefix, num_suffix, raw_number=raw_number_str
        )

    def _exact_match_no_year(self, text: str) -> Optional[ParsedStdInfo]:
        """无年份精确匹配——仅接受带字母后缀的修订版标准（如 MIL-STD-810G）。"""
        match = self.regex_no_year.match(text)
        if not match:
            return None
        prefix = self._parser._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix, raw_number_str = self._parser._extract_number(num_str)
        if number is None:
            return None
        if not num_suffix:
            return None
        num_prefix = self._parser._extract_num_prefix(num_str)
        part = self._parser._extract_part(match.group("part"))
        logical_code = self.code_mapping.get(prefix, prefix)
        return self._parser._build_result(  # type: ignore[no-any-return]
            text,
            match.end(),
            logical_code,
            number,
            part,
            0,
            num_prefix,
            num_suffix,
            raw_number=raw_number_str,
            require_year=False,
        )

    def _exact_match_typed(self, text: str) -> Optional[ParsedStdInfo]:
        """带类型前缀的精确匹配通道：先尝试 regex_typed，失败回退到 regex_typed_v2。"""
        match = self.regex_typed.match(text)
        if not match:
            match = self.regex_typed_v2.match(text)  # 回退：无分册号的简化版正则
        if not match:
            return None

        prefix = self._parser._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix, raw_number_str = self._parser._extract_number(num_str)
        if number is None:
            return None
        num_prefix = self._parser._extract_num_prefix(num_str)
        part = self._parser._extract_part(match.group("part"))

        year_str = match.group("year")
        if not year_str:
            year = 0
        else:
            year = self._parser._normalize_year(year_str)

        endorser = match.group("endorser")
        if endorser:
            logical_code = f"{prefix}/{endorser}"
        else:
            logical_code = self.code_mapping.get(prefix, prefix)

        return self._parser._build_result(  # type: ignore[no-any-return]
            text, match.end(), logical_code, number, part, year, num_prefix, num_suffix, raw_number=raw_number_str
        )

    def _fuzzy_match_with_context(self, raw_name: str) -> Optional[ParsedStdInfo]:
        """上下文感知模糊匹配：取最后一个年份 → 找最靠近年份的编号 → 代号验证。"""
        # 1. 找所有候选年份（1900-2099），取最后一个
        year_matches = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", raw_name)
        year_candidates = [
            self._parser._normalize_year(y)
            for y in year_matches
            if 1900 <= self._parser._normalize_year(y) <= 2099
        ]
        if not year_candidates:
            return None
        year = year_candidates[-1]

        str_year = str(year)[-2:] if year < 2000 else str(year)
        year_pos = raw_name.rfind(str_year)
        before_year = raw_name[:year_pos] if year_pos > 0 else raw_name
        order_matches = list(re.finditer(r"(?<!\d)(\d{3,6})(?!\d)", before_year))
        if not order_matches:
            return None
        number = int(max(order_matches, key=lambda m: m.end()).group(1))

        part = None
        part_match = re.search(rf"(?<!\d){re.escape(str(number))}\.(\d{{1,2}})", before_year)
        if part_match:
            part = int(part_match.group(1))

        prefix_match = re.match(r"^[^A-Za-z]*([A-Z]{2,6})", raw_name, re.IGNORECASE)
        if not prefix_match:
            return None
        prefix = prefix_match.group(1).upper()

        logical_code = self.code_mapping.get(prefix, None)
        if logical_code is None:
            slash_variant = re.sub(r"^([A-Z]{2,6})(T)$", r"\1/\2", prefix)
            logical_code = self.code_mapping.get(slash_variant, None)
            if logical_code is None:
                logical_code = prefix

        if not self._parser._validate_result(year, number, logical_code):
            return None

        return ParsedStdInfo(
            raw_filename=raw_name,
            logical_code=logical_code,
            number=number,
            num_prefix="",
            part=part,
            year=year,
            std_name="",
            source_name="",
            file_kind=getattr(self._parser, "_current_file_kind", ""),
        )
