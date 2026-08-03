# pilotstd/query/models.py
# 查询结果数据模型

from dataclasses import dataclass
from datetime import datetime


@dataclass
class QueryResult:
    """单个标准的查询结果"""

    standard_number: str  # 标准完整编号，如 GB/T 19001—2020
    standard_name: str = ""  # 标准名称
    status: str = ""  # 现行 / 废止 / 即将实施 / 未知
    replaces: str = ""  # 代替标准
    implementation_date: str = ""  # 实施日期
    responsible_dept: str = ""  # 归口单位（适配器有数据时覆盖）
    is_adopted: bool = False  # 是否采标（True 时 UI 显示"采标"）
    match_status: str = ""  # 原始匹配状态（exact/newer/older/code_only/mismatch）
    source_site: str = ""  # 来源网站标识
    source: str = ""  # 数据来源标注：web端公告缓存 / live_fallback / 空=本地适配器
    publish_date: str = ""  # 发布日期
    abolition_date: str = "网站无此分类"  # 废止日期
    hcno: str = ""  # 标准唯一ID（新平台 hcno = std_gov 查询结果的 pid，
    # 直接用于下载，无需额外搜索步骤）
    split_into: str = ""  # 多部分拆分时，逗号分隔的部分编号列表

    is_downloadable: bool = True  # 是否可下载（采标标准不可下载）
    error_message: str = ""  # 查询失败时的错误信息

    def is_found(self) -> bool:
        """查询结果是否有效。
        契约：standard_name 非空 且 error_message 为空。
        构造 QueryResult 时若遗漏 standard_name，此方法返回 False。"""
        return bool(self.standard_name) and not self.error_message


@dataclass
class BatchQueryStats:
    """批量查询统计"""

    total: int = 0
    found: int = 0
    downloadable: int = 0
    adopted_restricted: int = 0
    exact: int = 0  # 精确匹配条数（置信100分）
    pending: int = 0  # 待确认条数（match_score <= 80，含 mismatch）
    not_found: int = 0
    errors: int = 0


@dataclass
class CacheEntry:
    """缓存条目元数据"""

    standard_number: str
    source_site: str
    cached_at: datetime
    expires_at: datetime
