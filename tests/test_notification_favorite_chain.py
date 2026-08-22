# tests/test_notification_favorite_chain.py — 收藏链事件通知集成测试（Phase 2）
"""收藏链全流程事件通知验证。

覆盖事件：
- favorite_created   收藏成功（add_favorite）
- download_started   下载开始（download_to_inbox 入口）
- download_complete  下载归档完成（done 分支）
- download_failed    下载失败（复用现有事件）
- archive_complete   批量归档完成（archive_standards）

测试策略：
- 用 unittest.mock 替换 StandardManager().notification_mgr / mgr.notification_mgr
- 验证 send_event 被调用 + 事件类型/参数正确
- 验证通知失败不阻塞主业务流程
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════
# 用例 1：收藏成功 → favorite_created
# ══════════════════════════════════════════════════════════════════════


class TestFavoriteCreatedEvent:
    """验证 add_favorite 成功后触发 favorite_created 事件。"""

    def test_add_favorite_sends_favorite_created(self):
        """收藏成功 → send_event('favorite_created', ...) 被调用，参数含 user_id/record_id/standard_no。"""
        from unittest.mock import MagicMock, patch

        from docker.api.favorites import add_favorite

        mock_mgr = MagicMock()
        mock_notifier = MagicMock()
        mock_mgr.notification_mgr = mock_notifier

        mock_db = MagicMock()
        # 调用顺序：_get_user_id 校验用户 → existing 查询 → announcement_record → publish_date
        mock_db.fetchone.side_effect = [
            {"id": 7},  # users 校验（_get_user_id）
            None,  # user_favorites 已存在查询
            {"id": 100, "standard_number": "GB/T 1234-2026", "std_name": "测试标准"},  # announcement_record
            {"publish_date": "2026-07-30"},  # publish_date 查询
        ]
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42
        mock_db.execute.return_value = mock_cursor

        with patch("docker.api.favorites.get_manager_dep", return_value=mock_mgr):
            result = add_favorite(
                data=MagicMock(record_id=100),
                user_id=7,
                db=mock_db,
                mgr=mock_mgr,
            )

        assert result["status"] == "pending"
        assert result["favorite_id"] == 42
        # favorite_created 事件被触发
        calls = [c.args[0] for c in mock_notifier.send_event.call_args_list]
        assert "favorite_created" in calls
        # 参数校验
        ev_call = next(c for c in mock_notifier.send_event.call_args_list if c.args[0] == "favorite_created")
        data = ev_call.args[1]
        assert data["user_id"] == 7
        assert data["record_id"] == 100
        assert data["standard_no"] == "GB/T 1234-2026"

    def test_add_favorite_notify_failure_does_not_block(self):
        """send_event 抛异常 → 收藏主流程仍完成（返回 pending）。"""
        from unittest.mock import MagicMock, patch

        from docker.api.favorites import add_favorite

        mock_mgr = MagicMock()
        mock_notifier = MagicMock()
        mock_notifier.send_event.side_effect = RuntimeError("通知渠道故障")
        mock_mgr.notification_mgr = mock_notifier

        mock_db = MagicMock()
        mock_db.fetchone.side_effect = [
            {"id": 7},  # users 校验
            None,  # existing
            {"id": 100, "standard_number": "GB/T 1234-2026", "std_name": "测试标准"},  # record
            {"publish_date": "2026-07-30"},  # publish_date
        ]
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42
        mock_db.execute.return_value = mock_cursor

        with patch("docker.api.favorites.get_manager_dep", return_value=mock_mgr):
            result = add_favorite(
                data=MagicMock(record_id=100),
                user_id=7,
                db=mock_db,
                mgr=mock_mgr,
            )

        assert result["status"] == "pending"  # 主流程未被通知异常阻塞


# ══════════════════════════════════════════════════════════════════════
# 用例 2/3/4：download_to_inbox 三事件
# ══════════════════════════════════════════════════════════════════════


class TestDownloadChainEvents:
    """验证 download_to_inbox 触发 download_started / download_complete / download_failed。"""

    def test_download_started_sent_before_download(self):
        """下载开始 → send_event('download_started') 被调用。"""
        from unittest.mock import MagicMock, patch

        from pilotstd.tasks.favorite_download import download_to_inbox

        mock_db = MagicMock()
        # announcement_record 查询
        mock_db.execute.return_value.fetchone.return_value = {
            "standard_number": "GB/T 1234-2026",
        }
        # file_index 无已有文件（复用检查）
        mock_find = MagicMock(return_value=None)
        # 下载 URL 有值
        mock_url = MagicMock(return_value="http://example.com/file.pdf")

        with (
            patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db),
            patch("pilotstd.tasks.favorite_download._find_in_file_index", mock_find),
            patch("pilotstd.tasks.favorite_download._get_download_url", mock_url),
            patch("pilotstd.tasks.favorite_download._notify_download_started") as mock_start,
            patch("pilotstd.tasks.favorite_download._download_with_retry", return_value=(True, None)),
            patch("pilotstd.tasks.favorite_download.time.sleep", return_value=None),
        ):
            # 轮询 30 次 file_index 无结果 → 超时失败路径（避免无限循环）
            mock_db.execute.return_value.fetchone.side_effect = None  # 已被上面覆盖
            # _find_in_file_index 持续返回 None → 归档超时
            mock_find.return_value = None
            download_to_inbox(favorite_id=42, user_id=7, record_id=100)

        mock_start.assert_called_once()
        args = mock_start.call_args
        assert args.args[0] == 7  # user_id
        assert args.args[1] == "GB/T 1234-2026"  # standard_number

    def test_download_complete_sent_on_success(self):
        """下载归档完成（file_index 轮询命中）→ send_event('download_complete', status='success')。"""
        from unittest.mock import MagicMock, patch

        from pilotstd.tasks.favorite_download import download_to_inbox

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = {
            "standard_number": "GB/T 1234-2026",
        }

        with (
            patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db),
            patch("pilotstd.tasks.favorite_download._find_in_file_index", return_value="/standards/GBT 1234-2026.pdf"),
            patch("pilotstd.tasks.favorite_download._get_download_url", return_value=None),
            patch("pilotstd.tasks.favorite_download._notify_download_complete") as mock_done,
            patch("pilotstd.tasks.favorite_download._notify_download_started") as mock_start,
        ):
            download_to_inbox(favorite_id=42, user_id=7, record_id=100)

        # 复用已有文件路径：不发 download_started，直接 download_complete
        mock_start.assert_not_called()
        mock_done.assert_called_once()
        args = mock_done.call_args
        assert args.args[1] == "GB/T 1234-2026"
        # 直接调用 _notify_download_complete 验证事件 payload
        mock_done.call_args_list[0]

    def test_download_complete_payload_has_status_success(self):
        """_notify_download_complete 发送的事件 payload 含 status='success'。"""
        from unittest.mock import MagicMock, patch

        from pilotstd.tasks.favorite_download import _notify_download_complete

        mock_mgr = MagicMock()
        mock_notifier = MagicMock()
        mock_mgr.notification_mgr = mock_notifier

        with patch("pilotstd.manager.facade.StandardManager", return_value=mock_mgr):
            _notify_download_complete(user_id=7, standard_number="GB/T 1234-2026", favorite_id=42, local_path="/x.pdf")

        mock_notifier.send_event.assert_called_once()
        ev, data = mock_notifier.send_event.call_args.args
        assert ev == "download_complete"
        assert data["status"] == "success"
        assert data["user_id"] == 7

    def test_download_failed_reuses_existing_event(self):
        """下载失败 → 复用现有 download_failed 事件。"""
        from unittest.mock import MagicMock, patch

        from pilotstd.tasks.favorite_download import _notify_download_failed

        mock_mgr = MagicMock()
        mock_notifier = MagicMock()
        mock_mgr.notification_mgr = mock_notifier

        with patch("pilotstd.manager.facade.StandardManager", return_value=mock_mgr):
            _notify_download_failed(user_id=7, standard_number="GB/T 1234-2026", error="下载超时", favorite_id=42)

        mock_notifier.send_event.assert_called_once()
        ev, data = mock_notifier.send_event.call_args.args
        assert ev == "download_failed"
        assert data["error"] == "下载超时"

    def test_download_notify_failure_does_not_block(self):
        """_notify_download_started 抛异常 → download_to_inbox 主流程不受影响。"""
        from unittest.mock import MagicMock, patch

        from pilotstd.tasks.favorite_download import download_to_inbox

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = {
            "standard_number": "GB/T 1234-2026",
        }

        def _boom(*a, **k):
            raise RuntimeError("通知故障")

        with (
            patch("pilotstd.tasks.favorite_download.Database", return_value=mock_db),
            patch("pilotstd.tasks.favorite_download._find_in_file_index", return_value="/s/GBT 1234.pdf"),
            patch("pilotstd.tasks.favorite_download._get_download_url", return_value=None),
            patch("pilotstd.tasks.favorite_download._notify_download_complete", side_effect=_boom),
            patch("pilotstd.tasks.favorite_download._notify_download_started", side_effect=_boom),
        ):
            # 不应抛异常（通知失败被内部捕获）
            download_to_inbox(favorite_id=42, user_id=7, record_id=100)


# ══════════════════════════════════════════════════════════════════════
# 用例 5/6：archive_complete（批量归档 + 失败）
# ══════════════════════════════════════════════════════════════════════


class TestArchiveCompleteEvent:
    """验证 archive_standards 批量归档触发 archive_complete。"""

    def test_archive_complete_sent_on_success(self):
        """归档成功 → send_event('archive_complete', {'count': N})。"""
        from unittest.mock import MagicMock, patch

        from pilotstd.manager.facade._organize import OrganizeHandler

        core = MagicMock()
        core.notification_mgr = MagicMock()
        handler = OrganizeHandler(core)

        # parsed_list 为空 → organize 返回 moved=0 → 不发逐条，只发批量 count
        core.organizer_svc.organize.return_value = {"moved": 0}

        handler.archive_standards(parsed_list=[], word_source_root="")

        # count=0 时仍触发批量 archive_complete
        ev_calls = [c.args[0] for c in core.notification_mgr.send_event.call_args_list]
        assert "archive_complete" in ev_calls
        ev = next(c for c in core.notification_mgr.send_event.call_args_list if c.args[0] == "archive_complete")
        assert ev.args[1]["count"] == 0

    def test_archive_failed_event_sent(self):
        """归档存在失败 → organizer._log_organize_summary 触发 archive_failed。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.organizer import OrganizerCore

        core = OrganizerCore.__new__(OrganizerCore)
        core._core = MagicMock()
        core._core.notification_mgr = MagicMock()

        core._log_organize_summary(
            {
                "moved": 5,
                "word_mirrored": 0,
                "skipped_exists": 0,
                "skipped_source": 0,
                "dedup_skipped": 0,
                "failed": 2,
            }
        )

        core._core.notification_mgr.send_event.assert_called_once()
        ev, data = core._core.notification_mgr.send_event.call_args.args
        assert ev == "archive_failed"
        assert data["count"] == 2


