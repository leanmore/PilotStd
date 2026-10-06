# 模块：项目/核心//_脚本
# 通知策略表读写—从管理器脚本拆分以控制文件规模

import json as _json
import logging
import secrets
from typing import Any, cast

logger = logging.getLogger(__name__)


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    return secrets.token_hex(4)


def _loads_str_list(raw: Any) -> list[str]:
    """把策略列的 JSON 文本解析成字符串列表；**任何异常/非列表都回退 `[]`，永不抛**。

    为什么防御式：策略数据由 UI/历史迁移写入，可能留有半截 JSON 或非列表结构；
    读侧若直接 `json.loads` 抛错，会整表退化成"读 config 回退"（把**用户配置**悄悄丢掉）。
    非字符串元素一律丢弃（值域只应是事件名/类别名）。
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        data = _json.loads(raw)
    except (TypeError, ValueError):
        # 日志文案用 ASCII：G-047 把"新增中文字面量"计为新违规，而这是开发者诊断、非用户文案
        logger.debug("notification_policy JSON column is invalid; falling back to empty list")
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if isinstance(item, str)]


def _notify_event_of(event_type: str) -> str:
    """取某业务事件所属的 `notify_event` 类别（10 类之一）；未知事件返回空串。

    用于"按类别订阅"（10 类层）的匹配。**经 `_manager_ops` 转一手**而不是直接 import mapping：
    防腐测试规定 mapping 只有一个集成点（`_manager_ops`），策略层再开一个接入点会被该测试拦下
    （这也是"先读测试再动手"救回来的一次——首版直接 import mapping 即被拦）。
    """
    from ._manager_ops import notify_event_of

    return notify_event_of(event_type)


class NotificationPolicyHelper:
    """通知策略表读写辅助类（组合模式，非 Mixin）。

    由 NotificationManager 实例化，传入 _db 和 _cfg 引用。
    """

    def __init__(self, db: Any, cfg: Any) -> None:
        self._db = db
        self._cfg = cfg

    def get_channels_for_event(self, user_id: int, event_type: str) -> list[str]:
        """从 notification_policy 表查询该事件应发送到哪些渠道（按用户隔离）。

        **双读（阶段 4 · P6 · 4a，裁定 4 甲：新字段优先）**：
        · 该行 `event_classes` **非空** ⇒ **只用类别层**（事件所属 `notify_event` 命中即订阅）；
          不并入 `events`——并集会让"关闭某类"无法表达；
        · `event_classes` **为空** ⇒ 回退旧字段 `events`（逐事件匹配）。
        这条回退路径是**第 1 层回滚开关**（`NOTIFY_REDESIGN_STAGE=3`）的技术前提：
        旧行为必须能原样工作，回滚才不需要改代码。
        """
        try:
            rows = self._db.fetchall(
                'SELECT "channel", "events", "event_classes" FROM "notification_policy"'
                ' WHERE "user_id"=? AND "enabled"=1',
                (user_id,),
            )
            if rows:
                channels = []
                event_class = _notify_event_of(event_type)
                for r in rows:
                    # 兼容"未跑 v68 的库/测试替身"：行里没有该键时按空串处理，等价于"未设置类别"
                    raw_classes = r["event_classes"] if "event_classes" in r.keys() else ""
                    classes = _loads_str_list(raw_classes)
                    if classes:
                        matched = bool(event_class) and event_class in classes
                    else:
                        matched = event_type in _loads_str_list(r["events"])
                    if matched:
                        channels.append(r["channel"])
                if channels:
                    return channels
        except Exception:
            # D-4 修复：策略表查询失败需带结构化上下文记录（回退 config 是显式设计，
            # 但 DB 异常必须可见，避免策略变更静默失效）；禁止静默吞错
            logger.error(
                "通知策略表查询失败，回退 config 规则: trace_id=%s source_type=notification_policy "
                "target_chat_id=- user_id=%s event_type=%s",
                _log_trace_id(),
                user_id,
                event_type,
                exc_info=True,
            )

        # 回退：从配置脚本读取旧版规则
        rules = self._cfg.get(f"notification.rules.{event_type}")
        if not rules:
            return []
        if isinstance(rules, str):
            return [c.strip() for c in rules.split(",") if c.strip()]
        return cast(list[str], rules)

    def get_policies(self, user_id: int) -> list[dict[str, Any]]:
        """返回某用户的全部策略（**两层原样返回**，由调用方/前端决定如何呈现）。

        `events`＝高级层的 41 个业务事件；`event_classes`＝类别层的 10 类（可能为空＝未设置）。
        解析一律走防御式 `_loads_str_list`（坏 JSON 回退 `[]`，不让单行脏数据拖垮整表查询）。
        """
        rows = self._db.fetchall(
            'SELECT "id", "channel", "enabled", "events", "event_classes", "updated_at"'
            ' FROM "notification_policy" WHERE "user_id"=? ORDER BY "channel"',
            (user_id,),
        )
        result: list[dict[str, Any]] = []
        for r in rows:
            raw_classes = r["event_classes"] if "event_classes" in r.keys() else ""
            result.append(
                {
                    "id": r["id"],
                    "channel": r["channel"],
                    "enabled": bool(r["enabled"]),
                    "events": _loads_str_list(r["events"]),
                    "event_classes": _loads_str_list(raw_classes),
                    "updated_at": r["updated_at"],
                }
            )
        return result

    def save_policy(
        self,
        user_id: int,
        channel: str,
        enabled: bool | None,
        events: list[str] | None,
        event_classes: list[str] | None = None,
    ) -> None:
        """更新或插入某用户的策略。

        `events`＝高级层（41 个业务事件）；`event_classes`＝类别层（10 类）。
        **两层互不覆盖**：传 `None` 表示"本次不动该层"（既有调用方零改动）；传 `[]` 表示"清空该层"。
        读侧按"类别层非空则优先"生效（见 `get_channels_for_event`）。
        """
        existing = self._db.fetchone(
            'SELECT "id" FROM "notification_policy" WHERE "user_id"=? AND "channel"=?',
            (user_id, channel),
        )
        if existing:
            if enabled is not None:
                self._db.execute(
                    'UPDATE "notification_policy" SET "enabled"=?, "updated_at"=CURRENT_TIMESTAMP WHERE "id"=?',
                    (1 if enabled else 0, existing["id"]),
                )
            if events is not None:
                self._db.execute(
                    'UPDATE "notification_policy" SET "events"=?, "updated_at"=CURRENT_TIMESTAMP WHERE "id"=?',
                    (_json.dumps(events, ensure_ascii=False), existing["id"]),
                )
            if event_classes is not None:
                # 类别层单独可写（与 events 互不覆盖）⇒ 前端双层配置各自保存，互不干扰
                self._db.execute(
                    'UPDATE "notification_policy" SET "event_classes"=?, "updated_at"=CURRENT_TIMESTAMP'
                    ' WHERE "id"=?',
                    (_json.dumps(event_classes, ensure_ascii=False), existing["id"]),
                )
        else:
            self._db.execute(
                'INSERT INTO "notification_policy" ("user_id", "channel", "enabled", "events",'
                ' "event_classes") VALUES (?, ?, ?, ?, ?)',
                (
                    user_id,
                    channel,
                    1 if (enabled is None or enabled) else 0,
                    _json.dumps(events or [], ensure_ascii=False),
                    _json.dumps(event_classes or [], ensure_ascii=False),
                ),
            )
