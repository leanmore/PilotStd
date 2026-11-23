"""收藏事件通知的日志契约（A-35 诊断日志清理配套，2026-11-24）。

背景：A-35 闭合后清理了 5 处 `[A35-DIAG]` 临时诊断日志（4 删 1 改）。
本测试锁住清理后的**日志契约**，防止「诊断日志被误加回来」或
「失败日志被一起删掉」。

关键取舍：`send failed` 的 **error 日志必须保留** —— 真实失败必须可见
（G-050 口径：失败不静默）。
"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import docker.api.favorites as fav_api  # noqa: E402


def test_no_a35_diag_logs_remain():
    """源码里不得再有 `[A35-DIAG]` 标记（A-35 已闭合，诊断日志应已清理）。"""
    src = (ROOT / "docker" / "api" / "favorites.py").read_text(encoding="utf-8")
    assert "[A35-DIAG]" not in src, "A-35 已闭合，临时诊断日志应已清理"


def test_send_failure_still_logs_error(caplog):
    """发送失败必须记 error（真实失败可见，不能随诊断日志一起删掉）。"""
    mgr = MagicMock()
    mgr.notification_mgr.send_event.side_effect = RuntimeError("boom")

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            fav_api._notify_favorite_created(mgr, user_id=7, payload={"a": 1})

    assert any(
        r.levelno >= logging.ERROR and "favorite_created" in r.getMessage()
        for r in caplog.records
    ), [r.getMessage() for r in caplog.records]


def test_normal_path_logs_no_info_noise(caplog):
    """正常发送路径不应产生 INFO 噪声（诊断日志已清理）。"""
    mgr = MagicMock()
    mgr.notification_mgr.send_event.return_value = None

    with caplog.at_level(logging.INFO):
        fav_api._notify_favorite_created(mgr, user_id=7, payload={"a": 1})

    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert not any("A35" in m for m in info_msgs), info_msgs


def test_missing_notification_mgr_logs_warning(caplog):
    """`notification_mgr` 为 None 时必须记 warning（不静默跳过）。"""
    mgr = MagicMock()
    mgr.notification_mgr = None

    with caplog.at_level(logging.WARNING):
        fav_api._notify_favorite_created(mgr, user_id=7, payload={"a": 1})

    assert any(
        r.levelno >= logging.WARNING and "notification_mgr" in r.getMessage()
        for r in caplog.records
    ), [r.getMessage() for r in caplog.records]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
