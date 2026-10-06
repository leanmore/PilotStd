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
from ..interaction import ANCHOR_MESSAGE_ID, MessageHandle

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from ..interaction import ChannelCapabilities
from ..renderer import CHANNEL_TEXT_LIMITS, FeishuCardRenderer, split_for_channel
from .base import NotificationChannel

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书渠道：**机器人 Webhook** 与**企业自建应用**两种形态（阶段 3 · Step 4 ③）。

    | 形态 | 必需参数 | 能力 |
    |---|---|---|
    | 机器人 Webhook | `webhook_url`（可选 `secret` 加签） | 发交互式卡片；**拿不到 `message_id`
      ⇒ 不能编辑** |
    | 企业自建应用 | `app_id` + `app_secret` + `receive_id` | 发卡片并**留存 `message_id`**
      ⇒ 可 **`PATCH` 编辑已发消息** |

    两者都配好时**优先应用形态**（与 `channel_spec.status_rule` 分支序一致）。

    **端点取证（[实现] 等级）**：第三方插件 `ui-beam-9/MoviePilot-Plugins` 的
    `plugins.v2/larkmessager/client.py`：
    · token `POST /open-apis/auth/v3/tenant_access_token/internal`（`:49-60`）；
    · 发送 `POST /open-apis/im/v1/messages?receive_id_type=…`
      （字段 `receive_id`/`msg_type`/`content`（**JSON 字符串**））（`:125-146`）；
    · 编辑 `PATCH /open-apis/im/v1/messages/{message_id}`
      （`{"content": <JSON 字符串>}`，`code==0` 为成功）（`:437-489`）。
    `content` 必须是**JSON 字符串**（不是对象）——与 Webhook 形态（`card` 直接给对象）最易错的一处差异。
    """

    # 开放平台基址（飞书中国站）；如需 Lark 国际站可在此改（第三方实现用的是 larksuite.com）
    _API_BASE = "https://open.feishu.cn/open-apis"

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        app_id: str = "",
        app_secret: str = "",
        receive_id: str = "",
        receive_id_type: str = "open_id",
    ):
        # 签名校验密钥（大阶段 5 起**真正生效**；此前仅声明未实现——见提交说明）。
        # 注意与钉钉的差异：钉钉 `_sign()` 把密钥当 HMAC **key**、把 "timestamp\nsecret"
        # 当消息；飞书反过来——把 "timestamp\nsecret" 当 **key**、且没有独立消息。
        # 两种口径不可互相套用。
        self._url = webhook_url
        self._secret = secret
        self._app_id = app_id
        self._app_secret = app_secret
        self._receive_id = receive_id
        self._receive_id_type = receive_id_type or "open_id"
        self._renderer = FeishuCardRenderer()
        # 应用形态的 tenant_access_token 缓存（官方有效期 7200 秒，留余量）
        self._token = ""
        self._token_expire_at = 0.0
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    # ── 应用形态（阶段 3 · Step 4 ③）────────────────────────────────────────────

    @property
    def _app_configured(self) -> bool:
        """应用形态是否配置完整（app_id + app_secret + receive_id）。"""
        return bool(self._app_id and self._app_secret and self._receive_id)

    def _api_base(self) -> str:
        """开放平台基址（默认飞书中国站；如需 Lark 国际站可改类属性）。"""
        return self._API_BASE

    def _tenant_token(self) -> str:
        """取 `tenant_access_token`（7200 秒缓存；失败返回空串并记录原因）。"""
        now = time.time()
        if self._token and now < self._token_expire_at:
            return self._token
        payload = json.dumps({"app_id": self._app_id, "app_secret": self._app_secret}).encode("utf-8")
        req = Request(
            f"{self._api_base()}/auth/v3/tenant_access_token/internal",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.last_error = str(e)
            return ""
        if int(data.get("code", -1)) != 0 or not data.get("tenant_access_token"):
            self.last_error = t("notification.channel.feishu.token_failed")
            return ""
        self._token = str(data["tenant_access_token"])
        self._token_expire_at = now + 6900
        return self._token

    def _post_app_message(self, card: dict) -> str:
        """经应用端点发送一张卡片，返回 `message_id`（失败返回空串）。"""
        token = self._tenant_token()
        if not token:
            return ""
        payload = json.dumps(
            {
                "receive_id": self._receive_id,
                # `content` 必须是 **JSON 字符串**（实测第三方实现口径）
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            }
        ).encode("utf-8")
        url = f"{self._api_base()}/im/v1/messages?receive_id_type={self._receive_id_type}"
        req = Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.last_error = str(e)
            logger.warning("feishu app message failed: %s", e)
            return ""
        if int(data.get("code", -1)) != 0:
            self.last_error = t("notification.channel.feishu.api_failed").format(
                detail=data.get("msg", "")
            )
            return ""
        return str((data.get("data") or {}).get("message_id") or "")

    def edit_message(self, handle: "MessageHandle", message: NotificationMessage) -> bool:
        """按 `message_id` 更新已发出的消息（飞书 `PATCH /im/v1/messages/{message_id}`）。

        **契约与 Telegram 同款**（`channels/base.py::edit_message(handle, message)`）：用渠道无关的
        `MessageHandle`（`anchor == ANCHOR_MESSAGE_ID`、`value == message_id`）定位消息，
        内容由 `message` 重新渲染（与 `send()` 共用渲染器 ⇒ 编辑后的卡片与初次发送同构）。

        只做**一次**尝试（编辑是低频补偿动作，不引入与发送相同的重试放大）。
        Webhook 形态**天然不支持**（拿不到 `message_id`）⇒ 如实返回 False 并写 `last_error`。
        """
        self.last_error = ""
        if handle.anchor != ANCHOR_MESSAGE_ID:
            self.last_error = t("notification.channel.edit_anchor_unsupported").format(
                anchor=handle.anchor
            )
            return False
        if not self._app_configured:
            self.last_error = t("notification.channel.feishu.not_configured_app")
            return False
        if not handle.value:
            self.last_error = t("notification.channel.feishu.missing_message_id")
            return False
        return self._patch_message(handle.value, self._renderer.render(message))

    def _patch_message(self, message_id: str, card: dict) -> bool:
        """`PATCH /im/v1/messages/{message_id}`（`{"content": <JSON 字符串>}`，`code==0` 为成功）。"""
        token = self._tenant_token()
        if not token:
            return False
        payload = json.dumps({"content": json.dumps(card, ensure_ascii=False)}).encode("utf-8")
        req = Request(
            f"{self._api_base()}/im/v1/messages/{message_id}",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="PATCH",
        )
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.last_error = str(e)
            logger.warning("feishu edit message failed: %s", e)
            return False
        if int(data.get("code", -1)) != 0:
            self.last_error = t("notification.channel.feishu.api_failed").format(
                detail=data.get("msg", "")
            )
            return False
        return True

    def _send_app(self, message: NotificationMessage) -> bool:
        """应用形态发送：逐张卡片经应用端点投递，并**把 `message_id` 留存到消息上**。"""
        card = self._renderer.render(message)
        for one in self._split_card(card):
            message_id = self._post_app_message(one)
            if not message_id:
                return False
            # 只记首张：编辑场景针对"这条通知的主卡片"（分段续卡不参与后续编辑）
            ids = getattr(message, "channel_message_ids", None)
            if isinstance(ids, dict) and "feishu" not in ids:
                ids["feishu"] = message_id
        return True

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
        """发送卡片通知：应用形态（可留存 `message_id`）优先；否则走机器人 Webhook。"""
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if self._app_configured:
            try:
                return self._send_app(message)
            except Exception as e:
                self.last_error = str(e)
                logger.warning("feishu app send raised: %s", e, exc_info=True)
                return False
        if not self._url:
            self.last_error = t("notification.channel.not_configured_webhook")
            return False
        try:
            # 分段（P2，2026-10-05）：飞书卡片超长时必须**按元素切成多张卡片**——
            # 卡片是 `elements[]` 数组，若把 markdown 字符串从中间切开，`**加粗**` 之类标记会跨段断裂；
            # 按元素装填既保持卡片结构合法，又能用「续 N/M」明确告知还有后续。
            # 未超限时 `_split_card` 原样返回单张（零行为变更）。
            card = self._renderer.render(message)
            for one in self._split_card(card):
                if not self._send_card(one):
                    return False
            return True
        except Exception as e:
            # 外层兜底：渲染或分片本身出错（卡片投递内的异常由 `_send_card` 自行处理）
            self.last_error = str(e)
            logger.warning("飞书通知异常（分片外层）: %s", e, exc_info=True)
            return False

    def _split_card(self, card: dict) -> list[dict]:
        """按飞书上限把一张卡片切成多张；**未超限时原样返回 `[card]`**。

        · 上限取 `CHANNEL_TEXT_LIMITS["feishu"]`（4096 字符；飞书按 UTF-16 单元计数、官方数字本轮未取证
          ⇒ 取保守值，口径见 `renderer.CHANNEL_TEXT_LIMITS` 注释）；
        · **按元素装填**：累计内容长度不超"上限 − 标题长度"就留在同一张卡；
        · **单元素自身超预算**：对该元素 `content` 走 `split_for_channel`，保证任何一张都不超限；
        · 第 2 张起在**末元素**追加「续 N/M」（i18n `notification.segment.continued`），
          与纯文本渠道同口径，读者能看出还有后续。
        """
        limit = CHANNEL_TEXT_LIMITS.get("feishu", (4096, "chars"))[0]
        header = card.get("header") or {}
        title = str(((header.get("title") or {}).get("content")) or "")
        budget = limit - len(title)
        elements = list(card.get("elements") or [])
        if not elements or budget <= 0:
            return [card]

        pages: list[list[dict]] = []
        current: list[dict] = []
        used = 0
        for el in elements:
            content = str(el.get("content") or "")
            if len(content) > budget:
                # 单元素就超预算：先收束当前页，再把这个元素本身切成若干独立页
                if current:
                    pages.append(current)
                    current, used = [], 0
                for piece in split_for_channel(content, "feishu"):
                    # 显式标注元素类型：`dict` 与 `dict[Any, Any]` 的差异会让 mypy 报列表推导类型不符
                    piece_el: dict = {**el, "content": piece}
                    pages.append([piece_el])
                continue
            if used + len(content) > budget:
                pages.append(current)
                current, used = [], 0
            current.append(el)
            used += len(content)
        if current:
            pages.append(current)

        total = len(pages)
        if total == 1:
            return [card]
        out: list[dict] = []
        for idx, page in enumerate(pages, start=1):
            els = [dict(e) for e in page]
            if idx > 1 and els:
                suffix = t("notification.segment.continued").format(n=idx, total=total)
                els[-1]["content"] = f"{els[-1].get('content', '')}\n{suffix}"
            out.append({"header": header, "elements": els})
        return out

    def _send_card(self, card: dict) -> bool:
        """投递**一张**卡片（原 send() 的请求与异常处理逻辑；分段后按卡片独立判定成败）。"""
        try:
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
