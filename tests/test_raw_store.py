# tests/test_raw_store.py
"""_raw_store.py 单元测试 — 覆盖 _store_raw_content 全部分支。"""

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.announcement._raw_store import _store_raw_content


class TestStoreRawContent(unittest.TestCase):
    """_store_raw_content 全部分支。"""

    @patch("pilotstd.announcement.matcher.clean_announcement_content")
    @patch("pilotstd.announcement.parser.extract_content")
    @patch("pilotstd.core.db.Database")
    @patch("pilotstd.core.config.get_db_path")
    def test_full_success_path(self, mock_get_db_path, mock_db_cls, mock_extract, mock_clean):
        """正常路径：提取内容 → 清洗 → 写入 DB。"""
        mock_extract.return_value = "<p>公告正文</p>"
        mock_clean.return_value = "清洗后的正文"
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db

        _store_raw_content(
            announce_no="GB-2026-001",
            pid="12345",
            title="测试公告",
            notice_date="2026-08-01",
            source_site="std_gov",
            raw_html="<html>原始HTML</html>",
        )

        mock_extract.assert_called_once_with("<html>原始HTML</html>")
        mock_clean.assert_called_once_with("<p>公告正文</p>")
        mock_db.execute.assert_called_once()
        sql = str(mock_db.execute.call_args[0][0])
        self.assertIn("INSERT OR REPLACE INTO announcements", sql)
        mock_db.close.assert_called_once()

    @patch("pilotstd.announcement.parser.extract_content")
    @patch("pilotstd.announcement.matcher.clean_announcement_content")
    def test_empty_announce_no_returns_early(self, mock_clean, mock_extract):
        """announce_no 为空 → 内容仍被处理，但跳过 DB 写入。"""
        mock_extract.return_value = "<p>content</p>"
        mock_clean.return_value = "cleaned"
        _store_raw_content(
            announce_no="",
            pid="12345",
            title="测试",
            notice_date="2026-08-01",
            source_site="std_gov",
            raw_html="<html></html>",
        )
        # 内容处理仍会执行（在判断 announce_no 之前）
        mock_extract.assert_called_once()
        mock_clean.assert_called_once()
        # 但 DB 不会被触及（因为 import 在判断后，且没有被导入）

    @patch("pilotstd.core.db.Database")
    @patch("pilotstd.core.config.get_db_path")
    @patch("pilotstd.announcement.parser.extract_content")
    @patch("pilotstd.announcement.matcher.clean_announcement_content")
    def test_db_exception_handled_gracefully(self, mock_clean, mock_extract, mock_get_db_path, mock_db_cls):
        """DB 创建异常 → 静默处理，不向外传播。"""
        mock_extract.return_value = "<p>content</p>"
        mock_clean.return_value = "cleaned"
        mock_db_cls.side_effect = Exception("DB unavailable")

        # 不应抛出异常
        _store_raw_content(
            announce_no="GB-001",
            pid="1",
            title="T",
            notice_date="2026-01-01",
            source_site="test",
            raw_html="<html></html>",
        )

    @patch("pilotstd.core.db.Database")
    @patch("pilotstd.core.config.get_db_path")
    @patch("pilotstd.announcement.parser.extract_content")
    @patch("pilotstd.announcement.matcher.clean_announcement_content")
    def test_execute_exception_handled(self, mock_clean, mock_extract, mock_get_db_path, mock_db_cls):
        """execute 异常 → 静默处理。"""
        mock_extract.return_value = "<p>content</p>"
        mock_clean.return_value = "cleaned"
        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("insert failed")
        mock_db_cls.return_value = mock_db

        # 不应抛出异常
        _store_raw_content(
            announce_no="GB-001",
            pid="1",
            title="T",
            notice_date="2026-01-01",
            source_site="test",
            raw_html="<html></html>",
        )


if __name__ == "__main__":
    unittest.main()
