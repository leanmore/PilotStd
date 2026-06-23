# pilotstd/scan/parser.py
# 标准文件名解析器 — 按代号分流：国内/国际/国外三路解析

import logging
import os
import re
from typing import Dict, Optional

from ..core.file_utils import normalize_std_filename
from ..models import ParsedStdInfo
from .edition_detect import edition_skip_pattern
from .lang_detect import detect_language

logger = logging.getLogger(__name__)

# 需保留的多段前缀（不拆分首段）
PRESERVED_MULTI_WORD = frozenset(
    {
        "BS EN",
        "BS EN ISO",
        "DIN EN",
        "DIN EN ISO",
        "NF EN",
        # IEC 类型前缀（不可被 _normalize_prefix 拆分）
        "IEC TR",
        "IEC TS",
        "IEC PAS",
        # 国外标准代号+分类字母（不可拆分）
        "ASTM A",
        "ASTM B",
        "ASTM C",
        "ASTM D",
        "ASTM E",
        "ASTM F",
        "ASTM G",
        "JIS A",
        "JIS B",
        "JIS C",
        "JIS D",
        "JIS E",
        "JIS F",
        "JIS G",
        "JIS H",
        "JIS K",
        "JIS L",
        "JIS M",
        "JIS P",
        "JIS Q",
        "JIS R",
        "JIS S",
        "JIS T",
        "JIS W",
        "JIS X",
        "JIS Z",
        "CSA C",
        "CSA Z",
        "NF C",
        "NF L",
        "NF Z",
        "AWWA B",
        "AWWA C",
        "AWWA D",
        "AWWA E",
        "AWWA F",
        "AWWA G",
    }
)
# ── 国外代号集合 ────────────────────────────────────────────
# 用于分类路由：识别为国外标准后走专门解析分支
FOREIGN_CODE_SET = frozenset(
    {
        "API",
        "ANSI",
        "AS",
        "ASME",
        "ASTM",
        "AWWA",
        "BS",
        "CAC",
        "CSA",
        "DIN",
        "EN",
        "GOST",
        "IEEE",
        "ITU",
        "JIS",
        "KS",
        "MIL",
        "MSS",
        "NF",
        "NFPA",
        "SAE",
        "SANS",
        "UL",
        "UNE",
    }
)
# ISO/IEC 单独处理（冒号年份+类型前缀）
ISO_IEC_SET = frozenset({"ISO", "IEC"})
# ITU 系列代码（ITU-T 等）
ITU_CODES = frozenset({"ITU-T", "ITU-R", "ITU-D"})
# CAC 多前缀
CAC_PREFIXES = frozenset({"Codex Stan", "CXS", "CXA", "CXP", "CXG", "CAC"})
# API 类型前缀（含 Bull/Publ/TR 等文档类型）
API_TYPES = frozenset({"Spec", "Std", "RP", "MPMS", "Bull", "Publ", "TR", "TDB"})
# IEC 类型前缀
IEC_TYPES = frozenset({"TR", "TS", "PAS"})
# MIL 类型
MIL_TYPES = frozenset({"STD", "DTL", "HDBK", "PRF"})
# SAE 技术前缀
SAE_PREFIXES = frozenset({"J", "ARP", "AMS"})
# ASME BPVC 罗马数字卷号映射（不转换，仅用于 number 排序值）
_ROMAN_MAP = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
}
_ASME_BPVC_RE = re.compile(
    r"^ASME\s+(?:BPVC[\.\-\s]*)?"  # BPVC 可选（兼容 ASME IX-2021）
    r"([IVXLCDM]+)"  # 卷号（罗马数字）
    r"(?:[\.\-](\d{1,2})(?=[\-]\d{4}))?"  # 子分册（仅当后面还有-年份时匹配）
    r"(?:[\-](\d{4}))?",  # 年份（4位数字）
    re.IGNORECASE,
)

