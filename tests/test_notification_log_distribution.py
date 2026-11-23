"""G-43：通知日志 event_type × level 分布端点（2026-11-24）。

背景：G-43 记录「`notification_log` 的 info/warning 计数口径是否偏差，待核实
（缺两时点分布）」。此前只能手工 SQL 到生产库查，而 `level` 是**动态计算**的
（`_business_level(event_type)`，非存储字段），手工算容易与代码口径不一致。

新增 `GET /api/notification/logs/stats/distribution`（仅管理员、只读）后，
运维可间隔取两次做对比。本测试锁住：
  1. level 口径与列表接口**完全一致**（同一个 `_business_level`）
  2. 分布聚合正确（by_level / by_event_type / total）
  3. 只读：不写库
"""

from unittest.mock import MagicMock

import docker.api.notification_logs as logs_api


def _nmgr_with(rows):
    nmgr = MagicMock()
    nmgr.ops._db.fetchall.return_value = rows
    return nmgr


def test_business_level_rule_is_stable():
    """level 计算规则必须稳定（列表与分布共用同一函数）。"""
    assert logs_api._business_level("security_alert") == "warning"
    assert logs_api._business_level("task_failure") == "error"
    assert logs_api._business_level("task_completed") == "info"
    assert logs_api._business_level("anything_else") == "info"


def test_distribution_counts_by_level_and_event():
    """分布按 level 与 event_type 双维度聚合。"""
    rows = [
        {"event_type": "security_alert"},
        {"event_type": "security_alert"},
        {"event_type": "task_failure"},
        {"event_type": "task_completed"},
        {"event_type": "task_completed"},
        {"event_type": "task_completed"},
    ]
    result = logs_api.get_log_level_distribution.__wrapped__(
        request=MagicMock(), days=7, nmgr=_nmgr_with(rows)
    )

    assert result["days"] == 7
    assert result["total"] == 6
    assert result["by_level"] == {"error": 1, "info": 3, "warning": 2}
    assert result["by_event_type"]["task_completed"] == 3
    assert result["by_event_type"]["security_alert"] == 2
    assert result["by_event_type"]["task_failure"] == 1


def test_distribution_empty_table():
    """空表 → 全零，不抛异常。"""
    result = logs_api.get_log_level_distribution.__wrapped__(
        request=MagicMock(), days=7, nmgr=_nmgr_with([])
    )
    assert result["total"] == 0
    assert result["by_level"] == {}
    assert result["by_event_type"] == {}


def test_distribution_is_read_only():
    """只读性反证：只调 `fetchall`，绝不调 `execute`（不写库）。"""
    nmgr = _nmgr_with([{"event_type": "task_completed"}])
    logs_api.get_log_level_distribution.__wrapped__(
        request=MagicMock(), days=7, nmgr=nmgr
    )
    nmgr.ops._db.execute.assert_not_called()


def test_distribution_exposes_level_rule():
    """返回体带 level 规则说明，便于运维核对口径（避免「猜为什么这条是 warning」）。"""
    result = logs_api.get_log_level_distribution.__wrapped__(
        request=MagicMock(), days=7, nmgr=_nmgr_with([])
    )
    assert result["level_rule"]["security_alert"] == "warning"
    assert result["level_rule"]["task_failure"] == "error"
