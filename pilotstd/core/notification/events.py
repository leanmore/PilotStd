# pilotstd/core/notification/events.py
"""预置通知事件类型——单一数据源（SSOT）。

所有后端事件定义集中于此。新增事件只需在 ALL_EVENTS 中加一行，
ALL_EVENT_KEYS / BYPASS_EVENTS 自动派生，defaults / manager / API 全部同步。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventDef:
    """通知事件元数据。"""

    key: str
    bypass_aggregation: bool = False  # True → 跳过聚合器，实时发送


# ── 事件常量（向后兼容旧代码中的字符串引用） ──

EVENT_ARCHIVE_COMPLETE = "archive_complete"
EVENT_STATUS_CHANGED = "standard_status_changed"
EVENT_EXPIRED = "standard_expired"
EVENT_FIRST_REGISTERED = "standard_first_registered"
EVENT_CHECK_BATCH_COMPLETE = "check_batch_complete"
EVENT_ANNOUNCEMENT_FETCH = "announcement_fetch_complete"
EVENT_AUTO_BACKUP = "auto_backup"
EVENT_ANNOUNCEMENT_CHECK = "announcement_check_complete"
EVENT_BATCH_DOWNLOAD = "batch_download_complete"
EVENT_AUTO_SCAN_FAILED = "auto_scan_failed"
EVENT_VALIDITY_BATCH_REPORT = "validity_batch_report"
EVENT_VALIDITY_ROUND_SUMMARY = "validity_round_summary"
EVENT_VALIDITY_STANDARD_FAILED = "validity_standard_failed"
EVENT_VALIDITY_SYSTEM_FAILED = "validity_system_failed"
EVENT_DATE_REMINDER = "date_reminder"

# ── 唯一数据源：所有事件定义 ──

ALL_EVENTS: list[EventDef] = [
    EventDef(EVENT_ARCHIVE_COMPLETE),
    EventDef(EVENT_STATUS_CHANGED),
    EventDef(EVENT_EXPIRED),
    EventDef(EVENT_FIRST_REGISTERED),
    EventDef(EVENT_CHECK_BATCH_COMPLETE),
    EventDef(EVENT_ANNOUNCEMENT_FETCH),
    EventDef(EVENT_AUTO_BACKUP, bypass_aggregation=True),
    EventDef(EVENT_ANNOUNCEMENT_CHECK),
    EventDef(EVENT_BATCH_DOWNLOAD),
    EventDef(EVENT_AUTO_SCAN_FAILED, bypass_aggregation=True),
    EventDef(EVENT_VALIDITY_BATCH_REPORT),
    EventDef(EVENT_VALIDITY_ROUND_SUMMARY),
    EventDef(EVENT_VALIDITY_STANDARD_FAILED),
    EventDef(EVENT_VALIDITY_SYSTEM_FAILED, bypass_aggregation=True),
    EventDef("image_update_available", bypass_aggregation=True),
    EventDef("batch_query_summary"),
    EventDef("trust_ip_update", bypass_aggregation=True),
    EventDef("worker_error", bypass_aggregation=True),
    EventDef(EVENT_DATE_REMINDER),
]

# ── 派生变量（供各模块引用，避免硬编码重复） ──

ALL_EVENT_KEYS = [e.key for e in ALL_EVENTS]
BYPASS_EVENTS = frozenset(e.key for e in ALL_EVENTS if e.bypass_aggregation)
