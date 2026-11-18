"""通知日志业务级别：安全告警/任务失败不得显示为 info。"""
from docker.api.notification_logs import _business_level


def test_business_level_mapping():
    assert _business_level("security_alert") == "warning"
    assert _business_level("task_failure") == "error"
    assert _business_level("task_result") == "info"
