"""`/api/system/archive-stats` 的扫描逻辑（2026-11-20，用于核对公告原文补抓）。"""

from __future__ import annotations

from pathlib import Path

from docker.api import system


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_counts_html_and_attachments(tmp_path, monkeypatch):
    monkeypatch.setattr(system, "_archive_root", lambda: str(tmp_path))
    _write(tmp_path / "gb" / "2022年第1号.html", b"<html/>")
    _write(tmp_path / "gb" / "2022年第1号.pdf", b"PDF")
    _write(tmp_path / "hb" / "2023年第2号.html", b"<html/>")

    stats = system._scan_archive(system._archive_root())

    assert stats.exists is True
    assert stats.total_files == 3
    assert stats.total_bytes == 7 + 3 + 7
    assert stats.by_type["gb"]["html"] == 1
    assert stats.by_type["gb"]["attachments"] == 1
    assert stats.by_type["hb"]["html"] == 1
    assert any(s.startswith("gb/") for s in stats.samples)


def test_missing_dir_reports_not_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(system, "_archive_root", lambda: str(tmp_path / "nope"))
    stats = system._scan_archive(system._archive_root())
    assert stats.exists is False
    assert stats.total_files == 0
    assert stats.by_type == {}
