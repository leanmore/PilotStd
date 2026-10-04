# 模块：项目/核心//渠道/脚本
"""飞书机器人 Webhook 通知渠道。"""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.request import Request, urlopen

from pilotstd.i18n import t

from ..channel import NotificationMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from ..interaction import ChannelCapabilities
from ..renderer import FeishuCardRenderer
from .base import NotificationChannel

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书机器人 Webhook。"""

    def __init__(self, webhook_url: str, secret: str = ""):
        # 签名校验密钥（大阶段 5 起**真正生效**；此前仅声明未实现——见提交说明）。
        # 注意与钉钉的差异：钉钉 `_sign()` 把密钥当 HMAC **key**、把 "timestamp\nsecret"
        # 当消息；飞书反过来——把 "timestamp\nsecret" 当 **key**、且没有独立消息。
        # 两种口径不可互相套用。
        self._url = webhook_url
        self._secret = secret
        self._renderer = FeishuCardRenderer()
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    def _sign(self) -> dict[str, str]:
        """飞书自定义机器人签名（官方口径）。

        算法：`timestamp = str(int(time.time()))`；`string_to_sign = f"{timestamp}\n{secret}"`；
        `sign = base64(HMAC-SHA256(key=string_to_sign))`——**key 是 string_to_sign，没有独立消息**。
        与钉钉的 `_sign()`（key=secret、msg="timestamp\nsecret"）恰好互换，故单独写明防误抄。
        """
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{self._secret}"
        digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        return {"timestamp": timestamp, "sign": base64.b64encode(digest).decode("utf-8")}

    def send(self, message: NotificationMessage) -> bool:
        """发送交互式卡片通知到飞书群。"""
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._url:
            self.last_error = t("notification.channel.not_configured_webhook")
            return False
        try:
            # 使用飞书渲染卡片（标准号由构建器渲染进正文，发送层不再追加，
            # 与电报渠道同口径——见提交 57f58a6c 的尾部重复行消除）
            card = self._renderer.render(message)

            # 变量名避开 except 分支里的 `body`（那是 str，同名会让 mypy 报类型冲突）
            request_body: dict[str, Any] = {
                "msg_type": "interactive",
                "card": card,
            }
            # 配了签名密钥才带 timestamp/sign（未配时保持既有请求体逐字不变）
            if self._secret:
                request_body.update(self._sign())
            payload = json.dumps(request_body).encode("utf-8")
            req = Request(self._url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    # 飞书返回=0表示成功
                    if data.get("code") == 0:
                        return True
                    msg = data.get("msg", "")
                    self.last_error = t("notification.channel.feishu.api_failed").format(detail=msg)
                    logger.warning("飞书通知失败: %s", msg)
                    return False
                self.last_error = t("notification.channel.feishu.http_error").format(status=resp.status)
                return False
        except Exception as e:
            # 读取错误响应体用于诊断（回调返回非 200 时的具体错误）
            body = ""
            from urllib.error import HTTPError

            if isinstance(e, HTTPError):
                try:
                    body = e.read().decode("utf-8", errors="replace")[:500]
                except Exception as read_exc:
                    # 区分"服务端未返回 body"与"body 读取失败"，避免诊断信息静默丢失
                    body = f"<body 读取失败: {read_exc}>"
                    logger.debug("错误响应体读取失败: %s", read_exc)
            # 透传具体错误描述
            self.last_error = f"{e}: {body}" if body else str(e)
            logger.warning("飞书通知异常: %s, body=%s", e, body, exc_info=True)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        """飞书配置只需 webhook_url。"""
        return bool(config.get("webhook_url"))

    # ── 渠道契约（第一版修订二：继承自渠道基类的通知渠道接口） ──

    @property
    def capabilities(self) -> "ChannelCapabilities":
        """能力自述（阶段 B 如实声明）。

        钉钉/飞书可回调但**不可编辑**（钉钉卡片更新接口未取证=缺口 6；飞书现为 Webhook 形态无
        message_id）；企微连回调也不启用（缺口 1/2 未闭合）。`note_key` 解释原因，
        避免把"渠道限制"误判为"系统故障"。
        """
        from ..interaction import ChannelCapabilities

        return ChannelCapabilities(
            supports_callback=True, note_key="notification.channel.feishu.capability_note"
        )

    @property
    def name(self) -> str:
        """渠道唯一标识。"""
        return "feishu"

    def test(self) -> bool:
        """发送一条测试消息验证渠道连通性。"""
        return self.send(
            NotificationMessage(
                title=t("notification.channel.test.title"),
                body=t("notification.channel.test.body"),
            )
        )

    def get_config_schema(self) -> dict[str, Any]:
        """渠道配置字段 schema（供前端动态渲染配置表单）——由 `channel_spec` 派生。"""
        from ..channel_spec import legacy_schema, spec_for

        return legacy_schema(spec_for(self.name), t)
