"""公告通知展示：适配器名本地化、站内提示不重复。"""

from pilotstd.core.notification._links import attach_web_actions
from pilotstd.core.notification.channel import NotificationMessage


def test_fetch_summary_uses_readable_adapter_labels() -> None:
    from pilotstd.core.notification._builders_task_results import _build_announce_fetch_summary_message

    msg = _build_announce_fetch_summary_message(
        {
            "total_count": 0,
            "has_error": False,
            "adapters": [
                {"name": "samr_gb", "status": "success", "count": 0},
                {"name": "samr_hb", "status": "success", "count": 0},
                {"name": "samr_db", "status": "success", "count": 0},
            ],
        }
    )
    texts = [getattr(b, "key", "") for b in msg.blocks]
    assert "samr_gb" not in texts
    assert "国标" in texts


def test_web_hint_is_not_appended_twice() -> None:
    msg = NotificationMessage(title="测试")
    assert attach_web_actions(msg, None) is False
    assert attach_web_actions(msg, None) is False
    hints = [b for b in msg.blocks if "未配置站内访问地址" in getattr(b, "text", "")]
    assert len(hints) == 1
