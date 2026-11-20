"""通知日志业务级别：安全告警/任务失败不得显示为 info。

2026-11-20 补：`level` 曾在 `_business_level()` 里算出来、却因响应模型
`NotificationLogItem` 未声明该字段而被 FastAPI 过滤掉 —— 前端映射层拿不到，
铃铛按 `msg.level` 着色的分支恒为 info（假闭合）。本文件锁定“接口真要吐出 level”。
"""
from docker.api.notification_logs import NotificationLogItem, _business_level


def test_business_level_mapping():
    assert _business_level("security_alert") == "warning"
    assert _business_level("task_failure") == "error"
    assert _business_level("task_result") == "info"


def test_response_model_declares_level():
    """响应模型必须声明 level，否则按 response_model 序列化时字段被静默丢弃。"""
    assert "level" in NotificationLogItem.model_fields


def test_response_model_keeps_level_value():
    """用模型校验一条带 level 的记录，序列化后仍应保留该字段与取值。"""
    item = NotificationLogItem(
        id=1,
        event_type="security_alert",
        channel="wechat",
        title="t",
        body="b",
        standard_number=None,
        status="sent",
        level=_business_level("security_alert"),
        error_msg=None,
        sent_at="2026-11-20T12:00:00+08:00",
        is_read=0,
        failed_count=0,
        notify_event="security",
        task_context={},
    )
    dumped = item.model_dump()
    assert dumped["level"] == "warning"
