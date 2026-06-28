# pilotstd/core/notification/events.py
"""预置通知事件类型。"""

EVENT_ARCHIVE_COMPLETE = "archive_complete"
EVENT_STATUS_CHANGED = "standard_status_changed"
EVENT_EXPIRED = "standard_expired"
EVENT_FIRST_REGISTERED = "standard_first_registered"
EVENT_CHECK_BATCH_COMPLETE = "check_batch_complete"
EVENT_ANNOUNCEMENT_FETCH = "announcement_fetch_complete"
EVENT_AUTO_BACKUP = "auto_backup"
EVENT_ANNOUNCEMENT_CHECK = "announcement_check_complete"
EVENT_BATCH_DOWNLOAD = "batch_download_complete"

ALL_EVENTS = [
    EVENT_ARCHIVE_COMPLETE,
    EVENT_STATUS_CHANGED,
    EVENT_EXPIRED,
    EVENT_FIRST_REGISTERED,
    EVENT_CHECK_BATCH_COMPLETE,
    EVENT_ANNOUNCEMENT_FETCH,
    EVENT_AUTO_BACKUP,
    EVENT_ANNOUNCEMENT_CHECK,
    EVENT_BATCH_DOWNLOAD,
]
