# 模块：项目/核心//锁脚本
"""业务事件 → 通知事件的**投影**（阶段 2a，纯新增，零行为变更）。

## 它在三层模型里的位置

```
业务事件（41 个，内部语义，代码直呼）          ← events.py 的 ALL_EVENTS
      │  project(event_type, data)            ← **本模块**
      ▼
通知事件（10 类，用户视角）                     ← NOTIFY_EVENTS
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

from .event_spec import EVENT_SPECS

__all__ = [
    "CONTENT_TYPES",
    "EVENT_MAPPINGS",
    "NOTIFY_EVENTS",
    "TASK_KINDS",
    "EventMapping",
    "NotificationProjection",
    "project",
]

# ── 通知事件（10 类，用户视角）────────────────────────────────────────────────
# 定义见 docs/plans/notification-redesign/02-目标架构.md §2.1。
# 类别清单以 pilotstd/core/notification/event_spec.py 为准；数不封顶。
# 新增类别须同时在本元组与 event_spec.py 登记（否则 project() 的
# "notify_event 必须取自 NOTIFY_EVENTS"契约被破坏，见下方 EventMapping.notify_event 注释）。
NOTIFY_EVENTS: tuple[str, ...] = (
    "task_progress",  # 我交办的事正在进行（过程型快照）
    "task_result",  # 我交办的事成功了（终局·可展示结果）
    "task_failure",  # 我交办的事失败了（终局·需说明原因）
    "user_activity",  # 我自己触发的日常动作（公告拉取/收藏/收藏转下载）
    "batch_summary",  # 这批活干完了，结果如何
    "anomaly_alert",  # 出问题了，可能需要你处理
    "security_alert",  # 有人动了你的配置/凭证
    "schedule_reminder",  # 到时间了，该做这件事
    "system_health",  # 系统自己出状况了
    "manual_test",  # 手动测试消息（非业务类别，供手动测试路径使用）
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
# **消费时点（2026-10-02 裁决；2026-10-02 阶段 2.5a 起已落地）**：
# `task_kind` 的消费点是**阶段 2.5 的聚合键切换**（`notify_event × correlation_id × target_id`）
# 与阶段 3 的回调。**2b-接入期间**曾刻意保持"算而不落"（回填消息/落库/进白名单均无），
# 并由当时的 `TestTaskKindAntiCorrosion` 锁定；**2.5a 已按裁决翻转闸门**——
# 现在它是消息字段 + 队列白名单成员 + `notification_log.task_kind` 列，
# 由 `tests/test_notification_stage2b_wiring.py::TestTaskKindPersisted` 锁定。
#
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
# **派生**（2026-10-03 步 B 第一步）：本表不再手写——三个投影字段一律取自事件规格声明；
# 上方分类原则与「与 04 表已知不一致」的说明保留（追溯用）。
EVENT_MAPPINGS: dict[str, EventMapping] = {
    s.key: EventMapping(s.notify_event, s.content_type, s.task_kind) for s in EVENT_SPECS
}


# ── 单向翻译：task_kind → task_type（阶段 2.5a）────────────────────────────────
# **双 SSOT 约定**（用户 2026-10-02 裁决）：
#   * `task_kind` 是**通知视角**的 SSOT —— 回答"用户交办的是哪类事"，值域见 TASK_KINDS；
#     其数据源就是本模块（`mapping.py`）。
#   * `task_type` 是**执行队列视角**的 SSOT —— 回答"哪个任务在跑"，
#     值域见 `pilotstd/task/models.py::TaskType`（scan/query/download/organize/expire），
#     其数据源是 `pilotstd/task/`。
# 本表**只做翻译**，不改变两侧任何一侧的权威性；**只做单向**
# （`task_kind` → `task_type`），**不提供反向函数**——反向是"一对多"（如 `query` 可来自
# `query` 或 `announce_fetch`），强行反向必然要猜，属"留后门"。将来若确需反向，
# 另开批次并明确该批的判据与歧义处置。
#
# 实测依据（2026-10-02）：两者**不同轴**——TaskType 有 5 值、TASK_KINDS 有 9 值，
# 交集仅 scan/query/organize；`task_queue` 现有数据只出现 download/organize/query/scan。
TASK_KIND_TO_TASK_TYPE: dict[str, str] = {
    # 三处**同名同义**（两侧概念一致，直接对应）
    "scan": "scan",
    "query": "query",
    "organize": "organize",
    # `favorite_download` 是最常用的下载语义（TaskType 侧的取值是 `download`）
    "favorite_download": "download",
    # —— 以下 task_kind 在 TaskType 里**无专门取值**，按"最接近的执行队列"收敛 ——
    "announce_fetch": "query",  # 公告抓取由查询侧适配器执行（无独立队列类型）
    "normalize": "organize",  # 规范化是归档整理链的一步
    "validity_check": "query",  # 时效性核查走站点查询
    "backup": "organize",  # 备份由整理侧定时任务承担
    "image_update": "organize",  # 镜像更新无独立队列类型，归入整理侧
}


def task_kind_to_task_type(task_kind: str) -> str:
    """把通知视角的 `task_kind` **单向**翻译为执行队列视角的 `task_type`。

    未知 `task_kind`（含空串）返回 `""`——**回退语义**，与 `project()` 的未映射回退同口径：
    调用方据此跳过翻译，而不是猜一个值。

    **注意**：本函数不落库（阶段 2.5a 只提供翻译工具；是否落 `task_type` 由后续批次决定）。
    """
    return TASK_KIND_TO_TASK_TYPE.get(task_kind, "")


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
