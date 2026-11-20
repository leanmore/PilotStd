"""公告原文/附件归档（2026-11-20）：data/announcements 目录此前只建不写。

背景：`_store_raw_content` 只把正文写进 DB 的 `announcements.raw_data`；
`crawler_service.check_all` 建了 `data/announcements/{gb,hb,db}` 却从没往里写东西，
用户看到的“抓下来的网页/附件没保存”就是它。本文件锁定归档的三条契约：

1. HTML 与附件字节都落到 `{raw_dir}/{std_type}/{安全化的公告号}{.html|原扩展名}`；
2. 公告号里的空格/斜杠等被压平，不会拼出越级路径；
3. 归档失败**只告警、不抛错**，解析主流程照常返回结果。
"""

from pathlib import Path

import pytest

from pilotstd.announcement import _raw_archive as arc


@pytest.fixture()
def raw_dir(tmp_path, monkeypatch):
    """把归档根目录指到 tmp，并确保开关为开。"""
    monkeypatch.setattr(arc, "_settings", lambda: (True, str(tmp_path)))
    return tmp_path


def test_archive_html_writes_file(raw_dir):
    path = arc.archive_html("gb", "2026年第30号", "<html>正文</html>")
    assert path is not None
    p = Path(path)
    assert p.exists() and p.parent.name == "gb"
    assert p.name == "2026年第30号.html"
    assert p.read_text(encoding="utf-8") == "<html>正文</html>"


def test_archive_attachment_keeps_whitelisted_suffix(raw_dir):
    path = arc.archive_attachment("db", "2026年第4号", "https://x/a.docx?token=1", b"PK\x03\x04")
    assert path is not None
    p = Path(path)
    assert p.suffix == ".docx"
    assert p.read_bytes() == b"PK\x03\x04"


def test_attachment_unknown_suffix_falls_back_to_bin(raw_dir):
    path = arc.archive_attachment("hb", "NO-1", "https://x/download", b"data")
    assert path is not None and Path(path).suffix == ".bin"


def test_unsafe_announce_no_is_sanitized(raw_dir):
    path = arc.archive_html("gb", "../../etc/passwd 2026/1", "<html/>")
    assert path is not None
    p = Path(path)
    # 不许越级：文件必须仍落在 raw_dir/gb 下
    assert p.parent == raw_dir / "gb"
    assert ".." not in p.name and "/" not in p.name


def test_disabled_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(arc, "_settings", lambda: (False, str(tmp_path)))
    assert arc.archive_html("gb", "X", "<html/>") is None
    assert arc.archive_attachment("gb", "X", "https://x/a.pdf", b"pdf") is None


def test_write_failure_is_swallowed(tmp_path, monkeypatch):
    """归档失败不能把抓取流程带崩：返回 None 且不抛。"""
    monkeypatch.setattr(arc, "_settings", lambda: (True, str(tmp_path)))

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom, raising=False)
    assert arc.archive_html("gb", "X", "<html/>") is None
