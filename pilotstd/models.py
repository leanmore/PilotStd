# 模块：项目/模型脚本
# 通用数据模型，供各模块共享
# 设计决策：而非（生命周期独立）、()+_()双字段（避免信息丢失）、
# _字符串枚举而非关联表（状态机固定，查询频率远高于定义变更频率）

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ParsedStdInfo:
    """解析后的标准信息"""

    raw_filename: str
    logical_code: str  # 如 GB/T, SH/T
    number: int  # 顺序号（纯数字部分，int 类型保持现有语义）
    year: int  # 四位年份
    raw_number: str = ""  # 原始数字字符串（保留前导零，如 "01"，仅用于展示/文件名）
    num_prefix: str = ""  # 编号字母前缀（如 ASME B16.5 中的 "B"，API RP 中的 "RP"）
    num_suffix: str = ""  # 编号字母后缀（如 API 6D 中的 "D"）
    part: Optional[int] = None  # 部分号
    std_name: str = ""  # 标准名称（扫描时从文件名提取，不被网站结果覆盖）
    ext: str = ".pdf"  # 源文件扩展名（parse() 入口获取，不再丢弃）
    language: str = ""  # 语言版本标记（仅国外标准）："中文版"/"英文版"/""
    found_name: str = ""  # 网站返回的标准名称（查询后填充）
    source_name: str = ""  # 源文件原始名称（解析时从文件名提取，不被任何后处理覆盖）
    normalized_name: str = ""  # 规范化中间值（自动格式化处理后的名称）
    final_name: str = ""  # 最终归档名称（路由阶段决策后写入，用户确认或系统自动选定）
    source_path: str = ""  # 源文件完整路径（扫描/下载后填充）
    effect_status: str = ""  # 有效性状态（查询后填充：现行/废止/即将实施/待确认/被代替）
    is_adopted: bool = False  # 是否采标（查询后填充）
    replaced_by: str = ""  # 被代替时的新标准编号（查询后填充）
    found_replaces: str = ""  # 网站返回的替代标准编号（查询后填充，用于路由判断是否需下载新版）
    split_parts: str = ""  # 多部分拆分时，逗号分隔的部分编号列表
    found_publish_date: str = ""  # 网站返回的发布日期（查询后填充）
    found_impl_date: str = ""  # 网站返回的实施日期（查询后填充）
    found_responsible_dept: str = ""  # 网站返回的归口单位（查询后填充）
    found_abolition_date: str = ""  # 网站返回的废止日期（查询后填充）
    next_action: str = ""  # 下一步动作（分类后填充：archive/normalize/expire/pending）
    match_status: str = ""  # 原始匹配状态（查询后填充：exact/newer/older/code_only/mismatch）
    found_source_site: str = ""  # 查询结果来源站点（查询后填充，供下载阶段路由）
    stage_status: str = ""  # 分类后所处阶段：download/expired/pending/archive_ready（分类后填充）
    file_kind: str = ""  # 文件属性标签：扫描版/扫描件/水印版/文本版（解析时从文件名提取）

    def get_full_number(self) -> str:
        """生成逻辑标准编号，如 GB/T 12345.1-2020、ASME VIII.1-2021、API Spec 6D-2021"""
        part_str = f".{self.part}" if self.part else ""
        prefix = self.num_prefix or ""
        suffix = self.num_suffix or ""
        year_str = f"-{self.year}" if self.year else ""
        num_display = self.raw_number or str(self.number)
        if prefix and len(prefix) >= 2 and all(c in "IVXLCDM" for c in prefix.upper()):
            return f"{self.logical_code} {prefix}{suffix}{part_str}{year_str}"
        sep = " " if len(prefix) > 1 and prefix.isalpha() else ""
        return f"{self.logical_code} {prefix}{sep}{num_display}{suffix}{part_str}{year_str}"

    @property
    def is_valid_standard(self) -> bool:
        """是否可识别为有效标准号（有代号、有顺序号、有年份）。"""
        return bool(self.logical_code and self.number > 0 and self.year > 0)


@dataclass
class FileInfo:
    """文件信息（扫描阶段初步信息）"""

    full_path: str
    filename: str
    size: int
    mtime: float
    parsed_info: Optional[ParsedStdInfo] = None
    status: str = "pending"  # pending, success, error, skipped


@dataclass
class ScanStats:
    """扫描统计"""

    total: int = 0
    success: int = 0
    error: int = 0
    skipped: int = 0


class ScanResult:
    """扫描结果容器"""

    def __init__(self) -> None:
        """初始化扫描结果容器，创建空的文件列表和统计。"""
        self.files: List[FileInfo] = []
        self.warnings: List[str] = []
        self.skipped_dirs: List[str] = []  # 被关键词排除的目录路径（后续原样归档）
        self.stats = ScanStats()

    def add_file(self, file: FileInfo) -> None:
        """添加一个文件到扫描结果，同时更新计数统计。"""
        self.files.append(file)
        self.stats.total += 1

    def add_warning(self, msg: str) -> None:
        """添加一条警告信息到扫描结果。"""
        self.warnings.append(msg)
