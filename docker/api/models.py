# docker/api/models.py — API 响应 Pydantic 模型，自动生成 OpenAPI 文档
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
    type: str          # "dir" 或 "file"
    path: str
    size: int


class ListFilesResponse(BaseModel):
    """文件列表响应"""
    path: str
    items: list[DirItem]


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
