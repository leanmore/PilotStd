# pilotstd/scan/parser/_exact.py
# 标准解析器精确匹配混入模块
"""精确匹配 + 模糊匹配方法。"""

import re
from typing import Optional, Pattern

from ...models import ParsedStdInfo
from ._constants import _ASME_BPVC_RE, _ROMAN_MAP


class ExactMatchMixin:
    """精确匹配混入类 — 提供 7 个匹配通道。

    以下属性和方法由 StandardParser 在运行时通过多重继承注入，
    此处声明仅用于通过 mypy 静态检查。
    """

    # 正则表达式（由 StandardParser.__init__ 初始化）
    regex: Pattern[str]
    regex_no_year: Pattern[str]
    regex_typed: Pattern[str]
    regex_typed_v2: Pattern[str]
    regex_db: Pattern[str]
    # 标准代号映射表（由 StandardParser 注入）
    code_mapping: dict

    def _normalize_year(self, year_str: str) -> int:
        raise NotImplementedError

    def _extract_number(self, number_str: str) -> tuple[Optional[int], str]:
        raise NotImplementedError

    def _extract_num_prefix(self, number_str: str) -> str:
        raise NotImplementedError

    def _extract_part(self, part_str: Optional[str]) -> Optional[int]:
        raise NotImplementedError

    def _clean_std_name(self, name: str) -> str:
        raise NotImplementedError

    def _validate_result(self, year: int, number: int, logical_code: str, require_year: bool = True) -> bool:
        raise NotImplementedError

    def _trim_prefix(self, prefix: str, text: str) -> str:
        raise NotImplementedError

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
        """占位声明：具体实现由 StandardParser 通过 MRO 注入（ParserCore.build_result）。"""
        raise NotImplementedError

    # ── 精确匹配通道 ────────────────────────────────────────

    def _exact_match_db(self, text: str) -> Optional[ParsedStdInfo]:
        """地方标准专用匹配：DB + 行政区划代码 + 顺序号 + 年份。"""
        m = self.regex_db.match(text)
        if not m:
            return None
        prefix = m.group("prefix")  # DB11, DB3501
        std_type = m.group("type")  # T 或 None
        logical_code = f"{prefix}/{std_type}" if std_type else prefix
        number_str = m.group("number")
        try:
            number = int(number_str)
        except ValueError:
            return None
        year = self._normalize_year(m.group("year")) if m.group("year") else 0
        remaining = text[m.end() :].strip()
        name = re.sub(r"^[-–—\s]+", "", remaining)
        name = self._clean_std_name(name)  # 剥离语种/版次标记，避免归档时重复叠加
        # 自查校验
        if not self._validate_result(year, number, logical_code):
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
        """ASME BPVC 罗马数字卷号专用匹配。标准正则需要数字，无法处理 IX/VIII 等。"""
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
        name = self._clean_std_name(name)  # 剥离语种/版次标记，避免归档时重复叠加
        # 自查校验
        if not self._validate_result(year, vol_num, "ASME"):
            return None
        return ParsedStdInfo(
            raw_filename=text,
            logical_code="ASME",  # BPVC 是分类标签，不改变标准代号
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
            r"(ITU-[TRD])\s+"  # ITU 系列代号
            r"([A-Z])"  # 系列字母 (G/M/F 等)
            r"\.(\d+(?:\.\d+)*)"  # 推荐号（支持点号层级如 G.992.1）
            r"(?:[\-]\s*((?:19|20)\d{2}))?",  # 年份（可选）
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
        name = self._clean_std_name(name)
        # 编号：取点号分隔的第一段为 number，完整推荐号为 num_prefix
        parts = numbers.split(".")
        number = int(parts[0])
        # 自查校验
        if not self._validate_result(year, number, code):
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
        prefix = self._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix, raw_number_str = self._extract_number(num_str)
        if number is None:
            return None
        num_prefix = self._extract_num_prefix(num_str)
        part = self._extract_part(match.group("part"))
        year = self._normalize_year(match.group("year"))
        logical_code = self.code_mapping.get(prefix, prefix)
        return self._build_result(
            text, match.end(), logical_code, number, part, year, num_prefix, num_suffix, raw_number=raw_number_str
        )

    def _exact_match_no_year(self, text: str) -> Optional[ParsedStdInfo]:
        """无年份精确匹配——仅接受带字母后缀的修订版标准（如 MIL-STD-810G）。

        设计意图：此路径是解析的最后兜底，不能接受所有无年份文件（否则表单模板、
        无版本标识的文件名都会被误解析）。只接受编号末尾带字母后缀的，字母后缀
        表示修订版次（如 810G 的 G），此类标准本身没有独立的年份字段。
        """
        match = self.regex_no_year.match(text)
        if not match:
            return None
        prefix = self._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix, raw_number_str = self._extract_number(num_str)
        if number is None:
            return None
        # 仅接受有字母后缀的修订版（如 810G），拒绝无版本标识的裸编号
        if not num_suffix:
            return None
        num_prefix = self._extract_num_prefix(num_str)
        part = self._extract_part(match.group("part"))
        logical_code = self.code_mapping.get(prefix, prefix)
        # require_year=False：字母修订版无年份，跳过年份校验
        return self._build_result(
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
            match = self.regex_typed_v2.match(text)
        if not match:
            return None

        prefix = self._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix, raw_number_str = self._extract_number(num_str)
        if number is None:
            return None
        num_prefix = self._extract_num_prefix(num_str)
        part = self._extract_part(match.group("part"))

        year_str = match.group("year")
        if not year_str:
            year = 0
        else:
            year = self._normalize_year(year_str)

        endorser = match.group("endorser")
        if endorser:
            logical_code = f"{prefix}/{endorser}"
        else:
            logical_code = self.code_mapping.get(prefix, prefix)

        return self._build_result(
            text, match.end(), logical_code, number, part, year, num_prefix, num_suffix, raw_number=raw_number_str
        )

    # ── 模糊匹配 ────────────────────────────────────────────

    def _fuzzy_match_with_context(self, raw_name: str) -> Optional[ParsedStdInfo]:
        """上下文感知模糊匹配：取最后一个年份 → 找最靠近年份的编号 → 代号验证。"""
        # 1. 找所有候选年份（1900-2099），取最后一个（实际文件名中年份通常靠后）
        year_matches = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", raw_name)
        year_candidates = [self._normalize_year(y) for y in year_matches if 1900 <= self._normalize_year(y) <= 2099]
        if not year_candidates:
            return None
        year = year_candidates[-1]  # 取最后一个年份

        # 2. 在年份之前的文本中找编号（3-6 位数字），取最靠近年份的那个
        str_year = str(year)[-2:] if year < 2000 else str(year)
        # 用 rfind 定位年份最后一次出现的位置
        year_pos = raw_name.rfind(str_year)
        before_year = raw_name[:year_pos] if year_pos > 0 else raw_name
        order_matches = list(re.finditer(r"(?<!\d)(\d{3,6})(?!\d)", before_year))
        if not order_matches:
            return None
        # 取最靠近年份的编号（end 位置最大的）
        number = int(max(order_matches, key=lambda m: m.end()).group(1))

        # 3. 提取部分号
        part = None
        part_match = re.search(rf"(?<!\d){re.escape(str(number))}\.(\d{{1,2}})", before_year)
        if part_match:
            part = int(part_match.group(1))

        # 4. 从文件名开头提取字母组合，对照 code_mapping 验证
        prefix_match = re.match(r"^[^A-Za-z]*([A-Z]{2,6})", raw_name, re.IGNORECASE)
        if not prefix_match:
            return None
        prefix = prefix_match.group(1).upper()

        # 尝试还原缺斜杠的代号（如 DB35T → DB35/T），查 code_mapping
        logical_code = self.code_mapping.get(prefix, None)
        if logical_code is None:
            # 尝试加 /T 变体：DB35T → DB35/T, SHT → SH/T, GBT → GB/T
            slash_variant = re.sub(r"^([A-Z]{2,6})(T)$", r"\1/\2", prefix)
            logical_code = self.code_mapping.get(slash_variant, None)
            if logical_code is None:
                # 仍不匹配则用原前缀
                logical_code = prefix

        # 自查校验
        if not self._validate_result(year, number, logical_code):
            return None

        return ParsedStdInfo(
            raw_filename=raw_name,
            logical_code=logical_code,
            number=number,
            num_prefix="",
            part=part,
            year=year,
            std_name="",
            source_name="",  # 模糊匹配无法可靠提取名称
            file_kind=getattr(self, "_current_file_kind", ""),
        )