# ── 正则原子构件 ────────────────────────────────────────────
# 各正则共享的子模式，定义为模块级常量以便独立测试和复用
_PFX = r"(?P<prefix>(?:ITU-[TRD])|[A-Z]{2,}(?:[\-\s]+[A-Z]{2,})*(?:/[A-Z]+)?)"  # 标准代号段（如 "BS EN", "ITU-T", "ANSI/UL"）  # noqa: E501
_NUM = r"(?P<number>[A-Z]?\d{1,6}[A-Z]?)"  # 编号（支持字母后缀如 API 6D）
_PART_SHORT = r"(?:[\.\-](?P<part>\d{1,2}))?"  # 短分册号（1-2位纯数字）
_PART_LONG = r"(?:[\.\-](?P<part>[A-Z]?\d{1,3}))?"  # 长分册号（可含前导字母，如 B16）
_YEAR4 = r"(?P<year>(?:19|20)\d{2})"  # 四位年份
_YEAR_LOOSE = r"(?P<year>(?:19|20)\d{2}|\d{2})"  # 宽年份（兼容两位年份）
_YEAR_DB = r"(?:[\-]?(?P<year>(?:19|20)\d{2}))"  # 地方标准年份（必需）
_SEP = r"[\s\.\-\+]{0,10}"  # 分隔符（限制最大10字符防回溯爆炸）
_SEP_LAZY = r"[\s\.\-\+]*?"  # 懒惰分隔符
# 版次跳过：N版 / 第N版 / Nth Edition / TENTH EDITION（来自 edition_detect 模块）
_EDITION_SKIP = edition_skip_pattern()
# endorser + type 前缀（regex_typed 系列共用）
_ENDORSER = r"(?:/(?P<endorser>[A-Z]{2,}))?"  # 背书者（如 ANSI/UL）
_TYPE = r"(?:(?P<type>[A-Z]{2,})(?:\s+|\-))?"  # 类型前缀（如 API Spec）


def _compile(*parts: str) -> re.Pattern[str]:
    """组装正则原子构件为编译后的 Pattern。"""
    return re.compile("".join(parts), re.IGNORECASE)


# 语言版本标记识别 — 委托 lang_detect 模块（parser + 归档规则共用）
_LANG_DETECTOR = detect_language  # 函数引用，保持向后兼容

# 国外代号→分组路由（6组）
_FOREIGN_GROUP_MAP = {
    # 组1: 纯序号型 — 无需后处理，正则可正确提取全部字段
    "UL": "pure_numeric",
    "AS": "pure_numeric",
    "KS": "pure_numeric",
    "SANS": "pure_numeric",
    "UNE": "pure_numeric",
    "IEEE": "pure_numeric",
    "NFPA": "pure_numeric",
    # 组2: 字母分类型 — 从 raw 提取分类字母 → num_prefix
    "ASTM": "letter_class",
    "JIS": "letter_class",
    "CSA": "letter_class",
    "AWWA": "letter_class",
    "NF": "letter_class",
    # 组3: 类型前缀型 — 从 raw 提取类型标识 → num_prefix
    "API": "type_prefix",
    "MIL": "type_prefix",
    "SAE": "type_prefix",
    "MSS": "type_prefix",
    "IEC": "type_prefix",
    # 组4: 多段前缀型 — PRESERVED_MULTI_WORD 已保留，无需后处理
    "BS": "multi_prefix",
    "DIN": "multi_prefix",
    "EN": "multi_prefix",
    # 组5: 特殊分隔符型 — GOST(点号) + ASME(BPVC罗马数字)
    "GOST": "special_sep",
    "ASME": "special_sep",
    # 组6: 独特体系 — 各一个 mini-handler
    "ANSI": "unique",
    "CAC": "unique",
    "ITU": "unique",
}


