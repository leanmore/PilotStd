"""D-13 P1：FileScanner 错误分支/去重分支覆盖（正常路径已由 test_scanner.py 覆盖）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pilotstd.models import ScanResult
from pilotstd.scan.scanner import FileScanner


class _Config:
    def get(self, key, default=None):
        return {
            "scan.skip_folders": ["skip"],
            "scan.extensions": [".pdf", ".docx"],
            "scan.exclude_patterns": ["exclude"],
            "scan.skip_query_exts": [".docx"],
        }.get(key, default)


def _scanner(file_index=None) -> FileScanner:
    return FileScanner(_Config(), file_index=file_index)


def _entry(name="a.pdf", path="/x/a.pdf", stat=None):
    e = MagicMock()
    e.name = name
    e.path = path
    e.stat.return_value = stat or SimpleNamespace(st_size=10, st_mtime=20.0)
    e.is_dir.return_value = False
    e.is_file.return_value = True
    return e


def test_scan_missing_root_adds_warning() -> None:
    result = _scanner().scan(["/definitely/not/exists"])
    assert result.stats.total == 0
    assert any("路径不存在" in w for w in result.warnings)


def test_keyword_skip_increments_stat() -> None:
    result = ScanResult()
    scanner = _scanner()
    scanner._process_file_entry(_entry("exclude.pdf"), result, [0], 0.0)
    assert result.stats.skipped == 1
    assert result.stats.total == 0


def test_stat_oserror_adds_warning_and_skips() -> None:
    entry = _entry()
    entry.stat.side_effect = OSError("stat failed")
    result = ScanResult()
    _scanner()._process_file_entry(entry, result, [0], 0.0)
    assert any("获取文件状态失败" in w for w in result.warnings)


def test_hash_oserror_still_records_file() -> None:
    result = ScanResult()
    with patch("pilotstd.scan.scanner.hash_file_content", side_effect=OSError("read")):
        _scanner()._process_file_entry(_entry(), result, [0], 0.0)
    assert result.stats.total == 1


def test_batch_duplicate_is_skipped() -> None:
    scanner = _scanner()
    result = ScanResult()
    with patch("pilotstd.scan.scanner.hash_file_content", return_value="same"):
        scanner._process_file_entry(_entry(), result, [0], 0.0)
        scanner._process_file_entry(_entry(path="/x/b.pdf"), result, [1], 0.0)
    assert result.stats.total == 1
    assert scanner.dup_count == 1


def test_index_duplicate_is_skipped() -> None:
    index = MagicMock()
    index.is_validation_complete = True
    index.find_by_hash.return_value = {"file_path": "/old.pdf"}
    scanner = _scanner(file_index=index)
    result = ScanResult()
    with patch("pilotstd.scan.scanner.hash_file_content", return_value="same"):
        scanner._process_file_entry(_entry(), result, [0], 0.0)
    assert result.stats.total == 0
    assert scanner.dup_count == 1


def test_word_template_is_recorded_with_skip_query_status() -> None:
    result = ScanResult()
    with patch("pilotstd.scan.scanner.hash_file_content", return_value="h"):
        _scanner()._process_file_entry(_entry("t.docx"), result, [0], 0.0)
    assert result.files[0].status == "word_template"


def test_recursive_permission_and_oserror_branches() -> None:
    scanner = _scanner()
    result = ScanResult()
    with patch("pilotstd.scan.scanner.os.scandir", side_effect=PermissionError("no")):
        scanner._scan_recursive("/x", result)
    assert any("无权限遍历目录" in w for w in result.warnings)

    result2 = ScanResult()
    err = OSError("long")
    err.winerror = 206
    with patch("pilotstd.scan.scanner.os.scandir", side_effect=err):
        scanner._scan_recursive("/x", result2)
    assert any("路径过长" in w for w in result2.warnings)


def test_recursive_valueerror_branch() -> None:
    scanner = _scanner()
    result = ScanResult()
    with patch("pilotstd.scan.scanner.os.scandir", side_effect=ValueError("bad")):
        scanner._scan_recursive("/x", result)
    assert any("遍历目录失败" in w for w in result.warnings)


def _dir_scan(entries):
    cm = MagicMock()
    cm.__enter__.return_value = entries
    cm.__exit__.return_value = False
    return cm


def test_recursive_entry_exceptions_are_caught_per_type() -> None:
    for exc, text in (
        (PermissionError("no"), "无权限访问"),
        (OSError("bad"), "文件系统错误"),
        (ValueError("bad"), "处理错误"),
    ):
        scanner = _scanner()
        result = ScanResult()
        with (
            patch("pilotstd.scan.scanner.os.scandir", return_value=_dir_scan([_entry()])),
            patch.object(scanner, "_process_file_entry", side_effect=exc),
        ):
            scanner._scan_recursive("/x", result)
        assert any(text in w for w in result.warnings)


def test_non_file_entry_is_ignored() -> None:
    scanner = _scanner()
    result = ScanResult()
    entry = _entry()
    entry.is_file.return_value = False
    with (
        patch("pilotstd.scan.scanner.os.scandir", return_value=_dir_scan([entry])),
        patch.object(scanner, "_process_file_entry") as process,
    ):
        scanner._scan_recursive("/x", result)
    process.assert_not_called()


def test_progress_logged_every_100_files() -> None:
    scanner = _scanner()
    scanner.log = MagicMock()
    result = ScanResult()
    entries = [_entry(name=f"f{i}.pdf", path=f"/x/f{i}.pdf") for i in range(100)]
    with (
        patch("pilotstd.scan.scanner.os.scandir", return_value=_dir_scan(entries)),
        patch("pilotstd.scan.scanner.hash_file_content", side_effect=[f"h{i}" for i in range(100)]),
    ):
        scanner._scan_recursive("/x", result)
    assert result.stats.total == 100
    assert any("扫描进度" in str(c) for c in scanner.log.info.call_args_list)
