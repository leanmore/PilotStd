# pilotstd/download/models.py
# 下载任务数据模型

from dataclasses import dataclass, field
from enum import Enum


class DownloadStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"        # 采标受限等
    RETRYING = "retrying"


@dataclass
class DownloadTask:
    """单个下载任务"""
    standard_number: str         # 标准完整编号
    download_url: str = ""       # 下载直链
    source_site: str = ""        # 来源网站标识
    query_result: object = None  # 关联的 QueryResult（含标准名、采标状态等）

    status: DownloadStatus = DownloadStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error_message: str = ""
    saved_path: str = ""         # 下载后本地路径

    # 供适配器使用的临时数据
    extra: dict = field(default_factory=dict)


@dataclass
class BatchDownloadStats:
    """批量下载统计"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped_adopted: int = 0     # 采标跳过
    skipped_exists: int = 0      # 文件已存在跳过
    errors: int = 0
