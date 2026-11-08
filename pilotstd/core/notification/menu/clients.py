"""四个通知渠道的菜单客户端。

官方接口（2026-11-08 核对，链接见 docs/reference/notification-menu-apis.md）：
- 企微：`cgi-bin/menu/get|create|delete`（自建应用，agentid 必填）
- 飞书：`/open-apis/im/v1/chats/{chat_id}/menu_tree`（群菜单，3+5）
- 钉钉：机器人无持久菜单 API（客户端 JSAPI 不算），明确不支持
- Telegram：`setMyCommands`/`getMyCommands`/`deleteMyCommands`（命令列表，不是持久菜单）
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pilotstd.i18n import t

from .model import Menu, MenuItem

Transport = Callable[[str, str, dict[str, Any] | None, dict[str, str] | None], dict[str, Any]]


# HTTP/JSON 层异常：客户端统一转成 MenuResult，不把网络异常抛给 API 层
class MenuHTTPError(RuntimeError):
    """HTTP 层失败（测试替身可直接抛）。"""


# 统一返回值：ok/code/message/data；code 保留渠道原始错误码便于排障
@dataclass(frozen=True)
class MenuResult:
    """菜单操作结果：ok + 渠道原始 code + 可读 message + data。"""

    ok: bool
    code: str = ""
    message: str = ""
    data: Any = None


def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """默认 HTTP 传输：JSON 进/出，HTTP/网络错误统一抛 MenuHTTPError。"""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        raise MenuHTTPError(f"HTTP {e.code}") from e
    except URLError as e:
        raise MenuHTTPError(str(e.reason)) from e
    return json.loads(raw) if raw else {}


# 渠道适配接口：能力声明 + 三动作；新增渠道必须实现全部抽象方法
class MenuClient(ABC):
    """渠道菜单适配接口：能力声明 + get/create/delete 三动作。"""

    channel: str = ""

    @abstractmethod
    def supports_menu(self) -> bool: ...

    @abstractmethod
    def supports_type(self, item_type: str) -> bool: ...

    @abstractmethod
    def get_menu(self) -> MenuResult: ...

    @abstractmethod
    def create_menu(self, menu: Menu) -> MenuResult: ...

    @abstractmethod
    def delete_menu(self) -> MenuResult: ...


# 企微菜单错误码（官方文档 + 发送侧已取证口径）
_WECOM_ERRORS = {
    40001: "invalid access_token",
    40014: "illegal access_token",
    42001: "expired access_token",
    45009: "api rate limit exceeded",
    48001: "menu api unauthorized",
    40054: "menu item limit exceeded",
}


# 企微：自建应用应用级菜单，agentid 必填；群机器人形态不支持
class WecomMenuClient(MenuClient):
    """企微自建应用菜单客户端（get/create/delete）。"""

    channel = "wechat"
    _BASE = "https://qyapi.weixin.qq.com/cgi-bin"
    _TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    _TOKEN_URL = _TOKEN_URL

    def __init__(
        self,
        corpid: str,
        corpsecret: str,
        agentid: str,
        *,
        transport: Transport = _http_json,
        proxy_url: str = "",
    ) -> None:
        self._corpid = corpid
        self._corpsecret = corpsecret
        self._agentid = str(agentid)
        self._transport = transport
        self._proxy_url = proxy_url
        self._token = ""
        self._token_expire_at = 0.0

    def supports_menu(self) -> bool:
        return bool(self._corpid and self._corpsecret and self._agentid)

    def supports_type(self, item_type: str) -> bool:
        return item_type in {"view", "click", "group"}

    def _access_token(self) -> str:
        """取并缓存企微应用 access_token；失败抛 MenuHTTPError。"""
        if self._token:
            return self._token
        url = f"{self._TOKEN_URL}?corpid={self._corpid}&corpsecret={self._corpsecret}"
        data = self._transport("GET", url, None, None)
        if int(data.get("errcode", -1)) != 0 or not data.get("access_token"):
            raise MenuHTTPError(str(data.get("errmsg") or "gettoken failed"))
        self._token = str(data["access_token"])
        return self._token

    def _url(self, action: str) -> str:
        token = self._access_token()
        return f"{self._BASE}/menu/{action}?access_token={token}&agentid={self._agentid}"

    def _call(self, method: str, action: str, payload: dict[str, Any] | None = None) -> MenuResult:
        """调企微 menu/{action} 并把 errcode 归一为 MenuResult。"""
        try:
            data = self._transport(method, self._url(action), payload, None)
        except MenuHTTPError as e:
            return MenuResult(False, "HTTP", str(e))
        code = int(data.get("errcode", -1))
        if code == 0:
            return MenuResult(True, data=data)
        return MenuResult(False, str(code), _WECOM_ERRORS.get(code, str(data.get("errmsg") or "")))

    def get_menu(self) -> MenuResult:
        return self._call("GET", "get")

    def create_menu(self, menu: Menu) -> MenuResult:
        """把 Menu 转成企微 button 数组并提交。"""
        return self._call("POST", "create", {"button": [_wecom_item(i) for i in menu.items]})

    def delete_menu(self) -> MenuResult:
        return self._call("GET", "delete")


# 企微按钮结构：有 children 时为分组，叶子按 type 区分 view/click
def _wecom_item(item: MenuItem) -> dict[str, Any]:
    """企微按钮：分组用 name+sub_button，叶子用 type/name/url|key。"""
    label = t(item.label_key)
    if item.children:
        return {"name": label, "sub_button": [_wecom_item(c) for c in item.children]}
    if item.type == "click":
        return {"type": "click", "name": label, "key": item.key}
    return {"type": "view", "name": label, "url": item.url}


# 飞书群菜单错误码（官方文档 232xxx 段）
_FEISHU_ERRORS = {
    232001: "invalid request parameter",
    232008: "unsupported chat mode",
    232009: "chat dissolved",
    232011: "operator not in chat",
    232014: "token permission denied",
    232025: "bot ability not activated",
    232034: "app not installed or disabled",
    232055: "no chat menu management permission",
    232070: "top-level menu exceeds 3",
    232071: "second-level menu exceeds 5",
    232073: "chat menu is being modified",
    232078: "illegal chat menu content",
}


# 飞书：群菜单（chat_id 维度），一级 3 项、二级 5 项；只支持跳转
class FeishuMenuClient(MenuClient):
    """飞书群菜单客户端（chat_id 维度的 menu_tree）。"""

    channel = "feishu"
    _BASE = "https://open.feishu.cn/open-apis"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        chat_id: str,
        *,
        transport: Transport = _http_json,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._chat_id = chat_id
        self._transport = transport
        self._token = ""

    def supports_menu(self) -> bool:
        return bool(self._app_id and self._app_secret and self._chat_id)

    def supports_type(self, item_type: str) -> bool:
        return item_type in {"view", "group"}

    def _access_token(self) -> str:
        """取并缓存飞书 tenant_access_token；失败抛 MenuHTTPError。"""
        if self._token:
            return self._token
        data = self._transport(
            "POST",
            f"{self._BASE}/auth/v3/tenant_access_token/internal",
            {"app_id": self._app_id, "app_secret": self._app_secret},
            None,
        )
        if int(data.get("code", -1)) != 0 or not data.get("tenant_access_token"):
            raise MenuHTTPError(str(data.get("msg") or "tenant token failed"))
        self._token = str(data["tenant_access_token"])
        return self._token

    def _url(self) -> str:
        return f"{self._BASE}/im/v1/chats/{self._chat_id}/menu_tree"

    def _call(self, method: str, payload: dict[str, Any] | None = None) -> MenuResult:
        """调飞书 menu_tree 并把 code/msg 归一为 MenuResult。"""
        try:
            headers = {"Authorization": f"Bearer {self._access_token()}"}
            data = self._transport(method, self._url(), payload, headers)
        except MenuHTTPError as e:
            return MenuResult(False, "HTTP", str(e))
        code = int(data.get("code", -1))
        if code == 0:
            return MenuResult(True, data=data.get("data") or data)
        return MenuResult(False, str(code), _FEISHU_ERRORS.get(code, str(data.get("msg") or "")))

    def get_menu(self) -> MenuResult:
        return self._call("GET")

    def create_menu(self, menu: Menu) -> MenuResult:
        """把 Menu 转成飞书 chat_menu_top_levels 并提交。"""
        return self._call("POST", {"menu_tree": {"chat_menu_top_levels": [_feishu_item(i) for i in menu.items]}})

    def delete_menu(self) -> MenuResult:
        return self._call("DELETE")


# 飞书菜单项：分组用 NONE；叶子用 REDIRECT_LINK，5 个 URL 字段同值
def _feishu_item(item: MenuItem) -> dict[str, Any]:
    """飞书菜单项：分组 action_type=NONE；叶子 REDIRECT_LINK 五 URL 同值。"""
    name = t(item.label_key)
    if item.children:
        return {
            "chat_menu_item": {"action_type": "NONE", "name": name},
            "children": [_feishu_item(c) for c in item.children],
        }
    return {
        "chat_menu_item": {
            "action_type": "REDIRECT_LINK",
            "name": name,
            "redirect_link": {
                "common_url": item.url,
                "web_url": item.url,
                "pc_url": item.url,
                "ios_url": item.url,
                "android_url": item.url,
            },
        }
    }


# Telegram：命令列表（setMyCommands），不是持久菜单；命令点击是文本消息
class TelegramCommandClient(MenuClient):
    """Telegram 命令列表（不是持久菜单）。"""

    channel = "telegram"
    _BASE = "https://api.telegram.org"

    def __init__(self, bot_token: str, *, transport: Transport = _http_json) -> None:
        self._bot_token = bot_token
        self._transport = transport

    def supports_menu(self) -> bool:
        return bool(self._bot_token)

    def supports_type(self, item_type: str) -> bool:
        return item_type == "command"

    def _url(self, method: str) -> str:
        return f"{self._BASE}/bot{self._bot_token}/{method}"

    def _call(self, method: str, payload: dict[str, Any] | None = None) -> MenuResult:
        """调 Telegram Bot API 并把 ok/error_code 归一为 MenuResult。"""
        try:
            data = self._transport("POST" if payload is not None else "GET", self._url(method), payload, None)
        except MenuHTTPError as e:
            return MenuResult(False, "HTTP", str(e))
        if data.get("ok"):
            return MenuResult(True, data=data.get("result"))
        return MenuResult(False, str(data.get("error_code", "")), str(data.get("description", "")))

    def get_menu(self) -> MenuResult:
        return self._call("getMyCommands")

    def create_menu(self, menu: Menu) -> MenuResult:
        """把 Menu 转成 Telegram 命令列表并 setMyCommands。"""
        commands = []
        for item in menu.items:
            commands.append(
                {
                    "command": item.command.lstrip("/"),
                    "description": t(item.label_key),
                }
            )
        return self._call("setMyCommands", {"commands": commands})

    def delete_menu(self) -> MenuResult:
        return self._call("deleteMyCommands")


# 钉钉：官方机器人无持久菜单，显式返回 unsupported，避免调用方误判
class DingtalkMenuClient(MenuClient):
    """钉钉机器人无持久菜单；保留显式“不支持”结论。"""

    channel = "dingtalk"

    def supports_menu(self) -> bool:
        return False

    def supports_type(self, item_type: str) -> bool:
        return False

    def get_menu(self) -> MenuResult:
        return MenuResult(False, "unsupported", "dingtalk bot has no persistent menu api")

    def create_menu(self, menu: Menu) -> MenuResult:
        """钉钉显式不支持：调用方据 code=unsupported 决定替代形态。"""
        return MenuResult(False, "unsupported", "dingtalk bot has no persistent menu api")

    def delete_menu(self) -> MenuResult:
        return MenuResult(False, "unsupported", "dingtalk bot has no persistent menu api")
