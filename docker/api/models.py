# docker/api/models.py — API 响应 Pydantic 模型，自动生成 OpenAPI 文档
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    version: str


class FileItem(BaseModel):
    """扫描文件条目"""

    name: str
    full_path: str
    size: int
    status: str


class ScanResponse(BaseModel):
    """扫描结果响应"""

    total: int
    pdf_count: int
    word_count: int
    dup_skipped: int
    skipped_dirs: int
    files: list[FileItem]


class DirItem(BaseModel):
    """文件/目录条目"""

    name: str
    type: Literal["dir", "file"]
    path: str
    size: int


class ListFilesResponse(BaseModel):
    """文件列表响应"""

    path: str
    files: list[DirItem]


class DownloadResult(BaseModel):
    """单个下载任务结果"""

    standard_number: str
    status: str
    saved_path: str = ""


class DownloadStats(BaseModel):
    """批量下载统计"""

    total: int
    success: int
    failed: int
    skipped: int
    skipped_exists: int = 0


class DownloadResponse(BaseModel):
    """批量下载响应"""

    stats: DownloadStats
    results: list[DownloadResult]


class ErrorResponse(BaseModel):
    """通用错误响应"""

    error: str


# ── Phase 3: 公告详情 ──────────────────────────────────


class AnnouncementResponse(BaseModel):
    id: int
    announce_no: str
    title: str
    publish_date: str = ""
    source_url: str = ""
    attachment_url: str = ""


class AnnouncementRecordResponse(BaseModel):
    id: int
    row_index: int = 0
    standard_number: str = ""
    std_name: str = ""
    implement_date: str = ""
    expiry_date: str = ""
    superseded_by: str = ""
    status: str = "draft"
    confidence: float = 0.0
    created_at: str = ""
    updated_at: str = ""


class AnnouncementDetailResponse(BaseModel):
    announcement: AnnouncementResponse
    records: list[AnnouncementRecordResponse]
    parse_status: str  # pending | parsing | completed | failed


class ParseStatusResponse(BaseModel):
    status: str
    record_count: int = 0


class BatchApproveResponse(BaseModel):
    status: str
    approved_count: int
    errors: list[str] = []
