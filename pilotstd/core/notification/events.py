# 模块：项目/核心//脚本
"""预置通知事件类型——单一数据源（SSOT）。

所有后端事件定义集中于此。新增事件只需在 ALL_EVENTS 中加一行，
ALL_EVENT_KEYS / BYPASS_EVENTS 自动派生，defaults / manager / API 全部同步。

v1.1（Step 2a）：所有事件均经 L2 聚合器（bypass_aggregation 全部为 False），
用户可通过 Web 设置页关闭聚合（notification.aggregate_enabled=False）恢复实时通知。
bypass_aggregation 参数保留仅为兼容旧签名，语义已废弃，一律取默认 False。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventDef:
    """通知事件元数据。

    bypass_aggregation 参数已废弃（v1.1 起所有事件均聚合），仅保留字段兼容。
    """

    key: str
    bypass_aggregation: bool = False  # 已废弃：恒为 False，保留字段兼容


# ── 事件常量（向后兼容旧代码中的字符串引用） ──

EVENT_ARCHIVE_COMPLETE = "archive_complete"
EVENT_STATUS_CHANGED = "standard_status_changed"
EVENT_EXPIRED = "standard_expired"
EVENT_FIRST_REGISTERED = "standard_first_registered"
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
EVENT_DOWNLOAD_FAILED = "download_failed"
EVENT_ARCHIVE_ABANDONED = "archive_abandoned"
EVENT_NORMALIZE_COMPLETE = "normalize_complete"
EVENT_SCAN_COMPLETE = "scan_complete"
EVENT_TASK_EXECUTION_FAILED = "task_execution_failed"
EVENT_SCAN_EMPTY = "scan_empty"
EVENT_QUERY_FAILED = "query_failed"
EVENT_QUERY_EMPTY = "query_empty"
EVENT_ARCHIVE_FAILED = "archive_failed"
EVENT_ANNOUNCEMENT_FETCH_FAILED = "announcement_fetch_failed"
EVENT_NORMALIZE_FAILED = "normalize_failed"
EVENT_EXPIRE_STANDARD_MOVED = "expire_standard_moved"
EVENT_REPLACEMENT_NOT_FOUND = "replacement_not_found"
EVENT_QUOTA_EXHAUSTED = "quota_exhausted"
EVENT_ANNOUNCE_FETCH_SUMMARY = "announce_fetch_summary"
EVENT_FAVORITE_CREATED = "favorite_created"
EVENT_DOWNLOAD_STARTED = "download_started"
EVENT_DOWNLOAD_COMPLETE = "download_complete"
# 收藏告终汇总：**仅在实际发生放弃时**发送一次（P0 修复）。
# 背景：`abandoned` 是终态，系统**永远不会再自动重试**；
# 而原先该状态被并进 `batch_download_complete` 的 failed 计数里，
# 用户看不出"哪些已经彻底放弃、需要人工介入"。本事件承担该告终语义：
# 含总数 + 原因分类 + 操作建议。
EVENT_FAVORITE_ABANDONED_SUMMARY = "favorite_abandoned_summary"
# 通知投递失败告警（P0）：**通知系统自身故障**的唯一出口。
# 生产实测：32 天内 629 条发送失败（54.8%），连续 7 天每天失败 25~151 条，
# 全程无人知晓。本事件在"连败"或"窗口失败率超阈"时发出，避免"通知坏了没人知道"。
EVENT_NOTIFICATION_DELIVERY_FAILED = "notification_delivery_failed"

# ── 安全告警（第 2 批：安全与审计闭环）──
# 这三个事件的投递由 security_notifier 直连旧渠道同步发送，不经聚合器与静音时段
# （否则凭证变更告警会被推迟到新凭证落库之后，流向新地址）。
EVENT_NOTIFICATION_CREDENTIAL_CHANGED = "notification_credential_changed"
EVENT_SECURITY_PASSWORD_CHANGED = "security_password_changed"
EVENT_SECURITY_TOKEN_REFRESHED = "security_token_refreshed"
EVENT_SECURITY_LOGIN_FAILED = "security_login_failed"

# ── 平台层事件（阶段 4 · P6 · 4c）──
# `desktop_toast` 是 **L2 桌面协调层**向 L1 聚合器投递时使用的标签（唯一产出点
# `pilotstd/core/notification_aggregator.py` 的 `push(event_type="desktop_toast", ...)`）。
# 它此前**未登记进本清单**（G-045 盲区，旧处置＝方案 B"显式声明未覆盖"）；
# 用户裁决 Q10（2026-10-02）＝**借阶段 4 正式登记**（方案 A），本批执行。
# 语义：平台层回显（同一条通知在桌面端的本地呈现），**不是**新的业务事件 ⇒ 归 `system_health`、
# `subscribable=False`（不进用户配置入口，与 `notification_delivery_failed` 同口径）。
EVENT_DESKTOP_TOAST = "desktop_toast"

# ── 唯一数据源：所有事件定义（全部经第二层聚合器，无绕过） ──

ALL_EVENTS: list[EventDef] = [
    EventDef(EVENT_ARCHIVE_COMPLETE),
    EventDef(EVENT_STATUS_CHANGED),
    EventDef(EVENT_FIRST_REGISTERED),
    EventDef(EVENT_ANNOUNCEMENT_FETCH),
    EventDef(EVENT_AUTO_BACKUP),
    EventDef(EVENT_ANNOUNCEMENT_CHECK),
    EventDef(EVENT_BATCH_DOWNLOAD),
    EventDef(EVENT_AUTO_SCAN_FAILED),
    EventDef(EVENT_VALIDITY_BATCH_REPORT),
    EventDef(EVENT_VALIDITY_ROUND_SUMMARY),
    EventDef(EVENT_VALIDITY_STANDARD_FAILED),
    EventDef(EVENT_VALIDITY_SYSTEM_FAILED),
    EventDef("image_update_available"),
    EventDef("batch_query_summary"),
    EventDef("trust_ip_update"),
    EventDef("worker_error"),
    EventDef(EVENT_DATE_REMINDER),
    EventDef(EVENT_DOWNLOAD_FAILED),
    EventDef(EVENT_ARCHIVE_ABANDONED),
    EventDef(EVENT_NORMALIZE_COMPLETE),
    EventDef(EVENT_SCAN_COMPLETE),
    EventDef(EVENT_TASK_EXECUTION_FAILED),
    EventDef(EVENT_SCAN_EMPTY),
    EventDef(EVENT_QUERY_FAILED),
    EventDef(EVENT_QUERY_EMPTY),
    EventDef(EVENT_ARCHIVE_FAILED),
    EventDef(EVENT_ANNOUNCEMENT_FETCH_FAILED),
    EventDef(EVENT_NORMALIZE_FAILED),
    EventDef(EVENT_EXPIRE_STANDARD_MOVED),
    EventDef(EVENT_REPLACEMENT_NOT_FOUND),
    EventDef(EVENT_QUOTA_EXHAUSTED),
    EventDef(EVENT_ANNOUNCE_FETCH_SUMMARY),
    EventDef(EVENT_FAVORITE_CREATED),
    EventDef(EVENT_DOWNLOAD_STARTED),
    EventDef(EVENT_DOWNLOAD_COMPLETE),
    EventDef(EVENT_FAVORITE_ABANDONED_SUMMARY),
    EventDef(EVENT_NOTIFICATION_DELIVERY_FAILED),
    EventDef(EVENT_NOTIFICATION_CREDENTIAL_CHANGED),
    EventDef(EVENT_SECURITY_PASSWORD_CHANGED),
    EventDef(EVENT_SECURITY_TOKEN_REFRESHED),
    EventDef(EVENT_SECURITY_LOGIN_FAILED),
    # 平台层（阶段 4 · P6 · 4c）：桌面弹层回显，登记以消除 G-045 盲区
    EventDef(EVENT_DESKTOP_TOAST),
]

# ── 派生变量（供各模块引用，避免硬编码重复） ──

ALL_EVENT_KEYS = [e.key for e in ALL_EVENTS]
# 所有事件均聚合，绕过聚合的集合恒为空（兼容旧签名，语义废弃）
BYPASS_EVENTS = frozenset(e.key for e in ALL_EVENTS if e.bypass_aggregation)
