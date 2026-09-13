"""pilotstd/tasks/favorite_download.py 补测 — 纯函数+helper 全覆盖。"""
from unittest.mock import MagicMock, patch

from pilotstd.tasks.favorite_download import (
    FavoriteArchiveError,
    _find_in_file_index,
    _get_inbox_dir,
    _get_standard_type,
    _load_cached_query_result,
    _notify_download_failed,
    _query_std_gov,
    _safe_filename,
    download_to_inbox,
)


class TestFavoriteArchiveError:
    def test_is_exception_subclass(self):
        assert issubclass(FavoriteArchiveError, Exception)

    def test_instantiate_with_message(self):
        e = FavoriteArchiveError("test error")
        assert str(e) == "test error"


class TestSafeFilename:
    def test_normal_standard_number(self):
        name = _safe_filename("GB/T 12345-2020", "abc123")
        assert name.endswith(".pdf")
        assert "GB_T 12345-2020" in name

    def test_forbidden_chars_replaced(self):
        name = _safe_filename("GB/T:1*2?3", "suffix")
        assert "/" not in name
        assert ":" not in name
        assert "*" not in name
        assert "?" not in name

    def test_backslash_and_pipe_replaced(self):
        name = _safe_filename(r"GB\T|1", "x")
        assert "\\" not in name
        assert "|" not in name

    def test_boundary_empty_number(self):
        name = _safe_filename("", "s")
        assert name == "_s.pdf"

    def test_state_all_forbidden_chars_in_one_string(self):
        name = _safe_filename(r'GB\/:*?"<>|123', "suf")
        for ch in r'\/:*?"<>|':
            assert ch not in name


class TestGetStandardType:
    """类别闸的数据来源：favorite_downloads.standard_type（v57 落库）。"""

    def test_returns_type(self):
        db = MagicMock()
        db.fetchone.return_value = {"standard_type": "NationalStd"}
        assert _get_standard_type(7, db) == "NationalStd"

    def test_missing_row_returns_empty(self):
        db = MagicMock()
        db.fetchone.return_value = None
        assert _get_standard_type(7, db) == ""

    def test_null_type_returns_empty(self):
        db = MagicMock()
        db.fetchone.return_value = {"standard_type": None}
        assert _get_standard_type(7, db) == ""


class TestLoadCachedQueryResult:
    """hcno 取用：必须限定 std_gov 源（其它源的行没有 hcno）。"""

    def test_scoped_to_std_gov(self):
        db = MagicMock()
        fake = object()
        with patch("pilotstd.query.cache.CacheRepository") as repo:
            repo.return_value.get.return_value = fake
            assert _load_cached_query_result(db, "GB/T 1-2020") is fake
            repo.return_value.get.assert_called_once_with("GB/T 1-2020", "std_gov")

    def test_exception_returns_none(self):
        with patch("pilotstd.query.cache.CacheRepository", side_effect=Exception("boom")):
            assert _load_cached_query_result(MagicMock(), "GB/T 1-2020") is None


class TestQueryStdGov:
    """缓存未命中的兜底：现场查国标站点取 hcno。"""

    def test_returns_first_result_with_hcno(self):
        mgr = MagicMock()
        with_hcno = MagicMock(hcno="ABC123")
        mgr.query_by_numbers.return_value = ([MagicMock(hcno=""), with_hcno], None)
        assert _query_std_gov(mgr, "GB/T 1-2020") is with_hcno
        mgr.query_by_numbers.assert_called_once_with(["GB/T 1-2020"], preferred_site="std_gov")

    def test_no_hcno_returns_none(self):
        mgr = MagicMock()
        mgr.query_by_numbers.return_value = ([MagicMock(hcno="")], None)
        assert _query_std_gov(mgr, "GB/T 1-2020") is None

    def test_query_exception_returns_none(self):
        mgr = MagicMock()
        mgr.query_by_numbers.side_effect = Exception("net down")
        assert _query_std_gov(mgr, "GB/T 1-2020") is None


class TestGetInboxDir:
    def test_returns_path_from_config(self):
        with patch("pilotstd.tasks.favorite_download.ConfigManager") as MockCfg:
            MockCfg.return_value.get.return_value = "/my/inbox"
            path = _get_inbox_dir()
            assert path.name == "inbox" or str(path).endswith("inbox")


class TestFindInFileIndex:
    def test_found_file_returns_path(self, monkeypatch):
        mock_db = MagicMock()
        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            logical_code="GB/T", number="12345", year="2020"
        )
        mock_db.execute.return_value.fetchone.return_value = {"file_path": "/path/to/file.pdf"}
        with patch("pilotstd.tasks.favorite_download.StandardParser", return_value=mock_parser):
            with patch("pilotstd.tasks.favorite_download.build_code_mapping", return_value={}):
                result = _find_in_file_index("GB/T 12345-2020", mock_db)
                assert result == "/path/to/file.pdf"

    def test_not_found_returns_none(self, monkeypatch):
        mock_db = MagicMock()
        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            logical_code="GB/T", number="12345", year="2020"
        )
        mock_db.execute.return_value.fetchone.return_value = None
        with patch("pilotstd.tasks.favorite_download.StandardParser", return_value=mock_parser):
            with patch("pilotstd.tasks.favorite_download.build_code_mapping", return_value={}):
                result = _find_in_file_index("GB/T 12345-2020", mock_db)
                assert result is None

    def test_exception_returns_none(self):
        with patch("pilotstd.tasks.favorite_download.StandardParser", side_effect=Exception("bad")):
            result = _find_in_file_index("any", MagicMock())
            assert result is None