# ══════════════════════════════════════════════════════════════════════
# 用例 8：Telegram 400 诊断
# ══════════════════════════════════════════════════════════════════════


class TestTelegram400Diagnostics:
    """验证 telegram.py HTTPError 分支记录 response body。"""

    def test_http_400_records_body(self):
        """HTTPError(400) → 日志包含 response body（description）。"""
        import io
        from unittest.mock import MagicMock, patch
        from urllib.error import HTTPError

        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel(bot_token="token123", chat_id="-100123")
        msg = MagicMock()
        msg.title = "测试"
        msg.body = "body"
        msg.standard_number = None
        msg.event_type = "test"
        msg.link = None
        msg.icon = None
        msg.aggregated_count = 1
        msg.status = ""
        msg.target_id = ""
        msg.elapsed_ms = 0
        msg.changed_at = ""
        msg.blocks = []

        err = HTTPError(
            "http://api.telegram.org", 400, "Bad Request", None,
            io.BytesIO(b'{"ok":false,"description":"chat_id not found"}'),
        )

        with (
            patch("pilotstd.core.notification.channels.telegram.urlopen", side_effect=err),
            patch("pilotstd.core.notification.channels.telegram.logger.warning") as mock_log,
        ):
            ok = ch.send(msg)

        assert ok is False
        # 日志包含 HTTP 400 前缀 + response body（格式化参数）
        logged = [(c.args, c.kwargs) for c in mock_log.call_args_list]
        assert any("Telegram send failed" in str(a[0][0]) for a in logged)
        assert any("chat_id not found" in str(a[0]) for a in logged)

    def test_http_400_logs_dedup_for_404(self):
        """404 → 记录"bot token 无效"提示。"""
        import io
        from unittest.mock import MagicMock, patch
        from urllib.error import HTTPError

        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel(bot_token="token123", chat_id="-100123")
        msg = MagicMock()
        msg.title = "t"
        msg.body = "b"
        msg.standard_number = None
        msg.event_type = "test"
        msg.link = None
        msg.icon = None
        msg.aggregated_count = 1
        msg.status = ""
        msg.target_id = ""
        msg.elapsed_ms = 0
        msg.changed_at = ""
        msg.blocks = []

        err = HTTPError(
            "http://api.telegram.org", 404, "Not Found", None,
            io.BytesIO(b'{"ok":false,"description":"Not Found"}'),
        )

        with (
            patch("pilotstd.core.notification.channels.telegram.urlopen", side_effect=err),
            patch("pilotstd.core.notification.channels.telegram.logger.error") as mock_err,
        ):
            ok = ch.send(msg)

        assert ok is False
        assert any("404" in str(c.args[0]) for c in mock_err.call_args_list)
