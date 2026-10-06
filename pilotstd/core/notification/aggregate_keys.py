"""聚合分组键语义（T-41/4 从 `aggregate_buffer.py` 拆出，守 G-010）。

**为什么单独成模块**：分组键是聚合器的「身份定义」（决定哪些消息并成一条），语义重、注释多；
把它与缓冲/调度/渲染分离，既降 `aggregate_buffer.py` 体积，也让键语义的改动面收敛到一处。

**形态：纯函数（组合），不是 Mixin** —— 本仓 ADR-010 明令禁止新增 Mixin（护栏用例
`tests/test_architecture_mixin_guard.py::test_no_new_mixins` 会拦下），故这里只提供模块级纯函数；
`NotificationAggregator` 用**薄委托方法**调用它们（保持原有方法名与签名不变），并再导出
`_GROUP_SEP`/`agg_key_mode` 以兼容既有用法。

**搬迁注意**：切片起点必须取**装饰器行**——首轮曾因取 `def` 行导致 `@staticmethod` 丢失/漂移
（实测使 `_on_timer` 变静态方法、定时器强制发送失效）。
"""

from __future__ import annotations

import logging
import os

from .channel import NotificationMessage

logger = logging.getLogger("pilotstd.notification.aggregate")

# 非法取值告警的去重状态（随 `agg_key_mode` 一并迁入；按取值各告警一次）
_warned_bad_key = ""


_GROUP_SEP = "\x1f"


def agg_key_mode() -> str:
    """聚合键模式（`NOTIFY_AGG_KEY`）：`v1`＝旧键、`v2`＝分层键（默认）。

    · 只认 `v1` / `v2`（大小写不敏感、去空白）；
    · **未设置** ⇒ `v2`（默认，不告警：默认值不是错误）；
    · **非法值**（如 `v22`、`V2`、中文） ⇒ 回退 `v2` 并**告警**——不静默吞掉配置错误：
      静默降级会让运维以为"已切到某模式"而实际没有（本簿 P-107 精神：问题要可见）。
      告警按**不同取值各一次**（用 `_warned_bad_key` 去重），避免每条通知都刷一行日志。
    · 供回滚/灰度：`NOTIFY_AGG_KEY=v1` 时聚合行为回到 2026-10-05 之前的"事件类型 × 实体"。
    """
    global _warned_bad_key

    raw = (os.environ.get("NOTIFY_AGG_KEY") or "").strip()
    if not raw:
        return "v2"
    low = raw.lower()
    if low in ("v1", "v2"):
        return low
    if _warned_bad_key != raw:
        _warned_bad_key = raw
        # 开发者日志用 ASCII：G-047（Python 侧 i18n 硬编码）把"新增中文字面量"计为新违规，
        # 而这条是给运维看的配置诊断、不是用户可见文案 ⇒ 不进 i18n 资源。
        logger.warning(
            "Invalid NOTIFY_AGG_KEY value %r; falling back to v2 (valid: v1 / v2)", raw
        )
    return "v2"