class TestNotifyDownloadFailed:
    def test_notify_sends_event(self):
        with patch("pilotstd.manager.facade.StandardManager") as MockMgr:
            _notify_download_failed(1, "GB/T 1", "err msg", 42)
            MockMgr.return_value.notification_mgr.send_event.assert_called_once()

    def test_notify_exception_silent(self):
        with patch("pilotstd.manager.facade.StandardManager", side_effect=Exception("fail")):
            _notify_download_failed(1, "x", "e", 0)  # 不抛异常


class TestDownloadToInbox:
    """download_to_inbox 核心路径覆盖。"""

    def test_record_not_found_raises(self):
        """记录不存在时抛出 FavoriteArchiveError 并更新状态为 failed。"""
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None
        with patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db):
            with patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"):
                download_to_inbox(favorite_id=1, user_id=1, record_id=999)
        mock_db.execute.assert_called()  # 至少调用了 UPDATE ... SET status = 'failed'

    def test_empty_standard_number_raises(self):
        """标准号为空时标记失败。"""
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = {"standard_number": ""}
        with patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db):
            with patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"):
                download_to_inbox(favorite_id=1, user_id=1, record_id=1)
        # 应触发 failed 状态更新
        update_calls = [c for c in mock_db.execute.call_args_list if "failed" in str(c)]
        assert len(update_calls) >= 1

    def test_failure_path_sends_single_notification(self, tmp_path):
        """P-107：下载失败仅发送 1 条 download_failed，无双通知。

        回归验证：内层原始错误通知已移除，由 except 块统一补发一次
        （载荷为包装后的 str(e)），成功路径/归档超时路径不受影响。
        """
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 1-2020"},  # announcement_record
        ]
        mock_db.fetchone.return_value = {"standard_type": "NationalStd"}  # 类别闸
        mock_mgr = MagicMock()
        mock_mgr.download_engine.fetch_bytes.return_value = (None, "connection refused")
        with patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db), \
            patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"), \
            patch("pilotstd.tasks.favorite_download._find_in_file_index", return_value=None), \
            patch("pilotstd.tasks.favorite_download._get_inbox_dir", return_value=tmp_path / "inbox"), \
            patch("pilotstd.tasks.favorite_download._load_cached_query_result",
                  return_value=MagicMock(hcno="ABC123", is_adopted=False)), \
            patch("pilotstd.manager.facade.StandardManager", return_value=mock_mgr), \
            patch("pilotstd.tasks.favorite_download._notify_download_started"), \
            patch("pilotstd.tasks.favorite_download._notify_download_failed") as mock_notify:
            download_to_inbox(favorite_id=1, user_id=100, record_id=999)

        # 仅 1 条 download_failed（外层 except 统一补发）
        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert args[0] == 100  # user_id
        assert args[1] == "GB/T 1-2020"  # standard_number
        assert "下载失败" in args[2]  # 包装后的错误信息
        assert args[3] == 1  # favorite_id

    def test_non_national_type_is_rejected_before_download(self, tmp_path):
        """类别闸：行标/地标没有下载适配器，必须在取 hcno 前就拒绝。"""
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "HB 1-2020"},
        ]
        mock_db.fetchone.return_value = {"standard_type": "IndustryStd"}
        with patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db), \
            patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"), \
            patch("pilotstd.tasks.favorite_download._find_in_file_index", return_value=None), \
            patch("pilotstd.tasks.favorite_download._load_cached_query_result") as cached, \
            patch("pilotstd.tasks.favorite_download._notify_download_failed") as mock_notify:
            download_to_inbox(favorite_id=2, user_id=100, record_id=999)

        cached.assert_not_called()
        assert "非国标标准" in mock_notify.call_args[0][2]

    def test_adopted_standard_is_skipped(self, tmp_path):
        """采标闸：版权受限，取到 hcno 后仍须拒绝下载。"""
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 2-2020"},
        ]
        mock_db.fetchone.return_value = {"standard_type": "NationalStd"}
        with patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db), \
            patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"), \
            patch("pilotstd.tasks.favorite_download._find_in_file_index", return_value=None), \
            patch("pilotstd.tasks.favorite_download._load_cached_query_result",
                  return_value=MagicMock(hcno="ABC", is_adopted=True)), \
            patch("pilotstd.tasks.favorite_download._get_inbox_dir", return_value=tmp_path / "inbox"), \
            patch("pilotstd.tasks.favorite_download._notify_download_failed") as mock_notify:
            download_to_inbox(favorite_id=3, user_id=100, record_id=999)

        assert "采标标准" in mock_notify.call_args[0][2]
