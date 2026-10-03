# 模块：项目/核心//锁脚本
"""业务事件 → 通知事件的**投影**（阶段 2a，纯新增，零行为变更）。

## 它在三层模型里的位置

```
业务事件（41 个，内部语义，代码直呼）          ← events.py 的 ALL_EVENTS
      │  project(event_type, data)            ← **本模块**
      ▼
通知事件（7 类，用户视角）                     ← NOTIFY_EVENTS
      │
      ▼
内容类型（决定"长什么样"）                     ← CONTENT_TYPES（及 renderer 的 Block）
```

现有实现把这层压在 `event_type` 一个字段里，导致"分类维度是系统模块而不是用户意图"
（见 01-现状盘点.md §1.2 的关键观察）。

## 阶段 2a 的边界（**重要**）

- **本批不接入 `send_event`**：`mapping.py` 是纯新增模块，2a 交付后没有任何生产代码调用它。
  接入与字段回填属阶段 2b（见 06-阶段0-1实施方案.md §3.2）。
- **不 import `task` 模块**：避免 `notification → task` 依赖环；`task_kind` 只是**词表值**
  （与 `task_queue.task_type` 取值对齐），不等于 Task 实体的类型。
- **4 个分支归属事件不实现分支判定**：`auto_backup` / `image_update_available` /
  `validity_batch_report` / `validity_round_summary` 会按 `data` 内容落到不同通知事件
  （成功走 task_lifecycle、失败走 anomaly_alert）。本批**恒返回单值**（见下方 `_BRANCH_PENDING`
  与各条目的注释），但 `project()` 的签名**已接收 `data`**，为后续批次留门。

## 语义约定（由单测钉死）

1. **未知 `event_type` → `notify_event=""`**（回退语义）。接入方（阶段 2b）必须把空值当作
   "未映射，走原有行为"，**不得**当作错误抛出。
2. **41 个已注册事件全部有归属**：不得有事件落到 `""`（由 `tests/test_notification_stage2a_mapping.py`
   的表驱动用例逐事件断言）。
3. 映射表是**唯一数据源**（`EVENT_MAPPINGS`）：新增业务事件时必须同步登记，否则上一条会失败。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = [
    "CONTENT_TYPES",
    "EVENT_MAPPINGS",
    "NOTIFY_EVENTS",
    "TASK_KINDS",
    "EventMapping",
    "NotificationProjection",
    "project",
]

# ── 通知事件（7 类，用户视角）────────────────────────────────────────────────
# 定义见 docs/plans/notification-redesign/02-目标架构.md §2.1。
# 设计约束：数量封顶 7±1；新增一类的准入条件是"现有 7 类没有任何一类的
# 默认渠道 + 默认 level + 交互需求三者能容纳它"。
NOTIFY_EVENTS: tuple[str, ...] = (
    "task_lifecycle",  # 我交办的事有进展/有结果了
    "batch_summary",  # 这批活干完了，结果如何
    "anomaly_alert",  # 出问题了，可能需要你处理
    "security_alert",  # 有人动了你的配置/凭证
    "schedule_reminder",  # 到时间了，该做这件事
    "system_health",  # 系统自己出状况了
    "manual_test",  # 手动测试消息
)

# ── 内容类型（6 种）───────────────────────────────────────────────────────────
# 1–4 对应现有 Block（text/field_list/status_change/list），5–6 为阶段 3 新增。
CONTENT_TYPES: tuple[str, ...] = (
    "text",
    "field_list",
    "status_change",
    "list",
    "task_progress",
    "action_prompt",
)

# ── 任务种类（业务域名词，非定时任务名）────────────────────────────────────────
# 与 `_builders_system.py::_TASK_NAME_KEY_MAP` 的**关系校正**（2026-10-02 实测）：
# 02-目标架构.md §2.3 原文称"九个值恰好对应现有 9 个定时任务名"，**实测不成立**——
# 那张表是 9 个**定时任务**名（auto_announce / auto_archive_retry / auto_backup /
# auto_health_check / auto_scan / date_reminder / notification_cleanup /
# release_suppressed / validity_check），与本元组的**业务域**名词不同轴：
# 前者是"哪个 cron 在跑"，后者是"用户交办的是哪类事"（一个任务名可产出多个 task_kind 的通知，
# 如 auto_scan 产出 scan 类；一个 task_kind 也可被多个任务写，如 organize 由扫描/整理两条路写）。
# 故本元组是**新词表**，不是既有表的别名——"复用既有词表"的表述在此更正。
TASK_KINDS: tuple[str, ...] = (
    "announce_fetch",
    "scan",
    "query",
    "organize",
    "normalize",
    "favorite_download",
    "validity_check",
    "backup",
    "image_update",
)

# 阶段 2b/后续批次需按 `data` 分支的事件（本批恒返回单值，先登记以免被遗忘）
_BRANCH_PENDING: frozenset[str] = frozenset(
    {
        "auto_backup",  # 成功 → task_lifecycle；失败 → anomaly_alert（判据 data["success"]）
        "image_update_available",  # 版本变更 → task_lifecycle；error 分支 → anomaly_alert
        "validity_batch_report",  # 无失败 → batch_summary；有失败 → anomaly_alert
        "validity_round_summary",  # 同上
    }
)


@dataclass(frozen=True)
class EventMapping:
    """单个业务事件的投影声明。"""

    notify_event: str  # 必须取自 NOTIFY_EVENTS
    content_type: str  # 必须取自 CONTENT_TYPES
    task_kind: str = ""  # 取自 TASK_KINDS；无任务语义时留空


@dataclass
class NotificationProjection:
    """`project()` 的返回值——业务事件到通知事件层的**投影结果**。

    阶段 2a 只填前三个字段（纯查表即可确定）；后两个需要**运行期上下文**
    （任务实体状态、同一批次的其他事件），由阶段 2b 接入时填充。
    """

    notify_event: str = ""  # 空 = 未映射（未知事件），接入方应回退原有行为
    content_type: str = ""
    task_kind: str = ""
    # ── 以下字段阶段 2a 恒为空，属"接口留门" ──────────────────────────────
    correlation_id: str = ""  # 同一次业务运行的关联键（建议 f"{task_kind}:{started_at[:19]}"）
    task_context: dict[str, Any] = field(default_factory=dict)  # 任务上下文快照


# ── 映射表（**唯一数据源**，覆盖全部 41 个已注册事件）─────────────────────────
# 分类原则（用户 2026-10-02 裁决）：**代表"一次批量运行的总结"归 batch_summary，
# 代表"单条任务终局"归 task_lifecycle。**
#
# 与 04-影响面.md §4.1 归属表的**已知不一致**（4 处，本表以"单条终局"原则为准，见表后注释）：
#   archive_failed / normalize_failed → 04 表列 anomaly_alert，本表列 task_lifecycle
#     （它们是"单条/单类的终局失败"，与 archive_complete/normalize_complete 对称；
#      真正的系统级失败走 task_execution_failed / worker_error）
#   validity_batch_report / validity_round_summary → 04 表列 anomaly_alert，本表列 batch_summary
#     （二者都是"一轮批量校验的汇总"，与 batch_summary 的定义相符；其失败子集的分支判定
#      留待后续批次，见 _BRANCH_PENDING）
EVENT_MAPPINGS: dict[str, EventMapping] = {
    # ── task_lifecycle：单条任务的终局（含"做了但没成"）─────────────────────
    "favorite_created": EventMapping("task_lifecycle", "field_list", "favorite_download"),
    "download_started": EventMapping("task_lifecycle", "field_list", "favorite_download"),
    "download_complete": EventMapping("task_lifecycle", "field_list", "favorite_download"),
    "download_failed": EventMapping("task_lifecycle", "text", "favorite_download"),
    "archive_complete": EventMapping("task_lifecycle", "list", "organize"),
    # archive_failed：单类归档失败（系统级失败另有 task_execution_failed）
    "archive_failed": EventMapping("task_lifecycle", "text", "organize"),
    "archive_abandoned": EventMapping("task_lifecycle", "text", "favorite_download"),
    "normalize_complete": EventMapping("task_lifecycle", "text", "normalize"),
    # normalize_failed：同上，单条规范化失败
    "normalize_failed": EventMapping("task_lifecycle", "text", "normalize"),
    "scan_complete": EventMapping("task_lifecycle", "list", "scan"),
    "scan_empty": EventMapping("task_lifecycle", "text", "scan"),
    # query_failed：单条标准查询失败（属"我交办的单件事没成"；批量汇总走 batch_query_summary）
    "query_failed": EventMapping("task_lifecycle", "text", "query"),
    "expire_standard_moved": EventMapping("task_lifecycle", "text", "organize"),
    "replacement_not_found": EventMapping("task_lifecycle", "text", "query"),
    # standard_first_registered：新增标准首次登记（与 standard_status_changed 同族，
    # 但语义是"数据集合发生变化"而非"到时间了"。02 表把它归 schedule_reminder，
    # 本表按"单条事项有结果"归 task_lifecycle——不一致处，见本文件顶部说明）
    "standard_first_registered": EventMapping("task_lifecycle", "list", "validity_check"),
    # ── batch_summary：一次批量运行的总结 ──────────────────────────────────
    "batch_download_complete": EventMapping("batch_summary", "list", "favorite_download"),
    "favorite_abandoned_summary": EventMapping("batch_summary", "list", "favorite_download"),
    "batch_query_summary": EventMapping("batch_summary", "list", "query"),
    "query_empty": EventMapping("batch_summary", "text", "query"),
    "auto_scan_failed": EventMapping("batch_summary", "text", "scan"),
    "announce_fetch_summary": EventMapping("batch_summary", "list", "announce_fetch"),
    "announcement_fetch_complete": EventMapping("batch_summary", "list", "announce_fetch"),
    "announcement_check_complete": EventMapping("batch_summary", "list", "announce_fetch"),
    "announcement_fetch_failed": EventMapping("batch_summary", "text", "announce_fetch"),
    # validity_batch_report / validity_round_summary：一轮批量校验的汇总
    "validity_batch_report": EventMapping("batch_summary", "list", "validity_check"),
    "validity_round_summary": EventMapping("batch_summary", "list", "validity_check"),
    # ── anomaly_alert：需要人处理的问题 ────────────────────────────────────
    "task_execution_failed": EventMapping("anomaly_alert", "text", ""),
    "worker_error": EventMapping("anomaly_alert", "text", ""),
    # auto_backup / image_update_available：成功分支属 task_lifecycle（见 _BRANCH_PENDING）
    "auto_backup": EventMapping("anomaly_alert", "field_list", "backup"),
    "image_update_available": EventMapping("anomaly_alert", "text", "image_update"),
    "quota_exhausted": EventMapping("anomaly_alert", "text", ""),
    "validity_standard_failed": EventMapping("anomaly_alert", "text", "validity_check"),
    "validity_system_failed": EventMapping("anomaly_alert", "text", "validity_check"),
    # ── system_health：通知系统自身故障 ────────────────────────────────────
    "notification_delivery_failed": EventMapping("system_health", "text", ""),
    # ── schedule_reminder：到时间了 ────────────────────────────────────────
    "date_reminder": EventMapping("schedule_reminder", "field_list", ""),
    "standard_status_changed": EventMapping("schedule_reminder", "status_change", "validity_check"),
    # ── security_alert：三个共用物理调用点（event_type 是变量）+ 登录失败 ────
    # 显式登记三个键：security_notifier.py 用一个物理调用点发三种事件，
    # 静态扫描识别不了，只能靠本表人工登记（这正是"间接载荷"盲区）
    "notification_credential_changed": EventMapping("security_alert", "list", ""),
    "security_password_changed": EventMapping("security_alert", "list", ""),
    "security_token_refreshed": EventMapping("security_alert", "text", ""),
    "security_login_failed": EventMapping("security_alert", "field_list", ""),
    # trust_ip_update：企业微信「可信 IP」变更——属**渠道信任关系**变更（与凭证变更同族），
    # 故归 security_alert 而非 system_health。载荷只有 title/body（调用点直出，P2 残留）
    "trust_ip_update": EventMapping("security_alert", "field_list", ""),
}


def project(event_type: str, data: Mapping[str, Any]) -> NotificationProjection:
    """把业务事件投影到通知事件层。

    :param event_type: 业务事件 key（`events.py::ALL_EVENTS` 之一）
    :param data: 事件载荷。**阶段 2a 不读它**（4 个分支归属事件的分支判定留待后续批次），
        但签名已接收，以免后续批次改签名波及调用方。
    :return: `NotificationProjection`；**未知事件类型时 `notify_event=""`**（回退语义，
        接入方应据此走原有行为，不得抛错）。

    **为什么接收 `data` 却不用**：见模块 docstring 的"4 个分支归属事件"。
    参数名保持 `data`（与既有构建器 `_build_*(data)` 同口径）。
    """
    del data  # 阶段 2a 不读载荷；保留形参为后续批次留门（见 docstring）
    mapping = EVENT_MAPPINGS.get(event_type)
    if mapping is None:
        return NotificationProjection()
    return NotificationProjection(
        notify_event=mapping.notify_event,
        content_type=mapping.content_type,
        task_kind=mapping.task_kind,
        # correlation_id / task_context 需运行期上下文，阶段 2b 填充
    )
