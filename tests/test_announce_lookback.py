"""公告定时漏跑：lookback 应覆盖实际 gap（超过默认 7 天）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pilotstd.manager.announce_service import AnnounceService


def test_scheduled_lookback_covers_missed_gap():
    file_index = MagicMock()
    mgr = MagicMock()
    mgr.cfg.get.return_value = 7
    svc = AnnounceService(file_index, manager=mgr)
    with patch.object(svc, "_is_manual_running", return_value=False), patch.object(
        svc, "_missed_gap_hours", return_value=240
    ), patch.object(svc, "_get_user_since_date", return_value=""), patch.object(
        svc, "_after_fetch"
    ), patch.object(
        svc.crawler, "check_all", return_value={"ok": True}
    ) as check_all:
        svc.check_announce_scheduled()
    assert check_all.call_args.kwargs["lookback_days"] >= 10


def test_scheduled_lookback_uses_config_when_no_gap():
    file_index = MagicMock()
    mgr = MagicMock()
    mgr.cfg.get.return_value = 7
    svc = AnnounceService(file_index, manager=mgr)
    with patch.object(svc, "_is_manual_running", return_value=False), patch.object(
        svc, "_missed_gap_hours", return_value=0
    ), patch.object(svc, "_get_user_since_date", return_value=""), patch.object(
        svc, "_after_fetch"
    ), patch.object(
        svc.crawler, "check_all", return_value={"ok": True}
    ) as check_all:
        svc.check_announce_scheduled()
    assert check_all.call_args.kwargs["lookback_days"] == 7
