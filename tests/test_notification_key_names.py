"""通知用户文案不得直接输出内部字段名。"""

from pilotstd.core.notification._builders_system import (
    _build_fallback_message,
    _build_trust_ip_update_message,
)


def _texts(msg) -> list[str]:
    out = []
    for block in msg.blocks:
        out.append(str(getattr(block, "key", "")))
        out.append(str(getattr(block, "value", "")))
        out.append(str(getattr(block, "text", "")))
    return out


def test_trust_ip_uses_localized_labels() -> None:
    msg = _build_trust_ip_update_message(
        {"ip": "1.2.3.4", "update_time": "2026-10-22", "status": "success", "body": "已更新"}
    )
    text = "\n".join(_texts(msg))
    assert "update_time" not in text
    assert "status" not in text
    assert "IP 地址" in text
    assert "成功" in text


def test_fallback_does_not_dump_raw_dict() -> None:
    msg = _build_fallback_message("unknown_event", {"internal_key": "value", "another_key": 1})
    text = "\n".join(_texts(msg))
    assert "internal_key" not in text
    assert "another_key" not in text
    assert "未分类通知" in msg.title
