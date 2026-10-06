# 模块：项目/核心//渠道/脚本
"""企业微信机器人 Webhook 通知渠道。"""

import json
import logging
from typing import TYPE_CHECKING, Any
from urllib.request import Request, urlopen

from pilotstd.i18n import t

from ..channel import NotificationMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from ..interaction import ChannelCapabilities
from ..renderer import MarkdownRenderer, split_for_channel
from .base import NotificationChannel

logger = logging.getLogger(__name__)


class WechatChannel(NotificationChannel):
    """企业微信机器人 Webhook。支持 text 和 markdown 类型。"""

    def __init__(self, webhook_url: str):
        self._url = webhook_url
        self._renderer = MarkdownRenderer()
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    def send(self, message: NotificationMessage) -> bool:
        """发送通知；超长按**企业微信 2048 字节**上限分段（P2）。"""
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._url:
            self.last_error = t("notification.channel.not_configured_webhook")
            return False
        # 分段（P2，2026-10-05）：企业微信文本上限是 **2048 字节**（官方口径，本仓按 UTF-8 计）⇒
        # 超长整条会被拒收，必须先切分；未超限时 `split_for_channel` 原样返回单段（零行为变更）。
        # 逐段独立发送，任一段最终失败即整体失败（**不静默丢段**）。
        rendered = self._renderer.render(message)
        for seg in split_for_channel(rendered, "wecom"):
            if not self._send_segment(seg):
                return False
        return True

    def _send_segment(self, rendered: str) -> bool:
        """发送**单个分段**（原 send() 的请求与异常处理逻辑；分段后按段独立判定成败）。"""
        try:
            payload = json.dumps(
                {
                    "msgtype": "markdown",
                    "markdown": {"content": rendered},
                }
            ).encode("utf-8")
            req = Request(self._url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                self.last_error = t("notification.channel.wechat.http_error").format(status=resp.status)
                logger.warning("企业微信通知失败: HTTP %d", resp.status)
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
            logger.warning("企业微信通知异常: %s, body=%s", e, body, exc_info=True)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
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
            supports_callback=False, note_key="notification.channel.wechat.capability_note"
        )

    @property
    def name(self) -> str:
        """渠道唯一标识。"""
        return "wechat"

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
