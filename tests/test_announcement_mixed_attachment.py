"""混合型公告：附件行数更多时必须实际解析附件。"""

from unittest.mock import patch

from pilotstd.announcement.adapters.samr_db import SamrDbCrawler


def test_mixed_announcement_prefers_larger_attachment() -> None:
    crawler = SamrDbCrawler()
    crawler._download_attachment = lambda url: b"doc-bytes"  # type: ignore[method-assign]

    def fake_parse(raw, att=None, name="", ocr_provider=None):
        if att:
            return ([{"std_code": f"DB11/T {i}-2014", "std_name": "x"} for i in range(3)], {})
        return ([{"std_code": "DB11/T 1-2014", "std_name": "x"}], {})

    with patch("pilotstd.announcement.parser.find_attachment_url", return_value="http://att"), patch(
        "pilotstd.announcement.parser.parse_announcement_detail", side_effect=fake_parse
    ):
        items = crawler._parse_items("<html></html>")
    assert len(items) == 3
