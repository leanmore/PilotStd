"""A-30：日志 API 只读字段与管理员诊断端点。"""

import json
from unittest.mock import MagicMock

import docker.api.notification_logs as logs_api


def test_task_context_view_filters_by_config():
    cfg = MagicMock()
    cfg.get.return_value = ["duration_seconds", "stage_tier"]
    raw = json.dumps({"duration_seconds": 12.5, "stage_tier": "long", "secret": "x"})
    assert logs_api.task_context_view(raw, cfg) == {"duration_seconds": 12.5, "stage_tier": "long"}


def test_task_context_view_bad_json_returns_empty():
    cfg = MagicMock()
    cfg.get.return_value = ["duration_seconds"]
    assert logs_api.task_context_view("not-json", cfg) == {}


def test_diagnostics_returns_exact_fields():
    nmgr = MagicMock()
    nmgr.ops.get_log_diagnostics.return_value = {
        "id": 7,
        "callback_data": "7:1",
        "channel_message_ids": json.dumps({"telegram": "42"}),
        "actions": json.dumps([{"key": "retry"}]),
        "attachments": json.dumps([{"name": "a.pdf"}]),
        "extra_secret": "must-not-leak",
    }
    result = logs_api.get_log_diagnostics.__wrapped__(7, request=None, nmgr=nmgr)
    assert set(result) == {"id", "callback_data", "channel_message_ids", "actions", "attachments"}
    assert result["channel_message_ids"] == {"telegram": "42"}
