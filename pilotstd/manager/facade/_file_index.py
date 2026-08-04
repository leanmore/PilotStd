# 模块：pilotstd/manager/facade/_file_index.py
"""FileIndexHandler：文件索引读写操作，替代原 FileIndexMixin。"""
# 薄包装层：透传 file_index 仓库调用，不包含业务逻辑；
# upsert 支持 raw_number 参数保留前导零（Q28），get_full_info JOIN 缓存表提供离线完整视图

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._core import ManagerCore


class FileIndexHandler:
    """文件索引处理器 — 封装 file_index 仓库操作，替代原 FileIndexMixin。"""

    def __init__(self, core: "ManagerCore"):
        self._core = core

    def upsert_file_index(
        self,
        file_path: str,
        logical_code: str,
        number: int,
        year: int,
        part: Any = None,
        std_name: str = "",
        status: str = "现行",
        raw_number: str = "",
    ) -> None:
        """封装 file_index.upsert，供 UI 层在归档完成后写入索引。"""
        if self._core.file_index:
            self._core.file_index.upsert(
                file_path=file_path,
                logical_code=logical_code,
                number=number,
                year=year,
                part=part,
                std_name=std_name,
                status=status,
                raw_number=raw_number,
            )

    def get_file_index(self, file_path: str) -> dict[str, Any] | None:
        """封装 file_index.get，供 UI 层查询文件索引。"""
        if self._core.file_index:
            return self._core.file_index.get(file_path)
        return None

    def get_file_index_full_info(self, logical_code: str, number: int) -> list[dict[str, Any]]:
        """封装 file_index.get_full_info。"""
        if self._core.file_index:
            return self._core.file_index.get_full_info(logical_code, number)
        return []

    def parse_standard_number(self, filename: str) -> Any | None:
        """封装 parser.parse，供 UI 层解析标准文件名。"""
        return self._core.parser.parse(filename)

    def restore_parsed_from_index(self, file_path: str) -> Any | None:
        """从 file_index 恢复已解析的标准信息。"""
        if self._core.file_index:
            return self._core.file_index.restore_parsed(file_path)
        return None
