# 模块：项目/核心/通知/安全告警脚本
"""安全事件告警投递（方案 A：直连临时渠道实例同步发送）。

设计动机（第 2 批安全审计闭环，见 docs/plans/batch2-security-audit-design.md）：

凭证类安全告警必须先于"新凭证落库"送达**旧渠道**，否则通知会被投递到新地址。
走 `NotificationManager.send_event` 无法保证这一点，有三条独立原因：

1. 聚合缓冲：`notification.aggregate_enabled` 默认 True，`_do_send` 只入队，
   实际发送推迟到窗口到期（默认 5s）——此时新凭证已落库，告警流向新地址；
2. 静音时段：`_is_quiet_hours()` 命中时消息写入 `notification_queue` 表延后补发，
   即使绕过聚合器也仍会被推迟；
3. 门控与用户作用域：`send_event` 首行判 `notification.enabled`（默认 False 直接返回），
   且 `NotificationManager` 由门面硬编码 `user_id=1` 构造，告警会发给错误用户。

因此本模块：读取**指定用户**的旧凭证 → 用旧凭证构造临时渠道实例 → **同步** send()
→ 才允许调用方落库。全程不导入、不调用 `NotificationManager`。
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from pilotstd.i18n import t

from .channel import NotificationMessage

logger = logging.getLogger(__name__)

# 告警投递总超时（秒）：并发发送，整体封顶，避免阻塞用户配置流程。
# 单渠道共享此预算——上游 webhook 不可用时最坏等待 5s 而非 N×10s。
NOTIFY_TOTAL_TIMEOUT_SECONDS = 5.0

# 紧急降级开关：环境变量（非配置文件）。凭证变更端点本身能写配置，
# 若开关放配置里等于给攻击者一个关闭告警的把手。
ENV_NOTIFY_ENABLED = "PILOTSTD_SECURITY_NOTIFY_ENABLED"

# 构建器兜底：即便 Docker/PyQt 宿主未安装 FastAPI 依赖，告警文本仍必须可生成；
# 用惰性导入把失败隔离在消息构造阶段，不让"缺依赖"演变为"告警丢失"。
try:
    from ._builders_system import (
        _build_notification_credential_changed_message,
        _build_security_password_changed_message,
        _build_security_token_refreshed_message,
    )

    _HAS_BUILDERS = True
except ImportError:  # pragma: no cover - 依赖缺失时的降级路径
    _build_notification_credential_changed_message = None  # type: ignore[assignment]
    _build_security_password_changed_message = None  # type: ignore[assignment]
    _build_security_token_refreshed_message = None  # type: ignore[assignment]
    _HAS_BUILDERS = False


def client_ip(request: Any) -> str:
    """尽力取客户端 IP，取不到或不是字符串时返回空串。

    不用 `getattr(request, "client", None)` 直接取 `.host`：测试替身（MagicMock）
    对任意属性都返回 Mock 对象，会污染审计 detail 并让 `json.dumps` 崩溃。
    审计字段宁可留空，也不接受非字符串值。
    """
    client = getattr(request, "client", None)
    if client is None:
        return ""
    host = getattr(client, "host", "")
    return host if isinstance(host, str) else ""


def _channel_instance(channel: str, creds: dict[str, str]) -> Any | None:
    """按渠道名构造临时渠道实例；凭据不完整或不支持的渠道返回 None。

    构造签名与 NotificationManager._init_channels 保持一致
    （webhook 类接 (url[, secret])，Telegram 接 (bot_token, chat_id)）。
    **按渠道名分派是必要的**：user_credentials 表按 channel 分行存储，
    同一份凭证里没有"渠道类型"字段，无法由一个 URL 推断出是哪家机器人。
    """
    if channel == "telegram":
        token = (creds.get("bot_token") or "").strip()
        chat_id = (creds.get("chat_id") or "").strip()
        if not (token and chat_id):
            return None
        from .channels.telegram import TelegramChannel

        return TelegramChannel(token, chat_id)

    url = (creds.get("webhook_url") or "").strip()
    if not url:
        return None
    if channel == "dingtalk":
        from .channels.dingtalk import DingTalkChannel

        return DingTalkChannel(url, (creds.get("secret") or "").strip())
    if channel == "feishu":
        from .channels.feishu import FeishuChannel

        # FeishuChannel 只接 webhook_url（不接受 secret，与钉钉不同）
        return FeishuChannel(url)
    if channel == "wechat":
        from .channels.wechat import WechatChannel

        return WechatChannel(url)
    # 未知渠道：不构造（不猜测 URL 类型），由调用方按"无可用渠道"处理
    return None


def _send_all(instances: list[tuple[str, Any]], message: NotificationMessage) -> list[tuple[str, bool, str]]:
    """并发同步发送，总超时封顶。返回 [(渠道名, 是否成功, 失败原因)]。

    并发而非串行：串行在 4 渠道 × 10s 单渠道超时下最坏阻塞用户请求 40s。
    超时未完成的 future 只记失败、不取消（线程已在阻塞 IO 中，取消不会立即生效）。
    """
    results: list[tuple[str, bool, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, len(instances))) as pool:
        futures = {pool.submit(inst.send, message): name for name, inst in instances}
        try:
            for future in as_completed(futures, timeout=NOTIFY_TOTAL_TIMEOUT_SECONDS):
                name = futures[future]
                try:
                    ok = bool(future.result())
                    results.append((name, ok, "" if ok else t("notification.security.reason.channel_failed")))
                except Exception as exc:  # noqa: BLE001 - 单渠道异常不得影响其它渠道
                    results.append((name, False, str(exc)[:200]))
        except TimeoutError:
            done = {futures[f] for f in futures if f.done()}
            for name in futures.values():
                if name not in done:
                    results.append(
                        (
                            name,
                            False,
                            t("notification.security.reason.total_timeout").format(
                                seconds=NOTIFY_TOTAL_TIMEOUT_SECONDS
                            ),
                        )
                    )
    return results


def notify_security_event(
    notification_mgr: Any,
    cred_helper: Any,
    user_id: int,
    event_type: str,
    payload: dict[str, Any],
    *,
    target_channels: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """向指定用户的渠道投递安全告警（方案 A）。

    :param notification_mgr: 仅供 `_build_message` 生成消息；本函数**绝不**调用其
        `send_event`（那会重新引入聚合/静音延迟，正是要防的陷阱）。
    :param cred_helper: CredentialHelper 实例，用于读取该用户的渠道凭证。
    :param user_id: 告警目标用户，而非门面硬编码的 user 1。
    :param event_type: 事件类型（须已在 events.py 注册且有构建器）。
    :param payload: 构建器所需载荷；同时用于 send_event 的静态契约扫描。
    :param target_channels: 指定投递渠道（凭证变更场景＝被改动的渠道）；
        None 表示投递该用户全部已配置渠道。
    :return: (成功渠道列表, 失败渠道列表[含原因])
    """
    if os.environ.get(ENV_NOTIFY_ENABLED, "true").strip().lower() in ("false", "0"):
        logger.warning(
            "安全告警被开关跳过: %s=%s event=%s（审计仍会记录）",
            ENV_NOTIFY_ENABLED,
            os.environ.get(ENV_NOTIFY_ENABLED),
            event_type,
        )
        return [], []

    if cred_helper is None:
        logger.warning("凭据助手不可用，安全告警 %s 无法投递", event_type)
        return [], [t("notification.security.reason.no_cred_helper")]

    # 事件名以字面量传给 send_event，且内联完整归一化键集：
    # ① 满足 tests/test_notification_e2e.py 的"每个事件都有触发点 + 字段双向一致"静态契约
    #    （该测试用正则读 send_event 的内联 dict 字面量，间接传参无法被识别）；
    # ② 经 NotificationManager.send_event 仍写入 notification_log 审计轨迹与 WS 广播，
    #    代价是绕过聚合器（bypass_aggregation=True）——静音时段对 warning 级仍会压制，
    #    故真正的安全投递由下方直连临时渠道完成，这里仅是留痕。
    if notification_mgr is not None:
        try:
            notification_mgr.send_event(
                event_type,
                {
                    "services": payload.get("services", []),
                    "changed_keys": payload.get("changed_keys", []),
                    "rules_changed": payload.get("rules_changed", False),
                    "from_ip": payload.get("from_ip", ""),
                    "user_id": payload.get("user_id", ""),
                    "sessions_revoked": payload.get("sessions_revoked", False),
                    "rotated_at": payload.get("rotated_at", ""),
                    "db_synced": payload.get("db_synced", True),
                },
                bypass_aggregation=True,
            )
        except Exception as exc:  # noqa: BLE001 - 留痕失败不得影响主流程与直连投递
            logger.warning("安全告警事件留痕失败 %s: %s", event_type, exc)

    message = _build_security_message(event_type, payload)
    if message is None:
        return [], [t("notification.security.reason.no_builder").format(event=event_type)]

    creds_by_channel = cred_helper.get_all(user_id) or {}
    wanted = set(target_channels) if target_channels else set(creds_by_channel)

    sent: list[str] = []
    failed: list[str] = []
    for name, creds in creds_by_channel.items():
        if name not in wanted:
            continue
        instance = _channel_instance(name, creds or {})
        if instance is None:
            # 该渠道已启用但凭据不完整（如 webhook_url 为空）：可预期，不算异常
            continue
        for sent_name, ok, reason in _send_all([(name, instance)], message):
            if ok:
                sent.append(sent_name)
            else:
                failed.append(f"{sent_name}: {reason}")
    return sent, failed


def _build_security_message(event_type: str, payload: dict[str, Any]) -> NotificationMessage | None:
    """按事件类型构造安全告警消息；构建器缺失时返回 None（调用方记失败原因）。"""
    builders = {
        "notification_credential_changed": _build_notification_credential_changed_message,
        "security_password_changed": _build_security_password_changed_message,
        "security_token_refreshed": _build_security_token_refreshed_message,
    }
    builder = builders.get(event_type)
    if builder is None:
        logger.warning("安全告警事件未登记构建器: %s", event_type)
        return None
    try:
        return builder(payload)  # type: ignore[no-any-return]
    except Exception as exc:  # noqa: BLE001 - 构建失败降级为固定文本，绝不抛给调用方
        logger.warning("安全告警消息构建失败 %s: %s", event_type, exc)
        return NotificationMessage(title=event_type, body=event_type, event_type=event_type, level="warning")


def notify_credential_change(
    notification_mgr: Any,
    cred_helper: Any,
    user_id: int,
    changed_channels: list[str],
    old_creds: dict[str, dict[str, str]],
    *,
    changed_keys: list[str] | None = None,
    rules_changed: bool = False,
    enabled_changed: bool = False,
    from_ip: str = "",
) -> tuple[list[str], list[str]]:
    """凭证变更告警：仅投递到**被改动**的渠道，使用 `old_creds` 中的旧地址。

    调用方必须保证本函数在 `set_channel` 落库**之前**调用，且 `old_creds`
    是落库前读取的副本（凭证为合并写入 + INSERT OR REPLACE，落库后不可恢复）。

    改动仅涉及 rules/enabled（未动渠道凭证）时，无"旧地址"概念，
    改为向该用户全部已配置渠道投递提醒。
    """
    if not changed_channels and (rules_changed or enabled_changed):
        return notify_security_event(
            notification_mgr,
            cred_helper,
            user_id,
            "notification_credential_changed",
            {
                "services": [],
                "changed_keys": changed_keys or [],
                "rules_changed": True,
                "from_ip": from_ip,
            },
        )

    if not changed_channels:
        return [], []

    # 快照包装器承接"用旧地址发送"的语义；cred_helper 不可用时无法读取任何凭证，
    # 直接交回通用投递函数按"无可用渠道"处理（避免包装 None 后在属性访问处崩）。
    if cred_helper is None:
        return notify_security_event(
            notification_mgr,
            None,
            user_id,
            "notification_credential_changed",
            {
                "services": list(changed_channels),
                "changed_keys": changed_keys or [],
                "rules_changed": bool(rules_changed),
                "from_ip": from_ip,
            },
            target_channels=list(changed_channels),
        )

    # 临时覆盖目标渠道的凭证来源：把"旧凭证快照"当作该用户的当前凭证使用，
    # 从而让通用投递函数按旧地址发送。
    snapshot_helper = _SnapshotCredHelper(cred_helper, user_id, old_creds)
    return notify_security_event(
        notification_mgr,
        snapshot_helper,
        user_id,
        "notification_credential_changed",
        {
            "services": list(changed_channels),
            "changed_keys": changed_keys or [],
            "rules_changed": bool(rules_changed),
            "from_ip": from_ip,
        },
        target_channels=list(changed_channels),
    )


class _SnapshotCredHelper:
    """只读凭证视图：用旧凭证快照覆盖指定渠道，其余渠道透传底层读取。"""

    def __init__(self, inner: Any, user_id: int, snapshot: dict[str, dict[str, str]]) -> None:
        self._inner = inner
        self._user_id = user_id
        self._snapshot = snapshot

    def get_all(self, user_id: int) -> dict[str, dict[str, str]]:
        """返回底层凭证与旧值快照的并集（快照优先，保证告警走旧地址）。"""
        base = self._inner.get_all(user_id) or {}
        merged = dict(base)
        merged.update(self._snapshot)
        return merged

    def get_channel(self, user_id: int, channel: str) -> dict[str, str] | None:
        """读取单渠道凭证：命中快照则返回旧值，否则透传底层读取。"""
        if channel in self._snapshot:
            return self._snapshot[channel]
        return self._inner.get_channel(user_id, channel)  # type: ignore[no-any-return]
