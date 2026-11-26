# 模块：项目/核心//渠道/脚本
"""企业微信渠道：**群机器人 Webhook** 与**企业应用（模板卡片）**两种形态。"""

import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from pilotstd.i18n import t

from ..channel import NotificationMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from ..interaction import ChannelCapabilities
from ..renderer import MarkdownRenderer, split_for_channel
from ..renderer_wecom_card import WeChatCardRenderer
from .base import NotificationChannel, is_rate_limited, is_retryable_http_status

logger = logging.getLogger(__name__)


class WechatChannel(NotificationChannel):
    """企业微信渠道：**两种形态**（阶段 3 · Step 4 ① 起支持应用形态）。

    形态选择（按用户填写的参数，符合"百货超市"口径）：

    | 形态 | 必需参数 | 出站形态 |
    |---|---|---|
    | **群机器人 Webhook** | `webhook_url` | `markdown`（按 2048 字节分段） |
    | **企业应用（自建应用）** | `corpid` + `corpsecret` + `agentid` | 合法时发 **`template_card`（模板卡片）**；
      卡片被拒/无合法动作时降级为 **`markdown` 应用消息**（按 2048 字节分段），
      两者都失败才退回 `text`（最后兜底，绝不静默丢消息） |

    两者都配好时**优先企业应用形态**（与 `channel_spec.status_rule` 的分支顺序一致）。

    **降级消息类型（D3，2026-11-25）**：旧实现降级用 `msgtype=text` 发 markdown **源码**，
    用户看到字面 `##`/`**`/`[x](url)`；企微应用消息支持 `msgtype=markdown`（≤2048 字节），
    故降级首选拔高为 markdown（与 Webhook 同渲染器/同分段口径），`text` 仅作最后兜底。

    **为什么应用形态才有卡片**：企微的 `template_card` 只能经应用消息端点
    `cgi-bin/message/send` 下发，群机器人 Webhook **不支持**（取证见 `renderer.WeChatCardRenderer`）。
    """

    _TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    _SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/message/send"

    def __init__(
        self,
        webhook_url: str = "",
        corpid: str = "",
        agentid: str = "",
        corpsecret: str = "",
        proxy_url: str = "",
        touser: str = "@all",
    ):
        # 参数顺序与 `channel_spec.ctor` **严格一致**（`manager._init_channels` 按序位置传参）
        self._url = webhook_url
        self._corpid = corpid
        self._agentid = agentid
        self._corpsecret = corpsecret
        self._proxy_url = proxy_url
        self._touser = touser or "@all"
        self._renderer = MarkdownRenderer()
        self._card_renderer = WeChatCardRenderer()
        # 2026-11-26 借鉴 MoviePilot（app/modules/wechat/wechat.py）：企微自建应用默认只发**纯文本**，
        # 「企业微信 + 微信插件」都能正常渲染、排版干净；`markdown` / `card` 为显式选项。
        import os as _os

        self._app_format = _os.environ.get("PILOTSTD_WECHAT_APP_FORMAT", "text").strip().lower() or "text"
        # access_token 缓存（应用形态；8600 秒有效期，留 300 秒余量）
        self._token = ""
        self._token_expire_at = 0.0
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    @property
    def _app_configured(self) -> bool:
        """应用形态是否配置完整（三者齐备才算，与 spec 的形态 `required` 同口径）。"""
        return bool(self._corpid and self._corpsecret and self._agentid)

    def send(self, message: NotificationMessage) -> bool:
        """发送通知：应用形态发**模板卡片**；否则走 Webhook markdown（分段）。"""
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if self._app_configured:
            if self._send_by_app(message):
                return True
            # 卡片与 markdown 应用消息都失败 ⇒ 最后兜底：纯 text 消息（保留"绝不静默丢"）
            logger.warning("wecom app message delivery failed, falling back to text: %s", self.last_error)
            if self._send_app_text(message):
                return True
            return False
        if not self._url:
            self.last_error = t("notification.channel.not_configured_webhook")
            return False
        # 分段（P2，2026-10-05）：企业微信文本上限是 **2048 字节**（官方口径，本仓按 UTF-8 计）⇒
        # 超长整条会被拒收，必须先切分；未超限时 `split_for_channel` 原样返回单段（零行为变更）。
        # 逐段独立发送，任一段最终失败即整体失败（**不静默丢段**）。
        rendered = self._renderer.render(message)
        for seg in split_for_channel(rendered, "wecom"):
            # 2026-10-17：接入渠道基座的统一重试（此前单次尝试即失败 ⇒ 一次 429/抖动就丢通知）
            if not self._send_segment_with_retry(seg):
                return False
        return True

    # ── 应用形态（模板卡片 / 文本）─────────────────────────────────────────────

    def _open(self, url: str, payload: dict | None = None) -> Any:
        """统一请求入口（带可选的 `proxy_url` 代理；无代理时行为与既有实现一致）。"""
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        if self._proxy_url:
            opener = build_opener(ProxyHandler({"http": self._proxy_url, "https": self._proxy_url}))
            return opener.open(req, timeout=10)
        return urlopen(req, timeout=10)

    def _access_token(self) -> str:
        """取应用 `access_token`（带 8600 秒缓存；失败返回空串并记录原因）。"""
        now = time.time()
        if self._token and now < self._token_expire_at:
            return self._token
        try:
            with self._open(f"{self._TOKEN_URL}?corpid={self._corpid}&corpsecret={self._corpsecret}") as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.last_error = f"{t('notification.channel.wechat.token_failed')}: {e}"
            return ""
        if int(body.get("errcode", -1)) != 0 or not body.get("access_token"):
            self.last_error = t("notification.channel.wechat.token_failed")
            return ""
        self._token = str(body["access_token"])
        # 官方有效期 7200 秒（实测实现按 8600 处理）；这里保守取 6900 秒余量
        self._token_expire_at = now + 6900
        return self._token

    def _post_app_with_retry(self, msgtype_payload: dict) -> bool:
        """按应用消息端点投递，并按**渠道基座**统一节奏重试。"""

        def _attempt(_attempt_no: int) -> tuple[bool, bool]:
            return self._post_app_once(msgtype_payload)

        return self._with_retry(_attempt)

    def _post_app(self, msgtype_payload: dict) -> bool:
        """按应用消息端点投递（兼容入口：单次尝试，不重试）。

        ⚠️ `_send_by_app` / `_send_app_text` 走 `_post_app_with_retry`（基座重试）。
        """
        ok, _retryable = self._post_app_once(msgtype_payload)
        return ok

    def _post_app_once(self, msgtype_payload: dict) -> tuple[bool, bool]:
        """投递一次，返回 `(是否成功, 是否可重试)`；失败原因写入 `last_error`。

        可重试口径：HTTP 429/5xx、网络类异常，以及响应文本像限流的 `errcode`
        （企业微信的限流码未逐码取证，用基座 `looks_rate_limited` 兜底）。
        """
        token = self._access_token()
        if not token:
            # 取令牌失败多为配置/网络问题：无法判定可重试 ⇒ 不重试（避免把配置错误放大 3 次）
            return False, False
        # 对齐 MoviePilot：显式声明非安全消息/不转译/不做重复检查（避免服务端默认策略变化影响排版）
        payload = {
            "touser": self._touser,
            "agentid": self._agentid,
            "safe": 0,
            "enable_id_trans": 0,
            "enable_duplicate_check": 0,
            **msgtype_payload,
        }
        try:
            with self._open(f"{self._SEND_URL}?access_token={token}", payload) as resp:
                if resp.status != 200:
                    self.last_error = t("notification.channel.wechat.http_error").format(status=resp.status)
                    return False, is_retryable_http_status(resp.status)
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.last_error = str(e)
            logger.warning("企业微信应用消息异常: %s", e, exc_info=True)
            return False, True
        errcode = int(body.get("errcode", -1))
        if errcode == 0:
            return True, False
        errmsg = str(body.get("errmsg", ""))
        self.last_error = f"errcode={errcode} errmsg={errmsg}"
        return False, is_rate_limited("wechat", errcode, errmsg)

    def _send_by_app(self, message: NotificationMessage) -> bool:
        """应用形态：默认发**纯文本**（对齐 MoviePilot）；`markdown`/`card` 需显式选（`PILOTSTD_WECHAT_APP_FORMAT`）。

        D1：`news_notice` 卡片缺必填项（`card_action` 等）会被平台 40058 拒收；渲染器在
        没有合法跳转 URL 时不产出这些字段 ⇒ 此处直接走 markdown，不发必然被拒的卡。
        D3：降级消息类型由 `text` 改为 `markdown`（应用消息支持、与 Webhook 同渲染器/分段）。
        """
        if self._app_format == "text":
            return self._send_app_text(message)
        if self._app_format == "markdown":
            return self._send_app_markdown(message)
        card = self._card_renderer.render_card(message)
        if card.get("card_action") and card.get("card_image"):
            if self._post_app_with_retry({"msgtype": "template_card", "template_card": card}):
                return True
            logger.warning("wecom template_card rejected, falling back to markdown: %s", self.last_error)
        return self._send_app_markdown(message)

    def _send_app_markdown(self, message: NotificationMessage) -> bool:
        """应用形态降级：发送 **`msgtype=markdown`** 应用消息（D3）。

        渲染来源仍是 `MarkdownRenderer`（`## 标题` / `**字段**：值` / `- 条目` / `[查看详情](url)`），
        但必须用企微**会解析 markdown** 的 `msgtype=markdown` 发送——旧实现用 `msgtype=text`
        发同一份 markdown 源码，用户看到的是字面 `##`/`**`，链接也不可点。
        分段沿用 `split_for_channel` 的**字节口径**（企微上限 2048 字节），任一段失败即整体失败。
        """
        text = self._renderer.render(message) or str(message.title or "")
        for segment in split_for_channel(text, "wecom"):
            if not self._post_app_with_retry({"msgtype": "markdown", "markdown": {"content": segment}}):
                return False
        return True

    def _format_app_text(self, message: NotificationMessage) -> str:
        """MP 风格文本：`title\n正文`（连续空行折叠），链接按需追加「点击查看：{url}」。

        对齐 MoviePilot `WeChat.__send_message`：正文空只发标题；空行折叠避免手机端大段留白。

        **2026-11-26 真机修正（0.209.2）**：
        1. 标题去重——多数 builder 的 `body` 首行就是标题，直接 `title\nbody` 会出现两遍；
        2. 链接去重——正文里常已带「详情：<url>」，再追加「点击查看」会重复两个链接。
        """
        title = str(getattr(message, "title", "") or "").strip()
        body = str(getattr(message, "body", "") or "").strip().replace("\n\n", "\n")
        # 1) body 首行与标题相同 ⇒ 去掉该行，避免标题出现两次（可能连续多次）
        lines = body.splitlines()
        while title and lines and lines[0].strip() == title:
            lines.pop(0)
        body = "\n".join(lines).strip()
        content = f"{title}\n{body}" if title and body else (title or body)
        link = str(getattr(message, "link", "") or "").strip()
        if not link:
            # 多数事件没有 `message.link`，站内入口在 `actions`（`view_detail`/`open_logs` 的 args.url）
            # 里 —— 纯文本模式从动作里取第一个绝对 URL 作为「点击查看」目标（与卡片 jump_list 同源）。
            for spec in getattr(message, "actions", []) or []:
                candidate = str((getattr(spec, "args", None) or {}).get("url") or "").strip()
                if candidate.lower().startswith(("http://", "https://")):
                    link = candidate
                    break
        # 2) 正文已包含该链接 ⇒ 不再追加（避免「详情：url」+「点击查看：url」重复）
        if link and link not in content:
            content = f"{content}\n点击查看：{link}" if content else f"点击查看：{link}"
        return content

    def _send_app_text(self, message: NotificationMessage) -> bool:
        """应用形态**默认路径**：发送 MP 风格纯文本（标题 + 正文 + 可选「点击查看」链接）。

        P1-2：企微文本上限是 **2048 字节**（不是 2000 字符）。原实现 `text[:2000]` 按字符
        硬截断——2000 汉字 ≈ 6000 字节，降级消息本身仍会被平台拒收，且尾部信息直接丢失。
        改为复用 `split_for_channel` 的**字节口径**分段、逐段发送（任一段失败即整体失败）。
        注意：`text` 消息不解析 markdown（用户会看到源码），故它只是最后兜底，正常降级走
        `_send_app_markdown`。
        """
        text = self._format_app_text(message)
        if not text:
            self.last_error = t("notification.channel.not_configured_webhook")
            return False
        for segment in split_for_channel(text, "wecom"):
            if not self._post_app_with_retry({"msgtype": "text", "text": {"content": segment}}):
                return False
        return True

    def _send_segment_with_retry(self, rendered: str) -> bool:
        """发送**单个分段**（Webhook markdown）并按渠道基座统一节奏重试。"""

        def _attempt(_attempt_no: int) -> tuple[bool, bool]:
            return self._post_segment_once(rendered)

        return self._with_retry(_attempt)

    def _send_segment(self, rendered: str) -> bool:
        """发送**单个分段**（兼容入口：单次尝试，不重试）。"""
        ok, _retryable = self._post_segment_once(rendered)
        return ok

    def _post_segment_once(self, rendered: str) -> tuple[bool, bool]:
        """投递单个分段一次，返回 `(是否成功, 是否可重试)`（走统一请求入口 `_open`）。"""
        try:
            with self._open(self._url, {"msgtype": "markdown", "markdown": {"content": rendered}}) as resp:
                if resp.status == 200:
                    return True, False
                self.last_error = t("notification.channel.wechat.http_error").format(status=resp.status)
                logger.warning("企业微信通知失败: HTTP %d", resp.status)
                return False, is_retryable_http_status(resp.status)
        except Exception as e:
            # 读取错误响应体用于诊断（回调返回非 200 时的具体错误）
            body = ""
            from urllib.error import HTTPError

            status = 0
            if isinstance(e, HTTPError):
                status = e.code
                try:
                    body = e.read().decode("utf-8", errors="replace")[:500]
                except Exception as read_exc:
                    # 区分"服务端未返回 body"与"body 读取失败"，避免诊断信息静默丢失
                    body = f"<body 读取失败: {read_exc}>"
                    logger.debug("错误响应体读取失败: %s", read_exc)
            # 透传具体错误描述
            self.last_error = f"{e}: {body}" if body else str(e)
            logger.warning("企业微信通知异常: %s, body=%s", e, body, exc_info=True)  # i18n-allow: 内部运维日志
            # HTTP 429/`5xx` 或网络类异常（无 HTTPError 即连接/超时类）⇒ 可重试
            return False, is_retryable_http_status(status) if status else True

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
