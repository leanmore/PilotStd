# 模块：项目/核心//渠道/脚本
"""钉钉通知渠道：群机器人 Webhook **或**企业级互动卡片（阶段 S，双读）。

- **旧形态**（既有，逐字保留）：群机器人 Webhook + 可选加签；
- **企业级形态**（阶段 S 新增）：应用凭证（AppKey/AppSecret）+ 机器人编码 + 卡片模板 ID
  + 群会话 ID，经 `/v1.0/oauth2/accessToken` 取令牌后创建并投递互动卡片。
- **双读优先级（方案 A2）**：企业级字段齐全 ⇒ 走企业级；否则回落旧 Webhook；
  两者都配 ⇒ 企业级优先并记一行 info 日志。不删旧字段、不做数据迁移。
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from pilotstd.i18n import t

from ..channel import NotificationMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from ..interaction import ChannelCapabilities
from ..renderer import DingTalkCardRenderer, MarkdownRenderer
from .base import NotificationChannel

logger = logging.getLogger(__name__)


class DingTalkChannel(NotificationChannel):
    """钉钉群机器人 Webhook。支持加签（secret）。"""

    # 企业级形态所需字段（缺任一即回落旧 Webhook）
    _ENTERPRISE_FIELDS = ("app_key", "app_secret", "robot_code", "card_template_id", "open_conversation_id")
    _TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
    _CARD_CREATE_URL = "https://api.dingtalk.com/v1.0/card/instances"
    _CARD_DELIVER_URL = "https://api.dingtalk.com/v1.0/card/instances/deliver"
    _TOKEN_SAFETY_SECONDS = 60  # 令牌过期前提前刷新，避免边界失败

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        app_key: str = "",
        app_secret: str = "",
        robot_code: str = "",
        card_template_id: str = "",
        open_conversation_id: str = "",
    ):
        self._url = webhook_url
        self._secret = secret  # 加签密钥，空字符串表示不加签
        self._app_key = app_key
        self._app_secret = app_secret
        self._robot_code = robot_code
        self._card_template_id = card_template_id
        self._open_conversation_id = open_conversation_id
        # 双读判定：企业级字段齐全即用企业级形态
        self._enterprise = all(
            getattr(self, f"_{name}") for name in self._ENTERPRISE_FIELDS
        )
        if self._enterprise and webhook_url:
            # 方案 A2：两者都配时企业级优先，留一行 info 便于排查
            logger.info(t("notification.channel.dingtalk.enterprise_dual_read"))
        self._renderer = MarkdownRenderer()
        self._card_renderer = DingTalkCardRenderer()
        self._token = ""
        self._token_expire_at = 0.0
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    def _sign(self) -> str:
        """钉钉加签：timestamp + secret → HMAC-SHA256 → Base64 → URL encode。"""
        # 无时不加签，直接返回空字符串
        if not self._secret:
            return ""
        # 钉钉要求毫秒级时间戳
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        # 链接签名：钉钉要求对64结果进行链接编码
        sign = quote(base64.b64encode(hmac_code).decode("utf-8"))
        return f"&timestamp={timestamp}&sign={sign}"

    def send(self, message: NotificationMessage) -> bool:
        """发送通知：企业级形态走互动卡片，否则回落群机器人 Webhook（双读）。"""
        if self._enterprise:
            return self._send_card(message)
        return self._send_webhook(message)

    def _send_webhook(self, message: NotificationMessage) -> bool:
        """（旧形态，逐字保留）发送 markdown 格式通知到钉钉群。"""
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._url:
            self.last_error = t("notification.channel.not_configured_webhook")
            logger.warning("钉钉通知 URL 为空")
            return False

        try:
            # 拼接加签参数到链接
            url = self._url + self._sign()

            # 使用渲染消息体（标准号由构建器渲染进正文，发送层不再追加，
            # 与电报渠道同口径——见提交 57f58a6c 的尾部重复行消除）
            rendered = self._renderer.render(message)

            payload = json.dumps(
                {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": message.title[:50],  # 钉钉标题上限 50 字符
                        "text": rendered,
                    },
                }
            ).encode("utf-8")

            req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    self.last_error = f"钉钉 HTTP {resp.status}"
                    logger.warning("钉钉通知 HTTP %d", resp.status)
                    return False
                data = json.loads(resp.read().decode("utf-8"))
                # 钉钉返回=0表示成功
                if data.get("errcode") == 0:
                    return True
                errmsg = data.get("errmsg", "未知错误")
                self.last_error = f"钉钉返回失败: {errmsg}"
                logger.warning("钉钉通知失败: %s", errmsg)
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
            logger.warning("钉钉通知异常: %s, body=%s", e, body, exc_info=True)
            return False

    # ── 企业级形态（阶段 S）──

    def _get_access_token(self) -> str:
        """取应用访问令牌（带进程内缓存：钉钉令牌有效期约 2 小时）。"""
        now = time.time()
        if self._token and now < self._token_expire_at:
            return self._token
        body = json.dumps({"appKey": self._app_key, "appSecret": self._app_secret}).encode("utf-8")
        req = Request(self._TOKEN_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        token = str(data.get("accessToken") or "")
        if not token:
            raise RuntimeError(
                t("notification.channel.dingtalk.token_failed").format(
                    detail=data.get("message") or data
                )
            )
        expire_in = int(data.get("expireIn") or 7200)
        self._token = token
        self._token_expire_at = now + max(0, expire_in - self._TOKEN_SAFETY_SECONDS)
        return token

    def _send_card(self, message: NotificationMessage) -> bool:
        """发送互动卡片：取令牌 → 创建卡片实例 → 投递到群会话。

        模板参数契约见 `DingTalkCardRenderer.render_card`（`title` / `content` / `level`）。
        """
        self.last_error = ""
        try:
            token = self._get_access_token()
            out_track_id = f"pilotstd-{int(time.time() * 1000)}"
            headers = {"Content-Type": "application/json", "x-acs-dingtalk-access-token": token}
            create_body = json.dumps(
                {
                    "cardTemplateId": self._card_template_id,
                    "outTrackId": out_track_id,
                    "cardData": self._card_renderer.render_card(message),
                },
                ensure_ascii=False,
            ).encode("utf-8")
            req = Request(self._CARD_CREATE_URL, data=create_body, headers=headers, method="POST")
            with urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    self.last_error = t("notification.channel.dingtalk.card_create_http").format(status=resp.status)
                    logger.warning("%s", t("notification.channel.dingtalk.card_create_http").format(status=resp.status))
                    return False

            deliver_body = json.dumps(
                {
                    "outTrackId": out_track_id,
                    "openConversationId": self._open_conversation_id,
                    "robotCode": self._robot_code,
                    "userIdType": 1,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            req2 = Request(self._CARD_DELIVER_URL, data=deliver_body, headers=headers, method="POST")
            with urlopen(req2, timeout=10) as resp2:
                if resp2.status != 200:
                    # 同一文案既进 last_error（日志表用户可见）也进 warning（排查用）
                    deliver_error = t("notification.channel.dingtalk.card_deliver_http").format(
                        status=resp2.status
                    )
                    self.last_error = deliver_error
                    logger.warning("%s", deliver_error)
                    return False
            return True
        except Exception as e:
            self.last_error = t("notification.channel.dingtalk.enterprise_send_failed").format(error=e)
            logger.warning(
                "%s",
                t("notification.channel.dingtalk.enterprise_send_failed").format(error=e),
                exc_info=True,
            )
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        """钉钉配置校验（双读）：企业级字段齐全，**或** 有 webhook_url 即可。

        两种形态各自完整即通过；都没有则视为未配置（与既有 `{}` → False 的行为一致）。
        """
        enterprise = all(config.get(f) for f in DingTalkChannel._ENTERPRISE_FIELDS)
        return bool(enterprise or config.get("webhook_url"))

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
            supports_callback=True, note_key="notification.channel.dingtalk.capability_note"
        )

    @property
    def name(self) -> str:
        """渠道唯一标识。"""
        return "dingtalk"

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
