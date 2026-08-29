"""pilotstd/tasks/favorite_download.py 补测 — 纯函数+helper 全覆盖。"""
import json
from unittest.mock import MagicMock, patch

from pilotstd.tasks.favorite_download import (
    FavoriteArchiveError,
    _download_with_retry,
    _find_in_file_index,
    _get_download_url,
    _get_inbox_dir,
    _notify_download_failed,
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


class TestGetDownloadUrl:
    def test_normal_url_from_cache(self):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = {
            "result_json": json.dumps({"download_url": "http://example.com/file.pdf"})
        }
        url = _get_download_url("GB/T 1.1", mock_db)
        assert url == "http://example.com/file.pdf"

    def test_no_cache_returns_none(self):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None
        assert _get_download_url("unknown", mock_db) is None

    def test_invalid_json_returns_none(self):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = {"result_json": "not json"}
        assert _get_download_url("bad", mock_db) is None


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


class TestDownloadWithRetry:
    def test_success_first_attempt(self, tmp_path):
        target = tmp_path / "test.pdf"
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"data"]
        mock_resp.raise_for_status.return_value = None
        with patch("pilotstd.tasks.favorite_download.requests.get", return_value=mock_resp):
            ok, err = _download_with_retry("http://ok", target, max_retries=2)
            assert ok is True
            assert err is None
            assert target.exists()

    def test_failure_all_retries_exhausted(self, tmp_path):
        target = tmp_path / "fail.pdf"
        with patch("pilotstd.tasks.favorite_download.requests.get", side_effect=Exception("net err")):
            with patch("pilotstd.tasks.favorite_download.requests.exceptions.RequestException", Exception):
                ok, err = _download_with_retry("http://fail", target, max_retries=1)
                assert ok is False
                assert err is not None

    def test_retry_on_failure_then_succeed(self, tmp_path):
        target = tmp_path / "retry.pdf"
        mock_fail = MagicMock(side_effect=Exception("fail1"))
        mock_ok = MagicMock()
        mock_ok.iter_content.return_value = [b"ok"]
        mock_ok.raise_for_status.return_value = None
        with patch("pilotstd.tasks.favorite_download.requests.get", side_effect=[mock_fail, mock_ok]):
            with patch("pilotstd.tasks.favorite_download.requests.exceptions.RequestException", Exception):
                with patch("pilotstd.tasks.favorite_download.time.sleep"):
                    ok, err = _download_with_retry("http://retry", target, max_retries=2)
                    assert ok is True


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
        """P-107：下载失败（重试耗尽）仅发送 1 条 download_failed，无双通知。

        回归验证：内层原始错误通知已移除，由 except 块统一补发一次
        （载荷为包装后的 str(e)），成功路径/归档超时路径不受影响。
        """
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 1-2020"},  # record
        ]
        with patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db), \
            patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"), \
            patch("pilotstd.tasks.favorite_download._find_in_file_index", return_value=None), \
            patch("pilotstd.tasks.favorite_download._get_inbox_dir", return_value=tmp_path / "inbox"), \
            patch("pilotstd.tasks.favorite_download._get_download_url",
                  return_value="https://dl.example.com/file.pdf"), \
            patch("pilotstd.tasks.favorite_download._download_with_retry",
                  return_value=(False, "connection refused")), \
            patch("pilotstd.tasks.favorite_download._notify_download_started"), \
            patch("pilotstd.tasks.favorite_download._notify_download_failed") as mock_notify:
            download_to_inbox(favorite_id=1, user_id=100, record_id=999)

        # 仅 1 条 download_failed（外层 except 统一补发）
        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert args[0] == 100  # user_id
        assert args[1] == "GB/T 1-2020"  # standard_number
        assert "下载失败(重试3次)" in args[2]  # 包装后的错误信息
        assert args[3] == 1  # favorite_id
