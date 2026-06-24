# pilotstd/core/notification/events.py
"""预置通知事件类型。"""

EVENT_ARCHIVE_COMPLETE = "archive_complete"
EVENT_STATUS_CHANGED = "standard_status_changed"
EVENT_EXPIRED = "standard_expired"
EVENT_FIRST_REGISTERED = "standard_first_registered"
EVENT_CHECK_BATCH_COMPLETE = "check_batch_complete"

ALL_EVENTS = [
    EVENT_ARCHIVE_COMPLETE,
    EVENT_STATUS_CHANGED,
    EVENT_EXPIRED,
    EVENT_FIRST_REGISTERED,
    EVENT_CHECK_BATCH_COMPLETE,
]
