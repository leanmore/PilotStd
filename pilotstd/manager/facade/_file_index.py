# pilotstd/manager/facade/_file_index.py
# StandardManager 文件索引混入模块
"""FileIndexMixin：文件索引读写操作。"""

from __future__ import annotations

from typing import Any


class FileIndexMixin:
    """文件索引混入类 — 封装 file_index 仓库操作。"""

    def upsert_file_index(
        self,
        file_path: str,
        logical_code: str,
        number: int,
        year: int,
        part: Any = None,
        std_name: str = "",
        status: str = "现行",
    ) -> None:
        """封装 file_index.upsert，供 UI 层在归档完成后写入索引。"""
        if self.file_index:
            self.file_index.upsert(
                file_path=file_path,
                logical_code=logical_code,
                number=number,
                year=year,
                part=part,
                std_name=std_name,
                status=status,
            )

    def get_file_index(self, file_path: str) -> dict[str, Any] | None:
        """封装 file_index.get，供 UI 层查询文件索引。"""
        if self.file_index:
            return self.file_index.get(file_path)
        return None

    def get_file_index_full_info(self, logical_code: str, number: int) -> list[dict[str, Any]]:
        """封装 file_index.get_full_info。"""
        if self.file_index:
            return self.file_index.get_full_info(logical_code, number)
        return []

    def parse_standard_number(self, filename: str) -> object | None:
        """封装 parser.parse，供 UI 层解析标准文件名。"""
        return self.parser.parse(filename)

    def restore_parsed_from_index(self, file_path: str) -> object | None:
        """从 file_index 恢复已解析的标准信息。"""
        if self.file_index:
            return self.file_index.restore_parsed(file_path)
        return None
