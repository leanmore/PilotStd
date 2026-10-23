"""DB 公告附件：.doc 完整清单与 dbba 下载链接。"""

from __future__ import annotations

from pilotstd.announcement._attachment_parser import find_attachment_url, parse_attachment_text
from pilotstd.announcement.parser import parse_announcement_detail


def _wps_doc(lines: list[str]) -> bytes:
    return ("\n".join(lines)).encode("utf-16-le")


def test_find_dbba_attachment_url() -> None:
    html = '<a href="http://dbba.sacinfo.org.cn/attachment/downloadRnAtt?pk=ABC">附件</a>'
    assert find_attachment_url(html) == "http://dbba.sacinfo.org.cn/attachment/downloadRnAtt?pk=ABC"


def test_doc_attachment_uses_wps_text() -> None:
    data = _wps_doc(["DB11/T 1-2014 标准一 2014-01-01", "DB11/T 2-2014 标准二 2014-01-01"])
    text = parse_attachment_text(data, "2014年第4号.doc")
    assert "DB11/T 1-2014" in text


def test_attachment_with_more_rows_becomes_primary() -> None:
    html = (
        "<table><thead><tr><th>标准编号</th><th>标准名称</th></tr></thead>"
        "<tbody><tr><td>DB11/T 1-2014</td><td>标准一</td></tr></tbody></table>"
    )
    data = _wps_doc(
        [
            "DB11/T 1-2014 标准一 2014-01-01",
            "DB11/T 2-2014 标准二 2014-01-01",
            "DB11/T 3-2014 标准三 2014-01-01",
        ]
    )
    items, _ = parse_announcement_detail(html, data, "2014年第4号.doc")
    assert len(items) == 3
