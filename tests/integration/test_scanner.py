"""集成测试: FileScanner 扫描 → 结果验证 + file_index 去重读取。"""
from __future__ import annotations

from pathlib import Path

import pytest

from pilotstd.core.db.database import Database
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.scan.scanner import FileScanner


class _StubConfig:
    def __init__(self, overrides: dict | None = None):
        self._data = overrides or {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)


@pytest.fixture
def scan_env(tmp_path: Path):
    db = Database(str(tmp_path / "scan_test.db"))
    repo = FileIndexRepository(db)
    scanner = FileScanner(config_manager=_StubConfig(), file_index=repo)
    yield scanner, repo, tmp_path
    repo.stop()


class TestScannerIntegration:
    def test_scan_populates_result(self, scan_env):
        """扫描后 ScanResult.files 应包含识别到的文件，非写入 file_index。"""
        scanner, repo, tmp_path = scan_env
        std_dir = tmp_path / "standards"
        std_dir.mkdir()
        (std_dir / "GB_T50001-2014.pdf").write_bytes(b"content-a")
        (std_dir / "JTG_D60-2015.pdf").write_bytes(b"content-b")

        result = scanner.scan([str(std_dir)])

        assert result is not None
        filenames = {f.filename for f in result.files}
        assert "GB_T50001-2014.pdf" in filenames
        assert "JTG_D60-2015.pdf" in filenames

    def test_scan_deduplicates_via_file_index(self, scan_env):
        """file_index 中有已归档哈希时，扫描器应跳过重复文件。"""
        scanner, repo, tmp_path = scan_env

        content = b"identical-standard-content"
        fp = str(tmp_path / "archived_copy.pdf")
        Path(fp).write_bytes(content)

        # 模拟归档管线：手动写入 file_index 并完成校验
        from pilotstd.core.file_utils import hash_file_content

        file_hash = hash_file_content(fp)
        repo.upsert(file_path=fp, logical_code="GB", number=50001, year=2014, file_hash=file_hash)
        repo.validate_paths()
        assert repo.is_validation_complete is True

        # 扫描含相同内容文件的目录
        scan_dir = tmp_path / "inbox"
        scan_dir.mkdir()
        (scan_dir / "GB_T50001-2014_duplicate.pdf").write_bytes(content)

        scanner.scan([str(scan_dir)])

        # 已归档哈希命中 → file_index 层去重生效
        assert scanner.dup_count >= 1, f"期望 dup_count>=1，实际 {scanner.dup_count}"

    def test_scan_handles_empty_directory(self, scan_env):
        scanner, repo, tmp_path = scan_env
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = scanner.scan([str(empty_dir)])

        assert result is not None
        assert len(result.files) == 0