def group_key(msg: NotificationMessage) -> str:
    """分组键 = **模式前缀 + 收敛类/事件类型 + （可选）关联实体**。

    2026-10-05 通知聚合改造（分组键分层，裁定口径）——两条路径**按是否有批次标识分流**：
    · **①批量导入路径**（`correlation_id` 非空）：键 = `批次 × notify_event`
      ⇒ 一次导入（同一批次）的查询/下载/规范化/存档通知收敛为**同一条**；
      **不含 `target_id`**：批次内每个标准的失败明细走 payload 的 `failed_items`（不靠分组键拆分）。
    · **②日常操作路径**（`correlation_id` 为空）：键 = `notify_event × target_id`
      ⇒ 保留实体维度（同一事件类型下 task_a / task_b 各自成组，绝不混为一组）。
    为什么用模式前缀 `1`/`2`：让键可自解释、避免两条路径的键**跨模式撞车**；
    为什么 `notify_event` 为空时回退 `event_type`：字段契约允许"尚未映射"（见 channel.py 注释），
    直拼空串会把所有未映射消息并进同一组。
    """
    notify = (getattr(msg, "notify_event", "") or "").strip() or msg.event_type
    entity = (msg.target_id or "").strip()
    batch = (getattr(msg, "correlation_id", "") or "").strip()
    # ── 灰度开关（P1，2026-10-05）：`NOTIFY_AGG_KEY` ──────────────────────────
    # `v2`（默认）＝本次分层键（①批次×收敛类 / ②日常桶 / ②收敛类×实体）；
    # `v1`＝**旧行为**（`event_type × target_id`），供回滚与灰度对照；
    # **非法值或缺失一律按 v2**——保证"没有配置"时行为确定（不静默落到第三种语义）。
    # 为什么必须留这个开关：键语义一变，用户在聚合里看到的分组就变；没有回滚开关的线上行为
    # 属"改了就没退路"，与本簿"两件可独立回滚的事不绑一个变量"的设计相悖（见 `03-实施路径.md:41`）。
    if agg_key_mode() == "v1":
        return f"{msg.event_type}{_GROUP_SEP}{entity}" if entity else msg.event_type
    if batch:
        return f"1{_GROUP_SEP}{batch}{_GROUP_SEP}{notify}"
    # ②日常路径（需求②原文："公告拉取/收藏/收藏转下载 → 时间窗内聚合成 1 条，不要短时间内连发多条"）：
    # 这三类场景刻意**共用一个"日常桶"**（`2<SEP>daily`）——
    #   · 公告拉取/收藏 ⇒ `notify_event == "user_activity"`；
    #   · 收藏转下载 ⇒ `task_kind == "favorite_download"`（同一业务链，跨 `task_*` 类别）。
    # 若按 `notify_event × target_id` 分组，这三类会各发一条（正是需求②要消除的"连发"）；
    # 信息不丢：聚合器按 Z-21 保留**全部条目**的 blocks（不再只留首条）。
    # 其余类别（非收藏链的任务终局/告警等）仍按 `notify_event × target_id` 分组——不同对象/不同业务链
    # 的结果混成一条会误导用户。
    task_kind = (getattr(msg, "task_kind", "") or "").strip()
    if notify == "user_activity" or task_kind == "favorite_download":
        return f"2{_GROUP_SEP}daily"
    return f"2{_GROUP_SEP}{notify}{_GROUP_SEP}{entity}" if entity else f"2{_GROUP_SEP}{notify}"


def events_in_group(group: str) -> set[str]:
    """从分组键还原**收敛类/事件类型**（代表事件与 formatter 查找依赖它）。

    键格式（2026-10-05 分层后）：
    · ①批次路径 `1<SEP>批次<SEP>收敛类` ⇒ 取**最后一段**（批次号在中间，不是收敛类）；
    · ②常规路径 `2<SEP>收敛类[<SEP>实体]` ⇒ 取**第 2 段**；
    · **v1 模式（灰度回滚）** 旧键 `事件类型[<SEP>实体]` ⇒ 取**第 1 段**（无模式前缀）。
    为什么按模式分支：三种键的段位语义不同，同一套下标会取到批次号或实体
    （回归实例见 `tests/test_aggregate_buffer.py::test_group_key_batch_path_uses_correlation_id`
    与 `tests/test_notification_failed_items.py::test_group_key_v1_mode_restores_legacy_behavior`）。
    """
    parts = group.split(_GROUP_SEP)
    if agg_key_mode() == "v1":
        return {parts[0]} if parts else {group}
    if parts[0] == "1":
        return {parts[-1]} if len(parts) >= 3 else {group}
    return {parts[1]} if len(parts) > 1 else {group}


def group_entity(group: str) -> str:
    """从分组键还原关联实体；**②路径的最后一段**才是实体，①路径无实体（返回空串）。

    v1 模式下旧键是 `事件类型[<SEP>实体]` ⇒ 实体在**第 2 段**（否则按实体筛选刷新会失效）。
    """
    parts = group.split(_GROUP_SEP)
    if agg_key_mode() == "v1":
        return parts[1] if len(parts) > 1 else ""
    if len(parts) >= 3 and parts[0] == "2":
        return parts[2]
    return ""
