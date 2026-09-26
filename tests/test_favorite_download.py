"""pilotstd/tasks/favorite_download.py 补测 — 纯函数+helper 全覆盖。"""
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.tasks.favorite_download import (
    FavoriteArchiveError,
    FavoriteSkip,
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

    def test_skip_is_archive_error_subclass(self):
        """FavoriteSkip 继承 FavoriteArchiveError：既有宽泛捕获仍能兜住。"""
        assert issubclass(FavoriteSkip, FavoriteArchiveError)


class TestSafeFilename:
    def test_normal_standard_number(self):
        name = _safe_filename("GB/T 12345-2020", "abc123")
        assert name.endswith(".pdf")
        assert "GBT 12345-2020" in name

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


class TestSafeFilenameRoundTrip:
    """契约（TD-30 残留）：`_safe_filename` 的产出必须能被解析器还原成**原标准号 code**。

    背景：monitor 只能靠文件名识别 inbox 文件。若 `/` 被转义成 `_`，`GB_T 5613-2026_x.pdf`
    会被解析成 `GB`（而非 `GB/T`）→ 归档写进错的 `file_index` 键 → 链路按 `GB/T` 永远查不到。
    数据驱动覆盖 `build_code_mapping()` 中**全部**含 `/` 的 code，防止将来映射表扩了而修复漏掉。
    """

    @staticmethod
    def _parser():
        from pilotstd.organizer.industry_lookup import build_code_mapping
        from pilotstd.scan.parser import StandardParser

        return StandardParser(build_code_mapping()), build_code_mapping()

    def test_every_slash_code_survives_round_trip(self):
        """124/124：产出文件名 → parser 还原 == 原 code。"""
        parser, mapping = self._parser()
        slash_codes = sorted({str(v) for v in mapping.values() if "/" in str(v)})
        assert len(slash_codes) >= 100, f"映射表含 / 的 code 太少({len(slash_codes)})，契约失效"

        failures = []
        for code in slash_codes:
            name = _safe_filename(f"{code} 1234-2020", "000001")
            info = parser.parse(name)
            got = getattr(info, "logical_code", None)
            if got != code:
                failures.append(f"{code} -> 文件名 {name!r} -> 解析得到 {got!r}")

        assert failures == [], f"往返还原失败 {len(failures)}/{len(slash_codes)}:\n" + "\n".join(failures[:10])

    def test_no_code_collision_after_dropping_slash(self):
        """0 撞名：去掉 `/` 后的串不得等于另一个 code 的写法。"""
        _, mapping = self._parser()
        collisions = []
        for value in sorted({str(v) for v in mapping.values() if "/" in str(v)}):
            joined = value.replace("/", "")
            other = mapping.get(joined)
            if other is not None and str(other) != value:
                collisions.append(f"{value} 去 / 得 {joined}，但该写法已映射到 {other!r}")
        assert collisions == [], "去掉 / 产生歧义:\n" + "\n".join(collisions)

    def test_part_number_and_plain_code_still_parse(self):
        """边界：带分部号（GB/Z 184.1）与本来就无 `/` 的 code（GB）都要正确。"""
        parser, _ = self._parser()
        cases = [("GB/Z 184.1-2026", "GB/Z"), ("GB 18047-2026", "GB"), ("JB/T 1234-2020", "JB/T")]
        for std, expect in cases:
            info = parser.parse(_safe_filename(std, "000002"))
            assert info is not None and info.logical_code == expect, (std, expect, info)


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
        """类别闸：行标/地标没有下载适配器，必须在取 hcno 前就拒绝。

        P1（2026-09-21）：该闸属**业务终态**，抛 FavoriteSkip 而非普通失败
        —— 由链路直接置终态并只通知一次，不再空转 7 天重试窗口。
        """
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
            with pytest.raises(FavoriteSkip, match="非国标标准"):
                download_to_inbox(favorite_id=2, user_id=100, record_id=999)

        cached.assert_not_called()
        # 终态跳过不发 download_failed（由链路发一条"放弃"通知）
        mock_notify.assert_not_called()

    def test_adopted_standard_is_skipped(self, tmp_path):
        """采标闸：版权受限，取到 hcno 后仍须拒绝，且按业务终态上抛。"""
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
            with pytest.raises(FavoriteSkip, match="采标标准"):
                download_to_inbox(favorite_id=3, user_id=100, record_id=999)

        mock_notify.assert_not_called()
        # 关键：不得把状态写成 failed（写 failed 会被链路按失败重试 7 次）
        failed_updates = [c for c in mock_db.execute.call_args_list if "'failed'" in str(c)]
        assert failed_updates == []

    def test_engine_adopted_error_maps_to_skip(self, tmp_path):
        """引擎侧版权闸（fetch_bytes 返回采标文案）同样归为业务终态跳过。"""
        from pilotstd.download.engine import ADOPTED_SKIP_MESSAGE

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 3-2020"},
        ]
        mock_db.fetchone.return_value = {"standard_type": "NationalStd"}
        mock_mgr = MagicMock()
        mock_mgr.download_engine.fetch_bytes.return_value = (None, ADOPTED_SKIP_MESSAGE)
        with patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db), \
            patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"), \
            patch("pilotstd.tasks.favorite_download._find_in_file_index", return_value=None), \
            patch("pilotstd.tasks.favorite_download._load_cached_query_result",
                  return_value=MagicMock(hcno="ABC", is_adopted=False)), \
            patch("pilotstd.tasks.favorite_download._get_inbox_dir", return_value=tmp_path / "inbox"), \
            patch("pilotstd.tasks.favorite_download._notify_download_started"), \
            patch("pilotstd.tasks.favorite_download._notify_download_failed") as mock_notify, \
            patch("pilotstd.manager.facade.StandardManager", return_value=mock_mgr):
            with pytest.raises(FavoriteSkip, match="采标标准"):
                download_to_inbox(favorite_id=4, user_id=100, record_id=999)

        mock_notify.assert_not_called()
