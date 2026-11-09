# tests/test_remaining_batch2b_logs.py — U-3/U-4 批 2b：公告/通知/watcher 日志升级
"""锁定批 2b 的代表点：附件解析/正文落盘/OCR 页数/通知凭证/watcher 事件失败必须 WARNING。"""

import logging
from types import SimpleNamespace

import pilotstd.announcement._attachment_parser as ap
import pilotstd.announcement._raw_store as raw_store
import pilotstd.announcement.parser as ann_parser
from pilotstd.core.notification.manager import NotificationManager
from pilotstd.scan.watcher import FileWatchHandler


def test_pdf_attachment_failure_warns(caplog) -> None:
    """PDF 附件解析失败 → WARNING「附件解析失败（PDF）」+ 空串。"""
    with caplog.at_level(logging.WARNING, logger="pilotstd.announcement._attachment_parser"):
        assert ap._parse_pdf_text(b"definitely-not-a-pdf") == ""

    assert any("附件解析失败（PDF）" in r.message for r in caplog.records)


def test_raw_content_store_failure_warns(monkeypatch, caplog) -> None:
    """公告正文落盘失败 → WARNING（带 announce_no）。"""
    import pilotstd.core.db as db_pkg

    class _Boom:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            raise RuntimeError("db open failed")

    monkeypatch.setattr(db_pkg, "Database", _Boom)
    monkeypatch.setattr(ann_parser, "extract_content", lambda html: "正文")
    import pilotstd.announcement.matcher as matcher

    monkeypatch.setattr(matcher, "clean_announcement_content", lambda c: c)

    with caplog.at_level(logging.WARNING, logger="pilotstd.announcement._raw_store"):
        raw_store._store_raw_content("公告2026-1号", "pid1", "标题", "2026-01-01", "site", "<html/>")

    assert any("公告正文落盘失败" in r.message for r in caplog.records)


def test_ocr_pdf_page_detection_failure_warns(monkeypatch, caplog) -> None:
    """PDF 页数检测失败 → WARNING「公告解析失败（PDF 页数检测…）」+ 按 1 页继续。"""
    import pypdf

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("bad pdf")

    monkeypatch.setattr(pypdf, "PdfReader", _boom)
    provider = SimpleNamespace(
        full_pdf=False,
        recognize_pdf=lambda pdf, page_num: SimpleNamespace(ok=True, text="text"),
    )
    with caplog.at_level(logging.WARNING, logger="pilotstd.announcement.parser"):
        assert ann_parser._ocr_pdf(b"x", provider) == "text"

    assert any("PDF 页数检测失败" in r.message for r in caplog.records)


def test_channel_credentials_failure_warns(monkeypatch, caplog) -> None:
    """单渠道凭证读取失败 → WARNING（轮询继续，返回空字典）。"""
    import pilotstd.core.notification._credentials as creds

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("credential broken")

    monkeypatch.setattr(creds, "CredentialHelper", _boom)
    mgr = object.__new__(NotificationManager)
    mgr._db = SimpleNamespace()
    mgr._cfg = SimpleNamespace(_filepath="/tmp/config.json")
    mgr._user_id = 1

    with caplog.at_level(logging.WARNING, logger="pilotstd.core.notification.manager"):
        assert mgr._channel_credentials("wechat") == {}

    assert any("credential" in r.message.lower() or "凭证" in r.message for r in caplog.records)


def test_watcher_event_failure_warns(tmp_path, caplog) -> None:
    """watcher 文件事件处理失败 → WARNING（带路径）。"""

    def _boom(name):  # noqa: ANN001
        raise RuntimeError("parse boom")

    handler = FileWatchHandler(
        file_index=SimpleNamespace(upsert=lambda **kw: None),
        parser=SimpleNamespace(parse=_boom),
    )
    target = tmp_path / "GB 1-2020.pdf"
    target.write_bytes(b"%PDF-1.4 x")

    with caplog.at_level(logging.WARNING, logger="pilotstd.scan.watcher"):
        handler._handle_new_or_modified(str(target))

    assert any("watcher 文件事件处理失败" in r.message for r in caplog.records)