class StandardParser:
    """增强型标准文件名解析器，支持精确匹配和模糊匹配，兼容历史两位年份"""

    def __init__(self, code_mapping: Dict[str, str], log: logging.Logger | None = None) -> None:
        self.code_mapping = code_mapping
        self.log = log or logger

        # 精确匹配（带年份） — "API 610-2004", "BS EN 1092.1-2018", "ISO 9001:2015"
        self.regex = _compile(_PFX, _SEP, _NUM, _PART_SHORT, _EDITION_SKIP, _SEP, _YEAR4)
        # 精确匹配（无年份） — "MIL-STD-810G"（字母修订版，无年份）
        self.regex_no_year = _compile(_PFX, _SEP, _NUM, _PART_SHORT)
        # 带类型前缀的精确匹配 — "ANSI/UL 560-1980", "API Spec 6A-2023", "GB 1234-86"
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
        # regex_typed 回退（无分册号） — 当 typed 因尾部分册号匹配失败时使用
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
        # 地方标准 — "DB11/T 1951-2021", "DB3501/T 002-2023"
        self.regex_db = _compile(
            r"(?P<prefix>DB\d{2,4})",  # DB + 2~4位行政区划代码
            r"(?:/(?P<type>T))?",  # 可选 /T 推荐性标识
            _SEP,
            r"(?P<number>\d{2,5})",  # 顺序号 2~5位
            _SEP,
            _YEAR_DB,
        )

    # ── 公共 API ────────────────────────────────────────────

    def parse(self, filename: str) -> Optional[ParsedStdInfo]:
        """解析文件名，按标准代号分流到对应解析分支。"""
        basename = os.path.splitext(filename)[0]
        raw_ext = os.path.splitext(filename)[1] or ".pdf"  # 不再丢弃扩展名
        cleaned = self._clean(basename)
        # 语言标记从原始 basename 识别（_clean 之前，保留括号结构）
        language = self._detect_language(basename)
        # 文件属性标签：扫描版/扫描件/水印版/文本版
        self._current_file_kind = self._detect_file_kind(basename)

        # 地方标准：DB + 行政区划代码，数字前缀正则无法处理，提前匹配
        info = self._exact_match_db(cleaned)
        if info:
            info.ext = raw_ext
            if language:
                info.language = language
            logger.debug(
                "解析: %s -> %s %s (DB)",
                filename,
                info.logical_code,
                info.get_full_number(),
            )
            return self._post_process(info)
        # ASME BPVC 罗马数字卷号：正则 \d{1,6} 无法匹配 IX/VIII 等，提前处理
        info = self._exact_match_bpvc(cleaned)
        if info:
            info.ext = raw_ext
            if language:
                info.language = language
            logger.debug(
                "解析: %s -> %s %s (BPVC)",
                filename,
                info.logical_code,
                info.get_full_number(),
            )
            return self._post_process(info)
        # ITU 推荐号格式 G.992.1 / M.1457，正则 \d{1,6} 无法匹配含点号编号
        info = self._exact_match_itu(cleaned)
        if info:
            info.ext = raw_ext
            if language:
                info.language = language
            logger.debug(
                "解析: %s -> %s %s (ITU)",
                filename,
                info.logical_code,
                info.get_full_number(),
            )
            return self._post_process(info)
        info = self._exact_match(cleaned)
        if info:
            info.ext = raw_ext
            if language:
                info.language = language
            logger.debug(
                "解析: %s -> %s %s (exact)",
                filename,
                info.logical_code,
                info.get_full_number(),
            )
            return self._post_process(info)
        info = self._exact_match_typed(cleaned)
        if info:
            info.ext = raw_ext
            if language:
                info.language = language
            logger.debug(
                "解析: %s -> %s %s (typed)",
                filename,
                info.logical_code,
                info.get_full_number(),
            )
            return self._post_process(info)
        info = self._fuzzy_match_with_context(basename)
        if info:
            info.ext = raw_ext
            if language:
                info.language = language
            logger.debug(
                "解析: %s -> %s %s (fuzzy)",
                filename,
                info.logical_code,
                info.get_full_number(),
            )
            return self._post_process(info)
        info = self._exact_match_no_year(cleaned)
        if info:
            info.ext = raw_ext
            if language:
                info.language = language
            logger.debug(
                "解析: %s -> %s %s (no_year)",
                filename,
                info.logical_code,
                info.get_full_number(),
            )
            return self._post_process(info)

        self.log.info("解析失败: %s", filename)
        return None

    def _classify_code(self, logical_code: str) -> str:
        """按标准代号返回分类: domestic / iso_iec / foreign / unknown。
        内部委托 classify_std_code()，再做返回值映射。"""
        from ..core.std_utils import classify_std_code

        # IEC 带类型前缀（TR/TS/PAS）按国外标准处理，触发 _handle_type_prefix 修正
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
            self._post_process_foreign(info)
        return info

    def _post_process_foreign(self, info: ParsedStdInfo) -> None:
        """国外标准定向后处理，按分组路由到对应 handler。"""
        raw = info.raw_filename
        base_code = info.logical_code.split()[0].upper()  # 取首段（如 "ASME BPVC"→"ASME"）
        group = _FOREIGN_GROUP_MAP.get(base_code)
        if group is None:
            return
        self._dispatch_foreign_handler(info, raw, group)

    def _dispatch_foreign_handler(self, info: ParsedStdInfo, raw: str, group: str) -> None:
        """按组路由到对应 handler，组1/组4 无需处理直接返回。"""
        if group == "letter_class":
            self._handle_letter_class(info, raw)
        elif group == "type_prefix":
            self._handle_type_prefix(info, raw)
        elif group == "special_sep":
            self._handle_special_sep(info, raw)
        elif group == "unique":
            self._handle_unique(info, raw)
        # pure_numeric / multi_prefix：无需后处理

    def _handle_letter_class(self, info: ParsedStdInfo, raw: str) -> None:
        """组2: 字母分类型 — 从原始文件名提取分类字母 → num_prefix。"""
        code = info.logical_code.upper()

        if code.startswith("ASTM"):
            m = re.search(r"\bASTM\s+([A-G])\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1).upper()

        elif code.startswith("JIS"):
            m = re.search(r"\bJIS\s+([A-Z])\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1).upper()

        elif code.startswith("CSA"):
            m = re.search(r"\bCSA\s+([A-Z])\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1).upper()

        elif code.startswith("AWWA"):
            m = re.search(r"\bAWWA\s+([A-G])\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1).upper()

        elif code.startswith("NF"):
            m = re.search(r"\bNF\s+([A-Z])\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1).upper()

    def _handle_type_prefix(self, info: ParsedStdInfo, raw: str) -> None:
        """组3: 类型前缀型 — 从原始文件名提取类型标识 → num_prefix。"""
        code = info.logical_code.upper()

        if code.startswith("API"):
            m = re.search(rf"(?<=\bAPI\s)({'|'.join(API_TYPES)})\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1)

        elif code.startswith("MSS"):
            if re.search(r"\bMSS\s+SP\b", raw, re.IGNORECASE):
                info.num_prefix = "SP"

        elif code.startswith("MIL"):
            m = re.search(rf"\bMIL[-\s]({'|'.join(MIL_TYPES)})\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1)

        elif code.startswith("SAE"):
            m = re.search(rf"\bSAE\s+({'|'.join(SAE_PREFIXES)})\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1)

        elif code.startswith("IEC"):
            m = re.search(rf"\bIEC\s+({'|'.join(IEC_TYPES)})\b", raw, re.IGNORECASE)
            if m:
                info.num_prefix = m.group(1)
                info.logical_code = "IEC"  # 从 "IEC TR" 修正为 "IEC"

    def _handle_special_sep(self, info: ParsedStdInfo, raw: str) -> None:
        """组5: 特殊分隔符型 — GOST(点号数字) + ASME(BPVC罗马数字卷号)。"""
        code = info.logical_code.upper()

        if code.startswith("GOST"):
            m = re.search(r"\bGOST\s*(?:R\s+)?(?:ISO\s+)?(\d+(?:\.\d+)+)", raw, re.IGNORECASE)
            if m:
                parts = m.group(1).split(".")
                if len(parts) >= 3:
                    # 三段格式: GOST 8.417.2 → 类别.顺序号.子编号
                    info.num_prefix = parts[0]
                    info.number = int(parts[1])
                    info.part = int(parts[2])
                else:
                    # 两段格式: GOST R 52857.1 → 顺序号.部分号（不要覆盖 num_prefix）
                    info.number = int(parts[0])
                    info.part = int(parts[1])
            # 年份：紧跟点号数字后的 -年份
            ym = re.search(r"[\-]\s*((?:19|20)\d{2})\b", raw)
            if ym:
                info.year = int(ym.group(1))

        elif code.startswith("ASME"):
            # BPVC 罗马数字卷号由 _exact_match_bpvc 在 post_process 之前处理
            # 此处仅处理非 BPVC 的 ASME 标准，当前无需额外后处理
            pass

    def _handle_unique(self, info: ParsedStdInfo, raw: str) -> None:
        """组6: 独特体系 — ANSI(双重署名, 无需后处理) + CAC(文本前缀) + ITU(部门后缀+点号编号)。"""
        code = info.logical_code.upper()

        if code.startswith("ANSI"):
            # 双重署名由 regex_typed 的 endorser 捕获组处理，无需后处理
            return

        if code.startswith("CAC"):
            # 尝试匹配 CAC 特殊前缀（Codex Stan/CXS/CXA/CXP/CXG/CAC）
            for cac_pfx in CAC_PREFIXES:
                if cac_pfx.upper() in raw.upper():
                    info.logical_code = cac_pfx
                    break

        elif code.startswith("ITU"):
            # ITU-T/R/D 部门后缀已在 logical_code 中保留
            # 尝试从 raw 补全年份（若无）
            if info.year == 0:
                ym = re.search(r"[\-]\s*((?:19|20)\d{2})\b", raw)
                if ym:
                    info.year = int(ym.group(1))

    # ── 文本清洗 ────────────────────────────────────────────

    def _clean(self, text: str) -> str:
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
        match = self.regex.match(text)
        if not match:
            return None
        prefix = self._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix = self._extract_number(num_str)
        if number is None:
            return None
        num_prefix = self._extract_num_prefix(num_str)
        part = self._extract_part(match.group("part"))
        year = self._normalize_year(match.group("year"))
        logical_code = self.code_mapping.get(prefix, prefix)
        return self._build_result(text, match.end(), logical_code, number, part, year, num_prefix, num_suffix)

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
        number, num_suffix = self._extract_number(num_str)
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
            require_year=False,
        )

    def _exact_match_typed(self, text: str) -> Optional[ParsedStdInfo]:
        match = self.regex_typed.match(text)
        if not match:
            match = self.regex_typed_v2.match(text)
        if not match:
            return None

        prefix = self._trim_prefix(match.group("prefix"), text)
        num_str = match.group("number")
        number, num_suffix = self._extract_number(num_str)
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

        return self._build_result(text, match.end(), logical_code, number, part, year, num_prefix, num_suffix)

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
