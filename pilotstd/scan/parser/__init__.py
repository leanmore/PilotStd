# 模块：项目/扫描/解析器/____脚本
# 标准文件名解析器 — 按代号分流：国内/国际/国外三路解析

import logging
import os
from typing import Dict, Optional

from ...models import ParsedStdInfo
from ._constants import (
    _EDITION_SKIP,
    _ENDORSER,
    _LANG_DETECTOR,
    _NUM,
    _PART_LONG,
    _PART_SHORT,
    _PFX,
    _ROMAN_MAP,
    _SEP,
    _SEP_LAZY,
    _TYPE,
    _YEAR4,
    _YEAR_DB,
    _YEAR_LOOSE,
    API_TYPES,
    CAC_PREFIXES,
    FOREIGN_CODE_SET,
    IEC_TYPES,
    ISO_IEC_SET,
    ITU_CODES,
    MIL_TYPES,
    PRESERVED_MULTI_WORD,
    SAE_PREFIXES,
    _compile,
)
from ._core import ParserCore
from ._exact_matcher import ExactMatcher
from ._file_kind_detector import FileKindDetector
from ._foreign import _post_process_foreign
from ._language_detector import LanguageDetector
from ._number_extractor import NumberExtractor
from ._result_builder import ResultBuilder
from ._text_cleaner import TextCleaner

logger = logging.getLogger(__name__)


