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

import requests

from pilotstd.i18n import t

from ..channel import NotificationMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from ..interaction import ChannelCapabilities
from ..renderer import DingTalkCardRenderer, MarkdownRenderer, split_for_channel
from .base import NotificationChannel, is_retryable_http_status, looks_rate_limited

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

            # 分段（P2，2026-10-05）：钉钉 markdown.text 上限按 **4000 字符**取保守值
            # （官方条款本轮未取证，口径见 renderer.CHANNEL_TEXT_LIMITS 的注释）⇒ 超长整条会被拒收，
            # 先切分；未超限时 `split_for_channel` 原样返回单段（零行为变更）。
            # 逐段独立发送，任一段最终失败即整体失败（**不静默丢段**）。
            rendered = self._renderer.render(message)
            for seg in split_for_channel(rendered, "dingtalk"):
                # 2026-10-17：接入渠道基座的统一重试（此前单次尝试即失败 ⇒ 一次 429/抖动就丢通知）
                if not self._send_segment_with_retry(url, message.title[:50], seg):
                    return False
            return True
        except Exception as e:
            # 外层兜底：签名计算或分段循环本身出错（分段内的异常由 `_post_segment_once` 自行处理）
            self.last_error = str(e)
            logger.warning("钉钉通知异常（分段外层）: %s", e, exc_info=True)
            return False

    def _send_segment_with_retry(self, url: str, title: str, seg: str) -> bool:
        """投递单段并按**渠道基座**的统一节奏重试（分段之间互不影响）。"""

        def _attempt(_attempt_no: int) -> tuple[bool, bool]:
            return self._post_segment_once(url, title, seg)

        return self._with_retry(_attempt)

    def _post_segment_once(self, url: str, title: str, rendered: str) -> tuple[bool, bool]:
        """投递**单个分段**一次，返回 `(是否成功, 是否可重试)`；失败原因写入 `last_error`。

        可重试口径：HTTP 429/5xx 与网络类异常（瞬时故障），以及响应文本像限流的业务码
        （钉钉的限流码**未取证**——官方文档正文是 JS 渲染取不到，故用基座的
        `looks_rate_limited` 关键词兜底；取证到具体 `errcode` 后应改为按码判定）。
        """
        try:
            payload = json.dumps(
                {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": title,  # 钉钉标题上限 50 字符（由调用方截断）
                        "text": rendered,
                    },
                }
            ).encode("utf-8")

            resp = requests.post(
                url, data=payload, headers={"Content-Type": "application/json"}, timeout=10
            )
            if resp.status_code != 200:
                self.last_error = t("notification.channel.dingtalk.http_error").format(
                    status=resp.status_code
                )
                logger.warning("钉钉通知 HTTP %d", resp.status_code)
                return False, is_retryable_http_status(resp.status_code)
            data = json.loads(resp.content.decode("utf-8"))
            # 钉钉返回=0表示成功
            if data.get("errcode") == 0:
                return True, False
            errmsg = data.get("errmsg") or t("notification.channel.api_unknown_error")
            self.last_error = t("notification.channel.dingtalk.api_failed").format(detail=errmsg)
            logger.warning("钉钉通知失败: %s", errmsg)
            return False, looks_rate_limited(f"{data.get('errcode', '')} {errmsg}")
        except (requests.RequestException, OSError) as e:
            # 网络类异常（连接重置/超时/域名解析失败）属瞬时故障 → 可重试
            self.last_error = str(e)
            logger.warning("钉钉通知异常: %s", e, exc_info=True)
            return False, True
        except Exception as e:
            # 非网络类异常（如 JSON 解析/编程错误）重试无意义
            self.last_error = str(e)
            logger.warning("钉钉通知异常: %s", e, exc_info=True)
            return False, False

    def _send_webhook_text(self, url: str, title: str, rendered: str) -> bool:
        """发送**单个分段**的 markdown 文本（兼容入口：单次尝试，不重试）。

        ⚠️ `send()` 走的是 `_post_segment_once` + 基座重试；本方法保留**单次**语义仅供
        既有调用方/测试使用（历史契约：返回 bool）。
        """
        ok, _retryable = self._post_segment_once(url, title, rendered)
        return ok

    # ── 企业级形态（阶段 S）──

    def _get_access_token(self) -> str:
        """取应用访问令牌（带进程内缓存：钉钉令牌有效期约 2 小时）。"""
        now = time.time()
        if self._token and now < self._token_expire_at:
            return self._token
        body = json.dumps({"appKey": self._app_key, "appSecret": self._app_secret}).encode("utf-8")
        resp = requests.post(
            self._TOKEN_URL, data=body, headers={"Content-Type": "application/json"}, timeout=10
        )
        if resp.status_code != 200:
            raise RuntimeError(
                t("notification.channel.dingtalk.token_failed").format(detail=resp.status_code)
            )
        data = json.loads(resp.content.decode("utf-8"))
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
            resp = requests.post(self._CARD_CREATE_URL, data=create_body, headers=headers, timeout=10)
            if resp.status_code != 200:
                    self.last_error = t("notification.channel.dingtalk.card_create_http").format(
                        status=resp.status_code
                    )
                    logger.warning(
                        "%s",
                        t("notification.channel.dingtalk.card_create_http").format(
                            status=resp.status_code
                        ),
                    )
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
            resp2 = requests.post(
                self._CARD_DELIVER_URL, data=deliver_body, headers=headers, timeout=10
            )
            if resp2.status_code != 200:
                # 同一文案既进 last_error（日志表用户可见）也进 warning（排查用）
                deliver_error = t("notification.channel.dingtalk.card_deliver_http").format(
                    status=resp2.status_code
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
