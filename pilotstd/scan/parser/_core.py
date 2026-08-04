# 模块：解析器核心组合容器
"""解析核心 —— 持有五个子处理器实例，对外暴露统一快捷方法。"""

from typing import Callable, Optional

from ...models import ParsedStdInfo
from ._file_kind_detector import FileKindDetector
from ._language_detector import LanguageDetector
from ._number_extractor import NumberExtractor
from ._result_builder import ResultBuilder
from ._text_cleaner import TextCleaner


class ParserCore:
    """解析器核心 —— 组合五个子处理器，暴露与原有混入类兼容的快捷方法。

    初始化要求：
      - 标准代号映射表：用于前缀截断和代号标准化
      - 文件类别提供器：无参回调，返回当前文件对应的文件类别
    """

    def __init__(
        self,
        code_mapping: dict,
        file_kind_provider: Callable[[], str],
    ) -> None:
        self.text_cleaner = TextCleaner()
        self.language_detector = LanguageDetector()
        self.file_kind_detector = FileKindDetector()
        self.number_extractor = NumberExtractor()
        self.result_builder = ResultBuilder(code_mapping, file_kind_provider)

    # ── 文本清洗 ────────────────────────────────────────────

    def clean(self, text: str) -> str:
        return self.text_cleaner.clean(text)

    # ── 语言检测 ────────────────────────────────────────────

    def detect_language(self, basename: str) -> str:
        return self.language_detector.detect(basename)

    # ── 文件属性标记 ────────────────────────────────────────

    def detect_file_kind(self, basename: str) -> str:
        return self.file_kind_detector.detect(basename)

    # ── 数字提取 ────────────────────────────────────────────

    def normalize_year(self, year_str: str) -> int:
        return self.number_extractor.normalize_year(year_str)

    def extract_number(self, number_str: str) -> tuple[Optional[int], str, str]:
        return self.number_extractor.extract_number(number_str)

    def extract_num_prefix(self, number_str: str) -> str:
        return self.number_extractor.extract_num_prefix(number_str)

    def extract_part(self, part_str: Optional[str]) -> Optional[int]:
        return self.number_extractor.extract_part(part_str)

    # ── 结果构建 ────────────────────────────────────────────

    def trim_prefix(self, prefix: str, text: str) -> str:
        return self.result_builder.trim_prefix(prefix, text)

    def clean_std_name(self, name: str) -> str:
        return self.result_builder.clean_std_name(name)

    def validate_result(
        self,
        year: int,
        number: int,
        logical_code: str,
        require_year: bool = True,
    ) -> bool:
        """委托结果构建器校验年份、编号、代号合法性。"""
        return self.result_builder.validate_result(year, number, logical_code, require_year)

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
        """委托结果构建器构造完整的已解析标准信息对象。"""
        return self.result_builder.build_result(
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