class StandardParser:
    """增强型标准文件名解析器，支持精确匹配和模糊匹配，兼容历史两位年份。

    匹配通道委托给 ExactMatcher（组合注入），辅助方法为 staticmethod 绑定。
    """

    # 静态方法代理（供通过._解析器._()回调）
    _clean = staticmethod(TextCleaner.clean)  # type: ignore[assignment]
    _detect_language = staticmethod(LanguageDetector.detect)  # type: ignore[assignment]
    _detect_file_kind = staticmethod(FileKindDetector.detect)  # type: ignore[assignment]
    _normalize_year = staticmethod(NumberExtractor.normalize_year)  # type: ignore[assignment]
    _extract_number = staticmethod(NumberExtractor.extract_number)  # type: ignore[assignment]
    _extract_num_prefix = staticmethod(NumberExtractor.extract_num_prefix)  # type: ignore[assignment]
    _extract_part = staticmethod(NumberExtractor.extract_part)  # type: ignore[assignment]
    _clean_std_name = staticmethod(ResultBuilder.clean_std_name)  # type: ignore[assignment]
    _validate_result = staticmethod(ResultBuilder.validate_result)  # type: ignore[assignment]

    def __init__(self, code_mapping: Dict[str, str], log: logging.Logger | None = None) -> None:
        """初始化标准解析器。
        Args:
            code_mapping: 标准代号映射表（如 {'GB/T': 'GB/T', 'GBT': 'GB/T'}）
            log: 日志记录器，默认使用模块级 logger
        """
        self.code_mapping = code_mapping
        self.log = log or logger
        self._core = ParserCore(code_mapping, lambda: self._current_file_kind)

        # 精确匹配（带年份）—"接口610-2004","1092.1-2018","9001:2015"
        self.regex = _compile(_PFX, _SEP, _NUM, _PART_SHORT, _EDITION_SKIP, _SEP, _YEAR4)
        # 精确匹配（无年份）—"--810"（字母修订版，无年份）
        self.regex_no_year = _compile(_PFX, _SEP, _NUM, _PART_SHORT)
        # 带类型前缀的精确匹配—"/560-1980","接口6-2023","1234-86"
        self.regex_typed = _compile(
            _PFX,
            _ENDORSER,
            r"(?:\s+|(?:\-))",
            _TYPE,
            _NUM,
            _EDITION_SKIP,
            _SEP_LAZY,
            r"[\-]?",
            _YEAR_LOOSE,
            r"?",
            _PART_LONG,
            _SEP,
        )
        # _回退（无分册号）—当因尾部分册号匹配失败时使用
        self.regex_typed_v2 = _compile(
            _PFX,
            _ENDORSER,
            r"(?:\s+|(?:\-))",
            _TYPE,
            _NUM,
            _EDITION_SKIP,
            _SEP_LAZY,
            r"[\-]?",
            _YEAR_LOOSE,
            r"?",
        )
        # 地方标准—"数据库11/1951-2021","数据库3501/002-2023","数据库50/1982-2026"
        self.regex_db = _compile(
            r"DB\s?(?P<code>\d{2,4})",  # DB + 可选空格 + 2~4位行政区划代码
            r"(?:/(?P<type>T))?",  # 可选 /T 推荐性标识
            _SEP,
            r"(?P<number>\d{2,5})",  # 顺序号 2~5位
            _SEP,
            _YEAR_DB,
        )
        # 组合实例（匹配通道委托）
        self._matcher = ExactMatcher(self)

    # ──实例方法代理（委托，供通过._解析器回调）──

    def _trim_prefix(self, prefix: str, text: str) -> str:
        return self._core.trim_prefix(prefix, text)

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
        raw_number: str = "",
        file_kind: str | None = None,
        require_year: bool = True,
    ) -> Optional[ParsedStdInfo]:
        """委托给 ParserCore 构建 ParsedStdInfo，供 ExactMatcher 内部调用。"""
        return self._core.build_result(
            text,
            match_end,
            logical_code,
            number,
            part,
            year,
            num_prefix,
            num_suffix,
            raw_number,
            file_kind,
            require_year,
        )

    # ──公共接口────────────────────────────────────────────

    def _preprocess_input(self, filename: str) -> tuple[str, str, str, str]:
        """输入规范化：路径→文件名、清理、语言检测、文件属性标记。
        返回 (cleaned, raw_ext, language, basename)。"""
        basename = os.path.splitext(filename)[0]
        raw_ext = os.path.splitext(filename)[1] or ".pdf"
        cleaned = self._clean(basename)
        language = self._detect_language(basename)
        self._current_file_kind = self._detect_file_kind(basename)
        return cleaned, raw_ext, language, basename

    def _enrich_and_finalize(
        self,
        info: ParsedStdInfo | None,
        raw_ext: str,
        language: str,
        filename: str,
        channel: str,
    ) -> ParsedStdInfo | None:
        """补全元数据 + 日志 + 后处理。info 为 None 时直接返回 None。"""
        if info is None:
            return None
        info.ext = raw_ext
        if language:
            info.language = language
        logger.debug("解析: %s -> %s %s (%s)", filename, info.logical_code, info.get_full_number(), channel)
        return self._post_process(info)

    def parse(self, filename: str) -> Optional[ParsedStdInfo]:
        """解析文件名，按标准代号分流到对应解析分支。"""
        cleaned, raw_ext, language, basename = self._preprocess_input(filename)

        channels = [
            (self._matcher._exact_match_db, cleaned, "DB"),
            (self._matcher._exact_match_group, cleaned, "group"),
            (self._matcher._exact_match_bpvc, cleaned, "BPVC"),
            (self._matcher._exact_match_itu, cleaned, "ITU"),
            (self._matcher._exact_match, cleaned, "exact"),
            (self._matcher._exact_match_typed, cleaned, "typed"),
            (self._matcher._fuzzy_match_with_context, basename, "fuzzy"),
            (self._matcher._exact_match_no_year, cleaned, "no_year"),
        ]
        for match_fn, arg, channel in channels:
            result = self._enrich_and_finalize(match_fn(arg), raw_ext, language, filename, channel)
            if result is not None:
                return result

        # TODO(P2): 统一文件解析失败日志格式，补充文件路径/文件类型/错误类型/错误详情
        self.log.info("解析失败: %s", filename)
        return None

    def _classify_code(self, logical_code: str) -> str:
        """按标准代号返回分类: domestic / iso_iec / foreign / unknown。
        内部委托 classify_std_code()，再做返回值映射。"""
        from ...core.std_utils import classify_std_code

        # 带类型前缀（/类型脚本/）按国外标准处理，触发___修正
        parts = logical_code.split()
        if len(parts) > 1 and parts[0].upper() == "IEC" and parts[1].upper() in IEC_TYPES:
            return "foreign"

        cat = classify_std_code(logical_code)
        if cat in ("gb", "industry", "db"):
            return "domestic"
        if cat == "iso_iec":
            return "iso_iec"
        if cat == "foreign":
            return "foreign"
        return "unknown"

    def _post_process(self, info: ParsedStdInfo) -> ParsedStdInfo:
        """根据代号分类做定向后处理。"""
        family = self._classify_code(info.logical_code)
        if family == "domestic":
            info.num_prefix = ""
            info.language = ""  # 国内标准不标语言版本
        elif family == "iso_iec":
            pass  # ISO/IEC 保留语言标记
        elif family == "foreign":
            if not info.language:  # parse() 入口未识别到时再尝试
                info.language = self._detect_language(info.raw_filename)
            _post_process_foreign(info)
        return info


__all__ = [
    "StandardParser",
    "PRESERVED_MULTI_WORD",
    "FOREIGN_CODE_SET",
    "ISO_IEC_SET",
    "ITU_CODES",
    "CAC_PREFIXES",
    "API_TYPES",
    "IEC_TYPES",
    "MIL_TYPES",
    "SAE_PREFIXES",
    "_ROMAN_MAP",
    "_LANG_DETECTOR",
]
